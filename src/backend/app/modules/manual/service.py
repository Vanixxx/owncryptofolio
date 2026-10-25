"""Manual entries: form, edit, delete, template (ADR 0036).

An entry is a raw row in the channel `manual`. Editing adds a new row and notes
old → new in `raw_retraction`; deleting notes old → nothing. The raw row itself is
never changed (ADR 0001).
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from zoneinfo import ZoneInfo

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.modules.merged import decisions
from app.modules.plugins.contract import IncomeKind, Kind, Market, Movement, fingerprint
from app.modules.raw import service as raw
from app.modules.raw.models import ImportRun, RawRetraction, RawTransaction, current
from app.modules.sources import service as sources
from app.modules.sources.models import Source

CHANNEL = "manual"
RUN_LABEL = "manual entries"

# Which sides each kind takes per market: required, allowed, and whether exactly one of
# incoming/outgoing is wanted (a futures result is a gain OR a loss, ADR 0037). A receive
# with an outgoing side would be a trade typed wrongly — refused instead of guessed.
IN, OUT, FEE = "incoming", "outgoing", "fee"
Rule = tuple[set[str], set[str], bool]
SIDES: dict[Market, dict[Kind, Rule]] = {
    Market.SPOT: {
        Kind.TRADE: ({IN, OUT}, {IN, OUT, FEE}, False),
        Kind.RECEIVE: ({IN}, {IN, FEE}, False),
        Kind.SEND: ({OUT}, {OUT, FEE}, False),
        Kind.FIAT_DEPOSIT: ({IN}, {IN, FEE}, False),
        Kind.FIAT_WITHDRAWAL: ({OUT}, {OUT, FEE}, False),
        Kind.INCOME: ({IN}, {IN}, False),
        Kind.FEE: ({FEE}, {FEE}, False),
        Kind.INTERNAL_TRANSFER: (set(), {IN, OUT, FEE}, False),  # one side or both
        Kind.MIGRATION: ({IN, OUT}, {IN, OUT}, False),
    },
    Market.FUTURES: {
        Kind.REALIZED_PNL: (set(), {IN, OUT, FEE}, True),
        Kind.FUNDING: (set(), {IN, OUT}, True),
        Kind.FEE: ({FEE}, {FEE}, False),
        Kind.INTERNAL_TRANSFER: (set(), {IN, OUT, FEE}, True),
        # a credit of the exchange to the futures account (Bitget "risk capital", 2026-10-11)
        Kind.INCOME: ({IN}, {IN}, False),
    },
}


class EntryIn(BaseModel):
    kind: str
    market: str = "spot"
    instrument: str | None = None  # futures contract, e.g. BTCUSDT
    income_kind: str | None = None
    time: str  # local time "YYYY-MM-DDTHH:MM[:SS]" in the configured time zone
    incoming_asset: str | None = None
    incoming_amount: str | None = None
    outgoing_asset: str | None = None
    outgoing_amount: str | None = None
    fee_asset: str | None = None
    fee_amount: str | None = None
    comment: str | None = None
    paid_by_card: bool = False
    """A trade paid by card: its fiat counts as paid in, whatever lay at the exchange."""
    source_id: int | None = None
    """Editing only: the correction belongs to another source (Vanixxx, 2026-10-08: the
    transfer's wallet was the wrong one). The original stays where it was."""


def _amount(value: str | None, side: str) -> Decimal | None:
    if value is None or not str(value).strip():
        return None
    text = str(value).strip().replace(" ", "").replace(" ", "")
    if "," in text and "." in text:  # 1.234,56 or 1,234.56: the last one is the decimal mark
        text = (
            text.replace(".", "").replace(",", ".")
            if text.rfind(",") > text.rfind(".")
            else text.replace(",", "")
        )
    else:
        text = text.replace(",", ".")
    try:
        number = Decimal(text)
    except InvalidOperation as exc:
        raise AppError("manual.invalid_amount", 400, side=side) from exc
    if not number.is_finite() or number <= 0:
        raise AppError("manual.invalid_amount", 400, side=side)
    return number


def local_time(text: str, tz: str, near: datetime | None = None) -> datetime:
    """A local time in `tz`. The hour that exists twice when the clocks go back is ambiguous:
    with `near` (the row's time so far) the reading that matches it wins, so a row saved
    unchanged keeps its moment (review 2026-10-24); else the first one."""
    try:
        naive = datetime.fromisoformat(text.strip())
    except ValueError as exc:
        raise AppError("manual.invalid_time", 400) from exc
    if naive.tzinfo is not None:
        return naive
    first = naive.replace(tzinfo=ZoneInfo(tz))
    second = naive.replace(tzinfo=ZoneInfo(tz), fold=1)
    # compared in UTC: Python never calls a time inside the repeated hour equal across zones
    if (
        near is not None
        and first.utcoffset() != second.utcoffset()
        and second.astimezone(UTC) == near.astimezone(UTC)
    ):
        return second.astimezone(UTC)
    return first


def to_movement(
    entry: EntryIn, tz: str, external_id: str, near: datetime | None = None
) -> Movement:
    try:
        kind, market = Kind(entry.kind), Market(entry.market or "spot")
    except ValueError as exc:
        raise AppError("manual.invalid_kind", 400) from exc
    if kind not in SIDES[market]:
        raise AppError("manual.invalid_kind", 400)
    sides = {}
    for side in ("incoming", "outgoing", "fee"):
        asset = (getattr(entry, f"{side}_asset") or "").strip()
        amount = _amount(getattr(entry, f"{side}_amount"), side)
        if bool(asset) != (amount is not None):
            raise AppError("manual.side_incomplete", 400, side=side)
        if amount is not None:
            sides[side] = (asset, amount)
    required, allowed, one_of = SIDES[market][kind]
    if missing := required - sides.keys():
        raise AppError("manual.side_missing", 400, side=sorted(missing)[0])
    if extra := sides.keys() - allowed:
        raise AppError("manual.side_not_allowed", 400, side=sorted(extra)[0])
    moving = sides.keys() & {IN, OUT}
    if one_of and len(moving) != 1:
        raise AppError("manual.one_side", 400)
    if not required and not moving:  # a transfer moves at least one side
        raise AppError("manual.side_missing", 400, side=IN)
    income_kind = None
    if kind is Kind.INCOME:
        try:
            income_kind = IncomeKind(entry.income_kind or "")
        except ValueError as exc:
            raise AppError("manual.invalid_income_kind", 400) from exc
    fields: dict[str, Any] = {}
    for side, (asset, amount) in sides.items():
        fields[f"{side}_asset"], fields[f"{side}_amount"] = asset, amount
    comment = (entry.comment or "").strip()[:1000] or None
    m = Movement(
        timestamp=local_time(entry.time, tz, near),
        kind=kind,
        market=market,
        instrument=(entry.instrument or "").strip().upper()[:60] or None
        if market is Market.FUTURES
        else None,
        income_kind=income_kind,
        external_id=external_id,
        comment=comment,
        raw={"manual": entry.model_dump(), "timezone": tz},
        **fields,
    )
    m.check()
    return m


def _run(session: Session, source: Source) -> ImportRun:
    run = session.scalar(
        select(ImportRun).where(ImportRun.source_id == source.id, ImportRun.channel == CHANNEL)
    )
    if run is None:
        run = ImportRun(source_id=source.id, channel=CHANNEL, label=RUN_LABEL, problems=[])
        session.add(run)
        session.flush()
    return run


def _insert(session: Session, source: Source, run: ImportRun, m: Movement) -> RawTransaction:
    fp = fingerprint(raw.source_key(source, CHANNEL), m)
    row = raw.make_row(source.id, CHANNEL, run.id, fp, m)
    session.add(row)
    run.read += 1
    run.added += 1
    run.data_from = m.timestamp if run.data_from is None else min(run.data_from, m.timestamp)
    run.data_to = m.timestamp if run.data_to is None else max(run.data_to, m.timestamp)
    session.flush()
    return row


def _current(session: Session, raw_id: int) -> RawTransaction:
    row = session.get(RawTransaction, raw_id)
    if row is None:
        raise AppError("manual.not_found", 404)
    if session.get(RawRetraction, raw_id) is not None:
        raise AppError("manual.already_changed", 409)
    return row


def add(session: Session, source_id: int, entry: EntryIn, tz: str) -> dict:
    source = sources.get(session, source_id)
    m = to_movement(entry, tz, f"form:{uuid.uuid4()}")
    row = _insert(session, source, _run(session, source), m)
    session.commit()
    return entry_dict(row, tz)


def edit(session: Session, raw_id: int, entry: EntryIn, tz: str) -> dict:
    """Edit a manual row, or correct a row from API, file or chain (ADR 0037): either
    way a new manual row replaces the old one, which stays stored."""
    old = _current(session, raw_id)
    source = sources.get(session, entry.source_id or old.source_id)
    m = to_movement(entry, tz, f"form:{uuid.uuid4()}", near=old.timestamp)
    if source.id == old.source_id and _same(old, m):
        return entry_dict(old, tz)  # saved without a change: no empty version in the history
    if old.channel == CHANNEL:
        m.raw["replaces"] = old.id
        if "corrects" in (old.raw or {}):
            m.raw["corrects"] = old.raw["corrects"]  # the original stays known
    else:
        m.raw["corrects"] = old.id
    new = _insert(session, source, _run(session, source), m)
    session.add(RawRetraction(raw_id=old.id, replaced_by_id=new.id))
    decisions.carry(session, old.fingerprint, new.fingerprint)
    session.commit()
    return entry_dict(new, tz)


def _same(old: RawTransaction, m: Movement) -> bool:
    fields = (
        "timestamp",
        "kind",
        "market",
        "instrument",
        "income_kind",
        "incoming_asset",
        "incoming_amount",
        "outgoing_asset",
        "outgoing_amount",
        "fee_asset",
        "fee_amount",
        "comment",
    )

    def value(x: object, f: str) -> object:
        v = getattr(x, f)
        return getattr(v, "value", v)  # enums as their text, like the raw row stores them

    def card(raw: dict | None) -> bool:
        return bool(((raw or {}).get("manual") or {}).get("paid_by_card"))

    return all(value(old, f) == value(m, f) for f in fields) and card(old.raw) == card(m.raw)


def remove(session: Session, raw_id: int) -> None:
    """Delete a manual row, hide any other one: it stays stored, but no longer counts."""
    old = _current(session, raw_id)
    session.add(RawRetraction(raw_id=old.id, replaced_by_id=None))
    session.commit()


def _links(row: RawTransaction) -> list[int]:
    if row.channel != CHANNEL:
        return []  # an exchange's own raw JSON may use any key names
    raw = row.raw or {}
    return [int(raw[k]) for k in ("replaces", "corrects") if raw.get(k) is not None]


def chain(session: Session, row: RawTransaction) -> list[RawTransaction]:
    """Every version linked to this row: the original, corrections, edits (ADR 0037)."""
    seen: dict[int, RawTransaction] = {row.id: row}
    todo = [row]
    while todo:
        r = todo.pop()
        linked = set(_links(r))
        note = session.get(RawRetraction, r.id)
        if note is not None and note.replaced_by_id:
            linked.add(note.replaced_by_id)
        children = session.scalars(
            select(RawTransaction.id).where(
                RawTransaction.channel == CHANNEL,
                (RawTransaction.raw["replaces"].astext == str(r.id))
                | (RawTransaction.raw["corrects"].astext == str(r.id)),
            )
        ).all()
        linked.update(children)
        for i in linked - seen.keys():
            other = session.get(RawTransaction, i)
            # a correction may have moved to another source: the chain follows it
            if other is not None:
                seen[i] = other
                todo.append(other)
    return sorted(seen.values(), key=lambda r: r.id)


def restore(session: Session, raw_id: int) -> None:
    """Make this version the valid one again ("reset to original"); whatever else of
    its chain was valid now counts as replaced by it — never as a hidden row of its own,
    and a transaction never counts twice."""
    row = session.get(RawTransaction, raw_id)
    if row is None:
        raise AppError("manual.not_found", 404)
    note = session.get(RawRetraction, raw_id)
    if note is None:
        raise AppError("manual.not_changed", 409)
    for other in chain(session, row):
        if other.id != row.id and session.get(RawRetraction, other.id) is None:
            session.add(RawRetraction(raw_id=other.id, replaced_by_id=row.id))
            decisions.carry(session, other.fingerprint, row.fingerprint)
    session.delete(note)
    session.commit()


def state(session: Session, row: RawTransaction) -> str:
    note = session.get(RawRetraction, row.id)
    if note is None:
        return "current"
    return "replaced" if note.replaced_by_id else "hidden"


def history(session: Session, raw_id: int, tz: str) -> list[dict]:
    row = session.get(RawTransaction, raw_id)
    if row is None:
        raise AppError("manual.not_found", 404)
    return [
        {
            **entry_dict(r, tz),
            "channel": r.channel,
            "state": state(session, r),
            "recorded_at": r.imported_at.isoformat(),
        }
        for r in chain(session, row)
    ]


def entries(session: Session, source_id: int, tz: str) -> list[dict]:
    sources.get(session, source_id)
    rows = session.scalars(
        select(RawTransaction)
        .where(RawTransaction.source_id == source_id, RawTransaction.channel == CHANNEL, current())
        .order_by(RawTransaction.timestamp.desc(), RawTransaction.id.desc())
    ).all()
    return [entry_dict(r, tz) for r in rows]


def _plain(v: Decimal | None) -> str | None:
    return None if v is None else format(v.normalize(), "f")


def entry_dict(r: RawTransaction, tz: str) -> dict:
    return {
        "id": r.id,
        "timestamp": r.timestamp.isoformat(),
        "time": r.timestamp.astimezone(ZoneInfo(tz)).strftime("%Y-%m-%dT%H:%M:%S"),
        "kind": r.kind,
        "market": r.market,
        "instrument": r.instrument,
        "income_kind": r.income_kind,
        "incoming_asset": r.incoming_asset,
        "incoming_amount": _plain(r.incoming_amount),
        "outgoing_asset": r.outgoing_asset,
        "outgoing_amount": _plain(r.outgoing_amount),
        "fee_asset": r.fee_asset,
        "fee_amount": _plain(r.fee_amount),
        "comment": r.comment,
        "edited": bool(_links(r)),
        "paid_by_card": bool(((r.raw or {}).get("manual") or {}).get("paid_by_card"))
        if r.channel == CHANNEL
        else False,
        "corrects": (r.raw or {}).get("corrects"),
    }


def add_many(session: Session, source: Source, movements: Iterable[Movement]) -> dict[str, int]:
    """Template rows: known fingerprints (also of retracted rows) count as duplicates, so
    the same template uploaded twice adds nothing and a deleted row does not come back."""
    known = raw.existing_fingerprints(session, source.id, CHANNEL)
    key = raw.source_key(source, CHANNEL)
    run = _run(session, source)
    stats = {"added": 0, "duplicates": 0}
    for m in movements:
        fp = fingerprint(key, m)
        if fp in known:
            stats["duplicates"] += 1
            continue
        known.add(fp)
        _insert(session, source, run, m)
        stats["added"] += 1
    session.commit()
    return stats
