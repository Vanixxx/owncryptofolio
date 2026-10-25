"""Portfolio views (ADR 0040) on top of the pass in `engine`: summary, holdings, daily
history, gap search, futures positions. The pass is cached until the data changes."""

from __future__ import annotations

import re
import threading
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session

from app.modules.balances.service import reconcile
from app.modules.merged import service as merged
from app.modules.merged.models import OpenSendMark, SpamMark, TransferDecision, TransferExtra
from app.modules.portfolio.engine import FIAT, OUTSIDE, ZERO, Book, Engine
from app.modules.portfolio.models import PortfolioTick
from app.modules.prices.models import AssetAlias, FxDaily, PriceAsset, PriceDaily
from app.modules.prices.service import Valuer
from app.modules.raw.models import ImportRun, RawRetraction, RawTransaction

_lock = threading.Lock()
_cache: dict[str, tuple[tuple, object]] = {}


def _stamp(session: Session) -> tuple:
    """Changes whenever anything the pass reads changes: rows, corrections, decisions,
    spam, aliases, daily prices. Cheap: counts and maxima."""
    one = lambda q: session.execute(q).one()  # noqa: E731
    return (
        one(select(func.count(), func.max(RawTransaction.id))),
        one(select(func.count(), func.max(ImportRun.created_at))),
        one(select(func.count(), func.max(RawRetraction.created_at))),
        one(select(func.count(), func.max(TransferDecision.id))),
        one(select(func.count(), func.max(OpenSendMark.created_at))),
        one(select(func.count(), func.max(SpamMark.created_at))),
        one(select(func.count(), func.max(TransferExtra.created_at))),
        one(select(func.count(), func.max(PriceAsset.updated_at))),
        one(select(func.count()).select_from(AssetAlias)),
        one(select(func.max(PriceDaily.fetched_at))),
        one(select(func.max(FxDaily.fetched_at))),
        datetime.now(UTC).date(),
    )


def _cached(session: Session, name: str, make):
    stamp = _stamp(session)
    with _lock:
        hit = _cache.get(name)
        if hit and hit[0] == stamp:
            return hit[1]
    value = make()
    with _lock:
        _cache[name] = (stamp, value)
    return value


def compute(session: Session) -> tuple[Book, merged.View]:
    def make():
        view = merged.build(session)
        return Engine(view, Valuer(session)).run(datetime.now(UTC).date()), view

    return _cached(session, "book", make)


def _plain(v: Decimal | None) -> str | None:
    if v is None:
        return None
    return format(v.quantize(Decimal("0.01")), "f")


def _q(v: Decimal | None) -> str | None:
    return None if v is None else format(v.normalize(), "f")


def _pct(a: Decimal, base: Decimal) -> str | None:
    return None if not base else format((a / base * 100).quantize(Decimal("0.01")), "f")


class Money:
    """EUR → display currency: today's ECB rate for amounts, the day's for the history."""

    def __init__(self, valuer: Valuer, currency: str) -> None:
        self.valuer, self.currency, self.today = valuer, currency, datetime.now(UTC).date()

    def __call__(self, eur: Decimal | None, day: date | None = None) -> Decimal | None:
        return self.valuer.in_currency(eur, day or self.today, self.currency)


# --- summary and holdings ----------------------------------------------------------------


