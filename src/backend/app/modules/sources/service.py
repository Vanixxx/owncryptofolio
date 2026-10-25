from __future__ import annotations

import re
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.modules.plugins.manifest import Channel, SourceKind
from app.modules.plugins.registry import Plugin, registry
from app.modules.raw.models import ImportRun, RawTransaction, current
from app.modules.sources import vault
from app.modules.sources.models import Source, Wallet


def providers() -> list[dict[str, Any]]:
    """Everything the 'add source' dialog needs, built from the plugin manifests."""
    reg = registry()
    out: dict[str, dict[str, Any]] = {}
    for p in reg.plugins.values():
        s = p.manifest.source
        entry = out.setdefault(
            s.provider,
            {
                "provider": s.provider,
                "name": s.provider_name,
                "kind": s.kind.value,
                "channels": [],
                "credentials": None,
                "address_pattern": None,
            },
        )
        entry["channels"].append(
            {
                "plugin": p.key,
                "channel": s.channel.value,
                "history_days": s.history_days,
                "provides_balance": s.provides_balance,
                "futures": s.futures,
                "expected_files": s.expected_files,
                "not_read": s.not_read,
                "description": p.manifest.plugin.description,
                "version": p.manifest.plugin.version,
                "status": p.manifest.plugin.status,
            }
        )
        if p.manifest.credentials:
            entry["credentials"] = p.manifest.credentials.model_dump()
        entry.setdefault("family", None)
        entry.setdefault("native_asset", None)
        if p.manifest.chain:
            entry["address_pattern"] = p.manifest.chain.address_pattern
            entry["family"] = p.manifest.chain.family or None
            entry["native_asset"] = p.manifest.chain.native_asset
    return sorted(out.values(), key=lambda e: (e["kind"], e["name"]))


def plugin_for(source: Source, channel: Channel) -> Plugin:
    plugin = registry().find(source.provider, channel)
    if plugin is None:
        raise AppError("sources.channel_unavailable", 400, channel=channel.value)
    return plugin


def get(session: Session, source_id: int) -> Source:
    source = session.get(Source, source_id)
    if source is None:
        raise AppError("sources.not_found", 404)
    return source


def create(
    session: Session, provider: str, label: str, address: str | None, wallet_id: int | None = None
) -> Source:
    plugins = registry().for_provider(provider)
    if not plugins:
        raise AppError("sources.unknown_provider", 400, provider=provider)
    kind = plugins[0].manifest.source.kind
    label = label.strip()
    if not label:
        raise AppError("sources.label_required", 400)
    if kind is SourceKind.WALLET:
        if wallet_id is None or session.get(Wallet, wallet_id) is None:
            raise AppError("wallets.required", 400)
        chain = next((p.manifest.chain for p in plugins if p.manifest.chain), None)
        address = (address or "").strip()
        if chain is None:
            # a network kept by hand (no plugin for the chain): the address is a note
            source = Source(
                provider=provider,
                kind=kind.value,
                label=label[:100],
                address=address or None,
                wallet_id=wallet_id,
                auto_fetch=False,
            )
            session.add(source)
            session.commit()
            return source
        if not re.fullmatch(chain.address_pattern, address):
            # A typo becomes a 400 here instead of an empty wallet later.
            raise AppError("sources.invalid_address", 400, provider=provider)
        exists = session.scalar(
            select(Source.id).where(
                Source.provider == provider, func.lower(Source.address) == address.lower()
            )
        )
        if exists:
            raise AppError("sources.duplicate_address", 409)
    else:
        address, wallet_id = None, None
    source = Source(
        provider=provider, kind=kind.value, label=label[:100], address=address, wallet_id=wallet_id
    )
    session.add(source)
    session.commit()
    return source


def delete_source(session: Session, source_id: int) -> None:
    source = get(session, source_id)
    runs = session.scalars(select(ImportRun).where(ImportRun.source_id == source.id)).all()
    live = session.scalar(
        select(func.count())
        .select_from(RawTransaction)
        .where(RawTransaction.source_id == source.id, current())
    )
    if any(r.channel != "manual" for r in runs) or live:
        # Raw rows are not deleted as a side effect of removing a source;
        # the user reverts the imports first, deliberately.
        raise AppError("sources.has_imports", 409)
    if runs:
        # Only manual entries the user already deleted one by one are left (ADR 0036):
        # removing the source removes them with their notes.
        from sqlalchemy import delete, or_

        from app.modules.raw.guard import raw_unlocked
        from app.modules.raw.models import RawRetraction

        ids = select(RawTransaction.id).where(RawTransaction.source_id == source.id)
        with raw_unlocked(f"delete source {source.id} with only deleted manual entries"):
            session.execute(
                delete(RawRetraction).where(
                    or_(RawRetraction.raw_id.in_(ids), RawRetraction.replaced_by_id.in_(ids))
                )
            )
            session.execute(delete(RawTransaction).where(RawTransaction.source_id == source.id))
            for r in runs:
                session.delete(r)
            session.delete(source)
            session.commit()
        return
    session.delete(source)
    session.commit()


