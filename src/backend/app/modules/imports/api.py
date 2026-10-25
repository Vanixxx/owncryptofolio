"""File import: preview (writes nothing) and import (keeps the originals, ADR 0014 level 3).

One import may consist of several files: MEXC exports twenty separate workbooks
that only make sense together (the time zone is stated in some, not in others).
A single file is handed to the reader as a file, several as a folder.
"""

from __future__ import annotations

import json
import re
import shutil
import tempfile
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_session
from app.core.errors import AppError
from app.modules.imports import mapped
from app.modules.imports.models import ImportMapping
from app.modules.plugins.contract import fingerprint
from app.modules.plugins.manifest import Channel
from app.modules.raw import service as raw
from app.modules.settings import service as settings_service
from app.modules.sources import service as sources

router = APIRouter(prefix="/api", tags=["imports"])
MAX_UPLOAD = 100 * 1024 * 1024  # all files of one import together
MAX_FILES = 50


def safe_name(name: str) -> str:
    """Only the last path component, no NUL, no dot-only names: a file name from
    the browser must never leave the target folder."""
    base = Path((name or "").replace("\x00", "")).name
    base = re.sub(r"[^\w.\- ]", "_", base).strip()
    return base if base.strip(".") else "upload"


async def _read_uploads(files: list[UploadFile]) -> list[tuple[str, bytes]]:
    if not files:
        raise AppError("imports.file_empty", 400)
    if len(files) > MAX_FILES:
        raise AppError("imports.too_many_files", 400, max=MAX_FILES)
    out: list[tuple[str, bytes]] = []
    total = 0
    used: set[str] = set()
    for upload in files:
        data = await upload.read(MAX_UPLOAD + 1)
        total += len(data)
        if total > MAX_UPLOAD:
            raise AppError("imports.file_too_large", 413, max_mb=MAX_UPLOAD // 1024 // 1024)
        if not data:
            raise AppError("imports.file_empty", 400)
        name = safe_name(upload.filename or "")
        while name in used:  # two uploads with the same name must not overwrite each other
            name = f"_{name}"
        used.add(name)
        out.append((name, data))
    return out


def _write(folder: Path, uploads: list[tuple[str, bytes]]) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    for name, data in uploads:
        (folder / name).write_bytes(data)
    return folder / uploads[0][0] if len(uploads) == 1 else folder


def _label(uploads: list[tuple[str, bytes]]) -> str:
    if len(uploads) == 1:
        return uploads[0][0]
    return f"{uploads[0][0]} (+{len(uploads) - 1})"


def _movements(plugin, path: Path, db: Session):
    options = {"timezone": settings_service.all_settings(db)["general.timezone"]}
    try:
        return list(plugin.module.read(path, options))
    except (ValueError, KeyError) as exc:
        # The reader rejects files it cannot read correctly instead of guessing.
        raise AppError("imports.unreadable", 400, reason=str(exc)[:200]) from exc


def _skipped(plugin, path: Path) -> dict[str, int]:
    fn = getattr(plugin.module, "skipped", None)
    try:
        return fn(path) if fn else {}
    except (ValueError, KeyError):
        return {}


@router.post("/imports/preview")
async def preview(
    source_id: int = Form(...),
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_session),
) -> dict:
    source = sources.get(db, source_id)
    plugin = sources.plugin_for(source, Channel.FILE)
    uploads = await _read_uploads(files)
    with tempfile.TemporaryDirectory() as tmp:  # outside the data dir, gone right after
        path = _write(Path(tmp), uploads)
        movements = await run_in_threadpool(_movements, plugin, path, db)
        skipped = _skipped(plugin, path)
    known = raw.existing_fingerprints(db, source.id, "file")
    overlap = raw.Overlap(db, [source.id])
    key = raw.source_key(source, "file")
    kinds: Counter[str] = Counter()
    duplicates = rejected = covered = 0
    problems: list[str] = []
    for m in movements:
        try:
            m.check()
        except ValueError as exc:
            rejected += 1
            problems.append(f"{m.timestamp.isoformat()} {m.kind.value}: {exc}")
            continue
        fp = fingerprint(key, m)
        if fp in known:
            duplicates += 1  # already imported, or twice in this upload (overlapping exports)
        known.add(fp)
        kinds[f"{m.market.value}:{m.kind.value}"] += 1
        covered += overlap.covered(
            source.id,
            m.market.value,
            "file",
            m.timestamp,
            [(m.incoming_asset, m.incoming_amount), (m.outgoing_asset, m.outgoing_amount)],
        )
    times = [m.timestamp for m in movements]
    return {
        "file": _label(uploads),
        "read": len(movements),
        "new": len(movements) - duplicates - rejected,
        "duplicates": duplicates,
        "rejected": rejected,
        "problems": problems[:20],
        "covered_by_api": covered,
        "kinds": dict(sorted(kinds.items())),
        "skipped": skipped,
        "data_from": min(times).isoformat() if times else None,
        "data_to": max(times).isoformat() if times else None,
    }


