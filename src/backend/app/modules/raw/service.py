"""Writing into the raw layer: validation, duplicate detection, import runs, revert."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from datetime import datetime
from decimal import Decimal

from sqlalchemy import and_, delete, func, select, update
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.modules.plugins.contract import Movement, fingerprint
from app.modules.raw.guard import raw_unlocked
from app.modules.raw.models import ImportRun, RawTransaction, SourceChange, current
from app.modules.sources.models import Source

log = logging.getLogger(__name__)
MAX_PROBLEMS = 50


def source_key(source: Source, channel: str) -> str:
    return f"{source.id}:{channel}"


def existing_fingerprints(session: Session, source_id: int, channel: str) -> set[str]:
    return set(
        session.scalars(
            select(RawTransaction.fingerprint).where(
                RawTransaction.source_id == source_id,
                RawTransaction.channel == channel,
            )
        )
    )


def import_movements(
    session: Session,
    source: Source,
    channel: str,
    label: str,
    movements: Iterable[Movement],
    original_file: str | None = None,
) -> ImportRun:
    """Inserts new rows, skips known ones, rejects invalid ones — in ONE commit.

    If the reader itself fails (unreadable file, broken API response) nothing is
    written and no run is left behind: a ghost run would block reverting the one
    before it.
    """
    known = existing_fingerprints(session, source.id, channel)
    run = ImportRun(
        source_id=source.id,
        channel=channel,
        label=label[:300],
        original_file=original_file,
        problems=[],
    )
    session.add(run)
    session.flush()
    key = source_key(source, channel)
    stats = {"read": 0, "added": 0, "duplicates": 0, "rejected": 0, "changed": 0}
    problems: list[str] = []
    first: datetime | None = None
    last: datetime | None = None
    fresh: list[tuple[Movement, str]] = []
    delivered: set[str] = set()
    try:
        for m in movements:
            stats["read"] += 1
            try:
                m.check()
            except ValueError as exc:
                stats["rejected"] += 1
                if len(problems) < MAX_PROBLEMS:
                    problems.append(f"{m.timestamp.isoformat()} {m.kind.value}: {exc}")
                continue
            fp = fingerprint(key, m)
            delivered.add(fp)
            if fp in known:
                # Counted and shown, not silently dropped: two identical partial
                # fills in the same second would land here (ADR 0017).
                stats["duplicates"] += 1
                continue
            known.add(fp)
            fresh.append((m, fp))
        held = _changes(session, source.id, channel, fresh, delivered)
        for m, fp in fresh:
            if fp in held:
                change = held[fp]
                if change is not None:
                    change.import_run_id = run.id
                    session.add(change)
                    stats["changed"] += 1
                else:
                    stats["duplicates"] += 1  # decided before: the old row stays
                continue
            session.add(make_row(source.id, channel, run.id, fp, m))
            stats["added"] += 1
            first = m.timestamp if first is None or m.timestamp < first else first
            last = m.timestamp if last is None or m.timestamp > last else last
    except Exception:
        session.rollback()
        raise
    for k, v in stats.items():
        setattr(run, k, v)
    run.problems = problems
    run.data_from, run.data_to = first, last
    session.commit()
    log.info("Import %s %s/%s: %s", run.id, source.provider, channel, stats)
    return run


def _match_key(external_id: str | None, timestamp: datetime, kind: str, market: str):
    return (external_id or "")[:200], timestamp, kind, market


def _changes(
    session: Session,
    source_id: int,
    channel: str,
    fresh: list[tuple[Movement, str]],
    delivered: set[str],
) -> dict[str, SourceChange | None]:
    """New rows that are an old row delivered again with other values (Vanixxx, 2026-10-23).

    The same id, time, kind and market as exactly one current row that this delivery no
    longer contains, and it is the only new one with that key. Then the source changed the
    row: held back as a change instead of a second row. A partial fill, or a chain
    transaction with several coins, has more rows per key and is never taken for a change.
    Rows without an id cannot be recognised and are added as before. The value is None
    when Vanixxx already decided on this very change (kept the old row, or a change open).
    """
    keyed = [(m, fp) for m, fp in fresh if m.external_id]
    if not keyed:
        return {}
    ids = {(m.external_id or "")[:200] for m, _ in keyed}
    old: dict[tuple, list[RawTransaction]] = {}
    for r in session.scalars(
        select(RawTransaction).where(
            RawTransaction.source_id == source_id,
            RawTransaction.channel == channel,
            RawTransaction.external_id.in_(ids),
            current(),
        )
    ):
        old.setdefault(_match_key(r.external_id, r.timestamp, r.kind, r.market), []).append(r)
    new: dict[tuple, list[tuple[Movement, str]]] = {}
    for m, fp in keyed:
        new.setdefault(
            _match_key(m.external_id, m.timestamp, m.kind.value, m.market.value), []
        ).append((m, fp))
    out: dict[str, SourceChange | None] = {}
    for k, items in new.items():
        gone = [r for r in old.get(k, []) if r.fingerprint not in delivered]
        if len(items) != 1 or len(gone) != 1 or len(old.get(k, [])) != 1:
            continue
        (m, fp), r = items[0], gone[0]
        seen = session.scalar(
            select(SourceChange).where(SourceChange.raw_id == r.id, SourceChange.fingerprint == fp)
        )
        out[fp] = (
            None
            if seen
            else SourceChange(raw_id=r.id, fingerprint=fp, movement=m.model_dump(mode="json"))
        )
    return out


def _sides(r) -> dict:
    def side(asset, amount):
        return [asset, None if amount is None else format(Decimal(amount).normalize(), "f")]

    return {
        "timestamp": r.timestamp.isoformat() if hasattr(r.timestamp, "isoformat") else r.timestamp,
        "kind": r.kind if isinstance(r.kind, str) else r.kind.value,
        "incoming": side(r.incoming_asset, r.incoming_amount),
        "outgoing": side(r.outgoing_asset, r.outgoing_amount),
        "fee": side(r.fee_asset, r.fee_amount),
        "external_id": r.external_id,
    }


def changes(session: Session) -> list[dict]:
    """What the sources changed and Vanixxx has not decided yet: old row next to the new."""
    out = []
    for c in session.scalars(
        select(SourceChange).where(SourceChange.status == "open").order_by(SourceChange.id)
    ):
        old = session.get(RawTransaction, c.raw_id)
        new = Movement.model_validate(c.movement)
        out.append(
            {
                "id": c.id,
                "source_id": old.source_id,
                "channel": old.channel,
                "raw_id": old.id,
                "old": _sides(old),
                "new": _sides(new),
                "found_at": c.created_at.isoformat() if c.created_at else None,
            }
        )
    return out


def decide_change(session: Session, change_id: int, take: bool) -> None:
    """Take the source's new values over (a new row replaces the old, which stays stored)
    or keep the old row; the same change is not offered again either way."""
    from app.modules.merged import decisions
    from app.modules.raw.models import RawRetraction

    c = session.get(SourceChange, change_id)
    if c is None or c.status != "open":
        raise AppError("raw.change_not_open", 409)
    c.decided_at = func.now()
    if not take:
        c.status = "kept"
        session.commit()
        return
    old = session.get(RawTransaction, c.raw_id)
    if session.get(RawRetraction, old.id) is not None:
        # corrected or hidden by hand meanwhile: that decision stands
        raise AppError("raw.change_old_changed", 409)
    m = Movement.model_validate(c.movement)
    new = make_row(old.source_id, old.channel, c.import_run_id, c.fingerprint, m)
    session.add(new)
    session.flush()
    session.add(RawRetraction(raw_id=old.id, replaced_by_id=new.id))
    decisions.carry(session, old.fingerprint, new.fingerprint)
    c.status, c.replaced_by_id = "taken", new.id
    session.commit()


def make_row(source_id: int, channel: str, run_id: int, fp: str, m: Movement) -> RawTransaction:
    return RawTransaction(
        source_id=source_id,
        channel=channel,
        import_run_id=run_id,
        fingerprint=fp,
        timestamp=m.timestamp,
        kind=m.kind.value,
        income_kind=m.income_kind.value if m.income_kind else None,
        market=m.market.value,
        incoming_asset=m.incoming_asset,
        incoming_amount=m.incoming_amount,
        outgoing_asset=m.outgoing_asset,
        outgoing_amount=m.outgoing_amount,
        fee_asset=m.fee_asset,
        fee_amount=m.fee_amount,
        external_id=(m.external_id or None) and m.external_id[:200],
        comment=m.comment,
        counterparty=(m.counterparty or None) and m.counterparty[:200],
        instrument=m.instrument,
        raw=_jsonable(m.raw),
    )


def _jsonable(value):
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_jsonable(v) for v in value]
    if value is None or isinstance(value, str | int | float | bool):
        return value
    return str(value)  # Decimal, datetime: keep the exact text


def latest_run_id(session: Session, source_id: int, channel: str) -> int | None:
    return session.scalar(
        select(func.max(ImportRun.id)).where(
            ImportRun.source_id == source_id, ImportRun.channel == channel
        )
    )


def revert(session: Session, run_id: int) -> dict[str, int]:
    """The ONLY way raw rows may disappear (ADR 0001 exception, old ADR 0021 rules).

    Only the latest run of a source+channel: earlier runs may carry rows later
    ones build on. The delete is bound to the run id AND the source — never to a
    time range or the source alone (the 2026-08-30 incident deleted 979 rows of
    all sources through a filter on the integration only).
    """
    run = session.get(ImportRun, run_id)
    if run is None:
        raise AppError("imports.run_not_found", 404)
    if run.channel == "manual":
        # Manual entries are removed one by one, with history (ADR 0036).
        raise AppError("imports.manual_run", 409)
    if latest_run_id(session, run.source_id, run.channel) != run.id:
        raise AppError("imports.not_latest_run", 409)
    from app.modules.raw.models import RawRetraction

    changed = session.scalar(
        select(func.count())
        .select_from(RawRetraction)
        .join(RawTransaction, RawTransaction.id == RawRetraction.raw_id)
        .where(RawTransaction.import_run_id == run.id)
    )
    if changed:
        # A correction without its original would be left over (ADR 0037).
        raise AppError("imports.has_corrections", 409, count=changed)
    taken = list(
        session.scalars(
            select(SourceChange).where(
                SourceChange.import_run_id == run.id, SourceChange.status == "taken"
            )
        )
    )
    with raw_unlocked(f"revert import run {run.id}"):
        # changes taken over from this run: the old row counts again
        for c in taken:
            session.execute(delete(RawRetraction).where(RawRetraction.raw_id == c.raw_id))
        session.execute(delete(SourceChange).where(SourceChange.import_run_id == run.id))
        # Discarded corrections that point to a row of this run (after "reset to the
        # original") lose that link: they stay stored, as hidden rows (ADR 0037).
        session.execute(
            update(RawRetraction)
            .where(
                RawRetraction.replaced_by_id.in_(
                    select(RawTransaction.id).where(RawTransaction.import_run_id == run.id)
                )
            )
            .values(replaced_by_id=None)
        )
        deleted = session.execute(
            delete(RawTransaction).where(
                and_(
                    RawTransaction.import_run_id == run.id,
                    RawTransaction.source_id == run.source_id,
                )
            )
        ).rowcount
        session.delete(run)
        session.commit()
    log.warning(
        "Reverted import run %s (source %s, %s, %r): %s rows deleted",
        run_id,
        run.source_id,
        run.channel,
        run.label,
        deleted,
    )
    return {"rows": deleted}


Coverage = dict[tuple[int, str], datetime]
EVENT_PRECISION = Decimal("1.000000000000")  # files and APIs round differently below 12 places


def api_coverage(session: Session, source_id: int | None = None) -> Coverage:
    """Earliest API row per (source, market). Taken from what the API actually
    delivered, not from its theoretical reach: Bitget's futures records stop a
    year back while spot goes to the account's start (measured 2026-10-03)."""
    q = (
        select(RawTransaction.source_id, RawTransaction.market, func.min(RawTransaction.timestamp))
        .where(RawTransaction.channel == "api")
        .group_by(RawTransaction.source_id, RawTransaction.market)
    )
    if source_id is not None:
        q = q.where(RawTransaction.source_id == source_id)
    # Files carry whole seconds, the API milliseconds: the same event would sit
    # 0.15 s "before" the API start and count twice (measured 2026-10-03).
    return {(sid, market): ts.replace(microsecond=0) for sid, market, ts in session.execute(q)}