def set_credentials(session: Session, source_id: int, values: dict[str, str]) -> None:
    source = get(session, source_id)
    manifest = plugin_for(source, Channel.API).manifest
    assert manifest.credentials is not None
    cleaned = {k: (values.get(k) or "").strip() for k in manifest.credentials.fields}
    groups = manifest.credentials.alternatives or [manifest.credentials.fields]
    complete = next((g for g in groups if all(cleaned.get(k) for k in g)), None)
    if complete is None:
        missing = [k for k in groups[0] if not cleaned.get(k)]
        raise AppError("sources.credentials_incomplete", 400, fields=missing)
    vault.store(session, source.id, {k: cleaned[k] for k in complete})
    source.last_check_at = source.last_check_ok = source.last_check_message = None
    session.commit()


WARN_DAYS = 14
"""Warn two weeks before an API's look-back runs out: time to fix the key."""
KEY_REJECTED = "sources.key_rejected"
"""What a fetch records when the exchange refuses the key (expired, deleted, rights)."""


def alerts(session: Session, today: date | None = None) -> list[dict[str, Any]]:
    """What threatens the completeness of the data (Vanixxx, 2026-10-05): a key the exchange
    refuses (Bitget/MEXC keys without IP binding expire after 90 days), a fetch that
    fails, and an API whose look-back is running out (MEXC answers only 89 days: a key dead
    for longer loses history for good). Exchanges do not report a key's expiry, so the app
    watches the fetches instead of a date nobody keeps up to date."""
    from app.modules.jobs.models import Job

    today = today or datetime.now(UTC).date()
    last_ok = dict(
        session.execute(
            select(ImportRun.source_id, func.max(ImportRun.created_at))
            .where(ImportRun.channel.in_(("api", "chain")), ImportRun.status == "done")
            .group_by(ImportRun.source_id)
        ).all()
    )
    out: list[dict[str, Any]] = []

    def add(s: Source, kind: str, when: date | None, days: int, message: str | None = None):
        out.append(
            {
                "source_id": s.id,
                "kind": kind,
                "date": when.isoformat() if when else None,
                "days": days,
                "message": message,
            }
        )

    for s in session.scalars(select(Source).order_by(Source.label)):
        api = registry().find(s.provider, Channel.API)
        has_key = api is not None and bool(vault.field_names(session, s.id))
        job = session.scalars(
            select(Job)
            .where(Job.source_id == s.id, Job.kind == "fetch")
            .order_by(Job.id.desc())
            .limit(1)
        ).first()
        failed = job is not None and job.status == "failed" and (s.auto_fetch or has_key)
        when = (job.finished_at or job.created_at).date() if failed else None
        if has_key and (s.last_check_ok is False or (failed and job.message == KEY_REJECTED)):
            checked = (
                s.last_check_at.date() if s.last_check_ok is False and s.last_check_at else None
            )
            add(s, "key_rejected", when or checked, 0)
        elif failed:
            add(s, "fetch_failed", when, (today - when).days, job.message)
        if has_key and api.manifest.source.history_days and s.id in last_ok:
            done = last_ok[s.id].date()
            left = api.manifest.source.history_days - (today - done).days
            if left <= WARN_DAYS:
                add(s, "history_at_risk", done, max(left, 0))
    return out


def delete_credentials(session: Session, source_id: int) -> None:
    source = get(session, source_id)
    vault.remove(session, source.id)
    source.last_check_at = source.last_check_ok = source.last_check_message = None
    session.commit()


