"""Job kind 'fetch': pull a source through its API or chain plugin."""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.modules.jobs.models import Job
from app.modules.plugins.chain import ChainUnavailable
from app.modules.plugins.manifest import Channel
from app.modules.raw import service as raw
from app.modules.raw.models import ImportRun
from app.modules.sources import service as sources
from app.modules.sources import services, vault
from app.modules.sources.service import KEY_REJECTED

SERVICE_KEY_REJECTED = "services.key_rejected"
OVERLAP = timedelta(days=2)  # re-read a little: late-booked rows; duplicates are skipped
# exchanges list a deposit or withdrawal only once it is done; one pending for days must
# still be asked for after a newer trade moved the newest row on (review 2026-10-24)
OVERLAP_API = timedelta(days=14)


def run_fetch(session: Session, job: Job, progress: Callable[[dict[str, Any]], None]) -> dict:
    source = sources.get(session, job.source_id)
    channel = Channel.CHAIN if source.kind == "wallet" else Channel.API
    plugin = sources.plugin_for(source, channel)
    last_to = session.scalar(
        select(func.max(ImportRun.data_to)).where(
            ImportRun.source_id == source.id, ImportRun.channel == channel.value
        )
    )
    overlap = OVERLAP_API if channel is Channel.API else OVERLAP
    since = last_to - overlap if last_to else None

    if channel is Channel.API:
        secrets = vault.read(session, source.id)
        if not secrets:
            raise AppError("sources.no_credentials", 400)
        try:
            movements = list(plugin.module.fetch(secrets, since, progress))
        except Exception as exc:
            # ccxt names a refused key by type (expired after 90 days, deleted, missing
            # rights): kept as a code, so the app can warn in plain words (2026-10-05)
            if type(exc).__name__ in ("AuthenticationError", "PermissionDenied"):
                raise RuntimeError(KEY_REJECTED) from None
            raise RuntimeError(vault.scrub(str(exc), secrets)) from None
    else:
        chain = plugin.manifest.chain
        key = services.read(session, chain.service) if chain and chain.service else None
        if chain and chain.service and not key and not chain.service_optional:
            raise AppError("services.key_missing", 400, service=chain.service)
        try:
            movements = list(plugin.module.fetch(source.address, since, progress, key=key))
        except ChainUnavailable as exc:
            # an explorer that refuses the key says so by status: named as such, so the
            # alert points at the settings instead of "HTTP 403" (review 2026-10-24)
            if key and str(exc) in ("HTTP 401", "HTTP 403"):
                raise RuntimeError(SERVICE_KEY_REJECTED) from None
            raise

    run = raw.import_movements(
        session, source, channel.value, "API" if channel is Channel.API else "Chain", movements
    )
    from app.modules.balances import service as balances

    if channel is Channel.API:
        balance = balances.after_fetch(session, source, plugin.module, secrets=secrets)
    else:
        balance = balances.after_fetch(session, source, plugin.module, key=key)
        chain = plugin.manifest.chain
        if chain and chain.accrues and "balance_assets" in balance:
            balance |= balances.book_accrual(session, source, chain.accrues)
    return {**sources.run_dict(run, True), **balance}
