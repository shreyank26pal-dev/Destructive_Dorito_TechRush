"""
lib/rate_limit.py — Section A, Day 1.

The Limiter instance lives here (not in main.py) so routers can import it for
per-route limits (@limiter.limit("5/minute")) without a circular import.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])
