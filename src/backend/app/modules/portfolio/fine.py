"""Fine portfolio values computed, not only recorded (ADR 0044): at every slot of the grid
(5 minutes for 31 days, every hour for 90 days) the holding of each coin — from the movements
of all places — times its fine price, else its daily price. Replaces what was recorded live:
gaps while the app was off fill, values taken while the data was still being corrected
(07.–11.10.2026) become right."""

from __future__ import annotations

from bisect import bisect_right
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.modules.portfolio.engine import ZERO
from app.modules.portfolio.models import PortfolioTick
from app.modules.prices.fine import WINDOW, slot
from app.modules.prices.models import PriceFine
from app.modules.prices.service import Valuer

TOLERANCE = {"5m": timedelta(minutes=30), "1h": timedelta(hours=3)}
"""How old a fine price may be at a slot before the daily price stands in."""


def grid(now: datetime, first: datetime) -> list[tuple[datetime, str]]:
    end = slot(now)
    fine_from = end - WINDOW["5m"]
    out: list[tuple[datetime, str]] = []
    hour = (end - WINDOW["1h"]).replace(minute=0)
    while hour < fine_from:
        if hour >= first:
            out.append((hour, "1h"))
        hour += timedelta(hours=1)
    t = fine_from
    while t <= end:
        if t >= first:
            out.append((t, "5m"))
        t += timedelta(minutes=5)
    return out


def rebuild(session: Session, now: datetime | None = None) -> int:
    from app.modules.portfolio.service import compute

    now = now or datetime.now(UTC)
    book, view = compute(session)
    if book.first is None:
        return 0
    # per coin: every change of the holding over all places, in time
    changes: dict[str, list[tuple[datetime, Decimal]]] = defaultdict(list)
    for (_src, _market, asset), track in book.tracks.items():
        before = ZERO
        for at, qty, _row in track:
            changes[asset].append((at, qty - before))
            before = qty
    for asset in changes:
        changes[asset].sort(key=lambda c: c[0])

    slots = grid(now, book.first)
    if not slots:
        return 0
    valuer = Valuer(session)
    prices: dict[tuple[str, str], tuple[list[datetime], list[tuple]]] = {}
    rows = session.execute(
        select(PriceFine.asset, PriceFine.step, PriceFine.at, PriceFine.close, PriceFine.quote)
        .where(PriceFine.at >= slots[0][0] - timedelta(hours=3))
        .order_by(PriceFine.asset, PriceFine.step, PriceFine.at)
    )
    for asset, step, at, close, quote in rows:
        times, values = prices.setdefault((asset, step), ([], []))
        times.append(at)
        values.append((close, quote))

    def price(asset: str, at: datetime, step: str) -> Decimal | None:
        for s in (step, "1h", "5m"):
            found = prices.get((asset, s))
            if not found:
                continue
            i = bisect_right(found[0], at) - 1
            if i >= 0 and at - found[0][i] <= TOLERANCE[s]:
                close, quote = found[1][i]
                eur = valuer._to_eur(close, quote, at.date())
                if eur is not None:
                    return eur
        return valuer.eur(asset, at.date())

    held: dict[str, Decimal] = defaultdict(Decimal)
    pos = {a: 0 for a in changes}
    out = []
    for at, step in slots:
        for asset, cs in changes.items():
            i = pos[asset]
            while i < len(cs) and cs[i][0] <= at:
                held[asset] += cs[i][1]
                i += 1
            pos[asset] = i
        total, priced = ZERO, False
        for asset, qty in held.items():
            if qty <= 0:
                continue
            p = price(view.asset(asset) or asset, at, step)
            if p is not None:
                total += p * qty
                priced = True
        if priced:
            out.append({"at": at, "value": total})
    session.execute(delete(PortfolioTick).where(PortfolioTick.at >= slots[0][0]))
    if out:
        session.execute(PortfolioTick.__table__.insert(), out)
    session.commit()
    return len(out)
