"""
Round 2 — Assisted "Co-Signer" Passkeys (delegated authentication).

For elderly/vulnerable users: a linked family member can register a passkey
on THEIR OWN device (no login account of their own) that's used only to
approve high-risk actions — a transfer above a threshold, or paying a new
payee for the first time — on the primary user's behalf.

Flow:
  1. Primary user invites a co-signer by email (POST /co-signer/invite).
  2. Co-signer opens the emailed link on their own device, registers a
     passkey there (register-options / register-verify).
  3. When the primary user creates a step-up challenge for a transaction
     that's flagged high-risk (see is_high_risk() below), and they have a
     registered co-signer, a CoSignerApprovalRequest is created and the
     co-signer is emailed an approval link.
  4. Co-signer opens that link, approves using their passkey
     (approve-options / approve-verify).
  5. The primary user's frontend polls GET /step-up/status/{challenge_id}
     (see routers/security.py) — the sensitive action may only proceed once
     BOTH the primary user's own step-up AND the co-signer's approval (if
     one was required) are complete.

Ownership: new in round 2 — needs a team decision on which section this
lives under long-term. Mounted under /api/security/co-signer for now since
it's WebAuthn-flavored, matching Section B's existing conventions.
"""

import os
import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session as DBSession

from webauthn import (
    generate_registration_options,
    verify_registration_response,
    generate_authentication_options,
    verify_authentication_response,
    options_to_json,
)
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    UserVerificationRequirement,
    PublicKeyCredentialDescriptor,
)

from database import get_db
from models import CoSigner, CoSignerCredential, CoSignerApprovalRequest, User
from schemas import (
    success_response,
    error_response,
    CoSignerInviteRequest,
    CoSignerRegisterOptionsRequest,
    CoSignerRegisterVerifyRequest,
    CoSignerApproveOptionsRequest,
    CoSignerApproveVerifyRequest,
)
from lib.session_utils import get_current_user
from lib.email_utils import send_email

router = APIRouter(prefix="/api/security/co-signer", tags=["co-signer"])

RP_ID = os.getenv("WEBAUTHN_RP_ID", "localhost")
RP_NAME = os.getenv("WEBAUTHN_RP_NAME", "SecureBank Demo")
ORIGIN = os.getenv("WEBAUTHN_ORIGIN", "http://localhost:8000")

INVITE_EXPIRE_HOURS = 24
APPROVAL_EXPIRE_MINUTES = 15  # matches typical step-up challenge lifetime

# High-risk thresholds — adjust freely, this is a policy choice, not a
# technical constraint. Kept as module constants so they're easy to find.
HIGH_RISK_AMOUNT_THRESHOLD = 10_000

# In-memory pending-challenge store, mirroring routers/security.py's pattern.
# Same production caveat applies: use Redis/shared store for multi-worker deploys.
_pending_challenges: dict[str, bytes] = {}


def is_high_risk(transaction: dict) -> bool:
    """
    A transaction is high-risk if it's above the amount threshold, OR if
    it's flagged as going to a new (not previously used) payee. The
    'is_new_payee' flag is expected to be set by whoever builds the
    transaction/payee-tracking logic (not yet built as of round 2) — until
    that exists, only the amount check is actually reachable.
    """
    amount = transaction.get("amount")
    is_new_payee = transaction.get("is_new_payee", False)
    if isinstance(amount, (int, float)) and amount > HIGH_RISK_AMOUNT_THRESHOLD:
        return True
    if is_new_payee:
        return True
    return False


def get_active_co_signer(db: DBSession, primary_user_id: str) -> CoSigner | None:
    """Used by routers/auth_entry.py when creating a step-up challenge, to
    decide whether a co-signer approval is also required."""
    return (
        db.query(CoSigner)
        .filter(CoSigner.primary_user_id == primary_user_id, CoSigner.registered == True)  # noqa: E712
        .first()
    )


def create_approval_request(
    db: DBSession, primary_user_id: str, co_signer: CoSigner, transaction_hash: str
) -> CoSignerApprovalRequest:
    """Used by routers/auth_entry.py right after creating a StepUpChallenge,
    when is_high_risk() and a registered co-signer both apply."""
    req = CoSignerApprovalRequest(
        primary_user_id=primary_user_id,
        co_signer_id=co_signer.id,
        transaction_hash=transaction_hash,
        expires_at=datetime.utcnow() + timedelta(minutes=APPROVAL_EXPIRE_MINUTES),
    )
    db.add(req)
    db.commit()
    db.refresh(req)

    approve_link = f"{ORIGIN}/co-signer/approve/{req.id}"
    send_email(
        to=co_signer.notify_email,
        subject="Approval needed for a high-value transaction",
        html=(
            f"<p>A high-value or new-payee transaction needs your approval "
            f"as a registered co-signer.</p>"
            f"<p><a href=\"{approve_link}\">Review and approve</a></p>"
            f"<p>This request expires in {APPROVAL_EXPIRE_MINUTES} minutes.</p>"
        ),
    )
    return req


