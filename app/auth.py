"""Single-user authentication via Google OAuth, restricted by email allow-list.

Flow:
    /auth/login     redirect to Google
    /auth/callback  validate token, check email against ALLOWED_EMAILS, set session
    /auth/logout    clear session

Protect routes by depending on ``require_user``. When AUTH_DISABLED=true the
dependency returns DEV_USER_EMAIL so the app is usable locally before OAuth is
configured. Do not set AUTH_DISABLED in production.
"""

from __future__ import annotations

from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse

from app.config import settings

oauth = OAuth()
if settings.google_client_id and settings.google_client_secret:
    oauth.register(
        name="google",
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        server_metadata_url=(
            "https://accounts.google.com/.well-known/openid-configuration"
        ),
        client_kwargs={"scope": "openid email profile"},
    )

router = APIRouter(prefix="/auth", tags=["auth"])


def current_user(request: Request) -> str | None:
    """Return the signed-in user's email, or None."""
    if settings.auth_disabled:
        return settings.dev_user_email
    user = request.session.get("user")
    return user.get("email") if user else None


def require_user(request: Request) -> str:
    """FastAPI dependency: enforce a signed-in, allow-listed user."""
    email = current_user(request)
    if not email or not settings.is_allowed(email):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sign in required.",
            headers={"Location": "/auth/login"},
        )
    return email


@router.get("/login")
async def login(request: Request):
    if settings.auth_disabled:
        return RedirectResponse("/")
    if "google" not in [c.name for c in oauth._clients.values()]:
        raise HTTPException(
            status_code=500,
            detail="Google OAuth is not configured. Set GOOGLE_CLIENT_ID/SECRET "
            "or AUTH_DISABLED=true for local development.",
        )
    redirect_uri = request.url_for("auth_callback")
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/callback", name="auth_callback")
async def callback(request: Request):
    token = await oauth.google.authorize_access_token(request)
    userinfo = token.get("userinfo") or {}
    email = (userinfo.get("email") or "").lower()
    if not email or not userinfo.get("email_verified"):
        raise HTTPException(status_code=403, detail="Email not verified.")
    if not settings.is_allowed(email):
        raise HTTPException(status_code=403, detail="This account is not authorized.")
    request.session["user"] = {"email": email, "name": userinfo.get("name", "")}
    return RedirectResponse("/")


@router.get("/logout")
async def logout(request: Request):
    request.session.pop("user", None)
    return RedirectResponse("/")