def holdings(session: Session, currency: str = "EUR") -> dict:
    book, _ = compute(session)
    valuer = Valuer(session)
    money = Money(valuer, currency)
    today = money.today
    names = dict(session.execute(select(PriceAsset.asset, PriceAsset.name)).all())
    icons = _icons(session)
    items, value, cash, cost, unrealized, unvalued = [], ZERO, ZERO, ZERO, ZERO, []
    places_of: dict[str, list[dict]] = {}
    for (source_id, market, asset), qty in book.places.items():
        if qty != 0:
            places_of.setdefault(asset, []).append(
                {
                    "source_id": source_id or None,
                    "market": market,
                    "qty": _q(qty),
                    "outside": source_id == OUTSIDE,
                }
            )
    for asset, p in book.positions.items():
        if p.qty <= 0 and not p.realized and not p.income and not p.unclear_qty:
            continue
        price = valuer.latest_eur(asset, today)
        worth = None if price is None else price * p.qty
        fiat = asset in FIAT
        if p.qty > 0:
            if worth is None:
                unvalued.append(asset)
            elif fiat:
                cash += worth
            else:
                value += worth
                cost += p.cost
                unrealized += worth - p.cost
        gain = None if worth is None or fiat or p.qty <= 0 else worth - p.cost
        items.append(
            {
                "asset": asset,
                "name": names.get(asset),
                "icon": icons.get(asset, asset),
                "fiat": fiat,
                "qty": _q(p.qty),
                "cost": _plain(money(p.cost)) if not fiat else None,
                "avg_price": _q(money(p.cost / p.qty)) if p.qty > 0 and not fiat else None,
                "price": _q(money(price)),
                "value": _plain(money(worth)),
                "unrealized": _plain(money(gain)),
                "unrealized_pct": _pct(gain, p.cost) if gain is not None else None,
                "realized": _plain(money(p.realized)),
                "realized_pct": _pct(p.realized, p.sold_cost),
                "income": _plain(money(p.income)),
                "since": p.since.isoformat() if p.since and p.qty > 0 else None,
                "days_held": (today - p.since.date()).days if p.since and p.qty > 0 else None,
                "unclear_qty": _q(p.unclear_qty) if p.unclear_qty else None,
                "unclear_value": _plain(money(p.unclear_value)) if p.unclear_qty else None,
                "open_qty": _q(p.open_qty) if p.open_qty else None,
                "places": sorted(places_of.get(asset, []), key=lambda x: -Decimal(x["qty"])),
            }
        )
    items.sort(key=lambda i: -(Decimal(i["value"]) if i["value"] else ZERO))
    realized = sum((p.realized for a, p in book.positions.items() if a not in FIAT), ZERO)
    sold = sum((p.sold_cost for p in book.positions.values()), ZERO)
    f = book.futures
    hist = history(session, currency)
    high = max((h for h in hist if h["value"]), key=lambda h: Decimal(h["value"]), default=None)
    total_now = value + cash
    if high is None or total_now > Decimal(high["value"]):
        high = {"day": today.isoformat(), "value": _plain(money(total_now))}
    summary = {
        "currency": currency,
        "value": _plain(money(total_now)),
        "crypto": _plain(money(value)),
        "cash": _plain(money(cash)),
        "cost": _plain(money(cost)),
        "unrealized": _plain(money(unrealized)),
        "unrealized_pct": _pct(unrealized, cost),
        "realized": _plain(money(realized)),
        "realized_pct": _pct(realized, sold),
        "futures": {
            "pnl": _plain(money(f.pnl)),
            "funding": _plain(money(f.funding)),
            "fees": _plain(money(f.fees)),
            "result": _plain(money(f.result)),
        },
        "result": _plain(money(realized + unrealized + f.result)),
        "income": _plain(money(book.income)),
        "net_deposited": _plain(sum((money(v, d) or ZERO for d, v, _ in book.deposits), ZERO)),
        "card_deposits": _plain(sum((money(v, d) or ZERO for d, v, c in book.deposits if c), ZERO)),
        "external_in": _plain(money(book.external_in)),
        "unclear": _plain(money(sum((p.unclear_value for p in book.positions.values()), ZERO))),
        "open": _plain(money(sum((p.open_value for p in book.positions.values()), ZERO))),
        "high": high,
        "unvalued": sorted(unvalued),
        "first": book.first.isoformat() if book.first else None,
    }
    return {"summary": summary, "items": items}


def _icons(session: Session) -> dict[str, str]:
    """The symbol to show where the icon set names a coin differently (RENDER → RNDR)."""
    return dict(
        session.execute(
            select(PriceAsset.asset, PriceAsset.icon).where(PriceAsset.icon.is_not(None))
        ).all()
    )


# --- daily history -----------------------------------------------------------------------


def history(session: Session, currency: str = "EUR") -> list[dict]:
    """Value per day (UTC close): held quantity × that day's price. The high is the
    maximum of this series (ADR 0013)."""

    def make():
        book, _ = compute(session)
        valuer = Valuer(session)
        money = Money(valuer, currency)
        out = []
        if not book.days:
            return out
        today = money.today
        snaps = book.days
        flows = sorted(book.deposits, key=lambda x: x[0])
        i, j, d, deposited = 0, 0, snaps[0][0], ZERO
        while d <= today:
            while i + 1 < len(snaps) and snaps[i + 1][0] <= d:
                i += 1
            # each deposit at its own day's rate: the line moves only when money moves
            while j < len(flows) and flows[j][0] <= d:
                deposited += money(flows[j][1], flows[j][0]) or ZERO
                j += 1
            _, held, cost, _ = snaps[i]
            total = ZERO
            for asset, qty in held.items():
                price = valuer.eur(asset, d)
                if price is not None:
                    total += price * qty
            if money(total, d) is None:  # no exchange rate yet for that day
                d += timedelta(days=1)
                continue
            out.append(
                {
                    "day": d.isoformat(),
                    "value": _plain(money(total, d)),
                    "cost": _plain(money(cost, d)),
                    "deposited": _plain(deposited),
                }
            )
            d += timedelta(days=1)
        return out

    return _cached(session, f"history-{currency}", make)


