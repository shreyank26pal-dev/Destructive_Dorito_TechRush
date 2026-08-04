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

    data = [
        {
            "id": r.id,
            "method": r.method,
            "success": r.success,
            "ip_address": r.ip_address,
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
