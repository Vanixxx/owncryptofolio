"""Statistics page (ADR 0043): fees, income, futures, activity and a comparison with
"everything in BTC", all in the display currency. Built on the portfolio pass and the
merged view; nothing is stored."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.modules.portfolio import service as portfolio
from app.modules.portfolio.engine import ZERO
from app.modules.prices.service import Valuer
from app.modules.raw import service as raw_service
from app.modules.settings import service as settings
from app.modules.tax.report import place_names


def _eur(v: Decimal | None) -> str | None:
    return None if v is None else f"{v.quantize(Decimal('0.01')):f}"


def compute(session: Session) -> dict:
    currency = settings.all_settings(session)["general.currency"]
    book, view = portfolio.compute(session)
    valuer = portfolio._cached(session, "valuer", lambda: Valuer(session))
    names = place_names(session)

    def money(eur: Decimal | None, day: date) -> Decimal:
        return valuer.in_currency(eur, day, currency) or ZERO

    def value(asset: str | None, qty: Decimal | None, day: date) -> Decimal:
        if not asset or not qty:
            return ZERO
        p = valuer.eur(view.asset(asset), day)
        return money(None if p is None else p * qty, day)

    fees: dict[tuple[int, int], Decimal] = defaultdict(Decimal)
    incomes: dict[tuple[str, str], Decimal] = defaultdict(Decimal)
    futures: dict[str, list[Decimal]] = defaultdict(lambda: [ZERO, ZERO, ZERO, ZERO])
    activity: dict[str, list] = defaultdict(lambda: [0, 0, ZERO, ZERO])
    for r in view.rows.values():
        if view.is_spam(r) or r.kind == "futures_position":
            continue
        day = r.timestamp.date()
        month = day.strftime("%Y-%m")
        if r.market == "futures" and r.kind in ("realized_pnl", "funding", "fee", "income"):
            e = futures[month]
            net = value(r.incoming_asset, r.incoming_amount, day) - value(
                r.outgoing_asset, r.outgoing_amount, day
            )
            fee = value(r.fee_asset, r.fee_amount, day)
            if r.kind == "funding":
                e[1] += net
            elif r.kind == "income" or (r.comment or "").strip().upper() == "BONUS":
                e[3] += net - fee
                fee = ZERO
            else:
                e[0] += net
            e[2] -= fee
            fees[(day.year, r.source_id)] += fee
            continue
        fee = value(r.fee_asset, r.fee_amount, day)
        if r.kind == "fee":
            fee += value(r.outgoing_asset, r.outgoing_amount, day)
        fees[(day.year, r.source_id)] += fee
        mark = view.marks.get(r.fingerprint)
        if r.kind == "income" or (mark is not None and mark.mark == "income"):
            kind = r.income_kind if r.kind == "income" else "reward"
            incomes[(month, kind or "reward")] += value(r.incoming_asset, r.incoming_amount, day)
        if r.kind == "trade" or (r.kind == "other" and r.incoming_asset and r.outgoing_asset):
            activity[month][0] += 1
        elif r.kind in ("send", "receive", "internal_transfer"):
            activity[month][1] += 1
    for d, v, _card in book.deposits:
        e = activity[d.strftime("%Y-%m")]
        if v >= 0:
            e[2] += money(v, d)
        else:
            e[3] -= money(v, d)

    positions = portfolio.futures_positions(session, currency)
    closed = [p for p in positions if not p["open"] and p["result_value"] is not None]
    wins = sum(1 for p in closed if Decimal(p["result_value"]) > 0)

    return {
        "currency": currency,
        "fees": [
            {"year": y, "place": names.get(s), "value": _eur(v)}
            for (y, s), v in sorted(fees.items())
            if v
        ],
        "incomes": [
            {"month": m, "kind": k, "value": _eur(v)} for (m, k), v in sorted(incomes.items()) if v
        ],
        "futures": {
            "months": [
                {
                    "month": m,
                    "pnl": _eur(e[0]),
                    "funding": _eur(e[1]),
                    "fees": _eur(e[2]),
                    "bonus": _eur(e[3]),
                    "net": _eur(sum(e, ZERO)),
                }
                for m, e in sorted(futures.items())
            ],
            "positions": len(closed),
            "wins": wins,
            "best": _eur(max((Decimal(p["result_value"]) for p in closed), default=None)),
            "worst": _eur(min((Decimal(p["result_value"]) for p in closed), default=None)),
        },
        "activity": [
            {
                "month": m,
                "trades": e[0],
                "transfers": e[1],
                "deposits": _eur(e[2]),
                "withdrawals": _eur(e[3]),
            }
            for m, e in sorted(activity.items())
        ],
        "benchmark": benchmark(book, valuer, currency, "BTC"),
        "spot": spot(session, currency, valuer),
        "health": health(session, view, book, currency),
    }


def spot(session: Session, currency: str, valuer: Valuer) -> dict:
    """The spot side (ADR 0043): totals from the portfolio (average cost), the sales one by
    one from the tax lots (the configured FIFO/LIFO) — how many came out ahead, the best and
    worst, per month (Berlin months, like the tax report)."""
    from app.modules.tax import report as tax
    from app.modules.tax.lots import local_day

    summary = portfolio.holdings(session, currency)["summary"]
    res = tax.compute(session, tax.params(session))
    sales: dict[int, list] = {}
    for d in res.disposals:
        if d.how != "trade" or d.gain is None:
            continue
        e = sales.setdefault(d.row, [local_day(d.sold), ZERO])
        e[1] += d.gain
    months: dict[str, Decimal] = defaultdict(Decimal)
    gains = []
    for day, gain in sales.values():
        g = valuer.in_currency(gain, day, currency) or ZERO
        months[day.strftime("%Y-%m")] += g
        gains.append(g)
    return {
        "realized": summary["realized"],
        "unrealized": summary["unrealized"],
        "income": summary["income"],
        "sales": len(gains),
        "wins": sum(1 for g in gains if g > 0),
        "best": _eur(max(gains, default=None)),
        "worst": _eur(min(gains, default=None)),
        "months": [{"month": m, "gain": _eur(v)} for m, v in sorted(months.items())],
    }


def health(session: Session, view, book, currency: str) -> list[dict]:
    """What makes the numbers less certain (ADR 0043), each with how many and where to fix it:
    gaps in the history, balances that differ, lines without counterpart, balances below
    zero, rows of kind "other" (often not assigned right), coins without price, card buys
    without euro, failed fetches."""
    from app.modules.balances.service import reconcile
    from app.modules.merged import service as merged
    from app.modules.portfolio.engine import card_purchase
    from app.modules.sources import service as sources

    items = merged.items(view)
    summary = merged.summary(view, items)
    after = portfolio.balances_after(session)
    short = sum(1 for bal in after.values() if any(neg for _, neg in bal.values()))
    rows = [r for r in view.rows.values() if not view.is_spam(r)]
    card = sum(1 for r in rows if card_purchase(r) and not r.outgoing_asset)
    other = sum(1 for r in rows if r.kind == "other" and not card_purchase(r))
    diffs = sum(e["differences"] for e in reconcile(session))
    return [
        {
            "key": "gaps",
            "count": len(portfolio.gaps(session, currency)),
            "to": "/holdings?tab=gaps",
        },
        {"key": "balances", "count": diffs, "to": "/sources"},
        {
            "key": "open",
            "count": summary["open"] + summary["ambiguous"],
            "to": "/transactions?show=open",
        },
        {"key": "short", "count": short, "to": "/transactions?show=short"},
        {"key": "other", "count": other, "to": "/transactions?kind=other"},
        # which coins: each name links to its price (Vanixxx, 2026-10-22)
        {
            "key": "unvalued",
            "count": len(book.unvalued),
            "to": "/prices",
            "assets": sorted(book.unvalued),
        },
        {"key": "card", "count": card, "to": "/transactions?show=card"},
        # rows a source delivered again with other values (Vanixxx, 2026-10-23)
        {"key": "changed", "count": len(raw_service.changes(session)), "to": "/sources#changes"},
        {"key": "fetch", "count": len(sources.alerts(session)), "to": "/sources"},
    ]


def benchmark(book, valuer: Valuer, currency: str, asset: str) -> list[dict]:
    """ "Had everything gone into BTC": every deposit buys BTC at that day's price, every
    withdrawal sells it; the value per day in the display currency (ADR 0043)."""
    flows: dict[date, Decimal] = defaultdict(Decimal)
    for d, v, _card in book.deposits:
        flows[d] += v
    if not flows:
        return []
    day, end = min(flows), datetime.now(UTC).date()
    qty = waiting = ZERO
    out = []
    while day <= end:
        price = valuer.eur(asset, day)
        waiting += flows.get(day, ZERO)
        if price:
            # a deposit on a day without a price buys on the next day with one
            qty += waiting / price
            waiting = ZERO
            qty = max(qty, ZERO)
            out.append(
                {
                    "day": day.isoformat(),
                    "value": _eur(valuer.in_currency(qty * price, day, currency)),
                }
            )
        day += timedelta(days=1)
    return out