def event_keys(ts: datetime, sides: list[tuple[str | None, Decimal | None]]) -> set[tuple]:
    """Second + asset + amount per side. Not the id: Coinbase file and API ids
    never match (Mongo ids vs UUIDs). Not one side only: a sale has the fiat side
    in USD in the file and in EUR in the API - one matching side is enough."""
    second = int(ts.timestamp())
    return {(second, a, abs(m).quantize(EVENT_PRECISION)) for a, m in sides if a and m is not None}


class Overlap:
    """Decides whether a file row is superseded by the API of the same exchange."""

    def __init__(self, session: Session, source_ids: list[int] | None = None):
        from app.modules.plugins.manifest import Channel
        from app.modules.plugins.registry import registry

        self.period = (
            api_coverage(session)
            if source_ids is None
            else {k: v for sid in source_ids for k, v in api_coverage(session, sid).items()}
        )
        q = select(Source)
        if source_ids is not None:
            q = q.where(Source.id.in_(source_ids))
        self.mode: dict[int, str] = {}
        self.events: dict[int, set[tuple]] = {}
        for src in session.scalars(q):
            plugin = registry().find(src.provider, Channel.API)
            mode = plugin.manifest.source.overlap if plugin else "period"
            self.mode[src.id] = mode
            if mode == "event":
                keys: set[tuple] = set()
                rows = session.execute(
                    select(
                        RawTransaction.timestamp,
                        RawTransaction.incoming_asset,
                        RawTransaction.incoming_amount,
                        RawTransaction.outgoing_asset,
                        RawTransaction.outgoing_amount,
                    ).where(RawTransaction.source_id == src.id, RawTransaction.channel == "api")
                )
                for ts, ia, im, oa, om in rows:
                    keys |= event_keys(ts, [(ia, im), (oa, om)])
                self.events[src.id] = keys

    def covered(
        self,
        source_id: int,
        market: str,
        channel: str,
        ts: datetime,
        sides: list[tuple[str | None, Decimal | None]],
    ) -> bool:
        if channel != "file":
            return False
        if self.mode.get(source_id) == "event":
            return bool(event_keys(ts, sides) & self.events.get(source_id, set()))
        start = self.period.get((source_id, market))
        return start is not None and ts >= start


def covered_by_api(
    coverage: Coverage, source_id: int, market: str, channel: str, ts: datetime
) -> bool:
    """Period rule only (kept for callers without amounts)."""
    start = coverage.get((source_id, market))
    return channel == "file" and start is not None and ts >= start
