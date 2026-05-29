"""FastAPI application entrypoint.

Run locally:
    pip install -e ".[web,export]"
    AUTH_DISABLED=true uvicorn app.main:app --reload
"""

from __future__ import annotations

from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app import auth
from app.auth import require_user
from app.config import settings
from app.routes import earnings, lcp, lhhs, lookups, persistence
from storage import connect, init_db

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

app = FastAPI(title="Forensic Economic Calculator")
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret,
    https_only=settings.secure_cookies,
    same_site="lax",  # allows the cookie on the OAuth callback top-level redirect
)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

app.include_router(auth.router)
app.include_router(earnings.router)
app.include_router(lcp.router)
app.include_router(lhhs.router)
app.include_router(lookups.router)
app.include_router(persistence.router)


@app.on_event("startup")
def _ensure_schema() -> None:
    conn = connect(settings.db_target)
    try:
        init_db(conn)
    finally:
        conn.close()


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request, user: str = Depends(require_user)):
    return templates.TemplateResponse(
        request, "index.html", {"user": user}
    )


@app.get("/healthz")
def healthz():
    return {"status": "ok"}
