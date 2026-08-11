"""
Section C — /api/sessions/... only (CONTRACT.md section 7).
Never call another section's HTTP route internally; if A or B need session logic,
they import functions from lib/session_utils.py directly.
"""

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import desc
from sqlalchemy.orm import Session as DBSession

import models
from database import get_db
from schemas import APIResponse, ProfileUpdateRequest
from lib.session_utils import (
    SESSION_COOKIE_NAME,
    get_current_user,
    get_current_session_id,
    revoke_session,
    revoke_all_sessions,
)

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


def _unauthorized(response: Response) -> APIResponse:
    # CONTRACT.md section 9: never trust a client-sent user ID, always 401 via
    # get_current_user(request) being None.
    response.status_code = 401
    return APIResponse(status="error", data=None, message="Not authenticated")


@router.get("/me", response_model=APIResponse)
def me(request: Request, response: Response):
    user = get_current_user(request)
    if not user:
        return _unauthorized(response)
    return APIResponse(status="success", data=user)


@router.post("/logout", response_model=APIResponse)
def logout(request: Request, response: Response):
    user = get_current_user(request)
    if not user:
        return _unauthorized(response)

    session_id = get_current_session_id(request)
    if session_id:
        revoke_session(session_id)

    response.delete_cookie(key=SESSION_COOKIE_NAME)
    return APIResponse(status="success", message="Logged out")


@router.post("/logout-all", response_model=APIResponse)
def logout_all(request: Request, response: Response):
    """Revokes every active session row for this user in one operation."""
    user = get_current_user(request)
    if not user:
        return _unauthorized(response)

    revoke_all_sessions(user["id"])
    response.delete_cookie(key=SESSION_COOKIE_NAME)
    return APIResponse(status="success", message="Logged out from all devices")


@router.get("/login-history", response_model=APIResponse)
def login_history(
    request: Request,
    response: Response,
    limit: int = 50,
    db: DBSession = Depends(get_db),
):
    user = get_current_user(request)
    if not user:
        return _unauthorized(response)

    rows = (
        db.query(models.LoginHistory)
        .filter(models.LoginHistory.user_id == user["id"])
        .order_by(desc(models.LoginHistory.created_at))
        .limit(min(limit, 200))
        .all()
    )

    # Section C, item 3 -- r.ip_address now holds a keyed hash, not a raw IP
    # (see lib/ip_utils.py). Showing a hash string to the user isn't useful,
    # so the response shows the resolved city/country instead. The hash
    # itself is intentionally NOT included here -- there's no legitimate
    # frontend need for it; it exists only for server-side correlation
    # (e.g. future abuse detection comparing hashes across attempts).
    data = [
        {
            "id": r.id,
            "method": r.method,
            "success": r.success,
            "city": r.city,
            "country": r.country,
            "device_info": r.device_info,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]
    return APIResponse(status="success", data=data)


@router.get("/profile", response_model=APIResponse)
def profile(request: Request, response: Response, db: DBSession = Depends(get_db)):
    user = get_current_user(request)
    if not user:
        return _unauthorized(response)

    db_user = db.query(models.User).filter(models.User.id == user["id"]).first()
    if not db_user:
        return _unauthorized(response)

    return APIResponse(
        status="success",
        data={
            "id": db_user.id,
            "email": db_user.email,
            "name": db_user.name,
            "created_at": db_user.created_at.isoformat(),
        },
    )


@router.post("/profile/update", response_model=APIResponse)
def update_profile(
    request: Request,
    response: Response,
    payload: ProfileUpdateRequest,
    db: DBSession = Depends(get_db),
):
    user = get_current_user(request)
    if not user:
        return _unauthorized(response)

    db_user = db.query(models.User).filter(models.User.id == user["id"]).first()
    if not db_user:
        return _unauthorized(response)

    if payload.name is not None:
        db_user.name = payload.name

    db.commit()
    db.refresh(db_user)

    return APIResponse(
        status="success",
        data={"id": db_user.id, "email": db_user.email, "name": db_user.name},
        message="Profile updated",
    )


# --- Section C, item 1 -- admin audit log (round 2, now role-gated) ---

def _require_admin(request: Request, response: Response, db: DBSession):
    """
    Shared admin gate for every /admin/... route in this file. Returns the
    admin User row on success, or None (with response.status_code already
    set) on failure -- callers should `if not admin: return <that response>`.
    """
    user = get_current_user(request)
    if not user:
        _unauthorized(response)
        return None

    db_user = db.query(models.User).filter(models.User.id == user["id"]).first()
    if not db_user or db_user.role != "admin":
        response.status_code = 403
        # Deliberately generic message -- don't reveal whether the account
        # exists or just lacks the role, same principle as not distinguishing
        # "wrong password" from "no such user" on a login form.
        return None
    return db_user


@router.get("/admin/audit-log", response_model=APIResponse)
def admin_audit_log(
    request: Request,
    response: Response,
    limit: int = 100,
    db: DBSession = Depends(get_db),
):
    """
    Cross-user login history for an admin dashboard. Deliberately excludes
    the ip_address field entirely (item 1) -- even though it's already a
    hash, not a raw IP (item 3), there's no reason an admin view needs it,
    so it's left out rather than relying on "it's just a hash" as the only
    protection. Requires role == "admin" (see _require_admin above).
    """
    if not _require_admin(request, response, db):
        return APIResponse(status="error", message="Admin access required")

    rows = (
        db.query(models.LoginHistory)
        .order_by(desc(models.LoginHistory.created_at))
        .limit(min(limit, 500))
        .all()
    )

    data = [
        {
            "id": r.id,
            "user_id": r.user_id,
            "method": r.method,
            "success": r.success,
            "city": r.city,
            "country": r.country,
            "device_info": r.device_info,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]
    return APIResponse(status="success", data=data)


@router.get("/admin/sensitive-actions", response_model=APIResponse)
def admin_sensitive_actions(
    request: Request,
    response: Response,
    limit: int = 100,
    db: DBSession = Depends(get_db),
):
    """
    Admin-only view of step-up-authenticated ("sensitive") actions -- the
    closest thing this system has to a transaction feed, since there's no
    real transactions table (see round-2 discussion). Shows which users
    triggered a step-up challenge, when, and whether it was actually
    completed (used=True) or is still pending/expired.

    transaction_hash is intentionally NOT exposed here -- it's an internal
    binding value (see models.StepUpChallenge), not something an admin view
    needs to display; showing it adds no information value and needlessly
    exposes an internal implementation detail.
    """
    if not _require_admin(request, response, db):
        return APIResponse(status="error", message="Admin access required")

    rows = (
        db.query(models.StepUpChallenge)
        .order_by(desc(models.StepUpChallenge.created_at))
        .limit(min(limit, 500))
        .all()
    )

    data = [
        {
            "id": r.id,
            "user_id": r.user_id,
            "completed": r.used,
            "expires_at": r.expires_at.isoformat(),
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]
    return APIResponse(status="success", data=data)