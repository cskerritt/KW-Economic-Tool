"""Fixtures for the browser end-to-end suite.

These start a real uvicorn server (auth disabled, throwaway SQLite) and drive a
headless Chromium against it. Playwright is imported lazily inside fixtures so
that the default ``pytest`` run -- which deselects ``-m e2e`` -- never fails to
collect just because playwright isn't installed.

Run the e2e suite with:
    pip install -e ".[web,export,e2e]"
    playwright install chromium
    pytest -m e2e
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_healthy(base_url: str, timeout: float = 30.0) -> None:
    deadline = time.time() + timeout
    last_err: Exception | None = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{base_url}/healthz", timeout=2) as r:
                if r.status == 200:
                    return
        except Exception as e:  # noqa: BLE001 - polling until up
            last_err = e
            time.sleep(0.3)
    raise RuntimeError(f"server did not become healthy at {base_url}: {last_err}")


@pytest.fixture(scope="session")
def live_server(tmp_path_factory: pytest.TempPathFactory) -> str:
    """Start uvicorn in a subprocess and yield its base URL."""
    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"
    db_path = tmp_path_factory.mktemp("e2e_db") / "e2e.sqlite"

    env = dict(os.environ)
    env.setdefault("AUTH_DISABLED", "true")
    env.setdefault("SESSION_SECRET", "e2e-secret")
    env["DB_PATH"] = str(db_path)
    # Local convenience: many dev machines (e.g. Homebrew Python) lack a wired-in
    # CA bundle, which breaks the live FRED call. If certifi is available and the
    # caller hasn't set SSL_CERT_FILE, point at certifi so the FRED helper works.
    if "SSL_CERT_FILE" not in env:
        try:
            import certifi

            env["SSL_CERT_FILE"] = certifi.where()
        except Exception:  # noqa: BLE001 - optional convenience
            pass

    proc = subprocess.Popen(
        [
            sys.executable, "-m", "uvicorn", "app.main:app",
            "--host", "127.0.0.1", "--port", str(port), "--log-level", "warning",
        ],
        cwd=str(REPO_ROOT),
        env=env,
    )
    try:
        _wait_healthy(base_url)
        yield base_url
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


@pytest.fixture(scope="session")
def _browser():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        yield browser
        browser.close()


@pytest.fixture()
def page(_browser):
    """A fresh browser page (with downloads enabled) per test."""
    ctx = _browser.new_context(accept_downloads=True)
    pg = ctx.new_page()
    pg.set_default_timeout(20000)
    yield pg
    ctx.close()
