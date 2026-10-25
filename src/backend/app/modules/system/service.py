"""Operations at a glance for the system page (M8, 2026-10-12): do backups, fetches and
price runs happen, are the backup tools there, is there room on the disk."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from datetime import UTC, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.modules.backup.models import BackupRun
from app.modules.backup.service import backup_dir
from app.modules.jobs.models import Job
from app.modules.prices.models import PriceLatest
from app.modules.settings import service as settings_service


def next_slot(at: str, tz: str, now: datetime) -> datetime:
    """The next time a daily "HH:MM" comes round in the given zone."""
    local = now.astimezone(ZoneInfo(tz))
    hh, mm = (int(x) for x in at.split(":"))
    slot = datetime.combine(local.date(), time(hh, mm), tzinfo=ZoneInfo(tz))
    return slot if slot > local else slot + timedelta(days=1)


def _iso(d: datetime | None) -> str | None:
    return d.isoformat() if d else None


def _jobs(session: Session, kind: str) -> dict:
    last = session.scalar(
        select(Job).where(Job.kind == kind).order_by(Job.created_at.desc()).limit(1)
    )
    failed = 0
    if last is not None:
        # a fetch round is one job per source, queued together
        failed = session.scalar(
            select(func.count())
            .select_from(Job)
            .where(
                Job.kind == kind,
                Job.status == "failed",
                Job.created_at >= last.created_at - timedelta(minutes=5),
            )
        )
    return {
        "last_at": _iso(last.finished_at or last.started_at or last.created_at) if last else None,
        "status": last.status if last else None,
        "failed": failed or 0,
    }


def _tools(session: Session) -> dict:
    """pg_dump must be there and at least the server's major version, else backups fail."""
    server = int(str(session.execute(text("SHOW server_version_num")).scalar())[:2])
    path = shutil.which("pg_dump")
    client = None
    if path:
        try:
            out = subprocess.run(
                [path, "--version"], capture_output=True, text=True, timeout=5, check=False
            ).stdout
            m = re.search(r"(\d+)\.\d+", out)
            client = int(m.group(1)) if m else None
        except (OSError, subprocess.SubprocessError):
            client = None
    return {
        "pg_dump": client,
        "server": server,
        "ok": client is not None and client >= server,
    }


def _used(path: Path) -> int:
    """Bytes owncryptofolio keeps in this folder (all files below it, links not followed)."""
    total = 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            try:
                st = os.lstat(os.path.join(root, name))
            except OSError:
                continue
            total += st.st_size
    return total


def _disk(path: Path) -> dict | None:
    try:
        path.mkdir(parents=True, exist_ok=True)
        u = shutil.disk_usage(path)
    except OSError:
        return None
    # what owncryptofolio itself takes there, beside what the disk has free (Vanixxx, 2026-10-12)
    return {"path": str(path), "free": u.free, "total": u.total, "used": _used(path)}


def operations(session: Session, now: datetime | None = None) -> dict:
    now = now or datetime.now(UTC)
    s = settings_service.all_settings(session)
    tz = s["general.timezone"]
    run = session.scalar(select(BackupRun).order_by(BackupRun.started_at.desc()).limit(1))
    latest = session.scalar(select(func.max(PriceLatest.at)))
    return {
        "backup": {
            "enabled": s["backup.enabled"],
            "next_at": _iso(next_slot(s["backup.time"], tz, now)) if s["backup.enabled"] else None,
            "last_at": _iso(run.finished_at or run.started_at) if run else None,
            "status": run.status if run else None,
            "probe_ok": run.probe_ok if run else None,
            "message": run.message if run else None,
        },
        "fetch": {
            "enabled": s["fetch.enabled"],
            "next_at": _iso(next_slot(s["fetch.time"], tz, now)) if s["fetch.enabled"] else None,
            **_jobs(session, "fetch"),
        },
        "prices": {
            "enabled": s["prices.enabled"],
            "next_at": _iso(next_slot(s["prices.time"], tz, now)) if s["prices.enabled"] else None,
            "live_at": _iso(latest),
            **_jobs(session, "prices"),
        },
        # fine prices and values every hour (ADR 0044)
        "fine": {"enabled": True, "next_at": None, **_jobs(session, "fine")},
        "tools": _tools(session),
        "disk": {
            "data": _disk(get_settings().data_dir),
            "backups": _disk(backup_dir()),
            "database": session.execute(
                text("SELECT pg_database_size(current_database())")
            ).scalar(),
        },
    }
