"""
Section A — /api/entry/... only (CONTRACT.md section 7).
Owns the `users` table (shared, created here) and `devices` table (writes only
from here — Section B/C may read but never insert/update device rows).

These endpoints run BEFORE a session exists (registration, first-touch device
check), so unlike routers/sessions.py they do not call get_current_user(request).
user_id is taken from the request body / path instead — a known, discussed
tradeoff (see chat), not an oversight.

INTEGRATION NOTE (from Section B's INTEGRATION_NOTES_SECTION_B.md):
- check-device now returns `trusted` alongside `known_device`, so B's frontend
  can decide when to prompt for step-up OTP after a biometric login.
- alerts now also flags accounts with repeated recent login failures, read from
  login_history (populated by Section B's webauthn/otp/qr endpoints via
  log_login_attempt). This was always part of the original pt-9 spec
  ("new device, repeated failures") — it was deferred earlier only because
  login_history had no real writers yet. It does now.
"""

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session as DBSession

import models
from database import get_db
from schemas import APIResponse, RegisterRequest, CheckDeviceRequest

router = APIRouter(prefix="/api/entry", tags=["entry"])

# How far back to look, and how many failures count as "repeated", for the
# failed-login alert rule. Simple fixed thresholds — no ML needed per the
# original plan.
FAILED_LOGIN_WINDOW_MINUTES = 30
FAILED_LOGIN_THRESHOLD = 3


def _error(response: Response, status_code: int, message: str) -> APIResponse:
    response.status_code = status_code
    return APIResponse(status="error", data=None, message=message)


@router.post("/register", response_model=APIResponse)
def register(
    payload: RegisterRequest,
    response: Response,
    db: DBSession = Depends(get_db),
):
    existing = db.query(models.User).filter(models.User.email == payload.email).first()
    if existing:
        return _error(response, 409, "An account with this email already exists")

    user = models.User(email=payload.email, name=payload.name)
    db.add(user)
    db.commit()
    db.refresh(user)

    response.status_code = 201
    return APIResponse(
        status="success",
        data={"id": user.id, "email": user.email, "name": user.name},
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

    # Repeated-failure rule — reads Section C's login_history table (read-only;
    # Section A never writes to it, per CONTRACT.md ownership rules).
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
