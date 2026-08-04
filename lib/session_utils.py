"""
Shared session contract (CONTRACT.md section 5) — built by Section C, imported by
Sections A and B. Nobody outside this file touches the `sessions` or `login_history`
tables with raw SQLAlchemy.

Function signatures are locked and must not change without telling the other two
sections first:

    create_session(user_id, device_id, response) -> str
    get_current_user(request) -> dict | None
    revoke_session(session_id) -> None
    revoke_all_sessions(user_id) -> None
    log_login_attempt(user_id, method, success, ip_address, device_info) -> None
"""

import os
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Request, Response
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

from database import SessionLocal
import models

SECRET_KEY = os.getenv("SECRET_KEY")
SESSION_COOKIE_NAME = os.getenv("SESSION_COOKIE_NAME", "session_token")
SESSION_EXPIRE_MINUTES = int(os.getenv("SESSION_EXPIRE_MINUTES", "1440"))
IS_PRODUCTION = os.getenv("ENVIRONMENT", "development") == "production"

if not SECRET_KEY or SECRET_KEY == "changeme-get-real-value-from-team":
    raise RuntimeError(
        "SECRET_KEY is not set to the shared team value. Session cookies signed with "
        "a different key on your machine will not validate for the other two sections "
        "(and vice versa). Get the real value from the team, do not generate your own."
    )

_serializer = URLSafeTimedSerializer(SECRET_KEY, salt="session-cookie")


def create_session(user_id: str, device_id: Optional[str], response: Response) -> str:
    """Creates a Session row, sets signed httpOnly cookie on `response`.
    Returns session_id."""
    db = SessionLocal()
    try:
        expires_at = datetime.utcnow() + timedelta(minutes=SESSION_EXPIRE_MINUTES)
        session = models.Session(
            user_id=user_id,
            device_id=device_id,
            expires_at=expires_at,
            revoked=False,
        )
        db.add(session)
        db.commit()
        db.refresh(session)

        signed_value = _serializer.dumps(session.id)
        response.set_cookie(
            key=SESSION_COOKIE_NAME,
            value=signed_value,
            httponly=True,
            secure=IS_PRODUCTION,
            samesite="lax",
            max_age=SESSION_EXPIRE_MINUTES * 60,
        )
        return session.id
    finally:
        db.close()


def _get_session_id_from_cookie(request: Request) -> Optional[str]:
    raw = request.cookies.get(SESSION_COOKIE_NAME)
    if not raw:
        return None
    try:
        # max_age here is a defense-in-depth check on the signature itself,
        # in addition to the DB-side expires_at check below.
        return _serializer.loads(raw, max_age=SESSION_EXPIRE_MINUTES * 60)
    except (BadSignature, SignatureExpired):
        return None


def get_current_user(request: Request) -> Optional[dict]:
    """Reads cookie, validates against Session table (checks revoked + expires_at).
    Returns {"id": ..., "email": ..., "name": ...} or None."""
    session_id = _get_session_id_from_cookie(request)
    if not session_id:
        return None

    db = SessionLocal()
    try:
        session = db.query(models.Session).filter(models.Session.id == session_id).first()
        if not session or session.revoked or session.expires_at < datetime.utcnow():
            return None

        user = db.query(models.User).filter(models.User.id == session.user_id).first()
        if not user:
            return None

        return {"id": user.id, "email": user.email, "name": user.name}
    finally:
        db.close()


def get_current_session_id(request: Request) -> Optional[str]:
    """Not part of the original 5-function contract, but needed by /api/sessions/logout
    to know *which* session to revoke. Safe for A/B to import too if ever useful —
    it only reads the cookie, it doesn't touch the DB."""
    return _get_session_id_from_cookie(request)


def revoke_session(session_id: str) -> None:
    """Sets revoked=True for one session."""
    db = SessionLocal()
    try:
        session = db.query(models.Session).filter(models.Session.id == session_id).first()
        if session:
            session.revoked = True
            db.commit()
    finally:
        db.close()


def revoke_all_sessions(user_id: str) -> None:
    """Sets revoked=True for all sessions belonging to a user."""
    db = SessionLocal()
    try:
        db.query(models.Session).filter(
            models.Session.user_id == user_id,
            models.Session.revoked.is_(False),
        ).update({"revoked": True})
        db.commit()
    finally:
        db.close()


def log_login_attempt(
    user_id: Optional[str],
    method: str,
    success: bool,
    ip_address: Optional[str],
    device_info: Optional[str],
) -> None:
    """Writes one row to login_history. method must be one of the 3 fixed strings."""
    if method not in ("webauthn", "otp", "qr"):
        raise ValueError(f"Invalid login method '{method}'. Must be webauthn, otp, or qr.")

    db = SessionLocal()
    try:
        entry = models.LoginHistory(
            user_id=user_id,
            method=method,
            success=success,
            ip_address=ip_address,
            device_info=device_info,
        )
        db.add(entry)
        db.commit()
    finally:
        db.close()