def dca(session: Session, asset: str, currency: str = "EUR") -> list[dict]:
    """The coin's average buying price whenever it changed (a buy, a sale, a transfer in
    with its cost), in the display currency at today's rate — like the DCA on the holdings
    page; `value` None while none was held."""
    book, view = compute(session)
    money = Money(Valuer(session), currency)
    steps = book.avg.get(view.asset(asset.upper()) or asset.upper(), [])

    def shown(v: Decimal | None) -> str | None:
        m = money(v) if v is not None else None
        return None if m is None else _q(m.quantize(Decimal("1e-8")).normalize())

    return [{"day": d.isoformat(), "value": shown(v)} for d, v in steps]


def balance_at(
    session: Session, source_id: int, market: str, asset: str, at: datetime, skip: int | None = None
) -> Decimal:
    """What lay at a place at a moment, for the entry form (Vanixxx, 2026-10-11: "max. 44").
    `skip` leaves out the row being edited, so its own amount does not count."""
    book, view = compute(session)
    track = book.tracks.get((source_id, market, view.asset(asset.upper())), [])
    last = ZERO
    for when, qty, row in track:
        if when > at or row == skip:
            break  # the edited row: what lay there just before it
        last = qty
    return last


def auto_deposits(session: Session) -> dict[int, tuple[str, Decimal]]:
    """Row id → (fiat, amount) the app assumed paid in by card at that row."""
    book, _ = compute(session)
    return {rid: (asset, qty) for rid, (asset, qty, _) in book.auto_deposits.items()}


def balances_after(session: Session) -> dict[int, dict[str, tuple[Decimal, bool]]]:
    """Per raw row: the balance of each coin it moved at its place right after it, and
    whether that went below zero — so the transactions list can show where something is
    missing (Vanixxx, 2026-10-08). The same tolerance as the gap search."""
    book, _ = compute(session)
    out: dict[int, dict[str, tuple[Decimal, bool]]] = {}
    for (source_id, _market, asset), track in book.tracks.items():
        if source_id == OUTSIDE or not track:
            continue
        top = max((abs(q) for _, q, _ in track), default=ZERO)
        tol = max(Decimal("0.00000001"), top * Decimal("0.0001"))
        for _, q, rid in track:
            out.setdefault(rid, {})[asset] = (q, q < -tol)
    return out


# --- gap search --------------------------------------------------------------------------


def gaps(session: Session, currency: str = "EUR") -> list[dict]:
    """Where a place ran below zero, from when: "from here on something is missing"
    (ADR 0040). Plus coins whose balance differs without running negative."""
    book, _ = compute(session)
    valuer = Valuer(session)
    money = Money(valuer, currency)
    today = money.today
    out = []
    icons = _icons(session)
    seen: set[tuple[int, str, str]] = set()
    for place, track in book.tracks.items():
        source_id, market, asset = place
        if source_id == OUTSIDE or not track:
            continue
        top = max((abs(q) for _, q, _ in track), default=ZERO)
        tol = max(Decimal("0.00000001"), top * Decimal("0.0001"))
        first = next(((at, q, rid) for at, q, rid in track if q < -tol), None)
        if first is None:
            continue
        low = min(track, key=lambda t: t[1])
        price = valuer.latest_eur(asset, today)
        seen.add(place)
        out.append(
            {
                "type": "negative",
                "source_id": source_id,
                "market": market,
                "asset": asset,
                "icon": icons.get(asset, asset),
                "from": first[0].isoformat(),
                "row_id": first[2],
                "lowest": _q(low[1]),
                "lowest_at": low[0].isoformat(),
                "now": _q(track[-1][1]),
                "missing_value": _plain(money(-low[1] * price)) if price is not None else None,
                "points": _thin([(at.isoformat(), _q(q)) for at, q, _ in track]),
            }
        )
    for entry in reconcile(session):
        for item in entry["items"]:
            key = (entry["source_id"], item["market"], item["asset"])
            if item["ok"] is not False or item["spam"] or key in seen:
                continue
            price = valuer.latest_eur(item["asset"], today)
            diff = Decimal(item["diff"]) if item["diff"] else ZERO
            out.append(
                {
                    "type": "balance",
                    "source_id": entry["source_id"],
                    "market": item["market"],
                    "asset": item["asset"],
                    "icon": icons.get(item["asset"], item["asset"]),
                    "computed": item["computed"],
                    "actual": item["actual"],
                    "diff": item["diff"],
                    "missing_value": _plain(money(abs(diff) * price))
                    if price is not None
                    else None,
                    "points": _thin(
                        [(at.isoformat(), _q(q)) for at, q, _ in book.tracks.get(key, [])]
                    ),
                }
            )
    out.sort(key=lambda g: -(Decimal(g["missing_value"]) if g["missing_value"] else ZERO))
    return out