@router.post("/imports")
async def import_files(
    source_id: int = Form(...),
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_session),
) -> dict:
    source = sources.get(db, source_id)
    plugin = sources.plugin_for(source, Channel.FILE)
    uploads = await _read_uploads(files)
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")
    # Never overwrites an earlier upload (ADR 0001): one folder per import.
    folder = get_settings().data_dir / "originals" / str(source.id) / stamp
    try:
        path = _write(folder, uploads)
    except OSError as exc:
        raise AppError("imports.store_failed", 400) from exc
    try:
        movements = await run_in_threadpool(_movements, plugin, path, db)
        run = await run_in_threadpool(
            raw.import_movements, db, source, "file", _label(uploads), movements, str(path)
        )
    except Exception:
        # nothing was booked: the stored copy would only be an orphan (review 2026-10-24)
        shutil.rmtree(folder, ignore_errors=True)
        raise
    return sources.run_dict(run, True)


@router.delete("/import-runs/{run_id}")
def revert(run_id: int, db: Session = Depends(get_session)) -> dict:
    return raw.revert(db, run_id)


# --- own files with a column mapping (ADR 0048, M13 B) ------------------------------------

MAPPED_LABEL = "Eigene Datei"
# next to the original; `safe_name` never yields "@", so an upload cannot take this name and
# be overwritten by it (review 2026-10-24)
MAPPING_FILE = "mapping@owncryptofolio.json"


def _exchange(db: Session, source_id: int):
    source = sources.get(db, source_id)
    if source.kind != "exchange":
        raise AppError("imports.mapped_exchange_only", 400)
    return source


def _mapping(text: str, db: Session) -> mapped.Mapping:
    try:
        return mapped.Mapping.model_validate(json.loads(text))
    except ValueError as exc:
        raise AppError("imports.mapping_invalid", 400, reason=str(exc)[:200]) from exc


def _read_mapped(path: Path, m: mapped.Mapping) -> dict:
    try:
        return mapped.read(path, m)
    except mapped.Problem as exc:
        raise AppError("imports.mapped_unreadable", 400, reason=str(exc)) from exc


@router.post("/imports/mapped/inspect")
async def mapped_inspect(
    source_id: int = Form(...),
    file: UploadFile = File(...),
    sheet: str | None = Form(None),
    header_row: int | None = Form(None),
    delimiter: str | None = Form(None),
    db: Session = Depends(get_session),
) -> dict:
    """Columns, first rows and a mapping to start from (the saved one if it still fits)."""
    source = _exchange(db, source_id)
    uploads = await _read_uploads([file])
    saved = db.get(ImportMapping, source.id)
    tz = settings_service.all_settings(db)["general.timezone"]
    with tempfile.TemporaryDirectory() as tmp:
        path = _write(Path(tmp), uploads)
        try:
            return await run_in_threadpool(
                mapped.inspect,
                path,
                sheet,
                header_row,
                delimiter or None,
                saved.mapping if saved else None,
                tz,
            )
        except mapped.Problem as exc:
            raise AppError("imports.mapped_unreadable", 400, reason=str(exc)) from exc


