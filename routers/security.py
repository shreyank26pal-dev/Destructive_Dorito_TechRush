"""
SECTION B — Actual Security Measures (pts 2, 3, 4)
Owns: WebAuthn (biometric) registration/login, OTP send/verify.

All routes live under /api/security/... per CONTRACT.md.
All responses use the shared APIResponse shape via success_response()/error_response().
Every login attempt (success or fail) is logged via lib/session_utils.log_login_attempt().
OTP codes are always hashed before storage — never stored in plaintext.
"""
import os
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
from models import User, Credential, OTPCode, LoginToken
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
)
from lib.session_utils import create_session, log_login_attempt, get_current_user

router = APIRouter()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

RP_ID = os.getenv("WEBAUTHN_RP_ID", "localhost")
RP_NAME = os.getenv("WEBAUTHN_RP_NAME", "SecureBank Demo")
ORIGIN = os.getenv("WEBAUTHN_ORIGIN", "http://localhost:8000")
OTP_EXPIRE_MINUTES = int(os.getenv("OTP_EXPIRE_MINUTES", "5"))

# ---------------------------------------------------------------------------
# In-memory challenge store for the WebAuthn ceremony.
# NOTE: this is fine for a single-process hackathon demo. If you deploy with
# multiple workers/instances, move this to the DB or Redis instead — a
# challenge generated on one worker won't be visible to another.
# ---------------------------------------------------------------------------
_pending_challenges: dict[str, bytes] = {}


def _get_client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


# ===========================================================================
# WEBAUTHN — BIOMETRIC REGISTRATION
# ===========================================================================

@router.post("/webauthn/register-options")
def webauthn_register_options(payload: WebAuthnLoginOptionsRequest, db: DBSession = Depends(get_db)):
    """
    Step 1 of registration: generate a challenge for the browser to sign
    with the platform authenticator (fingerprint/Face ID/Windows Hello).
    """
    user = db.query(User).filter(User.email == payload.email).first()
    if not user:
        return error_response("No account found for this email. Register first.")

    options = generate_registration_options(
        rp_id=RP_ID,
        rp_name=RP_NAME,
        user_id=user.id.encode("utf-8"),
        user_name=user.email,
        user_display_name=user.name or user.email,
        authenticator_selection=AuthenticatorSelectionCriteria(
            user_verification=UserVerificationRequirement.PREFERRED,
        ),
    )

    _pending_challenges[user.email] = options.challenge

    # options_to_json() returns a JSON STRING, not a dict — must parse it back
    # into an object, or the frontend's options.challenge access fails with
    # "Cannot read properties of undefined".
    return success_response(data=json.loads(options_to_json(options)))


@router.post("/webauthn/register-verify")
def webauthn_register_verify(payload: WebAuthnRegisterVerifyRequest, db: DBSession = Depends(get_db)):
    """
    Step 2 of registration: verify the signed credential the browser sends back,
    then store the public key. We never store any raw biometric data — only
    the public key, which is useless to an attacker without the device.
    """
    user = db.query(User).filter(User.email == payload.email).first()
    if not user:
        return error_response("No account found for this email.")

    expected_challenge = _pending_challenges.get(user.email)
    if not expected_challenge:
        return error_response("No pending registration challenge. Start again.")

    try:
        credential = parse_registration_credential_json(json.dumps(payload.credential))
        verification = verify_registration_response(
            credential=credential,
            expected_challenge=expected_challenge,
            expected_rp_id=RP_ID,
            expected_origin=ORIGIN,
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
def webauthn_login_options(payload: WebAuthnLoginOptionsRequest, db: DBSession = Depends(get_db)):
    """Step 1 of login: generate a challenge, tell the browser which credentials are allowed."""
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not user.credentials:
        return error_response("No biometric credential registered for this account.")

    allow_credentials = [
        PublicKeyCredentialDescriptor(id=bytes.fromhex(cred.webauthn_cred_id))
        for cred in user.credentials
    ]

    options = generate_authentication_options(
        rp_id=RP_ID,
        allow_credentials=allow_credentials,
        user_verification=UserVerificationRequirement.PREFERRED,
    )

    _pending_challenges[user.email] = options.challenge

    # options_to_json() returns a JSON STRING, not a dict — must parse it back
    # into an object, or the frontend's options.challenge access fails with
    # "Cannot read properties of undefined".
    return success_response(data=json.loads(options_to_json(options)))


@router.post("/webauthn/login-verify")
def webauthn_login_verify(payload: WebAuthnLoginVerifyRequest, response: Response, request: Request, db: DBSession = Depends(get_db)):
    """Step 2 of login: verify the signed assertion, create a session if valid."""
    user = db.query(User).filter(User.email == payload.email).first()
    ip = _get_client_ip(request)

    if not user:
        log_login_attempt(None, "webauthn", False, ip, payload.device_fingerprint)
        return error_response("No account found for this email.")

    expected_challenge = _pending_challenges.get(user.email)
    if not expected_challenge:
        log_login_attempt(user.id, "webauthn", False, ip, payload.device_fingerprint)
        return error_response("No pending login challenge. Start again.")

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
            expected_rp_id=RP_ID,
            expected_origin=ORIGIN,
            credential_public_key=stored_cred.public_key,
            credential_current_sign_count=stored_cred.counter,
        )
    except Exception as e:
        log_login_attempt(user.id, "webauthn", False, ip, payload.device_fingerprint)
        return error_response(f"Login verification failed: {str(e)}")

    stored_cred.counter = verification.new_sign_count
    stored_cred.last_used_at = datetime.utcnow()
    db.commit()

    _pending_challenges.pop(user.email, None)

    create_session(user_id=user.id, device_id=None, response=response)
    log_login_attempt(user.id, "webauthn", True, ip, payload.device_fingerprint)

    return success_response(
        data={"id": user.id, "email": user.email, "name": user.name},
        message="Biometric login successful.",
    )