def _thin(points: list, keep: int = 160) -> list:
    if len(points) <= keep:
        return points
    step = len(points) / keep
    return [points[int(i * step)] for i in range(keep)] + [points[-1]]


# --- futures positions -------------------------------------------------------------------

_SIDE = re.compile(r"\b(long|short)\b", re.I)
_TIMES = (
    ("Opening time", "Closed time"),  # Bitget
    ("Open Time", "Close Time"),  # MEXC
    ("Position Opening Time(UTC+02:00)", ",Position Closing Time(UTC+02:00)"),  # KuCoin
)
_PRICES = (("Average entry price", "Average closing price"), ("Avg Entry Price", "Avg Close Price"))


def _num(text) -> Decimal | None:
    m = re.search(r"-?\d+(\.\d+)?", str(text or ""))
    return Decimal(m.group()) if m else None


def _position(r: RawTransaction) -> dict:
    raw = r.raw or {}
    opened = None
    for a, b in _TIMES:
        if a in raw and b in raw:
            try:
                span = datetime.fromisoformat(raw[b]) - datetime.fromisoformat(raw[a])
                opened = r.timestamp - span
            except ValueError:
                pass
            break
    side = raw.get("Direction") or raw.get("Close Type") or raw.get("Futures") or ""
    m = _SIDE.search(side.replace("_", " "))
    entry = exit_ = None
    for a, b in _PRICES:
        if a in raw:
            entry, exit_ = _num(raw.get(a)), _num(raw.get(b))
    return {
        "opened": opened or r.timestamp,
        "closed": r.timestamp,
        "side": m.group(1).lower() if m else None,
        "entry": entry,
        "exit": exit_,
    }


LOOSE_GAP = timedelta(days=1)
OPEN_WINDOW = timedelta(hours=36)


