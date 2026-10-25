"""Backup (ADR 0014, ADR 0018): three levels, and the restore is tested every time.

Level 1: `pg_dump -Fc`, encrypted with the backup key.
Level 2: portable raw-data export (JSON Lines, gzip, encrypted): one line per raw
         row with its source described in words, amounts as strings (never float).
Level 3: the original upload files, kept in <data>/originals (imports module).

**A restore that was never tested is no backup.** Every run restores the dump
into a throw-away database and compares the set of raw fingerprints with the
original — not just row counts, which match even when values are corrupted.
"""

from __future__ import annotations

import gzip
import json
import logging
import os
import re
import secrets
import subprocess
import tempfile
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.keys import get_keys
from app.modules.backup.models import BackupRun
from app.modules.raw.models import ImportRun, RawRetraction, RawTransaction
from app.modules.sources.models import Source

log = logging.getLogger(__name__)
DUMP_SUFFIX = ".dump.enc"
EXPORT_SUFFIX = ".raw.jsonl.gz.enc"
KEYS_SUFFIX = ".keys.enc"
"""The other two keys, encrypted with the backup key (Vanixxx, 2026-10-21): the backup key alone
then brings everything back, the stored exchange credentials included."""


class BackupError(RuntimeError):
    pass


def backup_dir() -> Path:
    """BACKUP_DIR (the image sets /backups, which the user mounts); else inside the data folder."""
    return get_settings().backup_dir or get_settings().data_dir / "backups"


def unmounted() -> bool:
    """In the container, a backup folder that is no mount lives inside the container itself:
    gone when the container is created anew (Vanixxx, 2026-10-23)."""
    folder = backup_dir()
    return (
        get_settings().app_env == "production"
        and str(folder) == "/backups"
        and not os.path.ismount(folder)
    )


def _url() -> URL:
    return make_url(get_settings().database_url).set(drivername="postgresql")


def _tool(args: list[str], url: URL, stdin: bytes | None = None) -> bytes:
    env = dict(os.environ)
    if url.password:
        env["PGPASSWORD"] = url.password  # environment, never the command line
    conn = ["-h", url.host or "localhost", "-p", str(url.port or 5432), "-U", url.username or ""]
    res = subprocess.run(
        [args[0], *conn, *args[1:]], input=stdin, capture_output=True, env=env, check=False
    )
    if res.returncode != 0:
        raise BackupError(f"{args[0]} failed: {res.stderr.decode(errors='replace').strip()[:300]}")
    return res.stdout


def _fernet(key: str | None = None) -> Fernet:
    try:
        return Fernet(key or get_keys().backup_key)
    except (ValueError, TypeError) as exc:
        raise BackupError("backup.key_malformed") from exc


# --- level 1 ---------------------------------------------------------------


def write_dump(target: Path) -> tuple[int, set[tuple]]:
    """The dump and the fingerprints it holds, both from one snapshot: a fetch writing in
    between no longer fails the probe (review 2026-10-24)."""
    url = _url()
    engine = create_engine(url.set(drivername="postgresql+psycopg"))
    try:
        with engine.connect() as c:
            c.execution_options(isolation_level="REPEATABLE READ")
            with c.begin():
                snapshot = c.execute(text("SELECT pg_export_snapshot()")).scalar_one()
                data = _tool(["pg_dump", "-Fc", f"--snapshot={snapshot}", url.database or ""], url)
                held = set(c.execute(text(FINGERPRINTS)).all())
    finally:
        engine.dispose()
    target.write_bytes(_fernet().encrypt(data))
    return target.stat().st_size, held


def decrypt(path: Path, key: str | None = None) -> bytes:
    try:
        return _fernet(key).decrypt(path.read_bytes())
    except InvalidToken as exc:
        raise BackupError(f"{path.name} cannot be opened with this backup key") from exc


def write_keys(target: Path) -> None:
    k = get_keys()
    body = json.dumps({"credentials_key": k.credentials_key, "session_key": k.session_key})
    target.write_bytes(_fernet().encrypt(body.encode()))


