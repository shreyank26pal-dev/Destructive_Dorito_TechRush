# CONTRACT.md — Shared Rules for Passwordless Bank Auth Project

This file is the single source of truth for anything that must stay identical across
Section A (Entry Checks), Section B (Security Measures), and Section C (Sessions/Logout).

**Rule zero: paste this entire file as context into every AI coding prompt, for every
section, for the whole project.** If you're vibe-coding a new endpoint, page, or function,
include this file first so the AI follows the same conventions every other section is using.

No one changes anything in this file without telling the other two people first.

---

## 1. Tech Stack (do not deviate)

- Backend: FastAPI (Python)
- Database: PostgreSQL (hosted on Supabase)
- ORM: SQLAlchemy + Alembic for migrations
- Frontend: Jinja2 templates + vanilla JS (Tailwind via CDN for styling)
- Biometric auth: `py_webauthn` (the `webauthn` package)
- OTP: Python `secrets` module to generate, `passlib`/`bcrypt` to hash, Resend or `smtplib` to send
- Sessions: signed httpOnly cookies via `itsdangerous`
- Deployment: Railway or Render
- Local dev server: `uvicorn main:app --reload`

---

## 2. Environment Variables

Every person's local `.env` must use these exact keys. `SECRET_KEY` must be byte-identical
across all three machines or session cookies signed by one person won't validate for another.

```
DATABASE_URL=postgresql://...
SECRET_KEY=<shared value — get this from the team, do not generate your own>
RESEND_API_KEY=...
WEBAUTHN_RP_ID=localhost
WEBAUTHN_RP_NAME=SecureBank Demo
WEBAUTHN_ORIGIN=http://localhost:8000
SESSION_COOKIE_NAME=session_token
SESSION_EXPIRE_MINUTES=1440
OTP_EXPIRE_MINUTES=5
```

A `.env.example` file (placeholder values only, no secrets) is committed to the repo.
The real `.env` is shared privately (chat/password manager) and is listed in `.gitignore`.
Never commit `.env`.

---

## 3. Database Schema — Exact Field Names

Locked on Day 1. Nobody adds/renames a column without asking the other two first.

```python
# users
id: str (uuid, PK)
email: str (unique)
name: str | None
created_at: datetime

# credentials        -- Section B owns writes, others may read
id: str (uuid, PK)
user_id: str (FK -> users.id)
public_key: bytes
webauthn_cred_id: str (unique)
device_label: str | None
counter: int
created_at: datetime
last_used_at: datetime | None

# devices            -- Section A owns writes, others read
id: str (uuid, PK)
user_id: str (FK -> users.id)
fingerprint: str
trusted: bool
first_seen_at: datetime
last_seen_at: datetime

# sessions           -- Section C owns writes; everyone else reads via shared helper only
id: str (uuid, PK)
user_id: str (FK -> users.id)
device_id: str | None (FK -> devices.id)
created_at: datetime
expires_at: datetime
revoked: bool

# login_history      -- Section C owns the write function; A and B call it, never write directly
id: str (uuid, PK)
user_id: str (FK -> users.id)
method: str   # exactly one of: "webauthn" | "otp" | "qr"
success: bool
ip_address: str | None
device_info: str | None
created_at: datetime

# otp_codes          -- Section B owns
id: str (uuid, PK)
user_id: str (FK -> users.id)
code_hash: str
expires_at: datetime
used: bool
created_at: datetime
```

---

## 4. Fixed Vocabulary Strings (use exact casing, no variants)

```
login_history.method:   "webauthn" | "otp" | "qr"
API response status:    "success" | "error"
```

---

## 5. Shared Session Contract

File: `lib/session_utils.py` — built by Section C by end of Day 2. Sections A and B
import and call these functions. They never touch the `sessions` or `login_history`
tables directly with raw SQLAlchemy.

```python
def create_session(user_id: str, device_id: str | None, response) -> str:
    """Creates a Session row, sets signed httpOnly cookie on `response`.
    Returns session_id."""

def get_current_user(request) -> dict | None:
    """Reads cookie, validates against Session table (checks revoked + expires_at).
    Returns {"id": ..., "email": ..., "name": ...} or None."""

def revoke_session(session_id: str) -> None:
    """Sets revoked=True for one session."""

def revoke_all_sessions(user_id: str) -> None:
    """Sets revoked=True for all sessions belonging to a user."""

def log_login_attempt(user_id: str | None, method: str, success: bool,
                        ip_address: str, device_info: str) -> None:
    """Writes one row to login_history. method must be one of the 3 fixed strings above."""
```

---

## 6. API Response Shape (identical for every endpoint, every section)

Success:
```json
{
  "status": "success",
  "data": { "...": "..." },
  "message": "Optional human-readable string"
}
```

Error:
```json
{
  "status": "error",
  "data": null,
  "message": "Human-readable error string"
}
```

Shared Pydantic model, imported everywhere:

```python
# schemas.py
from pydantic import BaseModel
from typing import Any, Optional

class APIResponse(BaseModel):
    status: str
    data: Optional[Any] = None
    message: Optional[str] = None
```

---

## 7. Route Prefixes (each section stays inside its own prefix)

```
/api/entry/...       -> Section A only
/api/security/...     -> Section B only
/api/sessions/...      -> Section C only
```

Agreed endpoint list:

```
POST /api/entry/register
POST /api/entry/check-device
GET  /api/entry/alerts/{user_id}

POST /api/security/webauthn/register-options
POST /api/security/webauthn/register-verify
POST /api/security/webauthn/login-options
POST /api/security/webauthn/login-verify
POST /api/security/otp/send
POST /api/security/otp/verify

POST /api/sessions/logout
POST /api/sessions/logout-all
GET  /api/sessions/me
GET  /api/sessions/login-history
GET  /api/sessions/profile
POST /api/sessions/profile/update
```

If Section A needs something from Section C's logic, import the Python function —
never call another section's HTTP route internally.

---

## 8. Frontend JS Variable Names

```javascript
let currentUser = null;        // populated from /api/sessions/me
let deviceFingerprint = null;  // computed once on page load, sent with every auth call
let pendingChallenge = null;   // WebAuthn challenge currently in flight
```

No use of localStorage/sessionStorage for auth data — session state lives in httpOnly
cookies only, JS variables above are just for in-page UI state.

---

## 9. Non-Negotiable Security Baseline (every section, no exceptions)

- Cookies: `httponly=True`, `secure=True` (production), `samesite="lax"`
- OTP codes hashed with `passlib` bcrypt before storage — never store plaintext
- Every protected route calls `get_current_user(request)`; if `None`, return the
  standard error APIResponse with a 401 — never trust a client-sent user ID
- Every login attempt, success or fail, from any section, calls `log_login_attempt(...)`
- All timestamps stored as UTC (`datetime.utcnow()`), never local time

---

## 10. Folder Structure

```
bank-auth-app/
  main.py
  database.py
  models.py
  schemas.py
  routers/
    auth_entry.py     # Section A
    security.py        # Section B
    sessions.py          # Section C
  lib/
    session_utils.py    # Section C builds, everyone imports
  templates/
  static/
  alembic/
  .env.example
  .gitignore
  requirements.txt
  CONTRACT.md
```

---

## 11. Git Workflow

- One repo, one `main` branch that always stays deployable
- Each person works on their own branch: `feature/section-a`, `feature/section-b`, `feature/section-c`
- Pull `main` before starting each work session
- Schema changes (Alembic migrations) are announced in the team chat before pushing
- Merge to `main` only after a quick sanity check that your section still runs locally