def _side(mv, side: str) -> list:
    amount = getattr(mv, f"{side}_amount")
    return [getattr(mv, f"{side}_asset"), None if amount is None else str(amount)]


@router.post("/imports/mapped/preview")
async def mapped_preview(
    source_id: int = Form(...),
    file: UploadFile = File(...),
    mapping: str = Form(...),
    db: Session = Depends(get_session),
) -> dict:
    """The rows as they would be booked, problems with their row number. Writes nothing."""
    source = _exchange(db, source_id)
    m = _mapping(mapping, db)
    uploads = await _read_uploads([file])
    with tempfile.TemporaryDirectory() as tmp:
        path = _write(Path(tmp), uploads)
        result = await run_in_threadpool(_read_mapped, path, m)
    known = raw.existing_fingerprints(db, source.id, "file")
    key = raw.source_key(source, "file")
    duplicates = 0
    rows = []
    problems = list(result["problems"])
    for n, mv in result["movements"]:
        try:
            mv.check()
        except ValueError as exc:
            problems.append({"row": n, "message": str(exc)[:200]})
            continue
        fp = fingerprint(key, mv)
        dup = fp in known
        duplicates += dup
        known.add(fp)
        if len(rows) < 50:
            rows.append(
                {"row": n, "at": mv.timestamp.isoformat(), "kind": mv.kind.value, "duplicate": dup}
                | {side: _side(mv, side) for side in ("incoming", "outgoing", "fee")}
            )
    problems.sort(key=lambda x: x["row"])
    times = [mv.timestamp for _, mv in result["movements"]]
    return {
        "read": len(result["movements"]) + len(result["problems"]),
        "new": len(result["movements"]) - duplicates - (len(problems) - len(result["problems"])),
        "duplicates": duplicates,
        "skipped": result["skipped"],
        "rejected": len(problems),
        "problems": problems[:50],
        "rows": rows,
        "date_format": result["date_format"],
        "data_from": min(times).isoformat() if times else None,
        "data_to": max(times).isoformat() if times else None,
    }


@router.post("/imports/mapped")
async def mapped_import(
    source_id: int = Form(...),
    file: UploadFile = File(...),
    mapping: str = Form(...),
    db: Session = Depends(get_session),
) -> dict:
    """Keeps the file and its mapping side by side (ADR 0001), books the rows, keeps the
    mapping for the next file of this source."""
    source = _exchange(db, source_id)
    m = _mapping(mapping, db)
    uploads = await _read_uploads([file])
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")
    folder = get_settings().data_dir / "originals" / str(source.id) / stamp
    try:
        path = _write(folder, uploads)
        (folder / MAPPING_FILE).write_text(m.model_dump_json(indent=2))
    except OSError as exc:
        raise AppError("imports.store_failed", 400) from exc
    try:
        result = await run_in_threadpool(_read_mapped, path, m)
        movements = [mv for _, mv in result["movements"]]
        run = await run_in_threadpool(
            raw.import_movements,
            db,
            source,
            "file",
            f"{MAPPED_LABEL}: {_label(uploads)}",
            movements,
            str(path),
        )
    except Exception:
        shutil.rmtree(folder, ignore_errors=True)
        raise
    row = db.get(ImportMapping, source.id)
    if row is None:
        db.add(ImportMapping(source_id=source.id, mapping=m.model_dump(mode="json")))
    else:
        row.mapping = m.model_dump(mode="json")
    db.commit()
    return sources.run_dict(run, True) | {"problems_mapped": result["problems"][:50]}