def keys_file(dump: Path) -> Path:
    return dump.with_name(dump.name.removesuffix(DUMP_SUFFIX) + KEYS_SUFFIX)


def restore(path: Path, database: str, replace: bool = False, key: str | None = None) -> None:
    """Restores a dump into `database`. The target is mandatory on purpose: a
    restore that hits the running database by accident is the damage a backup
    exists to prevent."""
    url = _url()
    if replace:
        _tool(
            [
                "psql",
                "-d",
                "postgres",
                "-v",
                "ON_ERROR_STOP=1",
                "-c",
                f'DROP DATABASE IF EXISTS "{database}" WITH (FORCE)',
            ],
            url,
        )
    _tool(
        [
            "psql",
            "-d",
            "postgres",
            "-v",
            "ON_ERROR_STOP=1",
            "-c",
            f"CREATE DATABASE \"{database}\" ENCODING 'UTF8' TEMPLATE template0",
        ],
        url,
    )
    data = decrypt(path, key)
    with tempfile.TemporaryDirectory() as tmp:
        dump, listing = Path(tmp) / "restore.dump", Path(tmp) / "restore.list"
        dump.write_bytes(data)
        # only what the app's own dumps hold: tables, data, sequences, defaults, indexes and
        # keys. Anything else in a foreign file (functions, triggers, extensions …) would run
        # as SQL with the app's database role; it is left out (review 2026-10-24).
        entries = _tool(["pg_restore", "-l", str(dump)], url).decode(errors="replace")
        listing.write_text("\n".join(line for line in entries.splitlines() if _allowed(line)))
        _tool(
            ["pg_restore", "-d", database, "--no-owner", "--no-privileges", "-L", str(listing)]
            + [str(dump)],
            url,
        )


ALLOWED = (
    "TABLE DATA",
    "TABLE",
    "SEQUENCE SET",
    "SEQUENCE OWNED BY",
    "SEQUENCE",
    "DEFAULT",
    "INDEX",
    "FK CONSTRAINT",
    "CONSTRAINT",
)
_ENTRY = re.compile(r"^\d+; \d+ \d+ (.*)$")


def _allowed(line: str) -> bool:
    m = _ENTRY.match(line)
    return bool(m) and any(m.group(1).startswith(kind + " ") for kind in ALLOWED)


FINGERPRINTS = "SELECT source_id, channel, fingerprint FROM raw_transaction"


def _scratch(base: str | None, what: str) -> str:
    """A throw-away database of its own: two at once (two tabs) do not drop each other."""
    return f"{base}_{what}_{secrets.token_hex(3)}"


def _fingerprints(url: URL) -> set[tuple]:
    engine = create_engine(url.set(drivername="postgresql+psycopg"))
    try:
        with engine.connect() as c:
            return set(c.execute(text(FINGERPRINTS)).all())
    finally:
        engine.dispose()