def futures_positions(session: Session, currency: str = "EUR") -> list[dict]:
    """Futures grouped per position: its results, funding and fees in the margin coin
    (ADR 0040). Flows outside any known position are grouped per contract."""
    _, view = compute(session)
    valuer = Valuer(session)
    money = Money(valuer, currency)
    rows = [r for r in view.rows.values() if r.market == "futures" and not view.is_spam(r)]
    positions = sorted((r for r in rows if r.kind == "futures_position"), key=lambda r: r.timestamp)
    groups = []
    for r in positions:
        groups.append({"row": r, **_position(r), "flows": []})
    loose: dict[tuple[int, str], list[RawTransaction]] = {}
    margin = timedelta(minutes=1)
    for r in rows:
        if r.kind not in ("realized_pnl", "funding", "fee"):
            continue
        home = next(
            (
                g
                for g in groups
                if g["row"].source_id == r.source_id
                and g["row"].instrument == r.instrument
                and g["opened"] - margin <= r.timestamp <= g["closed"] + margin
            ),
            None,
        )
        if home is not None:
            home["flows"].append(r)
        else:
            loose.setdefault((r.source_id, r.instrument or "?"), []).append(r)

    def sums(flows: list[RawTransaction]) -> dict:
        pnl = funding = fees = eur = ZERO
        coin = None
        for f in flows:
            amount = (f.incoming_amount or ZERO) - (f.outgoing_amount or ZERO)
            if f.kind == "funding":
                funding += amount
            elif f.kind == "fee":
                fees -= amount  # a fee booked as an outflow
            else:
                pnl += amount
            fees += f.fee_amount or ZERO
            coin = coin or view.asset(f.incoming_asset or f.outgoing_asset or f.fee_asset)
            for asset, qty in (
                (f.incoming_asset, f.incoming_amount),
                (f.outgoing_asset, -(f.outgoing_amount or ZERO)),
                (f.fee_asset, -(f.fee_amount or ZERO)),
            ):
                if asset and qty:
                    p = valuer.eur(view.asset(asset), f.timestamp.date())
                    eur += (p or ZERO) * qty
        result = pnl + funding - fees
        return {
            "coin": coin,
            "pnl": _q(pnl),
            "funding": _q(funding),
            "fees": _q(fees),
            "result": _q(result),
            "result_value": _plain(money(eur)),
            "result_eur": _plain(eur),  # for exports: converted once, by the caller
            "flows": len(flows),
            "row_ids": [f.id for f in flows],
        }

    out = []
    for g in groups:
        r = g["row"]
        out.append(
            {
                "id": r.id,
                "source_id": r.source_id,
                "instrument": r.instrument,
                "side": g["side"],
                "opened": g["opened"].isoformat(),
                "closed": g["closed"].isoformat(),
                "entry": _q(g["entry"]),
                "exit": _q(g["exit"]),
                "known": True,
                "open": False,
                **sums(g["flows"]),
                "row_ids": [r.id, *(f.id for f in g["flows"])],
            }
        )
    clusters = []
    for (source_id, instrument), flows in loose.items():
        flows.sort(key=lambda f: f.timestamp)
        # funding runs every few hours while a position is open: a day without any flow
        # means the position was closed, the next flow starts a new one
        current = [flows[0]]
        for f in flows[1:]:
            if f.timestamp - current[-1].timestamp > LOOSE_GAP:
                clusters.append((source_id, instrument, current))
                current = []
            current.append(f)
        clusters.append((source_id, instrument, current))
    for source_id, instrument, flows in clusters:
        out.append(
            {
                "id": None,
                "source_id": source_id,
                "instrument": instrument,
                "side": None,
                "opened": flows[0].timestamp.isoformat(),
                "closed": flows[-1].timestamp.isoformat(),
                "entry": None,
                "exit": None,
                "known": False,
                # funding comes every few hours while a position runs: a recent flow without
                # a closing position row means it is (very likely) still open
                "open": flows[-1].timestamp > datetime.now(UTC) - OPEN_WINDOW,
                **sums(flows),
            }
        )
    out.sort(key=lambda p: p["closed"], reverse=True)
    return out


# --- 5-minute values (M7) ----------------------------------------------------------------

TICK = timedelta(minutes=5)
FINE_DAYS, HOURLY_DAYS = 7, 90


def value_now(session: Session) -> Decimal | None:
    """Coins at the current price plus cash, in EUR; None while nothing is held or priced."""
    book, _ = compute(session)
    valuer = Valuer(session)
    today = datetime.now(UTC).date()
    total, priced = ZERO, False
    for asset, p in book.positions.items():
        if p.qty > 0:
            price = valuer.latest_eur(asset, today)
            if price is not None:
                total += price * p.qty
                priced = True
    return total if priced else None


def record_tick(session: Session, now: datetime | None = None) -> bool:
    """One value per 5-minute slot, then thinning: after 7 days the first of each hour
    stays, after 90 days none (the daily history covers it)."""
    now = now or datetime.now(UTC)
    slot = now.replace(second=0, microsecond=0) - timedelta(minutes=now.minute % 5)
    if session.scalar(
        select(func.count()).select_from(PortfolioTick).where(PortfolioTick.at >= slot)
    ):
        return False
    value = value_now(session)
    if value is None:
        return False
    session.add(PortfolioTick(at=slot, value=value))
    session.execute(
        delete(PortfolioTick).where(PortfolioTick.at < now - timedelta(days=HOURLY_DAYS))
    )
    session.execute(
        text(
            "delete from portfolio_tick t where t.at < :cut and exists ("
            "select 1 from portfolio_tick u where date_trunc('hour', u.at) = "
            "date_trunc('hour', t.at) and u.at < t.at)"
        ),
        {"cut": now - timedelta(days=FINE_DAYS)},
    )
    session.commit()
    return True


def ticks(session: Session, hours: int, currency: str = "EUR") -> list[dict]:
    """The stored values of the last `hours`, in the display currency (today's rate), plus
    the live value as the last point."""
    since = datetime.now(UTC) - timedelta(hours=hours)
    valuer = Valuer(session)
    money = Money(valuer, currency)
    rows = session.execute(
        select(PortfolioTick.at, PortfolioTick.value)
        .where(PortfolioTick.at >= since)
        .order_by(PortfolioTick.at)
    ).all()
    out = [{"at": at.isoformat(), "value": _plain(money(v))} for at, v in rows]
    live = value_now(session)
    if live is not None:
        out.append({"at": datetime.now(UTC).isoformat(), "value": _plain(money(live))})
    return out
