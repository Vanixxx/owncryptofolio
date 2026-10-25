"""Fine prices (ADR 0044): every 5 minutes for 31 days and every hour for 90 days, per coin,
fetched from the coin's sources in rank order. Only what is missing is fetched: after the
newest fetched value, and before the oldest when the window has grown (7 → 31 days)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.modules.prices import sources
from app.modules.prices.models import AssetAlias, PriceAsset, PriceFine, PriceSource

WINDOW = {"5m": timedelta(days=31), "1h": timedelta(days=90)}


def slot(at: datetime) -> datetime:
    """The 5-minute slot a moment belongs to."""
    at = at.astimezone(UTC).replace(second=0, microsecond=0)
    return at - timedelta(minutes=at.minute % 5)


def _assets(session: Session) -> list[str]:
    ignored = set(session.scalars(select(PriceAsset.asset).where(PriceAsset.ignored.is_(True))))
    worthless = set(
        session.scalars(select(PriceAsset.asset).where(PriceAsset.worthless_since.is_not(None)))
    )
    until = set(
        session.scalars(select(PriceAsset.asset).where(PriceAsset.prices_until.is_not(None)))
    )
    # a merged symbol rests: its prices come under the name it was merged into (review 2026-10-24)
    resting = set(session.scalars(select(AssetAlias.alias)))
    return sorted(
        set(session.scalars(select(PriceSource.asset))) - ignored - worthless - until - resting
    )


def _store(session: Session, asset: str, step: str, src: PriceSource, ticks) -> int:
    if not ticks:
        return 0
    rows = [
        {
            "asset": asset,
            "step": step,
            "at": t.at,
            "close": t.close,
            "quote": src.quote,
            "source": src.source,
        }
        for t in ticks
    ]
    stmt = insert(PriceFine).values(rows)
    session.execute(
        stmt.on_conflict_do_update(
            index_elements=["asset", "step", "at"],
            set_={
                "close": stmt.excluded.close,
                "quote": stmt.excluded.quote,
                "source": stmt.excluded.source,
            },
        )
    )
    return len(rows)


def _missing(
    session: Session, asset: str, step: str, begin: datetime, now: datetime
) -> list[tuple[datetime, datetime]]:
    """The stretches to fetch: before the oldest and after the newest fetched value. Live
    values do not count, they are only every 5 minutes from when the app ran."""
    first, last = session.execute(
        select(func.min(PriceFine.at), func.max(PriceFine.at)).where(
            PriceFine.asset == asset, PriceFine.step == step, PriceFine.source != "live"
        )
    ).one()
    gap = timedelta(seconds=2 * sources.STEP_SECONDS[step])
    if first is None:
        return [(begin, now)]
    out = []
    if first - begin >= gap:
        out.append((begin, first))
    if now - last >= gap:
        out.append((last, now))
    return out


def fetch(
    session: Session, now: datetime | None = None, progress: Callable[[dict], None] | None = None
) -> dict:
    """Fills what is missing in both grids for every priced coin."""
    now = now or datetime.now(UTC)
    assets = _assets(session)
    written, failed = 0, []
    for i, asset in enumerate(assets):
        ranked = list(
            session.scalars(
                select(PriceSource).where(PriceSource.asset == asset).order_by(PriceSource.rank)
            )
        )
        for step, window in WINDOW.items():
            for start, end in _missing(session, asset, step, now - window, now):
                for src in ranked:
                    try:
                        ticks = sources.FINE[src.source](src.ticker, step, start, end)
                    except sources.SourceUnavailable:
                        continue
                    if ticks:
                        written += _store(session, asset, step, src, ticks)
                        break
                else:
                    # before the oldest value the sources may simply not reach back
                    if end == now:
                        failed.append(f"{asset} {step}")
        session.commit()
        if progress:
            progress({"done": i + 1, "total": len(assets)})
    for step, window in WINDOW.items():
        session.execute(
            delete(PriceFine).where(PriceFine.step == step, PriceFine.at < now - window)
        )
    session.commit()
    return {"assets": len(assets), "written": written, "failed": failed}


def record_live(session: Session, asset: str, price, quote: str, now: datetime) -> None:
    """The current price also goes into the 5-minute grid: no hole when a source has no
    candles (yet)."""
    stmt = insert(PriceFine).values(
        asset=asset, step="5m", at=slot(now), close=price, quote=quote, source="live"
    )
    session.execute(stmt.on_conflict_do_nothing(index_elements=["asset", "step", "at"]))
