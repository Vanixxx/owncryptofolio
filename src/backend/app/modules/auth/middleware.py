"""One guard over every API path instead of a dependency per endpoint (ADR 0023).

A new endpoint is protected without anyone remembering to protect it.
"""

import time

from fastapi import FastAPI, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from app.core.errors import error_body
from app.modules.auth import sessions

STAMP_TTL = 15  # seconds: a password reset on the command line ends old sessions this soon


def _read_stamp() -> str | None:
    from app.core.db import _session_factory
    from app.modules.auth import service

    with _session_factory()() as session:
        return service.password_stamp(session)


async def current_stamp(app) -> str | None:
    """The password stamp, read at most every few seconds (the web change sets it at once)."""
    cached = getattr(app.state, "password_stamp", None)
    if cached is None or time.monotonic() - cached[1] > STAMP_TTL:
        cached = (await run_in_threadpool(_read_stamp), time.monotonic())
        app.state.password_stamp = cached
    return cached[0]


def remember_stamp(app, value: str | None) -> None:
    app.state.password_stamp = (value, time.monotonic())


OPEN_PATHS = {
    "/api/health",
    "/api/auth/status",
    "/api/auth/setup",
    "/api/auth/setup/verify",
    "/api/auth/setup/backups",
    "/api/auth/setup/backup-upload",
    "/api/auth/setup/restore-inspect",
    "/api/auth/setup/restore",
    "/api/auth/login",
    "/api/auth/logout",
}
PROTECTED_PREFIXES = ("/api", "/docs", "/redoc", "/openapi.json")


def install_auth_guard(app: FastAPI) -> None:
    @app.middleware("http")
    async def guard(request: Request, call_next):
        path = request.url.path
        # no database yet (after a power cut it may come up later): every API answer says
        # so, the page shows it and keeps asking (Vanixxx, 2026-10-15)
        if path.startswith("/api") and path != "/api/health" and not request.app.state.ready:
            return JSONResponse(error_body("db.unavailable"), status_code=503)
        # /api/v1 checks its own token (ADR 0050), not the web login
        api = path == "/api/v1" or path.startswith("/api/v1/")
        if path.startswith(PROTECTED_PREFIXES) and path not in OPEN_PATHS and not api:
            if not request.app.state.setup_done:
                return JSONResponse(error_body("auth.setup_required"), status_code=401)
            token = request.cookies.get(sessions.COOKIE_NAME)
            stamp = await current_stamp(request.app)
            if not sessions.is_valid(request.app.state.boot.keys.session_key, token, stamp):
                return JSONResponse(error_body("auth.required"), status_code=401)
        return await call_next(request)
