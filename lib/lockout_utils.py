"""
lib/lockout_utils.py — Section A, Day 2.

Reads recent failures from login_history and decides whether to lock.
"""
from datetime import datetime, timedelta
from typing import Optional

import models
from lib.email_utils import send_email
from lib.ip_utils import resolve_location

FAILED_LOGIN_WINDOW_MINUTES = 30
FAILED_LOGIN_THRESHOLD = 3
LOCKOUT_DURATION_MINUTES = 15


def is_locked(user: "models.User") -> bool:
    return bool(user.locked_until and user.locked_until > datetime.utcnow())


def check_and_lock_if_needed(db, user: "models.User", ip_address: Optional[str] = None) -> bool:
    """
    Call this right after logging a FAILED attempt. Recounts recent failures
    from login_history; if the threshold is hit, sets locked_until and sends
    a notification email. Returns True if this call triggered a new lock.
    """
    since = datetime.utcnow() - timedelta(minutes=FAILED_LOGIN_WINDOW_MINUTES)
    recent_failures = (
        db.query(models.LoginHistory)
        .filter(
            models.LoginHistory.user_id == user.id,
            models.LoginHistory.success.is_(False),
            models.LoginHistory.created_at >= since,
        )
        .count()
    )

    if recent_failures < FAILED_LOGIN_THRESHOLD:
        return False

    user.locked_until = datetime.utcnow() + timedelta(minutes=LOCKOUT_DURATION_MINUTES)
    db.commit()

    # Section C, item 3 -- never put the raw IP in an outbound email. Resolve
    # it to a rough city/country instead (or omit the line entirely if that
    # fails/is unavailable, e.g. for local dev IPs).
    city, country = resolve_location(ip_address)
    if city and country:
        location_line = f"<p>Recent attempt from around: {city}, {country}</p>"
    else:
        location_line = ""
    send_email(
        to=user.email,
        subject="Your account was temporarily locked",
        html=(
            f"<p>We locked your account for {LOCKOUT_DURATION_MINUTES} minutes "
            f"after {recent_failures} failed login attempts in the last "
            f"{FAILED_LOGIN_WINDOW_MINUTES} minutes.</p>"
            f"{location_line}"
            f"<p>If this wasn't you, consider this a heads-up that someone has "
            f"been trying to access your account.</p>"
        ),
    )
    return True


def clear_lock(db, user: "models.User") -> None:
    """Call on a successful login to clear any stale lock state."""
    if user.locked_until is not None:
        user.locked_until = None
        db.commit()