# ===========================================================================
# OTP — EMAIL VERIFICATION
# ===========================================================================

@router.post("/otp/send")
def send_otp(payload: OtpSendRequest, db: DBSession = Depends(get_db)):
    """Generates a 6-digit code, stores its HASH (never plaintext), emails it out."""
    user = db.query(User).filter(User.email == payload.email).first()
    if not user:
        return error_response("No account found for this email.")

    code = f"{secrets.randbelow(1000000):06d}"
    code_hash = pwd_context.hash(code)
    expires_at = datetime.utcnow() + timedelta(minutes=OTP_EXPIRE_MINUTES)

    otp_row = OTPCode(user_id=user.id, code_hash=code_hash, expires_at=expires_at, used=False)
    db.add(otp_row)
    db.commit()

    _send_otp_email(user.email, code)

    return success_response(message=f"OTP sent to {user.email}. Expires in {OTP_EXPIRE_MINUTES} minutes.")


@router.post("/otp/verify")
def verify_otp(payload: OtpVerifyRequest, response: Response, request: Request, db: DBSession = Depends(get_db)):
    """Verifies the code against the stored hash, enforces expiry + single-use."""
    user = db.query(User).filter(User.email == payload.email).first()
    ip = _get_client_ip(request)

    if not user:
        log_login_attempt(None, "otp", False, ip, payload.device_fingerprint)
        return error_response("No account found for this email.")

    otp_row = (
        db.query(OTPCode)
        .filter(OTPCode.user_id == user.id, OTPCode.used == False)  # noqa: E712
        .order_by(OTPCode.created_at.desc())
        .first()
    )

    if not otp_row:
        log_login_attempt(user.id, "otp", False, ip, payload.device_fingerprint)
        return error_response("No active OTP found. Request a new one.")

    if otp_row.expires_at < datetime.utcnow():
        log_login_attempt(user.id, "otp", False, ip, payload.device_fingerprint)
        return error_response("OTP has expired. Request a new one.")

    if not pwd_context.verify(payload.code, otp_row.code_hash):
        log_login_attempt(user.id, "otp", False, ip, payload.device_fingerprint)
        return error_response("Incorrect OTP.")

    otp_row.used = True
    db.commit()

    create_session(user_id=user.id, device_id=None, response=response)
    log_login_attempt(user.id, "otp", True, ip, payload.device_fingerprint)

    return success_response(
        data={"id": user.id, "email": user.email, "name": user.name},
        message="OTP verified. Logged in.",
    )


# ===========================================================================
# QR CROSS-DEVICE LOGIN (pt 4 — alternative to biometric, for untrusted devices)
#
# Flow:
#   1. Untrusted device (e.g. laptop with no passkey set up) calls /qr/generate
#      and renders the returned token as a QR code on screen.
#   2. User scans it with their phone, which is already logged in there.
#      The phone calls /qr/approve with its own session + the scanned token.
#   3. Untrusted device polls /qr/status/{token} every ~2s. Once approved,
#      it receives a session cookie exactly like any other login method.
#
# No credentials are ever typed on the untrusted device — the phone vouches
# for it instead. This is the "answer for new/untrusted device logins"
# discussed with the team, not a replacement for biometric on trusted devices.
# ===========================================================================

QR_TOKEN_EXPIRE_MINUTES = 5


@router.post("/qr/generate")
def qr_generate(payload: QrGenerateRequest, db: DBSession = Depends(get_db)):
    """Called by the UNTRUSTED device. Returns a token to render as a QR code."""
    token_value = secrets.token_urlsafe(24)
    expires_at = datetime.utcnow() + timedelta(minutes=QR_TOKEN_EXPIRE_MINUTES)

    token_row = LoginToken(token=token_value, status="pending", expires_at=expires_at)
    db.add(token_row)
    db.commit()

    return success_response(
        data={"token": token_value, "expires_in_seconds": QR_TOKEN_EXPIRE_MINUTES * 60},
        message="Show this token as a QR code. Scan it with an already-logged-in device.",
    )


