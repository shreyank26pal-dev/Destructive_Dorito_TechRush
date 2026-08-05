"""
Entry point. All three section routers are wired in below.

MERGE NOTE on prefixes: Section B's router (security.py) declares no prefix of
its own — it's applied here via include_router(..., prefix=...). Sections A's
and C's routers (auth_entry.py, sessions.py) already declare their own prefix
via APIRouter(prefix="/api/..."), so they're included with no extra prefix arg.
Do not add prefix= to those two or routes will double up (e.g. /api/sessions/api/sessions/me).
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse

from database import Base, engine
from routers import security
from routers.auth_entry import router as auth_entry_router
from routers.sessions import router as sessions_router

app = FastAPI(title="Dorito Vault — Passwordless Auth")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

app.include_router(security.router, prefix="/api/security", tags=["Section B — Security"])
app.include_router(auth_entry_router, tags=["Section A — Entry Checks"])
app.include_router(sessions_router, tags=["Section C — Sessions"])


@app.on_event("startup")
def on_startup():
    # Dev convenience only. Once the schema is locked and shared on Supabase,
    # switch to Alembic migrations instead of create_all.
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
