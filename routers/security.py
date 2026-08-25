"""
SECTION B — Actual Security Measures (pts 2, 3, 4) + SECTION A Lockout & Step-Up integration.
Owns: WebAuthn registration/login, OTP send/verify, QR sync, Email verification, Recovery codes.
"""
import os
import sys
import json
import secrets

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session as DBSession
from passlib.context import CryptContext

from webauthn import (
    generate_registration_options,
    verify_registration_response,
    generate_authentication_options,
    verify_authentication_response,
    options_to_json,
)
from webauthn.helpers import (
    parse_registration_credential_json,
    parse_authentication_credential_json,
)
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    UserVerificationRequirement,
    PublicKeyCredentialDescriptor,
)

from database import get_db
from models import (
    User,
    Credential,
    OTPCode,
    LoginToken,
    EmailVerificationCode,
    RecoveryCode,
    StepUpChallenge,
)
from schemas import (
    success_response,
    error_response,
    OtpSendRequest,
    OtpVerifyRequest,
    WebAuthnRegisterVerifyRequest,
    WebAuthnLoginOptionsRequest,
    WebAuthnLoginVerifyRequest,
    QrGenerateRequest,
    QrApproveRequest,
    StepUpVerifyRequest,
    EmailVerificationSendRequest,
    EmailVerificationVerifyRequest,
    RecoveryCodeGenerateRequest,
    RecoveryCodeVerifyRequest,
)
from lib.session_utils import create_session, log_login_attempt, get_current_user
from lib.email_utils import send_email
from lib.lockout_utils import is_locked, check_and_lock_if_needed, clear_lock
from lib.rate_limit import limiter

router = APIRouter()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

RP_ID = os.getenv("WEBAUTHN_RP_ID", "localhost")
RP_NAME = os.getenv("WEBAUTHN_RP_NAME", "SecureBank Demo")
ORIGIN = os.getenv("WEBAUTHN_ORIGIN", "http://localhost:8000")
OTP_EXPIRE_MINUTES = int(os.getenv("OTP_EXPIRE_MINUTES", "5"))

_pending_challenges: dict[str, bytes] = {}


