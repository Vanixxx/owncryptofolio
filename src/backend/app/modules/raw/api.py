from datetime import date, datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import get_session
from app.modules.raw import filters
from app.modules.raw.models import RawRetraction, RawTransaction, current
from app.modules.raw.service import Overlap

router = APIRouter(prefix="/api/raw", tags=["raw"])


def _amount(v):
    return None if v is None else format(v.normalize(), "f")


@router.get("")
def list_raw(
    source_id: str | None = None,
    market: str | None = None,
    kind: str | None = None,
    wallet_id: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    tz: str = "UTC",
    asset: str | None = None,
    before: datetime | None = None,
    after: datetime | None = None,
    cursor_id: int | None = None,
    desc: bool = True,
    show_hidden: bool = False,
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_session),
) -> dict:
    """Newest first (or oldest with `desc=false`), keyset paging via `before` / `after`
    plus `cursor_id`, the id of the last row shown (stable while new rows arrive; rows of
    the same moment beyond the page edge are not skipped — review 2026-10-24)."""
    # Edited, corrected or hidden rows stay stored but no longer count (ADR 0036/0037);
    # `show_hidden` lists them too, to restore them.
    q = select(RawTransaction)
    count = select(func.count()).select_from(RawTransaction)
    if show_hidden:
        # what the user hid on purpose; replaced versions only show in the history
        hidden = select(RawRetraction.raw_id).where(RawRetraction.replaced_by_id.is_(None))
        visible = current() | RawTransaction.id.in_(hidden)
        q, count = q.where(visible), count.where(visible)
    else:
        q, count = q.where(current()), count.where(current())
    f = filters.build(
        db,
        source_id=source_id,
        wallet_id=wallet_id,
        date_from=date_from,
        date_to=date_to,
        tz=tz,
        kind=kind,
        asset=asset,
    )
    conditions = f.where()
    if market is not None:
        conditions.append(RawTransaction.market == market)
    for c in conditions:
        q, count = q.where(c), count.where(c)
    ts, rid = RawTransaction.timestamp, RawTransaction.id
    if before is not None:
        q = q.where(
            (ts < before) | ((ts == before) & (rid < cursor_id))
            if cursor_id is not None
            else ts < before
        )
    if after is not None:
        q = q.where(
            (ts > after) | ((ts == after) & (rid > cursor_id))
            if cursor_id is not None
            else ts > after
        )
    order = (
        (RawTransaction.timestamp.desc(), RawTransaction.id.desc())
        if desc
        else (RawTransaction.timestamp.asc(), RawTransaction.id.asc())
    )
    rows = db.scalars(q.order_by(*order).limit(limit)).all()
    overlap = Overlap(db, None if f.source_ids is None else list(f.source_ids))
    ids = [r.id for r in rows]
    # a row that replaced others (edit, or reset to the original) has a history too
    replacing = set(
        db.scalars(
            select(RawRetraction.replaced_by_id).where(RawRetraction.replaced_by_id.in_(ids))
        )
    )
    notes = {
        n.raw_id: n.replaced_by_id
        for n in db.scalars(
            select(RawRetraction).where(RawRetraction.raw_id.in_([r.id for r in rows]))
        )
    }
    return {
        "total": db.scalar(count),
        "rows": [
            {
                "id": r.id,
                "source_id": r.source_id,
                "channel": r.channel,
                "timestamp": r.timestamp.isoformat(),
                "kind": r.kind,
                "income_kind": r.income_kind,
                "market": r.market,
                "instrument": r.instrument,
                "incoming": [r.incoming_asset, _amount(r.incoming_amount)],
                "outgoing": [r.outgoing_asset, _amount(r.outgoing_amount)],
                "fee": [r.fee_asset, _amount(r.fee_amount)],
                "external_id": r.external_id,
                "comment": r.comment,
                "counterparty": r.counterparty,
                "corrects": (r.raw or {}).get("corrects") if r.channel == "manual" else None,
                "state": "current"
                if r.id not in notes
                else ("replaced" if notes[r.id] else "hidden"),
                # versions exist: an edit, a correction, or a row that was changed
                "edited": r.id in notes
                or r.id in replacing
                or (
                    r.channel == "manual" and bool({"replaces", "corrects"} & (r.raw or {}).keys())
                ),
                "covered_by_api": overlap.covered(
                    r.source_id,
                    r.market,
                    r.channel,
                    r.timestamp,
                    [(r.incoming_asset, r.incoming_amount), (r.outgoing_asset, r.outgoing_amount)],
                ),
            }
            for r in rows
        ],
    }


@router.get("/changes")
def source_changes(db: Session = Depends(get_session)) -> list[dict]:
    """Rows a source delivered again with other values, waiting for a decision."""
    from app.modules.raw import service

    return service.changes(db)


@router.post("/changes/{change_id}/take", status_code=204)
def take_change(change_id: int, db: Session = Depends(get_session)) -> None:
    from app.modules.raw import service

    service.decide_change(db, change_id, take=True)


@router.post("/changes/{change_id}/keep", status_code=204)
def keep_change(change_id: int, db: Session = Depends(get_session)) -> None:
    from app.modules.raw import service

    service.decide_change(db, change_id, take=False)
