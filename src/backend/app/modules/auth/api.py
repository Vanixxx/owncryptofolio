import asyncio
import hmac
import logging

from fastapi import APIRouter, Depends, Request, Response
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.db import get_session
from app.core.errors import AppError
from app.modules.auth import service, sessions
from app.modules.auth.middleware import current_stamp, remember_stamp

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])


class CodeIn(BaseModel):
    code: str | None = None


class SetupIn(BaseModel):
    code: str | None = None
    password: str


class LoginIn(BaseModel):
    password: str


class PasswordChangeIn(BaseModel):
    current: str
    new: str


def _secure(request: Request) -> bool:
    # Behind a TLS-terminating proxy the scheme is http; trust the forwarded header.
    proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    return proto.split(",")[0].strip() == "https"


def _set_cookie(request: Request, response: Response, stamp: str) -> None:
    remember_stamp(request.app, stamp)
    response.set_cookie(
        sessions.COOKIE_NAME,
        sessions.issue(request.app.state.boot.keys.session_key, stamp),
        max_age=sessions.TTL_SECONDS,
        httponly=True,
        samesite="lax",
        secure=_secure(request),
    )


async def _fail(request: Request, code: str, status: int) -> AppError:
    await asyncio.sleep(request.app.state.failure_delay)
    return AppError(code, status)


# Wrong setup codes wait in line, one at a time, and from the tenth on ten times as long:
# parallel requests can no longer try the million codes in hours (review 2026-10-24).
_CODE_LOCK = asyncio.Lock()
SLOW_AFTER = 10


async def _check_code(request: Request, code: str | None) -> None:
    expected = request.app.state.boot.setup_code
    if expected is None:  # a brand-new install: no code needed
        return
    if hmac.compare_digest((code or "").strip().replace(" ", ""), expected):
        return
    async with _CODE_LOCK:
        failures = getattr(request.app.state, "setup_failures", 0) + 1
        request.app.state.setup_failures = failures
        log.warning("Wrong setup code (%d so far)", failures)
        delay = request.app.state.failure_delay * (10 if failures >= SLOW_AFTER else 1)
        await asyncio.sleep(delay)
    raise AppError("auth.setup_code_invalid", 400)


@router.get("/status")
async def status(request: Request) -> dict:
    token = request.cookies.get(sessions.COOKIE_NAME)
    stamp = await current_stamp(request.app) if request.app.state.setup_done else None
    return {
        "setup_required": not request.app.state.setup_done,
        "code_required": not request.app.state.setup_done
        and bool(request.app.state.boot.setup_code),
        "authenticated": sessions.is_valid(request.app.state.boot.keys.session_key, token, stamp),
    }


class SetupRestoreIn(BaseModel):
    code: str | None = None
    name: str
    key: str
    confirm: bool = False


@router.post("/setup/backups")
async def setup_backups(body: CodeIn, request: Request) -> list[dict]:
    """First start: the backups in the folder, to restore instead of starting empty."""
    from app.modules.backup import service as backup

    if request.app.state.setup_done:
        raise AppError("auth.already_set_up", 409)
    await _check_code(request, body.code)
    return backup.files()


@router.post("/setup/backup-upload")
async def setup_backup_upload(request: Request) -> dict:
    from app.modules.backup.api import store_upload

    if request.app.state.setup_done:
        raise AppError("auth.already_set_up", 409)
    # the code comes as a header: checked before the body is read, so nobody without it can
    # fill the disk with an upload (review 2026-10-24)
    await _check_code(request, request.headers.get("x-setup-code"))
    form = await request.form()
    return {"name": await store_upload(form.getlist("files"))}


@router.post("/setup/restore-inspect")
async def setup_restore_inspect(body: SetupRestoreIn, request: Request) -> dict:
    from fastapi.concurrency import run_in_threadpool

    from app.modules.backup import api as backup_api
    from app.modules.backup import service as backup

    if request.app.state.setup_done:
        raise AppError("auth.already_set_up", 409)
    await _check_code(request, body.code)
    path = backup_api._wrap(backup.path_of, body.name)
    return await run_in_threadpool(backup_api._wrap, backup.inspect, path, body.key)


@router.post("/setup/restore")
async def setup_restore(
    body: SetupRestoreIn, request: Request, db: Session = Depends(get_session)
) -> dict:
    """First start from a backup: the data, the password and the keys come back."""
    from fastapi.concurrency import run_in_threadpool

    from app.core.keys import get_keys
    from app.modules.backup import api as backup_api
    from app.modules.backup import service as backup

    if request.app.state.setup_done:
        raise AppError("auth.already_set_up", 409)
    await _check_code(request, body.code)
    if not body.confirm:
        raise AppError("backup.confirm_required", 400)
    path = backup_api._wrap(backup.path_of, body.name)
    out = await run_in_threadpool(backup_api._wrap, backup.restore_live, db, path, body.key, False)
    request.app.state.boot.keys = get_keys()
    from app.core.db import _session_factory

    with _session_factory()() as fresh:
        request.app.state.setup_done = service.is_set_up(fresh)
    return out


@router.post("/setup/verify", status_code=204)
async def verify_setup_code(body: CodeIn, request: Request) -> None:
    if request.app.state.setup_done:
        raise AppError("auth.already_set_up", 409)
    await _check_code(request, body.code)


@router.post("/setup")
async def setup(
    body: SetupIn, request: Request, response: Response, db: Session = Depends(get_session)
) -> dict:
    if request.app.state.setup_done or service.is_set_up(db):
        raise AppError("auth.already_set_up", 409)
    await _check_code(request, body.code)
    await run_in_threadpool(service.set_password, db, body.password)
    request.app.state.setup_done = True
    _set_cookie(request, response, service.password_stamp(db))
    return {"backup_key": request.app.state.boot.keys.backup_key}


@router.post("/login", status_code=204)
async def login(
    body: LoginIn, request: Request, response: Response, db: Session = Depends(get_session)
) -> None:
    if not request.app.state.setup_done:
        raise AppError("auth.setup_required", 409)
    # scrypt costs tens of milliseconds: off the event loop, the rest keeps answering
    if not await run_in_threadpool(service.password_matches, db, body.password):
        raise await _fail(request, "auth.invalid_password", 401)
    _set_cookie(request, response, service.password_stamp(db))


@router.post("/logout", status_code=204)
def logout(response: Response) -> None:
    response.delete_cookie(sessions.COOKIE_NAME)


@router.post("/password", status_code=204)
async def change_password(
    body: PasswordChangeIn,
    request: Request,
    response: Response,
    db: Session = Depends(get_session),
) -> None:
    if not await run_in_threadpool(service.password_matches, db, body.current):
        raise await _fail(request, "auth.invalid_password", 400)
    await run_in_threadpool(service.set_password, db, body.new)
    # every other session ends with the old password; this one goes on with the new
    _set_cookie(request, response, service.password_stamp(db))