# ===========================================================================
# INVITE A CO-SIGNER
# ===========================================================================

@router.post("/invite")
def invite_co_signer(payload: CoSignerInviteRequest, request: Request, db: DBSession = Depends(get_db)):
    current_user = get_current_user(request)
    if not current_user or current_user["id"] != payload.primary_user_id:
        return error_response("You may only invite a co-signer for your own account.")

    invite_token = secrets.token_urlsafe(32)
    co_signer = CoSigner(
        primary_user_id=payload.primary_user_id,
        label=payload.label,
        notify_email=payload.notify_email,
        invite_token=invite_token,
        invite_expires_at=datetime.utcnow() + timedelta(hours=INVITE_EXPIRE_HOURS),
        registered=False,
    )
    db.add(co_signer)
    db.commit()
    db.refresh(co_signer)

    invite_link = f"{ORIGIN}/co-signer/setup/{invite_token}"
    send_email(
        to=payload.notify_email,
        subject="You've been added as a trusted co-signer",
        html=(
            f"<p>{current_user.get('name') or current_user['email']} has added you as a "
            f"trusted co-signer on their account, to help approve high-value transactions.</p>"
            f"<p><a href=\"{invite_link}\">Set up your approval passkey</a></p>"
            f"<p>This invite expires in {INVITE_EXPIRE_HOURS} hours.</p>"
        ),
    )

    return success_response(
        data={"co_signer_id": co_signer.id},
        message="Invite sent. The co-signer must complete passkey setup before approvals will work.",
    )


# ===========================================================================
# CO-SIGNER COMPLETES PASSKEY REGISTRATION (on their own device)
# ===========================================================================

@router.post("/register-options")
def co_signer_register_options(payload: CoSignerRegisterOptionsRequest, db: DBSession = Depends(get_db)):
    co_signer = db.query(CoSigner).filter(CoSigner.invite_token == payload.invite_token).first()
    if not co_signer:
        return error_response("Invalid or already-used invite link.")
    if co_signer.invite_expires_at < datetime.utcnow():
        return error_response("This invite has expired. Ask the account holder to send a new one.")

    options = generate_registration_options(
        rp_id=RP_ID,
        rp_name=RP_NAME,
        user_id=co_signer.id.encode("utf-8"),
        user_name=co_signer.notify_email,
        user_display_name=co_signer.label or co_signer.notify_email,
        authenticator_selection=AuthenticatorSelectionCriteria(
            user_verification=UserVerificationRequirement.PREFERRED,
        ),
    )
    _pending_challenges[co_signer.id] = options.challenge
    return success_response(data={"options": options_to_json(options)})


@router.post("/register-verify")
def co_signer_register_verify(payload: CoSignerRegisterVerifyRequest, db: DBSession = Depends(get_db)):
    co_signer = db.query(CoSigner).filter(CoSigner.invite_token == payload.invite_token).first()
    if not co_signer:
        return error_response("Invalid or already-used invite link.")

    expected_challenge = _pending_challenges.get(co_signer.id)
    if not expected_challenge:
        return error_response("No registration in progress for this invite. Start again.")

    try:
        verification = verify_registration_response(
            credential=payload.credential,
            expected_challenge=expected_challenge,
            expected_rp_id=RP_ID,
            expected_origin=ORIGIN,
        )
    except Exception as e:
        return error_response(f"Passkey registration failed: {e}")

    credential = CoSignerCredential(
        co_signer_id=co_signer.id,
        public_key=verification.credential_public_key,
        webauthn_cred_id=verification.credential_id.hex(),
        counter=verification.sign_count,
    )
    db.add(credential)

    co_signer.registered = True
    co_signer.invite_token = None  # one-time use, now consumed
    co_signer.invite_expires_at = None
    db.commit()

    _pending_challenges.pop(co_signer.id, None)
    return success_response(message="Passkey registered. You're now set up to approve transactions.")


# ===========================================================================
# CO-SIGNER APPROVES A PENDING REQUEST (on their own device)
# ===========================================================================

