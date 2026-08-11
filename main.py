"""
Entry point. All three section routers are wired in below.
Reconciled for Section A, Section B, and Section C.
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi.responses import HTMLResponse, JSONResponse

from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from database import Base, engine
from routers import security
from routers.auth_entry import router as auth_entry_router
from routers.sessions import router as sessions_router
from routers.co_signer import router as co_signer_router
from lib.rate_limit import limiter
from schemas import error_response

app = FastAPI(title="Dorito Vault — Passwordless Auth")

# Section A, Day 1 — global rate limiting
def custom_rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content=error_response("Rate limit exceeded (5 requests/minute). Please wait a minute before trying again.")
    )

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, custom_rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    # NOTE: allow_origins=["*"] combined with allow_credentials=True is
    # invalid per the CORS spec -- browsers silently reject/strip credentials
    # (your session cookie) on wildcard-origin responses. Since the frontend
    # is served by this same FastAPI app (templates/), same-origin requests
    # don't need CORS at all -- these origins only matter if you open the
    # frontend from a different port during testing. Add any other real
    # origins you actually use here explicitly; never use "*" with credentials.
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

app.include_router(security.router, prefix="/api/security", tags=["Section B — Security"])
app.include_router(auth_entry_router, tags=["Section A — Entry Checks"])
app.include_router(sessions_router, tags=["Section C — Sessions"])
app.include_router(co_signer_router, tags=["Co-Signer (Round 2)"])


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)


@app.get("/", response_class=HTMLResponse)
def root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard_page(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/test/security", response_class=HTMLResponse)
def security_test_page(request: Request):
    """Section B's manual test console for WebAuthn/OTP/QR flows."""
    return templates.TemplateResponse("security_test.html", {"request": request})


@app.get("/co-signer/setup/{invite_token}", response_class=HTMLResponse)
def co_signer_setup_page(invite_token: str, request: Request):
    """
    The single page a trusted family member sees after clicking the one-time
    setup link emailed to them (see routers/co_signer.py invite flow). They have
    no login of their own — this page registers their approval passkey via the
    /api/security/co-signer/register-* endpoints.

    We resolve the primary user's name for a warm, personalized header. If the
    token is unknown/expired we still render the page (default name) and let the
    client-side flow surface the friendly "expired link" state on register-options.
    """
    from database import SessionLocal
    from models import CoSigner, User

    primary_user_name = "your family member"
    db = SessionLocal()
    try:
        co_signer = db.query(CoSigner).filter(CoSigner.invite_token == invite_token).first()
        if co_signer:
            primary = db.query(User).filter(User.id == co_signer.primary_user_id).first()
            if primary:
                primary_user_name = primary.name or primary.email
    finally:
        db.close()

    return templates.TemplateResponse(
        "cosigner_setup.html",
        {
            "request": request,
            "invite_token": invite_token,
            "primary_user_name": primary_user_name,
        },
    )


@app.get("/co-signer/approve/{request_id}", response_class=HTMLResponse)
def co_signer_approve_page(request_id: str, request: Request):
    """
    The page a registered co-signer lands on from the "approval needed" email
    (see create_approval_request in routers/co_signer.py). They review a pending
    high-value/new-payee transaction and approve it with their passkey, or deny
    it. The actual crypto happens via /api/security/co-signer/approve-* and /deny.

    We resolve up-front context so the page can open directly in the right
    state (pending vs. already-resolved vs. expired) without a flash of the
    wrong UI. Transaction detail fields are optional — the model only stores a
    transaction_hash, so the page gracefully shows a generic summary unless
    richer details are wired in later.
    """
    import math
    from datetime import datetime
    from database import SessionLocal
    from models import CoSignerApprovalRequest, User

    ctx = {
        "request": request,
        "request_id": request_id,
        "primary_user_name": "a family member",
        "initial_status": "not_found",   # pending | approved | denied | expired | not_found
        "minutes_remaining": 0,
        # Optional transaction details — None means "show the generic summary".
        "transaction_amount": None,
        "transaction_recipient": None,
    }

    db = SessionLocal()
    try:
        req = (
            db.query(CoSignerApprovalRequest)
            .filter(CoSignerApprovalRequest.id == request_id)
            .first()
        )
        if req:
            primary = db.query(User).filter(User.id == req.primary_user_id).first()
            if primary:
                ctx["primary_user_name"] = primary.name or primary.email

            now = datetime.utcnow()
            if req.status == "pending" and req.expires_at <= now:
                ctx["initial_status"] = "expired"
            else:
                ctx["initial_status"] = req.status
                if req.status == "pending":
                    remaining = (req.expires_at - now).total_seconds()
                    ctx["minutes_remaining"] = max(1, math.ceil(remaining / 60))
    finally:
        db.close()

    return templates.TemplateResponse("cosigner_approve.html", ctx)


@app.get("/admin", response_class=HTMLResponse)
def admin_dashboard_page(request: Request):
    """
    Admin-only dashboard -- cross-user audit log and sensitive-action feed.
    Access control happens entirely via the API calls this page makes
    (GET /api/sessions/admin/audit-log and /admin/sensitive-actions, both
    gated by _require_admin() in routers/sessions.py). The page itself
    renders for anyone logged in, then shows an "Access denied" state if
    the API calls come back 403 -- consistent with how /dashboard already
    relies on client-side /api/sessions/me rather than a server-side check.
    """
    return templates.TemplateResponse("admin_dashboard.html", {"request": request})