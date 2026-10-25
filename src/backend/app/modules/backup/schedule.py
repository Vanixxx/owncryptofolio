"""Daily backup and daily fetch at their configured local times (ADR 0035). A plain
loop instead of a scheduler library: two rules, checked once a minute."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select

from app.core.db import _session_factory
from app.core.errors import AppError
from app.modules.backup.models import BackupRun
from app.modules.jobs import service as jobs
from app.modules.settings import service as settings

log = logging.getLogger(__name__)


def due(now: datetime, at: str, tz: str, last_scheduled: datetime | None) -> bool:
    local = now.astimezone(ZoneInfo(tz))
    hh, mm = (int(x) for x in at.split(":"))
    slot = datetime.combine(local.date(), time(hh, mm), tzinfo=ZoneInfo(tz))
    return local >= slot and (last_scheduled is None or last_scheduled < slot)


def check_once(now: datetime | None = None) -> bool:
    now = now or datetime.now(UTC)
    with _session_factory()() as session:
        s = settings.all_settings(session)
        if not s["backup.enabled"]:
            return False
        last = session.scalar(
            select(BackupRun.started_at)
            .where(BackupRun.trigger == "schedule")
            .order_by(BackupRun.started_at.desc())
            .limit(1)
        )
        if not due(now, s["backup.time"], s["general.timezone"], last):
            return False
        try:
            jobs.enqueue(session, "backup")
        except AppError:
            return False  # one already queued or running
        # Mark the slot as taken now, so a slow worker cannot enqueue it twice.
        session.add(BackupRun(trigger="schedule", status="queued", started_at=now))
        session.commit()
        log.info("Scheduled backup queued")
        return True


def fetch_once(now: datetime | None = None) -> int:
    """Queues one fetch per active source when the daily slot has come."""
    from app.modules.jobs.models import Job
    from app.modules.plugins.manifest import Channel
    from app.modules.plugins.registry import registry
    from app.modules.sources import vault
    from app.modules.sources.models import Source

    now = now or datetime.now(UTC)
    with _session_factory()() as session:
        s = settings.all_settings(session)
        if not s["fetch.enabled"]:
            return 0
        last = session.scalar(
            select(Job.created_at)
            .where(Job.kind == "fetch", Job.trigger == "schedule")
            .order_by(Job.created_at.desc())
            .limit(1)
        )
        if not due(now, s["fetch.time"], s["general.timezone"], last):
            return 0
        queued = 0
        for src in session.scalars(select(Source).where(Source.auto_fetch.is_(True))):
            channel = Channel.CHAIN if src.kind == "wallet" else Channel.API
            if registry().find(src.provider, channel) is None:
                continue  # file-only exchange (archive)
            if channel is Channel.API and not vault.field_names(session, src.id):
                continue  # no key yet
            try:
                job = jobs.enqueue(session, "fetch", src.id)
            except AppError:
                continue  # already queued or running
            job.trigger = "schedule"
            session.commit()
            queued += 1
        if queued == 0:
            # Mark the slot as taken even when nothing was due to fetch.
            session.add(
                Job(
                    kind="fetch",
                    trigger="schedule",
                    status="done",
                    progress={},
                    result={"note": "nothing to fetch"},
                )
            )
            session.commit()
        log.info("Scheduled fetch queued for %d source(s)", queued)
        return queued


RETRY_AFTER = timedelta(minutes=15)
RETRIES = ("schedule", "retry-1", "retry-2", "retry-3")
"""An automatic fetch and its retries; after the third retry the failure stays."""
TRANSIENT = (
    "timeout",
    "timed out",
    "temporar",
    "connection",
    "urlopen error",
    "remote end closed",
    "network",
    "http 429",
    "http 500",
    "http 502",
    "http 503",
    "http 504",
)
"""What a later try can fix: a slow or busy service. A refused key or a bad address
cannot — those are left for Vanixxx."""


def retry_once(now: datetime | None = None) -> int:
    """Re-queues an automatic fetch that failed on a passing error, 15 minutes later, at
    most three times (litecoinspace.org timed out at the 04:00 round, ADR 0043)."""
    from app.modules.jobs.models import Job

    now = now or datetime.now(UTC)
    queued = 0
    with _session_factory()() as session:
        failed = session.scalars(
            select(Job).where(
                Job.kind == "fetch",
                Job.status == "failed",
                Job.trigger.in_(RETRIES[:-1]),
                Job.finished_at <= now - RETRY_AFTER,
                Job.finished_at >= now - timedelta(hours=6),
            )
        ).all()
        for job in failed:
            if not any(w in (job.message or "").lower() for w in TRANSIENT):
                continue
            newer = session.scalar(
                select(Job.id).where(
                    Job.kind == "fetch", Job.source_id == job.source_id, Job.id > job.id
                )
            )
            if newer:
                continue  # tried again already (by hand or a retry)
            try:
                again = jobs.enqueue(session, "fetch", job.source_id)
            except AppError:
                continue
            again.trigger = RETRIES[RETRIES.index(job.trigger) + 1]
            session.commit()
            queued += 1
            log.info("Fetch of source %s retried (%s)", job.source_id, again.trigger)
    return queued


FINE_EVERY = timedelta(hours=1)


def fine_once(now: datetime | None = None) -> bool:
    """Fine prices and values every hour — and right after a start, so what the app missed
    while it was off fills (ADR 0044)."""
    from app.modules.jobs.models import Job

    now = now or datetime.now(UTC)
    with _session_factory()() as session:
        last = session.scalar(
            select(Job.created_at)
            .where(Job.kind == "fine")
            .order_by(Job.created_at.desc())
            .limit(1)
        )
        if last is not None and now - last < FINE_EVERY:
            return False
        try:
            job = jobs.enqueue(session, "fine")
        except AppError:
            return False
        job.trigger = "schedule"
        session.commit()
        return True


def prices_once(now: datetime | None = None) -> bool:
    """Queues the daily price run (history, gaps, mappings for new assets)."""
    from app.modules.jobs.models import Job

    now = now or datetime.now(UTC)
    with _session_factory()() as session:
        s = settings.all_settings(session)
        if not s["prices.enabled"]:
            return False
        last = session.scalar(
            select(Job.created_at)
            .where(Job.kind == "prices", Job.trigger == "schedule")
            .order_by(Job.created_at.desc())
            .limit(1)
        )
        if not due(now, s["prices.time"], s["general.timezone"], last):
            return False
        try:
            job = jobs.enqueue(session, "prices")
        except AppError:
            return False  # one already queued or running
        job.trigger = "schedule"
        session.commit()
        log.info("Scheduled price run queued")
        return True


def latest_once(now: datetime | None = None) -> int:
    """Current prices every `prices.latest_minutes` (display only). Runs right here, not
    as a job: every 15 minutes a job entry would bury the real ones."""
    from app.modules.prices import service as prices
    from app.modules.prices.models import PriceLatest

    now = now or datetime.now(UTC)
    with _session_factory()() as session:
        minutes = settings.all_settings(session)["prices.latest_minutes"]
        if not minutes:
            return 0
        last = session.scalar(select(func.max(PriceLatest.at)))
        if last is not None and now - last < timedelta(minutes=minutes):
            return 0
        if last is None and not session.scalar(select(func.count()).select_from(PriceLatest)):
            # nothing mapped yet: the daily run (or the user) starts the first one
            from app.modules.prices.models import PriceSource

            if not session.scalar(select(func.count()).select_from(PriceSource)):
                return 0
        return prices.refresh_latest(session)


def tick_once(now: datetime | None = None) -> bool:
    """The portfolio value every 5 minutes (M7), right after the current prices."""
    from app.modules.portfolio import service as portfolio
    from app.modules.raw.models import RawTransaction

    with _session_factory()() as session:
        if not session.scalar(select(func.count()).select_from(RawTransaction)):
            return False
        return portfolio.record_tick(session, now)


async def schedule_loop(stop: asyncio.Event) -> None:
    while not stop.is_set():
        try:
            await asyncio.to_thread(check_once)
            await asyncio.to_thread(fetch_once)
            await asyncio.to_thread(retry_once)
            await asyncio.to_thread(fine_once)
            await asyncio.to_thread(prices_once)
            await asyncio.to_thread(latest_once)
            await asyncio.to_thread(tick_once)
        except Exception:  # noqa: BLE001 — keep the loop alive
            log.exception("Schedule check failed")
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(stop.wait(), timeout=60)
