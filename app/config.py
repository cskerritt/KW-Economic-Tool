"""Application configuration, read from environment variables.

Kept dependency-free (plain os.getenv) so the engine stays light. Set these in
Railway secrets or a local .env loaded by your shell.

Required for real auth:
    SESSION_SECRET          random long string, signs the session cookie
    GOOGLE_CLIENT_ID        OAuth client id
    GOOGLE_CLIENT_SECRET    OAuth client secret
    ALLOWED_EMAILS          comma-separated allow-list (single user by default)

Local development without OAuth:
    AUTH_DISABLED=true      bypass Google sign-in and act as DEV_USER_EMAIL
    DEV_USER_EMAIL          email to act as when auth is disabled
"""

from __future__ import annotations

import os
from dataclasses import dataclass


def _bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes"}


@dataclass(frozen=True)
class Settings:
    session_secret: str = os.getenv("SESSION_SECRET", "dev-insecure-change-me")
    # SQLite file. On Railway, point this at a mounted volume, e.g.
    # /data/forensic_calc.sqlite, so saved cases survive redeploys.
    db_path: str = os.getenv("DB_PATH", "forensic_calc.sqlite")
    google_client_id: str = os.getenv("GOOGLE_CLIENT_ID", "")
    google_client_secret: str = os.getenv("GOOGLE_CLIENT_SECRET", "")
    allowed_emails: tuple[str, ...] = tuple(
        e.strip().lower()
        for e in os.getenv(
            "ALLOWED_EMAILS", "christophertskerritt@gmail.com"
        ).split(",")
        if e.strip()
    )
    auth_disabled: bool = _bool("AUTH_DISABLED", False)
    dev_user_email: str = os.getenv(
        "DEV_USER_EMAIL", "christophertskerritt@gmail.com"
    )
    # Branding for the PDF report header/signature block. Override per firm.
    report_firm: str = os.getenv("REPORT_FIRM", "Forensic Economic Analysis")
    report_author: str = os.getenv("REPORT_AUTHOR", "")
    # Send the session cookie only over HTTPS. Set COOKIE_SECURE=true in
    # production (Railway serves HTTPS); leave false for local http dev.
    secure_cookies: bool = _bool("COOKIE_SECURE", False)

    def is_allowed(self, email: str) -> bool:
        return email.strip().lower() in self.allowed_emails


settings = Settings()
