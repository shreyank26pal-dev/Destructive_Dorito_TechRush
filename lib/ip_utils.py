"""
lib/ip_utils.py — Section C, item 3 (IP address protection).

Problem: storing raw IP addresses in login_history means a database leak
exposes every user's approximate location and network history. This module
makes sure a raw IP is NEVER written to the database — only a one-way hash
(for correlation, e.g. "this same network tried again") and a resolved
city/country (for a human-readable location, e.g. in lockout emails and the
login-history UI).

Usage from log_login_attempt() (see lib/session_utils.py):
    from lib.ip_utils import hash_ip, resolve_location

    ip_hash = hash_ip(raw_ip)
    city, country = resolve_location(raw_ip)
    # raw_ip itself is discarded after this point — never passed to db.add()

Design notes:
- hash_ip() is a KEYED hash (HMAC-SHA256, keyed with SECRET_KEY), not a bare
  SHA256. A bare hash of an IP is reversible via a rainbow table (there are
  only ~4 billion IPv4 addresses — trivial to precompute). Keying it with a
  secret only your team knows makes that infeasible.
- resolve_location() calls a free external geolocation API (ip-api.com, no
  key required) with a short timeout and fails silently — a slow/down
  geolocation service must NEVER block or fail a login attempt. If it fails,
  city/country are just None; the login itself still succeeds and still gets
  logged (with a hash, so security correlation still works).
- Private/loopback IPs (127.0.0.1, 10.x, 192.168.x, etc.) are skipped
  entirely — they're extremely common during local dev/testing and
  geolocation APIs can't resolve them anyway.
"""

import hashlib
import hmac
import ipaddress
import os
from typing import Optional, Tuple

import requests

SECRET_KEY = os.getenv("SECRET_KEY")
_GEOLOCATION_TIMEOUT_SECONDS = 1.5


def hash_ip(raw_ip: Optional[str]) -> Optional[str]:
    """
    One-way, keyed hash of an IP address. Same IP always produces the same
    hash (so repeated-attacker detection still works), but the hash cannot
    be reversed back to the original IP without SECRET_KEY.

    Returns None if raw_ip is None/empty, so callers don't need to special-case
    missing IPs before calling this.
    """
    if not raw_ip:
        return None
    if not SECRET_KEY:
        raise RuntimeError(
            "SECRET_KEY is not set — hash_ip() requires it to key the hash. "
            "Without a secret key, IP hashes would be reversible via a rainbow "
            "table (there are only ~4 billion possible IPv4 addresses)."
        )
    return hmac.new(
        key=SECRET_KEY.encode("utf-8"),
        msg=raw_ip.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()


def _is_private_or_local(raw_ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(raw_ip)
        return addr.is_private or addr.is_loopback or addr.is_link_local
    except ValueError:
        # Not a parseable IP at all (e.g. empty string, malformed header) —
        # treat as unresolvable rather than crashing the caller.
        return True


def resolve_location(raw_ip: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """
    Best-effort (city, country) lookup for a raw IP. Returns (None, None) if:
      - raw_ip is missing
      - raw_ip is private/loopback (localhost, LAN, etc. — can't be geolocated)
      - the geolocation service is slow, down, or errors for any reason

    Never raises — a broken geolocation call must never break a login attempt.
    The raw_ip itself is only used transiently here and is never returned or
    stored by this function.
    """
    if not raw_ip or _is_private_or_local(raw_ip):
        return None, None

    try:
        resp = requests.get(
            f"http://ip-api.com/json/{raw_ip}",
            params={"fields": "status,city,country"},
            timeout=_GEOLOCATION_TIMEOUT_SECONDS,
        )
        data = resp.json()
        if data.get("status") == "success":
            return data.get("city"), data.get("country")
    except Exception:
        # Network hiccup, timeout, rate limit, whatever — degrade gracefully.
        pass

    return None, None
