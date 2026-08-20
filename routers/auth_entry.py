"""
Section A — /api/entry/... only (CONTRACT.md section 7).
Owns the `users` table (shared, created here) and `devices` table (writes only
from here — Section B/C may read but never insert/update device rows).
"""

import hashlib
import json
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session as DBSession

import models
from database import get_db
from schemas import APIResponse, RegisterRequest, CheckDeviceRequest, StepUpChallengeRequest
from lib.lockout_utils import FAILED_LOGIN_WINDOW_MINUTES, FAILED_LOGIN_THRESHOLD
from lib.rate_limit import limiter

router = APIRouter(prefix="/api/entry", tags=["entry"])

STEP_UP_CHALLENGE_EXPIRE_MINUTES = 5


def _error(response: Response, status_code: int, message: str) -> APIResponse:
    response.status_code = status_code
    return APIResponse(status="error", data=None, message=message)


@router.post("/register", response_model=APIResponse)
@limiter.limit("5/minute")
def register(
    request: Request,
    payload: RegisterRequest,
    response: Response,
    db: DBSession = Depends(get_db),
):
    existing = db.query(models.User).filter(models.User.email == payload.email).first()
    if existing:
        return _error(response, 409, "An account with this email already exists")

    user = models.User(email=payload.email, name=payload.name, is_verified=False)
    db.add(user)
    db.commit()
    db.refresh(user)

    response.status_code = 201
    return APIResponse(
        status="success",
        data={"id": user.id, "email": user.email, "name": user.name, "is_verified": user.is_verified},
        message="User registered",
    )


@router.post("/check-device", response_model=APIResponse)
def check_device(
    payload: CheckDeviceRequest,
    response: Response,
    db: DBSession = Depends(get_db),
):
    user = db.query(models.User).filter(models.User.id == payload.user_id).first()
    if not user:
        return _error(response, 404, "User not found")

    device = (
        db.query(models.Device)
        .filter(
            models.Device.user_id == payload.user_id,
            models.Device.fingerprint == payload.fingerprint,
        )
        .first()
    )

    if device:
        device.last_seen_at = datetime.utcnow()
        db.commit()
        return APIResponse(
            status="success",
            data={"known_device": True, "trusted": device.trusted},
        )

    device = models.Device(
        user_id=payload.user_id,
        fingerprint=payload.fingerprint,
        trusted=False,
    )
    db.add(device)
    db.commit()
    return APIResponse(
        status="success",
        data={"known_device": False, "trusted": False},
    )


