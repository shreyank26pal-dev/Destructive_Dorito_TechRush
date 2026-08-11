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


@app.get("/admin", response_class=HTMLResponse)
def admin_page(request: Request):
    """Admin-only Security Operations console (cross-user audit + step-up telemetry)."""
    return templates.TemplateResponse("admin.html", {"request": request})


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/test/security", response_class=HTMLResponse)
def security_test_page(request: Request):
    """Section B's manual test console for WebAuthn/OTP/QR flows."""
    return templates.TemplateResponse("security_test.html", {"request": request})