def check_credentials(session: Session, source_id: int) -> Source:
    """Asks the exchange whether the key works. Remembered and shown on the card."""
    source = get(session, source_id)
    plugin = plugin_for(source, Channel.API)
    secrets = vault.read(session, source.id)
    if not secrets:
        raise AppError("sources.no_credentials", 400)
    try:
        plugin.module.check(secrets)
        ok, message = True, None
    except Exception as exc:  # noqa: BLE001 — the exchange's own words, scrubbed
        first = (str(exc).strip().splitlines() or [type(exc).__name__])[0]
        ok, message = False, vault.scrub(first, secrets)[:200]
    source.last_check_at, source.last_check_ok, source.last_check_message = (
        datetime.now(UTC),
        ok,
        message,
    )
    session.commit()
    return source


def overview(session: Session) -> list[dict[str, Any]]:
    from app.modules.raw.service import api_coverage

    coverage = api_coverage(session)
    counts = dict(
        session.execute(
            select(RawTransaction.source_id, func.count())
            .where(current())
            .group_by(RawTransaction.source_id)
        ).all()
    )
    last_fetch = dict(
        session.execute(
            select(ImportRun.source_id, func.max(ImportRun.created_at))
            .where(ImportRun.channel.in_(("api", "chain")))
            .group_by(ImportRun.source_id)
        ).all()
    )
    out = []
    for s in session.scalars(select(Source).order_by(Source.kind, Source.label)):
        runs = session.scalars(
            select(ImportRun)
            # the manual run is shown as a list of entries instead (ADR 0036)
            .where(ImportRun.source_id == s.id, ImportRun.channel != "manual")
            .order_by(ImportRun.id.desc())
            .limit(10)
        ).all()
        latest = {}
        for r in runs:
            latest.setdefault(r.channel, r.id)
        out.append(
            {
                "id": s.id,
                "provider": s.provider,
                "kind": s.kind,
                "label": s.label,
                "address": s.address,
                "wallet_id": s.wallet_id,
                "auto_fetch": s.auto_fetch,
                "api_coverage": {
                    m: ts.isoformat() for (sid, m), ts in coverage.items() if sid == s.id
                },
                "credentials": vault.field_names(session, s.id),
                "last_check": None
                if s.last_check_at is None
                else {
                    "at": s.last_check_at.isoformat(),
                    "ok": s.last_check_ok,
                    "message": s.last_check_message,
                },
                "rows": counts.get(s.id, 0),
                "last_fetch": last_fetch[s.id].isoformat() if s.id in last_fetch else None,
                "runs": [run_dict(r, latest.get(r.channel) == r.id) for r in runs],
            }
        )
    return out


def run_dict(r: ImportRun, revertible: bool) -> dict[str, Any]:
    return {
        "id": r.id,
        "channel": r.channel,
        "label": r.label,
        "status": r.status,
        "read": r.read,
        "added": r.added,
        "duplicates": r.duplicates,
        "rejected": r.rejected,
        "changed": r.changed or 0,
        "problems": r.problems or [],
        "data_from": r.data_from.isoformat() if r.data_from else None,
        "data_to": r.data_to.isoformat() if r.data_to else None,
        "created_at": r.created_at.isoformat(),
        "revertible": revertible,
    }


# --- wallets (ADR 0034) ------------------------------------------------------


def wallets(session: Session) -> list[dict[str, Any]]:
    return [
        {"id": w.id, "name": w.name} for w in session.scalars(select(Wallet).order_by(Wallet.name))
    ]


def _wallet_name(session: Session, name: str, own_id: int | None = None) -> str:
    name = name.strip()[:100]
    if not name:
        raise AppError("wallets.name_required", 400)
    other = session.scalar(select(Wallet.id).where(func.lower(Wallet.name) == name.lower()))
    if other is not None and other != own_id:
        raise AppError("wallets.duplicate_name", 409)
    return name


def create_wallet(session: Session, name: str) -> Wallet:
    wallet = Wallet(name=_wallet_name(session, name))
    session.add(wallet)
    session.commit()
    return wallet


def rename_wallet(session: Session, wallet_id: int, name: str) -> Wallet:
    wallet = session.get(Wallet, wallet_id)
    if wallet is None:
        raise AppError("wallets.not_found", 404)
    wallet.name = _wallet_name(session, name, wallet.id)
    session.commit()
    return wallet


def delete_wallet(session: Session, wallet_id: int) -> None:
    wallet = session.get(Wallet, wallet_id)
    if wallet is None:
        raise AppError("wallets.not_found", 404)
    if session.scalar(
        select(func.count()).select_from(Source).where(Source.wallet_id == wallet.id)
    ):
        raise AppError("wallets.has_networks", 409)
    session.delete(wallet)
    session.commit()
