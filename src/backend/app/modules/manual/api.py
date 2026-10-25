"""Manual entries (ADR 0036): list, add, edit, delete, template download and upload."""

from __future__ import annotations

import tempfile
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, Response, UploadFile
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_session
from app.core.errors import AppError
from app.modules.imports.api import _read_uploads, _write
from app.modules.manual import service, template
from app.modules.manual.service import CHANNEL, EntryIn
from app.modules.plugins.contract import fingerprint
from app.modules.raw import service as raw
from app.modules.settings import service as settings_service
from app.modules.sources import service as sources

router = APIRouter(prefix="/api", tags=["manual"])
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _tz(db: Session) -> str:
    return settings_service.all_settings(db)["general.timezone"]


@router.get("/sources/{source_id}/manual")
def list_entries(source_id: int, db: Session = Depends(get_session)) -> dict:
    tz = _tz(db)
    return {"timezone": tz, "entries": service.entries(db, source_id, tz)}


@router.post("/sources/{source_id}/manual", status_code=201)
def add(source_id: int, body: EntryIn, db: Session = Depends(get_session)) -> dict:
    return service.add(db, source_id, body, _tz(db))


@router.put("/manual/{raw_id}")
def edit(raw_id: int, body: EntryIn, db: Session = Depends(get_session)) -> dict:
    return service.edit(db, raw_id, body, _tz(db))


@router.delete("/manual/{raw_id}", status_code=204)
def remove(raw_id: int, db: Session = Depends(get_session)) -> None:
    service.remove(db, raw_id)


@router.put("/raw/{raw_id}")
def change(raw_id: int, body: EntryIn, db: Session = Depends(get_session)) -> dict:
    """Edit a manual row or correct any other one (ADR 0037)."""
    return service.edit(db, raw_id, body, _tz(db))


@router.post("/raw/{raw_id}/hide", status_code=204)
def hide(raw_id: int, db: Session = Depends(get_session)) -> None:
    service.remove(db, raw_id)


@router.post("/raw/{raw_id}/restore", status_code=204)
def restore(raw_id: int, db: Session = Depends(get_session)) -> None:
    service.restore(db, raw_id)


@router.get("/raw/{raw_id}/history")
def history(raw_id: int, db: Session = Depends(get_session)) -> list[dict]:
    return service.history(db, raw_id, _tz(db))


@router.get("/manual/template")
def download_template(lang: str = "de", db: Session = Depends(get_session)) -> Response:
    lang = "de" if lang == "de" else "en"
    name = "owncryptofolio-vorlage.xlsx" if lang == "de" else "owncryptofolio-template.xlsx"
    return Response(
        template.write(lang, _tz(db)),
        media_type=XLSX,
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


def _upload(uploads: list[tuple[str, bytes]]) -> tuple[str, bytes]:
    if len(uploads) != 1:
        raise AppError("manual.template_one_file", 400)
    return uploads[0]


@router.post("/sources/{source_id}/manual/template/preview")
async def preview(
    source_id: int, file: UploadFile = File(...), db: Session = Depends(get_session)
) -> dict:
    source = sources.get(db, source_id)
    uploads = [_upload(await _read_uploads([file]))]
    tz = _tz(db)
    with tempfile.TemporaryDirectory() as tmp:  # writes nothing that stays
        path = _write(Path(tmp), uploads)
        movements, problems, rejected = await run_in_threadpool(template.read, path, tz)
    known = raw.existing_fingerprints(db, source.id, CHANNEL)
    key = raw.source_key(source, CHANNEL)
    duplicates = 0
    kinds: Counter[str] = Counter()
    for m in movements:
        fp = fingerprint(key, m)
        duplicates += fp in known
        known.add(fp)
        kinds[m.kind.value] += 1
    times = [m.timestamp for m in movements]
    return {
        "file": uploads[0][0],
        "read": len(movements) + rejected,
        "new": len(movements) - duplicates,
        "duplicates": duplicates,
        "rejected": rejected,
        "problems": problems[:20],
        "kinds": dict(sorted(kinds.items())),
        "data_from": min(times).isoformat() if times else None,
        "data_to": max(times).isoformat() if times else None,
    }


@router.post("/sources/{source_id}/manual/template")
async def import_template(
    source_id: int, file: UploadFile = File(...), db: Session = Depends(get_session)
) -> dict:
    source = sources.get(db, source_id)
    uploads = [_upload(await _read_uploads([file]))]
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")
    # The original stays, like every imported file (ADR 0014).
    folder = get_settings().data_dir / "originals" / str(source.id) / f"manual-{stamp}"
    try:
        path = _write(folder, uploads)
    except OSError as exc:
        raise AppError("imports.store_failed", 400) from exc
    movements, problems, rejected = await run_in_threadpool(template.read, path, _tz(db))
    stats = await run_in_threadpool(service.add_many, db, source, movements)
    return {**stats, "rejected": rejected, "problems": problems[:20]}