@router.get("/alerts/{user_id}", response_model=APIResponse)
def alerts(
    user_id: str,
    response: Response,
    db: DBSession = Depends(get_db),
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        return _error(response, 404, "User not found")

    alert_list = []

    untrusted_devices = (
        db.query(models.Device)
        .filter(models.Device.user_id == user_id, models.Device.trusted.is_(False))
        .all()
    )
    for d in untrusted_devices:
        alert_list.append({
            "type": "untrusted_device",
            "device_id": d.id,
            "fingerprint": d.fingerprint,
            "first_seen_at": d.first_seen_at.isoformat(),
            "last_seen_at": d.last_seen_at.isoformat(),
        })

    since = datetime.utcnow() - timedelta(minutes=FAILED_LOGIN_WINDOW_MINUTES)
    recent_failures = (
        db.query(models.LoginHistory)
        .filter(
            models.LoginHistory.user_id == user_id,
            models.LoginHistory.success.is_(False),
            models.LoginHistory.created_at >= since,
        )
        .count()
    )
    if recent_failures >= FAILED_LOGIN_THRESHOLD:
        alert_list.append({
            "type": "repeated_failed_logins",
            "count": recent_failures,
            "window_minutes": FAILED_LOGIN_WINDOW_MINUTES,
        })

    return APIResponse(status="success", data=alert_list)


def _get_country_from_ip(ip: str) -> str:
    """Detects country code from IP address."""
    if not ip or ip in ["127.0.0.1", "::1", "localhost", "unknown"]:
        return "IN"  # Default home region: India
    try:
        import urllib.request
        url = f"http://ip-api.com/json/{ip}?fields=countryCode"
        req = urllib.request.urlopen(url, timeout=1.5)
        data = json.loads(req.read().decode())
        return data.get("countryCode", "IN")
    except Exception:
        return "IN"


@router.post("/step-up/challenge", response_model=APIResponse)
def create_step_up_challenge(
    request: Request,
    payload: StepUpChallengeRequest,
    response: Response,
    db: DBSession = Depends(get_db),
):
    """
    Section A, Day 3. Call this before a sensitive action (e.g. a transfer)
    to get a challenge_id bound to a hash of that specific transaction's details.
    Enforces automatic Geolocation Firewall banning foreign transactions.
    """
    user = db.query(models.User).filter(models.User.id == payload.user_id).first()
    if not user:
        return _error(response, 404, "User not found")

    # Automatic Geolocation Firewall
    # Read client IP from X-Forwarded-For header to support deployed reverse proxies
    xff = request.headers.get("x-forwarded-for")
    if xff:
        client_ip = xff.split(",")[0].strip()
    else:
        client_ip = request.client.host if request.client else "unknown"
    client_tz = request.headers.get("x-client-timezone", "")
    client_lang = request.headers.get("x-client-language", "")
    emulated_header = request.headers.get("x-emulated-country", "").upper()

    # Detect foreign server / timezone / locale origin (Shanghai, London, Tokyo, US, UK, JP, etc.)
    is_foreign_tz = any(kw in client_tz for kw in ["Shanghai", "London", "Tokyo", "Europe", "America", "Asia/Shanghai", "Asia/Tokyo", "GMT"])
    is_foreign_lang = any(kw in client_lang for kw in ["zh-CN", "zh-TW", "en-GB", "ja-JP"])
    detected_country = emulated_header if emulated_header else _get_country_from_ip(client_ip)

    # Home country is India ("IN"). Ban all foreign transactions!
    if is_foreign_tz or is_foreign_lang or (detected_country not in ["IN", "INDIA"] and client_ip not in ["127.0.0.1", "::1", "localhost"]):
        loc_name = client_tz or client_lang or detected_country
        return _error(
            response,
            403,
            f"SECURITY POLICY VIOLATION: Cross-Border Geolocation Risk Detected! Wire transfers are restricted from foreign server location ({loc_name}). Step-Up authorization denied."
        )

    canonical = json.dumps(payload.transaction, sort_keys=True, separators=(",", ":"))
    transaction_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    challenge = models.StepUpChallenge(
        user_id=user.id,
        transaction_hash=transaction_hash,
        expires_at=datetime.utcnow() + timedelta(minutes=STEP_UP_CHALLENGE_EXPIRE_MINUTES),
    )
    db.add(challenge)
    db.commit()
    db.refresh(challenge)

    # Round 2 -- assisted authentication for high-risk actions. If this
    # transaction is high-risk (large amount / new payee) AND the user has
    # a registered co-signer, a second approval is required from them
    # before the action may proceed, alongside the primary user's own
    # step-up OTP. See routers/co_signer.py for the full flow.
    co_signer_request_id = None
    from routers.co_signer import is_high_risk, get_active_co_signer, create_approval_request

    if is_high_risk(payload.transaction):
        co_signer = get_active_co_signer(db, user.id)
        if co_signer:
            approval_req = create_approval_request(db, user.id, co_signer, transaction_hash, request=request)
            co_signer_request_id = approval_req.id

    return APIResponse(
        status="success",
        data={
            "challenge_id": challenge.id,
            "transaction_hash": transaction_hash,
            "expires_at": challenge.expires_at.isoformat(),
            "co_signer_approval_required": co_signer_request_id is not None,
            "co_signer_request_id": co_signer_request_id,
        },
        message="Present this challenge_id with the step-up OTP to authorize this specific transaction.",
    )