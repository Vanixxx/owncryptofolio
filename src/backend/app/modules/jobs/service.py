"""Queue, worker loop and the job kinds.

Two lessons from the old worker (2026-09-12): the job runs in a thread
(`asyncio.to_thread`) so the server keeps answering; and a failing job is rolled
back before it is marked failed, otherwise it stays "running" forever.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.db import _session_factory
from app.core.errors import AppError
from app.modules.jobs.models import Job

log = logging.getLogger(__name__)
Runner = Callable[[Session, Job, Callable[[dict[str, Any]], None]], dict[str, Any]]
RUNNERS: dict[str, Runner] = {}


def register(kind: str, runner: Runner) -> None:
    RUNNERS[kind] = runner


def enqueue(session: Session, kind: str, source_id: int | None = None) -> Job:
    if kind not in RUNNERS:
        raise AppError("jobs.unknown_kind", 400, kind=kind)
    busy = session.scalar(
        select(Job.id).where(
            Job.kind == kind,
            Job.source_id.is_(source_id) if source_id is None else Job.source_id == source_id,
            Job.status.in_(("queued", "running")),
        )
    )
    if busy:
        raise AppError("jobs.already_queued", 409)
    job = Job(kind=kind, source_id=source_id, progress={}, result={})
    session.add(job)
    session.commit()
    return job


def recover_interrupted(session: Session) -> int:
    """A job still 'running' at start-up was killed with the old process."""
    n = session.execute(
        update(Job)
        .where(Job.status == "running")
        .values(status="failed", message="interrupted by restart", finished_at=datetime.now(UTC))
    ).rowcount
    session.commit()
    return n


def _error_text(exc: Exception) -> str:
    if isinstance(exc, AppError):
        return exc.code
    first = (str(exc).strip().splitlines() or [type(exc).__name__])[0]
    return first[:200]  # SQL errors carry kilobytes of statement text


def run_one() -> bool:
    """Runs the oldest queued job in its own session. Returns False when idle."""
    factory = _session_factory()
    with factory() as session:
        job = session.scalars(
            select(Job)
            .where(Job.status == "queued")
            .order_by(Job.id)
            .limit(1)
            .with_for_update(skip_locked=True)
        ).first()
        if job is None:
            return False
        job_id = job.id
        job.status, job.started_at = "running", datetime.now(UTC)
        session.commit()

        def progress(data: dict[str, Any]) -> None:
            # Own session: the job's session may be mid-transaction.
            with factory() as s:
                s.execute(update(Job).where(Job.id == job_id).values(progress=data))
                s.commit()

        try:
            result = RUNNERS[job.kind](session, job, progress)
            session.execute(
                update(Job)
                .where(Job.id == job_id)
                .values(status="done", result=result or {}, finished_at=datetime.now(UTC))
            )
            session.commit()
        except Exception as exc:  # noqa: BLE001 — every failure ends as a visible failed job
            log.exception("Job %s (%s) failed", job_id, job.kind)
            session.rollback()
            session.execute(
                update(Job)
                .where(Job.id == job_id)
                .values(status="failed", message=_error_text(exc), finished_at=datetime.now(UTC))
            )
            session.commit()
    return True


async def worker_loop(stop: asyncio.Event, idle_seconds: float = 2.0) -> None:
    while not stop.is_set():
        try:
            busy = await asyncio.to_thread(run_one)
        except Exception:  # noqa: BLE001 — the loop must survive a database hiccup
            log.exception("Worker iteration failed")
            busy = False
        if not busy:
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(stop.wait(), timeout=idle_seconds)


def job_dict(j: Job) -> dict[str, Any]:
    return {
        "id": j.id,
        "kind": j.kind,
        "trigger": j.trigger,
        "source_id": j.source_id,
        "status": j.status,
        "progress": j.progress or {},
        "result": j.result or {},
        "message": j.message,
        "created_at": j.created_at.isoformat() if j.created_at else None,
        "started_at": j.started_at.isoformat() if j.started_at else None,
        "finished_at": j.finished_at.isoformat() if j.finished_at else None,
    }