@router.get("/qr/status/{token}")
def qr_status(token: str, response: Response, request: Request, db: DBSession = Depends(get_db)):
    """
    Polled by the UNTRUSTED device (every ~2s) to check if the phone has approved yet.
    Once approved, this is where the actual session gets created for the untrusted device.
    """
    token_row = db.query(LoginToken).filter(LoginToken.token == token).first()
    ip = _get_client_ip(request)

    if not token_row:
        return error_response("Invalid or unknown token.")

    if token_row.expires_at < datetime.utcnow() and token_row.status == "pending":
        token_row.status = "expired"
        db.commit()

    if token_row.status == "pending":
        return success_response(data={"status": "pending"})

    if token_row.status == "denied":
        return success_response(data={"status": "denied"})

    if token_row.status == "expired":
        return success_response(data={"status": "expired"})

    if token_row.status == "approved":
        user = db.query(User).filter(User.id == token_row.user_id).first()
        if not user:
            return error_response("Approved token has no associated user.")

        # Session gets created here, on the untrusted device's poll request —
        # this is the moment the untrusted device actually becomes "logged in".
        create_session(user_id=user.id, device_id=None, response=response)
        log_login_attempt(user.id, "qr", True, ip, None)

        # One-time use: consume the token so it can't be replayed.
        db.delete(token_row)
        db.commit()

        return success_response(
            data={"status": "approved", "user": {"id": user.id, "email": user.email, "name": user.name}},
            message="QR login approved. Logged in.",
        )

    return error_response("Unrecognized token status.")


@router.post("/qr/approve")
def qr_approve(payload: QrApproveRequest, db: DBSession = Depends(get_db)):
    """
    Called by the ALREADY-LOGGED-IN phone after it scans the QR code.
    In a full build this route would itself require the phone to already have
    a valid session (via get_current_user) — kept as an email-identified
    approval here for hackathon simplicity; tighten before a real deployment.
    """
    token_row = db.query(LoginToken).filter(LoginToken.token == payload.token).first()
    if not token_row:
        return error_response("Invalid or unknown token.")

    if token_row.status != "pending":
        return error_response(f"Token is no longer pending (status: {token_row.status}).")

    if token_row.expires_at < datetime.utcnow():
        token_row.status = "expired"
        db.commit()
        return error_response("This QR code has expired. Generate a new one.")

    user = db.query(User).filter(User.email == payload.email).first()
    if not user:
        return error_response("No account found for this email.")

    token_row.user_id = user.id
    token_row.status = "approved"
    db.commit()

    return success_response(message="Login approved for the other device.")


# ===========================================================================
# STEP-UP AUTH — extra OTP check for sensitive actions or untrusted devices.
#
# This is the "combine different factor types" approach discussed with the
# team instead of requiring two biometrics (which WebAuthn can't distinguish
# anyway). Section A's suspicious-login/device-trust check decides WHEN to
# call this; Section B just provides the verification endpoint.
#
# Usage pattern: user is already logged in (has a valid session) but is
# attempting something sensitive (e.g. a transfer) or logged in from a
# device Section A flagged as untrusted — frontend calls /otp/send first,
# then this endpoint to confirm the step-up before letting the action proceed.
# ===========================================================================

@router.post("/step-up/verify")
def step_up_verify(payload: StepUpVerifyRequest, request: Request, db: DBSession = Depends(get_db)):
    """
    Verifies an OTP as a SECOND factor for an already-logged-in user, without
    creating a new session (they already have one). Requires the caller to
    already be authenticated — this is not a login endpoint.
    """
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

    otp_row.used = True
    db.commit()
    log_login_attempt(user.id, "otp", True, ip, "step-up")

    return success_response(message="Step-up verification successful. Sensitive action may proceed.")


# ---------------------------------------------------------------------------
# Email sending — Resend if RESEND_API_KEY is set, otherwise prints to console
# (useful for local dev / demo dry-runs without burning email quota).
# ---------------------------------------------------------------------------

def _send_otp_email(to_email: str, code: str) -> None:
    api_key = os.getenv("RESEND_API_KEY")
    if not api_key:
        print(f"[DEV MODE — no RESEND_API_KEY set] OTP for {to_email}: {code}")
        return

    try:
        import resend
        resend.api_key = api_key
        resend.Emails.send({
            "from": "SecureBank Demo <onboarding@resend.dev>",
            "to": to_email,
            "subject": "Your SecureBank login code",
            "html": f"<p>Your one-time login code is <strong>{code}</strong>. "
                    f"It expires in {OTP_EXPIRE_MINUTES} minutes.</p>",
        })
    except Exception as e:
        # Don't let email failure block the demo — log it and move on.
        print(f"[EMAIL SEND FAILED] {e}. OTP for {to_email}: {code}")
