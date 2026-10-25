import secrets
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_session
from app.core.errors import AppError
from app.modules.backup import service
from app.modules.backup.models import BackupRun

router = APIRouter(prefix="/api/backups", tags=["backup"])
MAX_UPLOAD = 2 * 1024**3


@router.get("")
def list_backups(db: Session = Depends(get_session)) -> dict:
    runs = db.scalars(
        select(BackupRun)
        .where(BackupRun.status != "queued")
        .order_by(BackupRun.id.desc())
        .limit(60)
    )
    return {
        "folder": str(service.backup_dir()),
        "unmounted": service.unmounted(),
        "runs": [service.run_dict(r) for r in runs],
    }


# --- restore (Vanixxx, 2026-10-21) -------------------------------------------------------


class RestoreIn(BaseModel):
    name: str
    key: str | None = None  # empty: this installation's key
    confirm: bool = False


def _wrap(fn, *args):
    try:
        return fn(*args)
    except service.BackupError as exc:
        msg = str(exc)
        code = (
            msg
            if msg.startswith("backup.")
            else "backup.key_wrong"
            if "cannot be opened" in msg
            else "backup.restore_failed"
        )
        raise AppError(code, 400, reason=msg[:200]) from exc


async def store_upload(files: list[UploadFile]) -> str:
    """A backup from elsewhere (and its keys file) into the backup folder; returns its name.
    Streamed to disk in pieces, under a name no other upload gets, and only put in place when
    every file arrived whole (review 2026-10-24)."""
    folder = service.backup_dir()
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    dumps = [f for f in files if (f.filename or "").endswith(service.DUMP_SUFFIX)]
    if len(dumps) != 1:
        raise AppError("backup.upload_one_dump", 400)
    base = f"upload-{stamp}-{secrets.token_hex(3)}"
    written: list[tuple[Path, Path]] = []
    try:
        for f in files:
            name = f.filename or ""
            suffix = next(
                (x for x in (service.DUMP_SUFFIX, service.KEYS_SUFFIX) if name.endswith(x)), None
            )
            if suffix is None:
                continue
            target = folder / f"{base}{suffix}"
            part = target.with_name(target.name + ".part")
            written.append((part, target))
            size = 0
            with part.open("wb") as out:
                while chunk := await f.read(1024 * 1024):
                    size += len(chunk)
                    if size > MAX_UPLOAD:
                        raise AppError("imports.file_too_large", 413, max_mb=MAX_UPLOAD // 1024**2)
                    out.write(chunk)
        for part, target in written:
            part.replace(target)
    except BaseException:
        for part, _ in written:
            part.unlink(missing_ok=True)
        raise
    return f"{base}{service.DUMP_SUFFIX}"


@router.get("/files")
def files() -> list[dict]:
    """Backups in the folder that can be restored."""
    return service.files()


@router.post("/upload")
async def upload(files: list[UploadFile] = File(...)) -> dict:
    return {"name": await store_upload(files)}


@router.post("/inspect")
async def inspect(body: RestoreIn) -> dict:
    """What a backup holds — read from a throw-away copy, nothing changes."""
    path = _wrap(service.path_of, body.name)
    return await run_in_threadpool(_wrap, service.inspect, path, body.key or None)


@router.post("/restore")
async def restore(body: RestoreIn, request: Request, db: Session = Depends(get_session)) -> dict:
    """Overwrite all data with the backup. A backup of the current state is made first."""
    if not body.confirm:
        raise AppError("backup.confirm_required", 400)
    path = _wrap(service.path_of, body.name)
    request.app.state.ready = False  # other requests wait ("no database") meanwhile
    try:
        out = await run_in_threadpool(_wrap, service.restore_live, db, path, body.key or None)
    finally:
        request.app.state.ready = True
    from app.core.keys import get_keys

    request.app.state.boot.keys = get_keys()
    return out
