"""The portfolio pass (ADR 0040): one walk in time over the merged view, every coin pooled
over all sources with its average cost in EUR.

    buy 1 BTC for 30,000 €      qty 1    cost 30,000
    sell 0.5 BTC for 20,000 €   qty 0.5  cost 15,000   realized +5,000

Everything here is derived: nothing is stored, every correction counts at once.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal

from app.modules.merged.service import View
from app.modules.raw.models import RawTransaction

FIAT = frozenset({"EUR", "USD"})
ZERO = Decimal(0)
OUTSIDE = 0
"""Place id of coins in an own wallet owncryptofolio does not know (marked by Vanixxx)."""

Place = tuple[int, str, str]  # source id (OUTSIDE), market, asset


@dataclass
class Position:
    qty: Decimal = ZERO
    cost: Decimal = ZERO
    """EUR paid for what is held now, fees included."""
    realized: Decimal = ZERO
    sold_cost: Decimal = ZERO
    """Cost of what was sold: the base of realized % (ADR 0013)."""
    income: Decimal = ZERO
    since: datetime | None = None
    """Start of the current holding: the last time it rose from zero."""
    unclear_qty: Decimal = ZERO
    unclear_value: Decimal = ZERO
    open_qty: Decimal = ZERO
    open_value: Decimal = ZERO


@dataclass
class Futures:
    pnl: Decimal = ZERO
    funding: Decimal = ZERO
    fees: Decimal = ZERO

    @property
    def result(self) -> Decimal:
        return self.pnl + self.funding - self.fees


@dataclass
class Book:
    positions: dict[str, Position] = field(default_factory=lambda: defaultdict(Position))
    places: dict[Place, Decimal] = field(default_factory=lambda: defaultdict(Decimal))
    tracks: dict[Place, list[tuple[datetime, Decimal, int]]] = field(
        default_factory=lambda: defaultdict(list)
    )
    """Quantity after every movement per place (row id last): the gap search reads it."""
    transit: dict[str, tuple[Decimal, Decimal]] = field(default_factory=dict)
    futures: Futures = field(default_factory=Futures)
    net_deposited: Decimal = ZERO
    card_deposits: Decimal = ZERO
    deposits: list[tuple[date, Decimal, bool]] = field(default_factory=list)
    """Every deposit (+) and withdrawal (−) in EUR with its day, card purchases marked: shown
    in USD each converts at its own day, so the line does not move with the exchange rate."""
    """Fiat spent that never arrived in the data: money straight from the bank."""
    income: Decimal = ZERO
    external_in: Decimal = ZERO
    auto_deposits: dict[int, tuple[str, Decimal, Decimal]] = field(default_factory=dict)
    """Row id → (fiat, amount, EUR value) of money assumed paid in by card because the row
    spent more than was there: shown at the line (Vanixxx, 2026-10-09)."""
    unvalued: set[str] = field(default_factory=set)
    days: list[tuple[date, dict[str, Decimal], Decimal, Decimal]] = field(default_factory=list)
    """End of every day with movements: held quantities, cost of the coins, net deposited."""
    avg: dict[str, list[tuple[date, Decimal | None]]] = field(
        default_factory=lambda: defaultdict(list)
    )
    """The average buying price (EUR) per coin whenever it changed, None while none is held:
    the DCA as a line through time (Vanixxx, 2026-10-08)."""
    first: datetime | None = None


PAID_FROM_OUTSIDE = ("paid by card", "paid by paypal")
"""How readers mark a trade paid by card or PayPal, not from money at the exchange."""
CARD_PURCHASES = ("buy with card",)
"""How exchanges name a coin bought with a bank card, where they deliver only the coin."""


def paid_by_card(r) -> bool:
    """The entry says the trade was paid by card (form checkbox), whatever lay there."""
    if (r.comment or "").lower().startswith(PAID_FROM_OUTSIDE):
        return True  # a reader says so: Coinbase "Paid by card" / "Paid by PayPal"
    if r.channel != "manual":
        return False
    return bool(((r.raw or {}).get("manual") or {}).get("paid_by_card"))


def card_purchase(r) -> bool:
    text = (r.comment or "").lower()
    return any(c in text for c in CARD_PURCHASES)


class Engine:
    def __init__(self, view: View, valuer) -> None:
        self.view, self.valuer, self.book = view, valuer, Book()

    # --- prices --------------------------------------------------------------------------

    def price(self, asset: str, at: datetime) -> Decimal | None:
        p = self.valuer.eur(asset, at.date())
        if p is None:
            self.book.unvalued.add(asset)
        return p

    def value(self, asset: str, qty: Decimal, at: datetime) -> Decimal | None:
        p = self.price(asset, at)
        return None if p is None else p * qty

    def deposit(self, at: datetime, v: Decimal, card: bool = False) -> None:
        self.book.net_deposited += v
        if card:
            self.book.card_deposits += v
        self.book.deposits.append((at.date(), v, card))

    # --- the two primitives --------------------------------------------------------------

    def _auto(self, row: int, asset: str, qty: Decimal, value: Decimal) -> None:
        _, q, v = self.book.auto_deposits.get(row, (asset, ZERO, ZERO))
        self.book.auto_deposits[row] = (asset, q + qty, v + value)

    def _place(self, place: Place, delta: Decimal, at: datetime, row: int) -> None:
        self.book.places[place] += delta
        self.book.tracks[place].append((at, self.book.places[place], row))

    def gain(self, asset: str, qty: Decimal, cost: Decimal, at: datetime, place: Place, row: int):
        if qty <= 0:
            return
        p = self.book.positions[asset]
        if p.qty <= 0:
            p.since = at
        p.qty += qty
        p.cost += cost
        self._place(place, qty, at, row)

    def take(
        self,
        asset: str,
        qty: Decimal,
        at: datetime,
        place: Place | None,
        row: int,
        keep_cost=False,
        by_card=False,
    ) -> tuple[Decimal, Decimal]:
        """Takes qty out. Returns (cost of the covered part, covered qty). What exceeds the
        holding is no gain: unclear for a coin, money from the bank for fiat (ADR 0040).
        `keep_cost` is a fee: the rest carries its cost. `place=None` leaves the places."""
        if qty <= 0:
            return ZERO, ZERO
        p = self.book.positions[asset]
        # Money counts per place: euro spent where there were none came straight from the
        # bank (a card), a deposit — it never runs below zero there and never uses euro lying
        # at another exchange (MEXC card buys, Vanixxx 2026-10-09). A card buy is paid wholly by
        # card, never part from the balance: when the money there does not cover it, all of it
        # came by card and the balance stays (2026-10-10) — and so when the entry says so.
        if (
            asset in FIAT
            and place is not None
            and (by_card or qty > max(self.book.places[place], ZERO))
        ):
            v = self.value(asset, qty, at) or ZERO
            self.deposit(at, v, card=True)
            self._auto(row, asset, qty, v)
            p.qty += qty
            p.cost += v
            self._place(place, qty, at, row)
        if place is not None:
            self._place(place, -qty, at, row)
        covered = min(qty, max(p.qty, ZERO))
        short = qty - covered
        part = p.cost * covered / p.qty if p.qty > 0 else ZERO
        p.qty -= covered
        if not keep_cost:
            p.cost -= part
        elif p.qty > 0:
            part = ZERO
        else:
            p.realized -= p.cost  # nothing left to carry the fee: it is a loss
            part = ZERO
        if p.qty <= 0:
            p.cost = ZERO
        if short > 0:
            if asset in FIAT:
                v = self.value(asset, short, at) or ZERO
                self.deposit(at, v, card=True)
                self._auto(row, asset, short, v)
            else:
                p.unclear_qty += short
                p.unclear_value += self.value(asset, short, at) or ZERO
        return part, covered

    # --- the walk ------------------------------------------------------------------------

    def run(self, today: date) -> Book:
        v = self.view
        pair_of = {}
        for p in v.pairs:
            pair_of[p.send] = p
            pair_of[p.receive] = p
        done: set[str] = set()
        rows = sorted(
            (r for r in v.rows.values() if not v.is_spam(r)), key=lambda r: (r.timestamp, r.id)
        )
        day = None
        for r in rows:
            if r.fingerprint in done:
                continue
            d = r.timestamp.date()
            if day is not None and d != day:
                self._close_day(day)
            day = d
            if self.book.first is None:
                self.book.first = r.timestamp
            if r.fingerprint in v.extras:
                self.extra_fee(r)
                continue
            pair = pair_of.get(r.fingerprint)
            if pair is not None:
                done |= {pair.send, pair.receive}
                self.transfer(v.by_fp[pair.send], v.by_fp[pair.receive])
            else:
                self.row(r)
        if day is not None:
            self._close_day(day)
        return self.book

    def _close_day(self, d: date) -> None:
        held = {a: p.qty for a, p in self.book.positions.items() if p.qty > 0}
        cost = sum((p.cost for a, p in self.book.positions.items() if a not in FIAT), ZERO)
        if self.book.days and self.book.days[-1][0] == d:
            self.book.days.pop()
        self.book.days.append((d, held, cost, self.book.net_deposited))
        for a, p in self.book.positions.items():
            if a in FIAT:
                continue
            avg = p.cost / p.qty if p.qty > 0 else None
            steps = self.book.avg[a]
            if steps and steps[-1][0] == d:
                steps.pop()
            if not steps or steps[-1][1] != avg:
                steps.append((d, avg))

    def _a(self, asset: str | None) -> str | None:
        return self.view.asset(asset)

    def fee(self, r: RawTransaction, place: Place) -> None:
        if r.fee_asset and r.fee_amount:
            self.take(
                self._a(r.fee_asset),
                r.fee_amount,
                r.timestamp,
                (*place[:2], self._a(r.fee_asset)),
                r.id,
                keep_cost=True,
            )

    def transfer(self, s: RawTransaction, r: RawTransaction) -> None:
        """Moves the coin with its cost; sent minus arrived is the network fee (ADR 0039)."""
        asset = self._a(s.outgoing_asset)
        at = s.timestamp
        sent, arrived = s.outgoing_amount or ZERO, r.incoming_amount or ZERO
        self._place((s.source_id, s.market, asset), -sent, at, s.id)
        self._place((r.source_id, r.market, asset), arrived, r.timestamp, r.id)
        diff = sent - arrived
        if diff > 0:  # the places moved already; the pooled holding pays the fee
            self.take(asset, diff, at, None, r.id, keep_cost=True)
        elif diff < 0:
            self.book.positions[asset].qty -= diff
        self.fee(s, (s.source_id, s.market, asset))
        self.fee(r, (r.source_id, r.market, asset))

    def extra_fee(self, r: RawTransaction) -> None:
        """A booking attached to a transfer is its fee: the coins leave, the cost stays with
        the rest (like the network fee), no gain and no open send."""
        for asset, qty in ((r.outgoing_asset, r.outgoing_amount), (r.fee_asset, r.fee_amount)):
            if asset and qty:
                a = self._a(asset)
                self.take(a, qty, r.timestamp, (r.source_id, r.market, a), r.id, keep_cost=True)

    def row(self, r: RawTransaction) -> None:
        k, at = r.kind, r.timestamp
        ia, oa = self._a(r.incoming_asset), self._a(r.outgoing_asset)
        iq, oq = r.incoming_amount or ZERO, r.outgoing_amount or ZERO
        here = (r.source_id, r.market)
        if k == "futures_position":
            return
        if r.market == "futures" and k in ("realized_pnl", "funding", "fee"):
            self.futures(r)
            return
        if k == "trade" or (k == "other" and ia and oa):
            self.trade(r)
            return
        if k == "migration":
            part, _ = self.take(oa, oq, at, (*here, oa), r.id) if oa else (ZERO, ZERO)
            if ia:
                self.gain(ia, iq, part, at, (*here, ia), r.id)
        elif k == "internal_transfer":
            if oa:
                part, covered = self.take(oa, oq, at, (*here, oa), r.id)
                q, c = self.book.transit.get(oa, (ZERO, ZERO))
                self.book.transit[oa] = (q + covered, c + part)
            if ia:
                q, c = self.book.transit.get(ia, (ZERO, ZERO))
                use = min(q, iq)
                cost = c * use / q if q > 0 else ZERO
                self.book.transit[ia] = (q - use, c - cost)
                rest = iq - use
                if rest > 0:
                    cost += self.value(ia, rest, at) or ZERO
                self.gain(ia, iq, cost, at, (*here, ia), r.id)
        elif oa in FIAT and not ia and k in ("send", "other"):
            # and fiat leaving without counter side is a withdrawal — unless it is lost
            # (a scam exchange, Cryptex 2026-10-11): then nothing came back, the money
            # paid in stays paid in and the loss shows in the result
            v = self.value(oa, oq, at) or ZERO
            self.take(oa, oq, at, (*here, oa), r.id)
            mark = self.view.marks.get(r.fingerprint)
            if mark is None or mark.mark != "lost":
                self.deposit(at, -v)
        elif k == "send" or (k == "other" and oa):
            self.send(r)
            return
        elif k in ("receive", "income", "fiat_deposit", "other"):
            mark = self.view.marks.get(r.fingerprint) if k == "receive" else None
            outside = (OUTSIDE, "spot", ia)
            own = mark is not None and mark.mark == "own_untracked" and ia
            if own and self.book.places[outside] >= iq:
                # back from an own wallet that is not set up here: no new coins. Without
                # coins sent there first, they count as coming from outside (cost unknown)
                self._place(outside, -iq, at, r.id)
                self._place((*here, ia), iq, at, r.id)
                self.fee(r, (*here, ia))
                return
            if mark is not None and mark.mark == "income":
                k = "income"  # rewards for tasks and the like (Vanixxx, 2026-10-11)
            if ia:
                v = self.value(ia, iq, at)
                self.gain(ia, iq, v or ZERO, at, (*here, ia), r.id)
                if k == "income":
                    self.book.positions[ia].income += v or ZERO
                    self.book.income += v or ZERO
                elif ia in FIAT:
                    # Euro or dollars coming in without a counter side are a deposit, however
                    # the exchange names it (Bitget leaves the type empty, 2026-10-04)
                    self.deposit(at, v or ZERO)
                elif card_purchase(r) or (mark is not None and mark.mark == "bought"):
                    # bought with a card: money paid in, not a coin from nowhere (Bitget
                    # "Buy with card" has no euro side; 4,246 € counted as gain, 2026-10-08)
                    self.deposit(at, v or ZERO, card=True)
                else:
                    self.book.external_in += v or ZERO
        elif k == "fiat_withdrawal":
            if oa:
                v = self.value(oa, oq, at) or ZERO
                self.take(oa, oq, at, (*here, oa), r.id)
                if oa in FIAT:
                    self.deposit(at, -v)
        self.fee(r, (*here, ia or oa or ""))

    def send(self, r: RawTransaction) -> None:
        at, oa, oq = r.timestamp, self._a(r.outgoing_asset), r.outgoing_amount or ZERO
        here = (r.source_id, r.market, oa)
        mark = self.view.marks.get(r.fingerprint)
        self.fee(r, here)
        if mark is not None and mark.mark == "own_untracked":
            self._place(here, -oq, at, r.id)
            self._place((OUTSIDE, "spot", oa), oq, at, r.id)
            return
        v = self.value(oa, oq, at)
        part, covered = self.take(oa, oq, at, here, r.id)
        p = self.book.positions[oa]
        if mark is not None and mark.mark == "external" and oa not in FIAT and v is not None:
            proceeds = v * covered / oq if oq else ZERO
            p.realized += proceeds - part
            p.sold_cost += part
        elif mark is not None and mark.mark == "lost" and oa not in FIAT:
            # gone for good (a provider gone bust): nothing came back, the cost is the loss
            p.realized -= part
            p.sold_cost += part
        elif mark is None:
            p.open_qty += covered
            p.open_value += (v or ZERO) * covered / oq if oq else ZERO

    def trade(self, r: RawTransaction) -> None:
        at = r.timestamp
        ia, oa = self._a(r.incoming_asset), self._a(r.outgoing_asset)
        iq, oq = r.incoming_amount or ZERO, r.outgoing_amount or ZERO
        here = (r.source_id, r.market)
        # the value of the trade: the fiat side is exact, else what can be valued
        if oa in FIAT:
            worth = self.value(oa, oq, at)
        elif ia in FIAT:
            worth = self.value(ia, iq, at)
        else:
            worth = self.value(oa, oq, at) if oa else None
            if worth is None and ia:
                worth = self.value(ia, iq, at)
        part = ZERO
        if oa:
            part, covered = self.take(oa, oq, at, (*here, oa), r.id, by_card=paid_by_card(r))
            if oa not in FIAT and worth is not None and oq:
                p = self.book.positions[oa]
                p.realized += worth * covered / oq - part
                p.sold_cost += part
        cost = worth if worth is not None else part
        fa, fq = self._a(r.fee_asset), r.fee_amount or ZERO
        if ia:
            self.gain(ia, iq, cost, at, (*here, ia), r.id)
        if fa and fq:
            if fa == ia:
                # Bitget charges in the bought coin: booked after the gain (ADR 0040)
                self.take(fa, fq, at, (*here, fa), r.id, keep_cost=True)
                if ia in FIAT and oa and oa not in FIAT:
                    # a sale whose fee comes off the money received: the fee lowers the gain,
                    # as in the tax report (review 2026-10-24)
                    self.book.positions[oa].realized -= self.value(fa, fq, at) or ZERO
            else:
                # paid by card or PayPal: the fee in that money came the same way
                fee_cost, _ = self.take(
                    fa, fq, at, (*here, fa), r.id, by_card=paid_by_card(r) and fa in FIAT
                )
                if fa in FIAT:
                    fee_cost = self.value(fa, fq, at) or ZERO
                if ia and ia not in FIAT:
                    self.book.positions[ia].cost += fee_cost
                elif oa:
                    self.book.positions[oa].realized -= fee_cost

    def futures(self, r: RawTransaction) -> None:
        """Results, funding and fees of the futures account are real flows of the margin
        coin (ADR 0029), counted apart from the spot result."""
        at, here = r.timestamp, (r.source_id, r.market)
        f = self.book.futures
        ia, oa, fa = self._a(r.incoming_asset), self._a(r.outgoing_asset), self._a(r.fee_asset)
        # a fee booked as an outflow is a fee, not a loss (as in the tax report)
        attr = "funding" if r.kind == "funding" else "fees" if r.kind == "fee" else "pnl"
        if ia and r.incoming_amount:
            v = self.value(ia, r.incoming_amount, at) or ZERO
            self.gain(ia, r.incoming_amount, v, at, (*here, ia), r.id)
            setattr(f, attr, getattr(f, attr) + v)
        if oa and r.outgoing_amount:
            v = self.value(oa, r.outgoing_amount, at) or ZERO
            self.take(oa, r.outgoing_amount, at, (*here, oa), r.id)
            setattr(f, attr, getattr(f, attr) - v)
        if fa and r.fee_amount:
            v = self.value(fa, r.fee_amount, at) or ZERO
            self.take(fa, r.fee_amount, at, (*here, fa), r.id)
            f.fees += v