def probe(path: Path, original: set[tuple] | None = None) -> int:
    """Restores into a throw-away database, compares with what the dump held (or the live
    rows), always cleans up."""
    url = _url()
    name = _scratch(url.database, "probe")
    try:
        restore(path, name, replace=True)
        if original is None:
            original = _fingerprints(url)
        restored = _fingerprints(url.set(database=name))
        if original != restored:
            raise BackupError(
                f"probe mismatch: {len(original - restored)} missing, "
                f"{len(restored - original)} extra"
            )
        return len(original)
    finally:
        _tool(
            ["psql", "-d", "postgres", "-c", f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'], url
        )


# --- level 2 ---------------------------------------------------------------


def _plain(v: Any) -> Any:
    if isinstance(v, Decimal):
        return format(v, "f")
    if isinstance(v, datetime):
        return v.isoformat()
    return v


EXPORT_FIELDS = (
    "channel",
    "timestamp",
    "kind",
    "income_kind",
    "market",
    "incoming_asset",
    "incoming_amount",
    "outgoing_asset",
    "outgoing_amount",
    "fee_asset",
    "fee_amount",
    "external_id",
    "fingerprint",
    "comment",
    "counterparty",
    "instrument",
    "raw",
    "imported_at",
)


def write_export(session: Session, target: Path) -> int:
    """The source is described by provider/label/address, not by its id: ids
    belong to this database, the export must survive a different one."""
    sources = {s.id: s for s in session.scalars(select(Source))}
    runs = {r.id: r.label for r in session.scalars(select(ImportRun))}
    retracted = {r.raw_id: r.replaced_by_id for r in session.scalars(select(RawRetraction))}
    fingerprints = dict(
        session.execute(select(RawTransaction.id, RawTransaction.fingerprint)).all()
    )
    lines = []
    for row in session.scalars(select(RawTransaction).order_by(RawTransaction.id)).yield_per(500):
        s = sources[row.source_id]
        rec = {
            "source": {"provider": s.provider, "label": s.label, "address": s.address},
            "import_run": runs.get(row.import_run_id),
        }
        rec.update({f: _plain(getattr(row, f)) for f in EXPORT_FIELDS})
        if row.id in retracted:  # kept, but no longer counts (ADR 0036)
            rec["retracted"] = {"replaced_by_fingerprint": fingerprints.get(retracted[row.id])}
        lines.append(json.dumps(rec, ensure_ascii=False))
    payload = gzip.compress(("\n".join(lines) + "\n").encode())
    target.write_bytes(_fernet().encrypt(payload))
    return len(lines)


def read_export(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in gzip.decompress(decrypt(path)).decode().splitlines()
        if line.strip()
    ]


# --- run + retention ---------------------------------------------------------


def run_backup(
    session: Session, trigger: str = "manual", with_probe: bool = True, retention: bool = True
) -> BackupRun:
    folder = backup_dir()
    folder.mkdir(parents=True, exist_ok=True)
    # A scheduled slot is reserved as a 'queued' row; the job takes it over.
    run = session.scalars(
        select(BackupRun).where(BackupRun.status == "queued").order_by(BackupRun.id).limit(1)
    ).first()
    if run is None:
        run = BackupRun(trigger=trigger)
        session.add(run)
    run.status, run.started_at = "running", datetime.now(UTC)
    session.commit()
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    db = _url().database
    # never the name of an existing backup: two runs in one second (a backup right before a
    # restore) must not overwrite the one about to be restored
    base, n = f"{db}-{stamp}", 1
    while (folder / f"{base}{DUMP_SUFFIX}").exists():
        n += 1
        base = f"{db}-{stamp}-{n}"
    dump, export = folder / f"{base}{DUMP_SUFFIX}", folder / f"{base}{EXPORT_SUFFIX}"
    try:
        size, held = write_dump(dump)
        write_keys(keys_file(dump))
        run.dump_file = dump.name
        run.rows = write_export(session, export)
        run.export_file = export.name
        run.size_bytes = size + export.stat().st_size
        if with_probe:
            probe(dump, held)
            run.probe_ok = True
        run.status = "done"
    except Exception as exc:
        session.rollback()
        run.status, run.message = "failed", str(exc)[:500]
        if with_probe and run.dump_file:
            run.probe_ok = False
        log.error("Backup %s failed: %s", run.id, exc)
    run.finished_at = datetime.now(UTC)
    session.commit()
    if run.status == "done" and retention:
        apply_retention(session)
    return run


def keep_ids(runs: list[BackupRun], keep_daily: int, keep_monthly: int) -> set[int]:
    """Newest successful run per day for `keep_daily` days, plus the newest per
    month for `keep_monthly` months. Pure, so it is easy to test."""
    done = sorted(
        (r for r in runs if r.status == "done" and not r.deleted),
        key=lambda r: r.started_at,
        reverse=True,
    )
    days: dict[date, int] = {}
    months: dict[tuple[int, int], int] = {}
    for r in done:
        d = r.started_at.date()
        if d not in days and len(days) < keep_daily:
            days[d] = r.id
        m = (d.year, d.month)
        if m not in months and len(months) < keep_monthly:
            months[m] = r.id
    return set(days.values()) | set(months.values())


def apply_retention(session: Session) -> int:
    from app.modules.settings import service as settings

    s = settings.all_settings(session)
    runs = list(session.scalars(select(BackupRun)))
    keep = keep_ids(runs, s["backup.keep_daily"], s["backup.keep_monthly"])
    removed = 0
    for r in runs:
        # the state before a restore is the only way back: never removed by itself
        if r.status != "done" or r.deleted or r.id in keep or r.trigger == "before_restore":
            continue
        for name in (r.dump_file, r.export_file):
            if name:
                (backup_dir() / name).unlink(missing_ok=True)
        if r.dump_file:
            keys_file(backup_dir() / r.dump_file).unlink(missing_ok=True)
        r.deleted = True
        removed += 1
    session.commit()
    return removed


def run_dict(r: BackupRun) -> dict[str, Any]:
    return {
        "id": r.id,
        "trigger": r.trigger,
        "status": r.status,
        "probe_ok": r.probe_ok,
        "rows": r.rows,
        "size_bytes": r.size_bytes,
        "message": r.message,
        "dump_file": r.dump_file,
        "export_file": r.export_file,
        "deleted": r.deleted,
        "started_at": r.started_at.isoformat() if r.started_at else None,
        "finished_at": r.finished_at.isoformat() if r.finished_at else None,
    }


# --- restoring from the web page (Vanixxx, 2026-10-21) ------------------------------------


def files() -> list[dict]:
    """The backups in the folder, newest first: what one can restore."""
    folder = backup_dir()
    if not folder.is_dir():
        return []
    out = []
    for f in sorted(folder.glob(f"*{DUMP_SUFFIX}"), key=lambda p: p.stat().st_mtime, reverse=True):
        st = f.stat()
        out.append(
            {
                "name": f.name,
                "size": st.st_size,
                "at": datetime.fromtimestamp(st.st_mtime, UTC).isoformat(),
                "keys": keys_file(f).exists(),
            }
        )
    return out


def path_of(name: str) -> Path:
    """A backup of the folder by its name — never a path from elsewhere."""
    if "/" in name or "\\" in name or not name.endswith(DUMP_SUFFIX):
        raise BackupError("backup.file_unknown")
    path = backup_dir() / name
    if not path.is_file():
        raise BackupError("backup.file_unknown")
    return path


def inspect(path: Path, key: str | None = None) -> dict:
    """What a backup holds, read from a throw-away copy: rows, sources, period."""
    decrypt(path, key)  # a wrong key says so before anything is created
    url = _url()
    name = _scratch(url.database, "inspect")
    try:
        restore(path, name, replace=True, key=key)
        engine = create_engine(url.set(database=name, drivername="postgresql+psycopg"))
        try:
            with engine.connect() as c:
                one = lambda q: c.execute(text(q)).one()  # noqa: E731
                rows, first, last = one(
                    "SELECT count(*), min(timestamp), max(timestamp) FROM raw_transaction"
                )
                sources = one("SELECT count(*) FROM source")[0]
                login = one("SELECT count(*) FROM auth_credential")[0] > 0
        finally:
            engine.dispose()
    finally:
        _tool(
            ["psql", "-d", "postgres", "-c", f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'], url
        )
    return {
        "file": path.name,
        "rows": rows,
        "sources": sources,
        "first": first.isoformat() if first else None,
        "last": last.isoformat() if last else None,
        "login": login,
        "keys": keys_file(path).exists(),
    }


def restore_live(session: Session, path: Path, key: str | None, safety: bool = True) -> dict:
    """Replace the running database with a backup. First a backup of the current state (the
    only way back), then the restore, the schema brought up to date and the keys from the
    backup put in place."""
    from app.bootstrap.keys import Keys, load_or_create_keys, save_keys
    from app.bootstrap.migrate import upgrade
    from app.core.db import get_engine
    from app.core.keys import set_keys

    decrypt(path, key)  # wrong key: stop before anything changes
    kf = keys_file(path)
    # the keys file too: a mismatch must stop here, not after the data was replaced
    other = json.loads(decrypt(kf, key)) if kf.exists() else None
    saved = None
    if safety:
        # no clean-up here: it would delete today's backup that is about to be restored
        run = run_backup(session, "before_restore", with_probe=True, retention=False)
        if run.status != "done":
            raise BackupError("backup.safety_failed")
        saved = run_dict(run)
    session.close()
    get_engine().dispose()
    settings = get_settings()
    url = _url()
    live = url.database or ""
    # into a database of its own first: a dump that does not restore leaves the running one
    # untouched; then the two swap names in a moment (review 2026-10-24)
    staging = _scratch(live, "restore")
    try:
        restore(path, staging, replace=True, key=key)
    except Exception:
        _drop(url, staging)
        raise
    try:
        _swap(url, live, staging)
    except _InPlace:
        restore(path, live, replace=True, key=key)
    upgrade(settings.database_url)

    restored_keys = False
    current = get_keys()
    if other is not None:
        new = Keys(
            credentials_key=other["credentials_key"],
            session_key=other["session_key"],
            backup_key=key or current.backup_key,
            sources=current.sources,
        )
        save_keys(settings.data_dir, new)
        set_keys(load_or_create_keys(settings.data_dir, _overrides(settings)))
        restored_keys = True
        if saved and new.backup_key != current.backup_key:
            # the backup of the state before was locked with the old key, which is gone now:
            # locked again with the new one, so the way back stays open (review 2026-10-24)
            _relock(saved, current.backup_key, new.backup_key)
    log.warning("Restored %s into the running database (keys %s)", path.name,
                "restored" if restored_keys else "kept")  # fmt: skip

    # the backup of the state before is not in the restored database: register it
    if saved:
        from app.core.db import _session_factory

        with _session_factory()() as db:
            db.add(
                BackupRun(
                    trigger="before_restore", status="done", dump_file=saved["dump_file"],
                    export_file=saved["export_file"], rows=saved["rows"],
                    size_bytes=saved["size_bytes"], probe_ok=saved["probe_ok"],
                    started_at=datetime.fromisoformat(saved["started_at"]),
                    finished_at=datetime.now(UTC),
                )
            )  # fmt: skip
            db.commit()
    return {
        "file": path.name,
        "keys_restored": restored_keys,
        "safety": saved["dump_file"] if saved else None,
    }


def _drop(url: URL, name: str) -> None:
    _tool(["psql", "-d", "postgres", "-c", f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'], url)


def _sql(url: URL, statement: str) -> None:
    _tool(["psql", "-d", "postgres", "-v", "ON_ERROR_STOP=1", "-c", statement], url)


def _swap(url: URL, live: str, staging: str) -> None:
    """The restored copy takes the running database's name. Where the role may not rename
    (not the owner), the copy is proven good and the running one is replaced as before."""
    old = _scratch(live, "old")
    try:
        _sql(url, f'ALTER DATABASE "{live}" ALLOW_CONNECTIONS false')
    except BackupError:
        log.warning("Cannot rename databases here: restoring in place")
        _drop(url, staging)
        raise _InPlace() from None
    try:
        _sql(
            url,
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            f"WHERE datname = '{live}' AND pid <> pg_backend_pid()",
        )
        _sql(url, f'ALTER DATABASE "{live}" RENAME TO "{old}"')
    except BackupError:
        _sql(url, f'ALTER DATABASE "{live}" ALLOW_CONNECTIONS true')
        raise
    try:
        _sql(url, f'ALTER DATABASE "{staging}" RENAME TO "{live}"')
    except BackupError:
        _sql(url, f'ALTER DATABASE "{old}" RENAME TO "{live}"')
        _sql(url, f'ALTER DATABASE "{live}" ALLOW_CONNECTIONS true')
        raise
    _drop(url, old)


class _InPlace(Exception):
    """Renaming is not allowed: restore straight into the running database."""


def _relock(saved: dict, old_key: str, new_key: str) -> None:
    folder = backup_dir()
    dump = folder / saved["dump_file"]
    for f in (dump, folder / saved["export_file"], keys_file(dump)):
        if f.exists():
            f.write_bytes(Fernet(new_key).encrypt(Fernet(old_key).decrypt(f.read_bytes())))


def _overrides(settings) -> dict:
    return {n: getattr(settings, n) for n in ("credentials_key", "session_key", "backup_key")}