def _get_client_ip(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _get_rp_id_and_origin(request: Request) -> tuple[str, str]:
    """
    Dynamically resolve RP_ID and ORIGIN based on the current HTTP request header,
    with fallback to environment variables. This guarantees WebAuthn works whether
    accessed via localhost, 127.0.0.1, ngrok tunnel, or custom domain name.
    """
    host = request.headers.get("host", "").split(":")[0]
    origin = request.headers.get("origin")
    
    if host and host not in ["127.0.0.1", "::1"]:
        rp_id = host
    else:
        rp_id = RP_ID
        
    if not origin:
        scheme = request.headers.get("x-forwarded-proto", request.url.scheme)
        raw_host = request.headers.get("host", "localhost:8000")
        origin = f"{scheme}://{raw_host}"
        
    return rp_id, origin


# ===========================================================================
# WEBAUTHN — BIOMETRIC REGISTRATION
# ===========================================================================

@router.post("/webauthn/register-options")
def webauthn_register_options(payload: WebAuthnLoginOptionsRequest, request: Request, db: DBSession = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user:
        return error_response("No account found for this email. Register first.")

    rp_id, _ = _get_rp_id_and_origin(request)

    options = generate_registration_options(
        rp_id=rp_id,
        rp_name=RP_NAME,
        user_id=user.id.encode("utf-8"),
        user_name=user.email,
        user_display_name=user.name or user.email,
        authenticator_selection=AuthenticatorSelectionCriteria(
            user_verification=UserVerificationRequirement.PREFERRED,
        ),
    )

    _pending_challenges[user.email] = options.challenge
    return success_response(data=json.loads(options_to_json(options)))


@router.post("/webauthn/register-verify")
def webauthn_register_verify(payload: WebAuthnRegisterVerifyRequest, request: Request, db: DBSession = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user:
        return error_response("No account found for this email.")

    expected_challenge = _pending_challenges.get(user.email)
    if not expected_challenge:
        return error_response("No pending registration challenge. Start again.")

    rp_id, origin = _get_rp_id_and_origin(request)

    try:
        credential = parse_registration_credential_json(json.dumps(payload.credential))
        verification = verify_registration_response(
            credential=credential,
            expected_challenge=expected_challenge,
            expected_rp_id=rp_id,
            expected_origin=origin,
        )
    except Exception as e:
        return error_response(f"Registration verification failed: {str(e)}")

    new_credential = Credential(
        user_id=user.id,
        public_key=verification.credential_public_key,
        webauthn_cred_id=verification.credential_id.hex(),
        counter=verification.sign_count,
    )
    db.add(new_credential)
    db.commit()

    _pending_challenges.pop(user.email, None)
    return success_response(message="Biometric credential registered successfully.")


# ===========================================================================
# WEBAUTHN — BIOMETRIC LOGIN
# ===========================================================================

@router.post("/webauthn/login-options")
def webauthn_login_options(payload: WebAuthnLoginOptionsRequest, request: Request, db: DBSession = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not user.credentials:
        return error_response("No biometric credential registered for this account.")

    allow_credentials = [
        PublicKeyCredentialDescriptor(id=bytes.fromhex(cred.webauthn_cred_id))
        for cred in user.credentials
    ]

    rp_id, _ = _get_rp_id_and_origin(request)

    options = generate_authentication_options(
        rp_id=rp_id,
        allow_credentials=allow_credentials,
        user_verification=UserVerificationRequirement.PREFERRED,
    )

    _pending_challenges[user.email] = options.challenge
    return success_response(data=json.loads(options_to_json(options)))


@router.post("/webauthn/login-verify")
def webauthn_login_verify(payload: WebAuthnLoginVerifyRequest, response: Response, request: Request, db: DBSession = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    ip = _get_client_ip(request)

    if not user:
        log_login_attempt(None, "webauthn", False, ip, payload.device_fingerprint)
        return error_response("No account found for this email.")

    if is_locked(user):
        return error_response("Account temporarily locked due to repeated failed attempts. Try again later.")

    expected_challenge = _pending_challenges.get(user.email)
    if not expected_challenge:
        log_login_attempt(user.id, "webauthn", False, ip, payload.device_fingerprint)
        check_and_lock_if_needed(db, user, ip)
        return error_response("No pending login challenge. Start again.")

    rp_id, origin = _get_rp_id_and_origin(request)

    try:
        credential = parse_authentication_credential_json(json.dumps(payload.credential))
        cred_id_hex = credential.raw_id.hex()
        stored_cred = (
            db.query(Credential)
            .filter(Credential.webauthn_cred_id == cred_id_hex, Credential.user_id == user.id)
            .first()
        )
        if not stored_cred:
            raise ValueError("Credential not recognized for this user.")

        verification = verify_authentication_response(
            credential=credential,
            expected_challenge=expected_challenge,
            expected_rp_id=rp_id,
            expected_origin=origin,
            credential_public_key=stored_cred.public_key,
            credential_current_sign_count=stored_cred.counter,
        )
    except Exception as e:
        log_login_attempt(user.id, "webauthn", False, ip, payload.device_fingerprint)
        check_and_lock_if_needed(db, user, ip)
        return error_response(f"Login verification failed: {str(e)}")

    stored_cred.counter = verification.new_sign_count
    stored_cred.last_used_at = datetime.utcnow()
    db.commit()

    _pending_challenges.pop(user.email, None)

    create_session(user_id=user.id, device_id=None, response=response)
    log_login_attempt(user.id, "webauthn", True, ip, payload.device_fingerprint)
    clear_lock(db, user)

    return success_response(
        data={"id": user.id, "email": user.email, "name": user.name},
        message="Biometric login successful.",
    )


# ===========================================================================
# OTP — EMAIL VERIFICATION / LOGIN
# ===========================================================================

@router.post("/otp/send")
@limiter.limit("5/minute")
def send_otp(request: Request, payload: OtpSendRequest, db: DBSession = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user:
        return error_response("No account found for this email.")

    raw_code = f"{secrets.randbelow(900000) + 100000:06d}"
    code_hash = pwd_context.hash(raw_code)
    expires_at = datetime.utcnow() + timedelta(minutes=OTP_EXPIRE_MINUTES)

    otp_row = OTPCode(user_id=user.id, code_hash=code_hash, expires_at=expires_at)
    db.add(otp_row)
    db.commit()

    # -- LOCAL DEV: Print OTP directly in terminal for testing (ASCII safe) --
    print("\n" + "=" * 50)
    print(f"  OTP CODE FOR {user.email}")
    print(f"  >>>  {raw_code}  <<<")
    print(f"  Expires in {OTP_EXPIRE_MINUTES} minutes")
    print("=" * 50 + "\n")
    sys.stdout.flush()

    send_email(
        to=user.email,
        subject="Your SecureBank login code",
        html=f"<p>Your one-time login code is <strong>{raw_code}</strong>. It expires in {OTP_EXPIRE_MINUTES} minutes.</p>"
    )

    return success_response(
        data={"dev_code": raw_code},
        message=f"Login code sent to {user.email}. [Code: {raw_code}]"
    )



@router.post("/otp/verify")
def verify_otp(payload: OtpVerifyRequest, response: Response, request: Request, db: DBSession = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    ip = _get_client_ip(request)

    if not user:
        log_login_attempt(None, "otp", False, ip, payload.device_fingerprint)
        return error_response("No account found for this email.")

    if is_locked(user):
        return error_response("Account temporarily locked due to repeated failed attempts. Try again later.")

    otp_row = (
        db.query(OTPCode)
        .filter(OTPCode.user_id == user.id, OTPCode.used == False)  # noqa: E712
        .order_by(OTPCode.created_at.desc())
        .first()
    )

    if not otp_row or otp_row.expires_at < datetime.utcnow():
        log_login_attempt(user.id, "otp", False, ip, payload.device_fingerprint)
        check_and_lock_if_needed(db, user, ip)
        return error_response("No active OTP found, or it has expired. Request a new one.")

    if not pwd_context.verify(payload.code, otp_row.code_hash):
        log_login_attempt(user.id, "otp", False, ip, payload.device_fingerprint)
        check_and_lock_if_needed(db, user, ip)
        return error_response("Incorrect OTP.")

    otp_row.used = True
    db.commit()

    create_session(user_id=user.id, device_id=None, response=response)
    log_login_attempt(user.id, "otp", True, ip, payload.device_fingerprint)
    clear_lock(db, user)

    return success_response(
        data={"id": user.id, "email": user.email, "name": user.name},
        message="OTP verification successful.",
    )


# ===========================================================================
# QR CROSS-DEVICE SYNC
# ===========================================================================

@router.post("/qr/generate")
def qr_generate(payload: QrGenerateRequest, db: DBSession = Depends(get_db)):
    token = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(minutes=5)
    token_row = LoginToken(token=token, status="pending", expires_at=expires_at)
    db.add(token_row)
    db.commit()

    return success_response(
        data={"token": token, "expires_at": expires_at.isoformat()},
        message="QR token generated.",
    )


@router.get("/qr/status/{token}")
def qr_status(token: str, response: Response, db: DBSession = Depends(get_db)):
    token_row = db.query(LoginToken).filter(LoginToken.token == token).first()
    if not token_row:
        return error_response("Invalid token.")

    if token_row.expires_at < datetime.utcnow() and token_row.status == "pending":
        token_row.status = "expired"
        db.commit()

    data = {"status": token_row.status}
    if token_row.status == "approved" and token_row.user_id:
        user = db.query(User).filter(User.id == token_row.user_id).first()
        if user:
            # Issue session cookie to the polling client upon QR approval
            create_session(user_id=user.id, device_id=None, response=response)
            data["user"] = {"id": user.id, "email": user.email, "name": user.name}

    return success_response(data=data)


@router.post("/qr/approve")
def qr_approve(payload: QrApproveRequest, request: Request, db: DBSession = Depends(get_db)):
    current_user = get_current_user(request)
    if not current_user:
        return error_response("You must be logged in to approve a QR sign-in.")

    user = db.query(User).filter(User.email == payload.email).first()
    if not user or user.id != current_user["id"]:
        return error_response("Email does not match the logged-in user.")

    token_row = db.query(LoginToken).filter(LoginToken.token == payload.token).first()
    if not token_row:
        return error_response("Invalid QR token.")

    if token_row.status != "pending":
        return error_response(f"QR token is already {token_row.status}.")

    if token_row.expires_at < datetime.utcnow():
        token_row.status = "expired"
        db.commit()
        return error_response("QR token has expired.")

    token_row.status = "approved"
    token_row.user_id = user.id
    db.commit()

    ip = _get_client_ip(request)
    log_login_attempt(user.id, "qr", True, ip, "approved via mobile")

    return success_response(message="Sign-in approved successfully.")


# ===========================================================================
# STEP-UP AUTH & TRANSACTION-BOUND CHALLENGES
# ===========================================================================

@router.post("/step-up/verify")
def step_up_verify(payload: StepUpVerifyRequest, request: Request, db: DBSession = Depends(get_db)):
    current_user = get_current_user(request)
    if not current_user:
        return error_response("You must be logged in to perform step-up verification.")

    user = db.query(User).filter(User.email == payload.email).first()
    ip = _get_client_ip(request)

    if not user or user.id != current_user["id"]:
        log_login_attempt(current_user.get("id"), "otp", False, ip, "step-up")
        return error_response("Email does not match the logged-in user.")

    otp_row = (
        db.query(OTPCode)
        .filter(OTPCode.user_id == user.id, OTPCode.used == False)  # noqa: E712
        .order_by(OTPCode.created_at.desc())
        .first()
    )

    if not otp_row or otp_row.expires_at < datetime.utcnow():
        log_login_attempt(user.id, "otp", False, ip, "step-up")
        return error_response("No active OTP found, or it has expired. Request a new one.")

    if not pwd_context.verify(payload.code, otp_row.code_hash):
        log_login_attempt(user.id, "otp", False, ip, "step-up")
        return error_response("Incorrect OTP.")

    challenge = None
    if payload.challenge_id:
        challenge = (
            db.query(StepUpChallenge)
            .filter(StepUpChallenge.id == payload.challenge_id, StepUpChallenge.user_id == user.id)
            .first()
        )
        if not challenge:
            log_login_attempt(user.id, "otp", False, ip, "step-up")
            return error_response("Step-up challenge not found for this user.")
        if challenge.used:
            log_login_attempt(user.id, "otp", False, ip, "step-up")
            return error_response("This step-up challenge was already used.")
        if challenge.expires_at < datetime.utcnow():
            log_login_attempt(user.id, "otp", False, ip, "step-up")
            return error_response("Step-up challenge expired. Start the action again.")

    otp_row.used = True
    if challenge:
        challenge.used = True
    db.commit()
    log_login_attempt(user.id, "otp", True, ip, "step-up")

    data = {"transaction_hash": challenge.transaction_hash} if challenge else None
    return success_response(data=data, message="Step-up verification successful. Sensitive action may proceed.")


# ===========================================================================
# EMAIL VERIFICATION FLOW — Person B Task
# ===========================================================================

@router.post("/email/send-verification")
@limiter.limit("5/minute")
def email_send_verification(request: Request, payload: EmailVerificationSendRequest, db: DBSession = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if user and user.is_verified:
        return error_response("An account with this email already exists and is verified. Please sign in.")

    if not user:
        user = User(email=payload.email, name=payload.email.split("@")[0], is_verified=False)
        db.add(user)
        db.commit()
        db.refresh(user)

    raw_code = f"{secrets.randbelow(900000) + 100000:06d}"
    code_hash = pwd_context.hash(raw_code)
    expires_at = datetime.utcnow() + timedelta(minutes=15)

    code_row = EmailVerificationCode(
        user_id=user.id,
        code_hash=code_hash,
        expires_at=expires_at,
    )
    db.add(code_row)
    db.commit()

    # -- LOCAL DEV: Print Registration Verification Code directly in terminal (ASCII safe) --
    print("\n" + "=" * 50)
    print(f"  REGISTRATION VERIFICATION CODE FOR {user.email}")
    print(f"  >>>  {raw_code}  <<<")
    print("  Expires in 15 minutes")
    print("=" * 50 + "\n")
    sys.stdout.flush()

    send_email(
        to=user.email,
        subject="Verify your Dorito Vault Registration",
        html=f"Your registration verification code is: <strong>{raw_code}</strong>. It expires in 15 minutes."
    )

    return success_response(
        data={"dev_code": raw_code},
        message=f"Verification code sent to {user.email}. [Code: {raw_code}]"
    )




@router.post("/email/verify")
def email_verify(payload: EmailVerificationVerifyRequest, db: DBSession = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user:
        return error_response("No registration attempt found for this email address.")

    active_codes = (
        db.query(EmailVerificationCode)
        .filter(
            EmailVerificationCode.user_id == user.id,
            EmailVerificationCode.used == False,  # noqa: E712
            EmailVerificationCode.expires_at >= datetime.utcnow(),
        )
        .order_by(EmailVerificationCode.created_at.desc())
        .all()
    )

    if not active_codes:
        return error_response("Verification code expired or not found. Request a new code.")

    matched_code = None
    for code_row in active_codes:
        if pwd_context.verify(payload.code.strip(), code_row.code_hash):
            matched_code = code_row
            break

    if not matched_code:
        return error_response("Invalid verification code.")

    matched_code.used = True
    user.is_verified = True
    db.commit()

    return success_response(
        data={"id": user.id, "email": user.email, "name": user.name, "is_verified": True},
        message="Email verified successfully! Registration complete."
    )


# ===========================================================================
# BACKUP RECOVERY CODES — Person B Task
# ===========================================================================

@router.post("/recovery-codes/generate")
def recovery_codes_generate(payload: RecoveryCodeGenerateRequest, db: DBSession = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user:
        return error_response("No account found for this email.")

    db.query(RecoveryCode).filter(RecoveryCode.user_id == user.id, RecoveryCode.used == False).delete()  # noqa: E712

    plain_codes = []
    for _ in range(8):
        part1 = secrets.token_hex(2).upper()
        part2 = secrets.token_hex(2).upper()
        code = f"{part1}-{part2}"
        plain_codes.append(code)
        
        rc_row = RecoveryCode(
            user_id=user.id,
            code_hash=pwd_context.hash(code),
        )
        db.add(rc_row)

    db.commit()

    return success_response(
        data={"recovery_codes": plain_codes, "count": len(plain_codes)},
        message="Backup recovery codes generated successfully. Store these codes in a safe place!"
    )


@router.post("/recovery-codes/verify")
def recovery_codes_verify(payload: RecoveryCodeVerifyRequest, response: Response, request: Request, db: DBSession = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    ip = _get_client_ip(request)

    if not user:
        log_login_attempt(None, "recovery_code", False, ip, payload.device_fingerprint)
        return error_response("No account found for this email.")

    if is_locked(user):
        return error_response("Account temporarily locked due to repeated failed attempts. Try again later.")

    unused_codes = (
        db.query(RecoveryCode)
        .filter(RecoveryCode.user_id == user.id, RecoveryCode.used == False)  # noqa: E712
        .all()
    )

    matched_code = None
    for rc in unused_codes:
        if pwd_context.verify(payload.code.strip().upper(), rc.code_hash):
            matched_code = rc
            break

    if not matched_code:
        log_login_attempt(user.id, "recovery_code", False, ip, payload.device_fingerprint)
        check_and_lock_if_needed(db, user, ip)
        return error_response("Invalid or previously used recovery code.")

    matched_code.used = True
    matched_code.used_at = datetime.utcnow()
    db.commit()

    log_login_attempt(user.id, "recovery_code", True, ip, payload.device_fingerprint)
    clear_lock(db, user)
    create_session(user_id=user.id, device_id=None, response=response)

    return success_response(
        data={"user": {"id": user.id, "email": user.email, "name": user.name}},
        message="Successfully authenticated using backup recovery code."
    )