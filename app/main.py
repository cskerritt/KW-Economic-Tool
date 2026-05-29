"""FastAPI application entrypoint.

Run locally:
    pip install -e ".[web,export]"
    AUTH_DISABLED=true uvicorn app.main:app --reload
"""

from __future__ import annotations

from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
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


@app.exception_handler(ValueError)
@app.exception_handler(KeyError)
def _bad_input(request: Request, exc: Exception) -> PlainTextResponse:
    """Turn malformed calculation input into a clean 422, not a 500.

    The calculate/save/export routes parse user-supplied JSON and numeric form
    fields and pass them to the engine, which raises ``ValueError`` (and
    ``json.JSONDecodeError``, a ValueError subclass) on bad input, or
    ``KeyError`` when a required field is missing. These are client errors, so
    surface them as 422 with the message instead of an opaque server error.
    """
    detail = str(exc) or exc.__class__.__name__
    if isinstance(exc, KeyError):
        detail = f"missing required field: {detail}"
    return PlainTextResponse(f"Invalid input: {detail}", status_code=422)


@app.exception_handler(401)
def _needs_login(request: Request, exc) -> object:
    """Send unauthenticated browser page-loads to the OAuth login.

    ``require_user`` raises 401 for anonymous requests. For a normal full-page
    GET (not an HTMX fragment or an API/JSON client) that should land the user
    on Google sign-in, not a bare 401 body. HTMX and non-HTML clients still get
    a plain 401 so they can handle it programmatically.
    """
    accept = request.headers.get("accept", "")
    is_page_load = (
        request.method == "GET"
        and "text/html" in accept
        and request.headers.get("hx-request") != "true"
    )
    if is_page_load:
        return RedirectResponse("/auth/login", status_code=302)
    return PlainTextResponse(getattr(exc, "detail", "Sign in required."), status_code=401)


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