@router.post("/approve-options")
def co_signer_approve_options(payload: CoSignerApproveOptionsRequest, db: DBSession = Depends(get_db)):
    req = db.query(CoSignerApprovalRequest).filter(CoSignerApprovalRequest.id == payload.request_id).first()
    if not req:
        return error_response("Approval request not found.")
    if req.status != "pending":
        return error_response(f"This request is already {req.status}.")
    if req.expires_at < datetime.utcnow():
        req.status = "expired"
        db.commit()
        return error_response("This approval request has expired.")

    credentials = (
        db.query(CoSignerCredential)
        .filter(CoSignerCredential.co_signer_id == req.co_signer_id)
        .all()
    )
    if not credentials:
        return error_response("No registered passkey found for this co-signer.")

    options = generate_authentication_options(
        rp_id=RP_ID,
        allow_credentials=[
            PublicKeyCredentialDescriptor(id=bytes.fromhex(c.webauthn_cred_id)) for c in credentials
        ],
        user_verification=UserVerificationRequirement.PREFERRED,
    )
    _pending_challenges[f"approval:{req.id}"] = options.challenge
    return success_response(data={"options": options_to_json(options)})


@router.post("/approve-verify")
def co_signer_approve_verify(payload: CoSignerApproveVerifyRequest, db: DBSession = Depends(get_db)):
    req = db.query(CoSignerApprovalRequest).filter(CoSignerApprovalRequest.id == payload.request_id).first()
    if not req:
        return error_response("Approval request not found.")
    if req.status != "pending":
        return error_response(f"This request is already {req.status}.")
    if req.expires_at < datetime.utcnow():
        req.status = "expired"
        db.commit()
        return error_response("This approval request has expired.")

    expected_challenge = _pending_challenges.get(f"approval:{req.id}")
    if not expected_challenge:
        return error_response("No approval in progress for this request. Start again.")

    cred_id = bytes.fromhex(payload.credential.get("id_hex", "")) if "id_hex" in payload.credential else None
    stored_cred = (
        db.query(CoSignerCredential)
        .filter(CoSignerCredential.co_signer_id == req.co_signer_id)
        .first()
    )
    if not stored_cred:
        return error_response("No registered passkey found for this co-signer.")

    try:
        verification = verify_authentication_response(
            credential=payload.credential,
            expected_challenge=expected_challenge,
            expected_rp_id=RP_ID,
            expected_origin=ORIGIN,
            credential_public_key=stored_cred.public_key,
            credential_current_sign_count=stored_cred.counter,
        )
    except Exception as e:
        return error_response(f"Approval verification failed: {e}")

    stored_cred.counter = verification.new_sign_count
    req.status = "approved"
    req.resolved_at = datetime.utcnow()
    db.commit()

    _pending_challenges.pop(f"approval:{req.id}", None)
    return success_response(message="Approved. The primary user's transaction may now proceed.")


@router.get("/approval-status/{request_id}")
def co_signer_approval_status(request_id: str, db: DBSession = Depends(get_db)):
    """Polled by the primary user's frontend to know when their co-signer
    has (or hasn't yet) approved."""
    req = db.query(CoSignerApprovalRequest).filter(CoSignerApprovalRequest.id == request_id).first()
    if not req:
        return error_response("Approval request not found.")
    return success_response(data={"status": req.status})


@router.get("/transaction-status/{challenge_id}")
def transaction_status(challenge_id: str, db: DBSession = Depends(get_db)):
    """
    The single status check a frontend should actually poll before letting a
    sensitive action proceed -- combines the primary user's own step-up
    (StepUpChallenge.used) with any required co-signer approval into one
    answer: is this transaction fully cleared to execute yet?
    """
    from models import StepUpChallenge  # local import avoids a circular import at module load time

    challenge = db.query(StepUpChallenge).filter(StepUpChallenge.id == challenge_id).first()
    if not challenge:
        return error_response("Step-up challenge not found.")

    co_signer_request = (
        db.query(CoSignerApprovalRequest)
        .filter(CoSignerApprovalRequest.transaction_hash == challenge.transaction_hash)
        .order_by(CoSignerApprovalRequest.created_at.desc())
        .first()
    )

    primary_user_cleared = challenge.used
    co_signer_cleared = (co_signer_request is None) or (co_signer_request.status == "approved")

    return success_response(
        data={
            "primary_user_step_up_complete": primary_user_cleared,
            "co_signer_approval_required": co_signer_request is not None,
            "co_signer_status": co_signer_request.status if co_signer_request else None,
            "fully_cleared": primary_user_cleared and co_signer_cleared,
        }
    )