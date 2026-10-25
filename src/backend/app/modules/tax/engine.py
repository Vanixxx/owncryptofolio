"""The tax pass (ADR 0042): one walk in time over the merged view, the same cases as the
portfolio pass, with lots per place instead of an average.

    buy 1 BTC for 30,000 € (Jan 2024)     lot 1 BTC, 30,000, 2024-01
    sell 0.5 BTC for 20,000 € (Mar 2024)  disposal: proceeds 20,000, cost 15,000, taxable

What it yields are tax events; sums per year are `report`'s job.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field, replace
from datetime import datetime
from decimal import Decimal

from app.modules.merged.service import View
from app.modules.portfolio.engine import OUTSIDE, card_purchase, paid_by_card
from app.modules.raw.models import RawTransaction
from app.modules.tax.lots import DUST, ZERO, Lot, Lots, Method, Piece, Place, local_day, tax_free
from app.modules.tax.trace import Trace

BANK = frozenset({"EUR", "USD"})
"""Money that can come straight from the bank: spent without a lot, it was paid in then
(a card), at its value — no gain, nothing unclear."""
TAXED_INCOME = frozenset({"staking", "reward", "interest"})


@dataclass
class Params:
    method: Method = Method.FIFO
    money: frozenset[str] = frozenset({"EUR"})
    """Spending these is no disposal and they hold no lots (default EUR)."""
    airdrop_taxable: bool = False
    trace: bool = False
    """Also trace the source of funds (ADR 0046): only for that view, the tax is the same."""


@dataclass
class Disposal:
    """A sale as far as it hits ONE lot: the tax unit — one sale can touch a lot past the
    holding period and one inside it."""

    asset: str
    source: int
    sold: datetime
    acquired: datetime
    qty: Decimal
    proceeds: Decimal | None
    cost: Decimal
    tax_free: bool
    estimated: bool
    row: int
    how: str
    """trade · external (paid to others) · fee (paid in coin) · futures (spent by the
    futures account)"""
    origin: int = 0
    """The row that bought the lot."""

    @property
    def gain(self) -> Decimal | None:
        return None if self.proceeds is None else self.proceeds - self.cost

    @property
    def days(self) -> int:
        return (local_day(self.sold) - local_day(self.acquired)).days


@dataclass
class Income:
    """§ 22 Nr. 3 EStG: its own pot with its own limit."""

    asset: str
    source: int
    at: datetime
    qty: Decimal
    value: Decimal | None
    kind: str
    row: int


@dataclass
class Loss:
    """Lost for good (insolvency, scam; mark 'lost'): listed apart, never netted (ADR 0042)."""

    asset: str
    source: int
    at: datetime
    acquired: datetime | None
    qty: Decimal
    cost: Decimal | None
    row: int
    origin: int = 0


@dataclass
class Uncovered:
    """A quantity without a lot: shown with its share of the proceeds, without cost — that
    is unknown, not zero — and not netted."""

    asset: str
    source: int
    at: datetime
    qty: Decimal
    proceeds: Decimal | None
    reason: str
    row: int


@dataclass
class FuturesFlow:
    """§ 20 EStG: results, funding and fees of the futures account in EUR."""

    source: int
    at: datetime
    kind: str  # pnl · funding · fee
    asset: str
    amount: Decimal
    """Signed: + received, − paid."""
    value: Decimal | None
    row: int


@dataclass
class Result:
    disposals: list[Disposal] = field(default_factory=list)
    incomes: list[Income] = field(default_factory=list)
    losses: list[Loss] = field(default_factory=list)
    uncovered: list[Uncovered] = field(default_factory=list)
    futures: list[FuturesFlow] = field(default_factory=list)
    open_sends: list[Uncovered] = field(default_factory=list)
    """Sends without a counter side and without a mark: the lots moved outside."""
    year_end: dict[int, list[tuple[Place, Lot]]] = field(default_factory=dict)
    lots: Lots | None = None
    unvalued: set[str] = field(default_factory=set)
    trace: Trace | None = None
    created: dict[int, list[Lot]] = field(default_factory=lambda: defaultdict(list))
    """Lots a row started, as they were then."""
    moved: dict[int, list[Piece]] = field(default_factory=lambda: defaultdict(list))
    """Lots a transfer, rebooking or migration carried, with their day and cost."""


class Engine:
    def __init__(self, view: View, valuer, params: Params) -> None:
        self.view, self.valuer, self.p = view, valuer, params
        self.lots = Lots(params.method)
        self.trace = Trace() if params.trace else None
        self.settled: dict[int, Decimal] = {}
        """Of a stand-in lot's node: how much the real lots arriving later covered."""
        self.out = Result(lots=self.lots, trace=self.trace)
        self.transit: dict[tuple[int, str], list[Piece]] = defaultdict(list)
        self.owed: dict[tuple[int, str], list[tuple[Place, Lot]]] = defaultdict(list)
        self.current = 0
        """The row being booked: lots it starts carry it as their origin."""

    # --- prices --------------------------------------------------------------------------

    def value(self, asset: str | None, qty: Decimal | None, at: datetime) -> Decimal | None:
        if not asset or not qty:
            return ZERO if asset else None
        price = self.valuer.eur(asset, at.date())
        if price is None:
            self.out.unvalued.add(asset)
            return None
        return price * qty

    def _a(self, asset: str | None) -> str | None:
        return self.view.asset(asset)

    def money(self, asset: str | None) -> bool:
        return asset in self.p.money

    # --- primitives ----------------------------------------------------------------------

    def acquire(
        self, place: Place, qty: Decimal, cost: Decimal | None, at, estimated=False, parts=None
    ):
        if qty <= 0:
            return
        if self.money(place[2]):
            if self.trace is not None:  # euro: into the pot of the source, with their origin
                amount = cost if cost is not None else qty
                parts = parts or self._leaf("money_unknown", place, qty, amount, at)
                self.trace.pot_add(place[0], place[2], amount, parts)
            return
        if self.trace is not None and not parts:
            parts = self._leaf("unknown", place, qty, cost, at)
        lot = Lot(
            place[2],
            qty,
            at,
            cost or ZERO,
            estimated or cost is None,
            self.current,
            parts=parts or (),
        )
        self.lots.add(place, lot)
        self.out.created[self.current].append(replace(lot))

    # --- source of funds (ADR 0046) ------------------------------------------------------

    def _leaf(self, kind: str, place: Place, qty, value, at, detail=None):
        if self.trace is None:
            return ()
        return self.trace.leaf(kind, self.current, at, place[0], place[2], qty, value, detail)

    def _from(self, pieces: list[Piece], worth) -> list[tuple[int, Decimal]]:
        """Parents of a step from the lots it took, weighted by cost — a lot without cost
        (an untaxed airdrop) by its share of the value instead, else it would vanish."""
        out: list[tuple[int, Decimal]] = []
        for p in pieces:
            w = p.cost if p.cost > 0 else (worth(p.qty) or ZERO)
            out += Trace.spread(p.parts, w)
        return out

    def _main(self, row: int, node) -> None:
        if self.trace is not None:
            self.trace.by_row[row] = node.id

    def carried(self, pieces: list[Piece]) -> None:
        self.out.moved[self.current].extend(replace(p) for p in pieces)

    def dispose(
        self,
        place: Place,
        qty: Decimal,
        proceeds: Decimal | None,
        at: datetime,
        row: int,
        how: str,
        by_card: bool = False,
    ) -> int | None:
        """Splits a sale over the lots it takes. The proceeds go by quantity over the SOLD
        quantity, not the covered one — else the shares always add up to 1 however little
        was covered (the costliest bug of the old tax part, 2026-09-03)."""
        asset = place[2]
        if self.money(asset) or qty <= 0:
            return None
        if by_card and asset in BANK:
            return None  # paid straight from the bank: the dollars never lay there
        pieces, short = self.lots.take(place, qty)

        def share(q: Decimal) -> Decimal | None:
            return None if proceeds is None else proceeds * q / qty

        node = None
        if self.trace is not None:
            parents = self._from(pieces, share)
            if short and share(short):
                parents += Trace.spread(
                    self._leaf("unknown", place, short, share(short), at), share(short)
                )
            basis = sum((w for _, w in parents), ZERO)
            worth = proceeds if proceeds is not None else basis
            if worth > basis:
                gain = worth - basis
                parents += Trace.spread(self._leaf("gain", place, qty, gain, at), gain)
            elif basis > worth:
                # a loss shows as such, a negative share — not hidden in smaller origins
                # (as Blockpit shows it, Vanixxx 2026-10-18)
                loss = basis - worth
                parents.append((self._leaf("loss", place, qty, loss, at)[0][0], -loss))
            kind = "payment" if how == "external" else "sale"
            node = self.trace.add(kind, row, at, place[0], asset, qty, worth, parents)
            if how in ("trade", "external"):
                self._main(row, node)

        for p in pieces:
            self.out.disposals.append(
                Disposal(
                    asset,
                    place[0],
                    at,
                    p.acquired,
                    p.qty,
                    share(p.qty),
                    p.cost,
                    tax_free(p.acquired, at),
                    p.estimated,
                    row,
                    how,
                    p.origin,
                )
            )
        if short and asset not in BANK:
            self.out.uncovered.append(
                Uncovered(asset, place[0], at, short, share(short), "no_lot", row)
            )
        return None if node is None else node.id

    def move(self, src: Place, dst: Place, sent: Decimal, arrived: Decimal, at, row) -> None:
        """No tax event: each lot moves with its day and full cost; a network fee in the coin
        lowers the quantity only. What no lot covered arrives as an estimated lot."""
        if sent <= 0:
            return
        if self.money(src[2]):
            if self.trace is not None:  # euro between sources keep their origin
                taken, short = self.trace.pot_take(src[0], src[2], sent)
                if short:
                    taken += Trace.spread(self._leaf("money_unknown", src, short, short, at), short)
                node = self.trace.add("transfer", row, at, src[0], src[2], sent, sent, taken)
                node.to_source = dst[0]
                self._main(row, node)
                self.trace.pot_add(dst[0], dst[2], arrived, ((node.id, Decimal(1)),))
            return
        pieces, short = self.lots.take(src, sent)
        factor = arrived / sent
        if self.trace is not None:
            parents = self._from(pieces, lambda q: self.value(src[2], q, at))
            worth = sum((w for _, w in parents), ZERO)
            node = self.trace.add("transfer", row, at, src[0], src[2], sent, worth, parents)
            node.to_source = dst[0]
            self._main(row, node)
            pieces = [replace(p, parts=((node.id, Decimal(1)),)) for p in pieces]
        self.lots.put(dst, pieces, factor)
        self.carried(pieces)
        if short and src[2] not in BANK:
            self.out.uncovered.append(Uncovered(src[2], src[0], at, short, None, "transfer", row))
            self.acquire(dst, short * factor, self.value(dst[2], short * factor, at), at, True)
        elif short:
            self.acquire(dst, short * factor, self.value(dst[2], short * factor, at), at)

    # --- the walk ------------------------------------------------------------------------

    def run(self) -> Result:
        v = self.view
        pair_of = {}
        for p in v.pairs:
            pair_of[p.send] = p
            pair_of[p.receive] = p
        done: set[str] = set()
        rows = sorted(
            (r for r in v.rows.values() if not v.is_spam(r)), key=lambda r: (r.timestamp, r.id)
        )
        year = None
        for r in rows:
            if r.fingerprint in done:
                continue
            y = local_day(r.timestamp).year
            if year is not None and y != year:
                for past in range(year, y):
                    self.out.year_end[past] = self.lots.snapshot()
            year = y
            self.current = r.id
            if r.fingerprint in v.extras:
                self.extra_fee(r)
                continue
            pair = pair_of.get(r.fingerprint)
            if pair is not None:
                done |= {pair.send, pair.receive}
                self.transfer(v.by_fp[pair.send], v.by_fp[pair.receive])
            else:
                self.row(r)
        if year is not None:
            self.out.year_end[year] = self.lots.snapshot()
        self._unsettled()
        return self.out

    def network_fee(self, r: RawTransaction, place: Place) -> None:
        """The fee field of a transfer or a booking without trade: the coin leaves, its cost
        stays with the rest there."""
        if r.fee_asset and r.fee_amount:
            fa = self._a(r.fee_asset)
            if not self.money(fa):
                self.lots.shrink((place[0], place[1], fa), r.fee_amount)

    def transfer(self, s: RawTransaction, r: RawTransaction) -> None:
        asset = self._a(s.outgoing_asset)
        sent, arrived = s.outgoing_amount or ZERO, r.incoming_amount or ZERO
        src, dst = (s.source_id, s.market, asset), (r.source_id, r.market, asset)
        self.network_fee(s, src)
        if arrived > sent:  # more arrived than left: the extra has no lot
            self.move(src, dst, sent, sent, s.timestamp, s.id)
            extra = arrived - sent
            self.acquire(dst, extra, self.value(asset, extra, r.timestamp), r.timestamp, True)
        else:
            self.move(src, dst, sent, arrived, s.timestamp, s.id)
        if self.trace is not None and s.id in self.trace.by_row:
            self.trace.by_row[r.id] = self.trace.by_row[s.id]
            self.trace.nodes[self.trace.by_row[s.id]].row_in = r.id
        self.network_fee(r, dst)

    def extra_fee(self, r: RawTransaction) -> None:
        for asset, qty in ((r.outgoing_asset, r.outgoing_amount), (r.fee_asset, r.fee_amount)):
            if asset and qty and not self.money(self._a(asset)):
                self.lots.shrink((r.source_id, r.market, self._a(asset)), qty)

    def row(self, r: RawTransaction) -> None:
        k, at = r.kind, r.timestamp
        ia, oa = self._a(r.incoming_asset), self._a(r.outgoing_asset)
        iq, oq = r.incoming_amount or ZERO, r.outgoing_amount or ZERO
        here = (r.source_id, r.market)
        mark = self.view.marks.get(r.fingerprint)
        m = mark.mark if mark is not None else None
        if k == "futures_position":
            return
        if r.market == "futures" and k in ("realized_pnl", "funding", "fee", "income"):
            self.futures(r)
            return
        if k == "trade" or (k == "other" and ia and oa):
            self.trade(r)
            return
        if k == "migration":
            # a new name for the same holding: day and cost carry over (Vanixxx, 2026-10-11)
            if oa and ia and oq:
                pieces, short = self.lots.take((*here, oa), oq)
                self.lots.put((*here, ia), pieces, iq / oq, asset=ia)
                self.carried(pieces)
                if short:
                    self.out.uncovered.append(
                        Uncovered(oa, r.source_id, at, short, None, "migration", r.id)
                    )
                    q = short * iq / oq
                    self.acquire((*here, ia), q, self.value(ia, q, at), at, True)
        elif k == "internal_transfer":
            if oa and not self.money(oa):
                pieces, short = self.lots.take((*here, oa), oq)
                self.carried(pieces)
                self.to_transit(r.source_id, oa, pieces)
                if short and oa not in BANK:
                    self.out.uncovered.append(
                        Uncovered(oa, r.source_id, at, short, None, "transfer", r.id)
                    )
            if ia and not self.money(ia):
                self.from_transit((*here, ia), iq, at)
        elif k in ("send", "fiat_withdrawal") or (k == "other" and oa and not ia):
            self.send(r, m)
            return
        elif k in ("receive", "income", "fiat_deposit", "other") and ia:
            self.receive(r, m)
            return
        elif k == "fee":
            # a fee without movement (failed transaction gas): paid in coin, a disposal
            if r.fee_asset and r.fee_amount:
                fa = self._a(r.fee_asset)
                v = self.value(fa, r.fee_amount, at)
                self.dispose((*here, fa), r.fee_amount, v, at, r.id, "fee")
            return
        self.network_fee(r, (*here, ia or oa or ""))

    def _split(self, pieces: list[Piece], qty: Decimal) -> tuple[list[Piece], list[Piece]]:
        temp: Place = (-1, "transit", pieces[0].asset if pieces else "")
        self.lots.put(temp, pieces)
        held = sum((p.qty for p in pieces), ZERO)
        used, _ = self.lots.take(temp, min(qty, held))
        rest, _ = self.lots.take(temp, held)
        return used, rest

    def to_transit(self, source: int, asset: str, pieces: list[Piece]) -> None:
        """Lots leaving for another market of the same source. Some exchanges book the
        arrival first (Kraken staking, Bitget futures): then a stand-in lot is waiting there
        and the real lots replace what is left of it."""
        owed = self.owed[(source, asset)]
        if self.trace is not None:
            self._settle(owed, pieces)
        while pieces and owed:
            place, lot = owed[0]
            if lot.qty > 0:
                used, pieces = self._split(pieces, lot.qty)
                q = sum((p.qty for p in used), ZERO)
                lot.cost -= lot.cost * q / lot.qty
                lot.qty -= q
                self.lots.put(place, used)
            if lot.qty <= DUST:
                owed.pop(0)
        self.transit[(source, asset)].extend(pieces)

    def _settle(self, owed: list[tuple[Place, Lot]], pieces: list[Piece]) -> None:
        """The source of funds of a stand-in lot (arrival booked before departure): the real
        lots that leave now. Its node turns from "unknown" into a rebooking pointing at them —
        also for what was spent from the stand-in in between."""
        i, offset = 0, ZERO
        for _, lot in owed:
            if not lot.parts:
                continue
            nid = lot.parts[0][0]
            node = self.trace.nodes[nid]
            need = node.qty - self.settled.get(nid, ZERO)
            while need > DUST and i < len(pieces):
                p = pieces[i]
                take = min(need, p.qty - offset)
                base = p.cost if p.cost > 0 else (self.value(p.asset, p.qty, node.at) or ZERO)
                real = base * take / p.qty
                node.parents += Trace.spread(p.parts, real)
                # the stand-in was valued at the arrival: above the real cost a price gain
                gain = node.value * take / node.qty - real
                if abs(gain) > DUST:
                    kind = "gain" if gain > 0 else "loss"
                    leaf = self.trace.leaf(
                        kind, node.row, node.at, node.source, node.asset, take, abs(gain)
                    )
                    node.parents.append((leaf[0][0], gain))
                node.kind = "rebook"
                self.settled[nid] = self.settled.get(nid, ZERO) + take
                need -= take
                offset += take
                if offset >= p.qty - DUST:
                    i, offset = i + 1, ZERO

    def _unsettled(self) -> None:
        """What no real lot ever covered stays of unknown origin, in proportion."""
        for nid, covered in self.settled.items():
            node = self.trace.nodes[nid]
            if covered >= node.qty - DUST or covered <= 0:
                continue
            weight = sum((w for _, w in node.parents), ZERO) * (node.qty - covered) / covered
            leaf = self.trace.leaf(
                "unknown", node.row, node.at, node.source, node.asset, node.qty - covered, None
            )
            node.parents += Trace.spread(leaf, weight)

    def from_transit(self, place: Place, qty: Decimal, at: datetime) -> None:
        """A rebooking between markets of one source arrives with the lots that left."""
        key = (place[0], place[2])
        used, self.transit[key] = self._split(self.transit[key], qty)
        self.lots.put(place, used)
        self.carried(used)
        q = qty - sum((p.qty for p in used), ZERO)
        if q > DUST:
            v = self.value(place[2], q, at)
            lot = Lot(
                place[2], q, at, v or ZERO, True, parts=self._leaf("unknown", place, q, v, at)
            )
            self.lots.add(place, lot)
            self.owed[key].append((place, lot))

    def send(self, r: RawTransaction, mark: str | None) -> None:
        at, oa, oq = r.timestamp, self._a(r.outgoing_asset), r.outgoing_amount or ZERO
        here: Place = (r.source_id, r.market, oa)
        self.network_fee(r, here)
        if self.trace is not None and oa and oq and self.money(oa) and mark is None:
            # euro to the bank: out of the pot of this source
            taken, short = self.trace.pot_take(r.source_id, oa, oq)
            if short:
                taken += Trace.spread(self._leaf("money_unknown", here, short, short, at), short)
            self._main(r.id, self.trace.add("withdrawal", r.id, at, r.source_id, oa, oq, oq, taken))
        if not oa or not oq or self.money(oa):
            return
        if mark == "own_untracked":
            self.move(here, (OUTSIDE, "spot", oa), oq, oq, at, r.id)
        elif mark == "external":
            self.dispose(here, oq, self.value(oa, oq, at), at, r.id, "external")
        elif mark == "lost":
            pieces, short = self.lots.take(here, oq)
            for p in pieces:
                self.out.losses.append(
                    Loss(oa, r.source_id, at, p.acquired, p.qty, p.cost, r.id, p.origin)
                )
            if short:
                self.out.losses.append(
                    Loss(
                        oa,
                        r.source_id,
                        at,
                        None,
                        short,
                        self.value(oa, short, at) if oa in BANK else None,
                        r.id,
                    )
                )
        elif r.kind == "fiat_withdrawal" or oa in BANK:
            pieces, _ = self.lots.take(here, oq)  # money to the bank: no sale
            if self.trace is not None:
                parents = self._from(pieces, lambda q: self.value(oa, q, at))
                v = self.value(oa, oq, at)
                self._main(
                    r.id, self.trace.add("withdrawal", r.id, at, r.source_id, oa, oq, v, parents)
                )
        else:
            self.out.open_sends.append(
                Uncovered(oa, r.source_id, at, oq, self.value(oa, oq, at), "open_send", r.id)
            )
            self.move(here, (OUTSIDE, "spot", oa), oq, oq, at, r.id)

    def receive(self, r: RawTransaction, mark: str | None) -> None:
        at, ia, iq = r.timestamp, self._a(r.incoming_asset), r.incoming_amount or ZERO
        here: Place = (r.source_id, r.market, ia)
        if mark == "own_untracked":
            outside: Place = (OUTSIDE, "spot", ia)
            held = sum((lot.qty for lot in self.lots.lots[outside]), ZERO)
            back = min(held, iq)
            self.move(outside, here, back, back, at, r.id)
            if iq > back:
                self.acquire(here, iq - back, self.value(ia, iq - back, at), at, True)
        else:
            v = self.value(ia, iq, at)
            kind = "reward" if mark == "income" else r.income_kind
            is_income = r.kind == "income" or mark == "income"
            if is_income:
                taxed = kind in TAXED_INCOME or (kind == "airdrop" and self.p.airdrop_taxable)
                if taxed:
                    self.out.incomes.append(Income(ia, r.source_id, at, iq, v, kind or "", r.id))
                # both halves move together: taxed at inflow → that value is the cost;
                # not taxed → cost 0, nothing was spent and nothing taxed
                parts = self._leaf("income", here, iq, v, at, kind)
                self.acquire(here, iq, v if taxed else ZERO, at, parts=parts)
            elif mark == "bought" or card_purchase(r):
                # bought with a card, but the euro paid are not in the data (Bitget delivers
                # only the coin): its market value stands in, the card fee is missing — so
                # it is marked estimated until the row gets its euro (Blockpit check 2024)
                self.acquire(
                    here, iq, v, at, estimated=True, parts=self._leaf("card", here, iq, v, at)
                )
            elif ia in BANK or r.kind == "fiat_deposit":
                self.acquire(here, iq, v, at, parts=self._leaf("bank", here, iq, v, at))
            else:
                # from a foreign address, no mark: the purchase is unknown
                self.acquire(here, iq, v, at, estimated=True)
        self.network_fee(r, here)

    def trade(self, r: RawTransaction) -> None:
        """Fees as the BMF reads them (ADR 0042): counted once, at the deal they belong to —
        on a buy for money they add to the cost, on a sale or swap they lower the proceeds.
        A fee in a third coin is also a sale of that coin."""
        at = r.timestamp
        ia, oa = self._a(r.incoming_asset), self._a(r.outgoing_asset)
        iq, oq = r.incoming_amount or ZERO, r.outgoing_amount or ZERO
        fa, fq = self._a(r.fee_asset), r.fee_amount or ZERO
        here = (r.source_id, r.market)
        card = paid_by_card(r)
        if oa in BANK or oa in self.p.money:
            worth = self.value(oa, oq, at)
        elif ia in BANK or ia in self.p.money:
            worth = self.value(ia, iq, at)
        else:
            worth = self.value(oa, oq, at) if oa else None
            if worth is None and ia:
                worth = self.value(ia, iq, at)
        fee_v = self.value(fa, fq, at) if fa and fq else ZERO
        sells = bool(oa and oq and not self.money(oa))

        got, gave = iq, oq
        if fa and fq:
            if fa == ia:
                got = iq - fq  # charged in the coin bought (Bitget)
            elif fa == oa:
                gave = oq + fq  # charged in the coin given: more of it leaves
            else:
                self.dispose((*here, fa), fq, fee_v, at, r.id, "fee", by_card=card)

        # the fee in the coin given leaves with the sale and earns nothing: proceeds stay
        # `worth`, so the fee lowers the gain; any other fee comes off the proceeds
        fee_off = fee_v if (fa and fq and fa != oa and fee_v is not None) else ZERO
        sale = None
        if sells:
            proceeds = None if worth is None else worth - fee_off
            sale = self.dispose((*here, oa), gave, proceeds, at, r.id, "trade", by_card=card)
            if sale is not None and ia and got > 0 and not self.money(ia):
                # coin for coin: one step with both sides, else the chain reads "sold USDT"
                # right under the LTC it bought (Vanixxx, 2026-10-18)
                node = self.trace.nodes[sale]
                node.kind, node.into = "swap", (ia, got)
        if ia and got > 0:
            if worth is None:
                cost = None
            elif sells:
                # a swap: the new coin costs its value; a fee taken from it already lowered
                # the proceeds and the quantity — counting it in the cost again would be twice
                cost = worth - (fee_v if fa == ia and fee_v is not None else ZERO)
            else:
                # bought for money: what was paid, any fee not taken from the coin included
                cost = worth + (fee_v if fa and fa != ia and fee_v is not None else ZERO)
            self.acquire((*here, ia), got, cost, at, parts=self._paid(r, here, ia, got, cost, sale))

    def _paid(self, r: RawTransaction, here, ia: str, got: Decimal, cost, sale: int | None):
        """Parts of what a trade bought: the sale it came from, or the euro paid — from the
        pot of the source, or straight from the bank by card."""
        if self.trace is None:
            return ()
        if sale is not None:
            return ((sale, Decimal(1)),)
        oa, oq = self._a(r.outgoing_asset), r.outgoing_amount or ZERO
        if not oa or not self.money(oa) or not oq:
            return ()
        at, place = r.timestamp, (*here, ia)
        if paid_by_card(r):
            parents = list(Trace.spread(self._leaf("card", place, got, oq, at), oq))
        else:
            parents, short = self.trace.pot_take(r.source_id, oa, oq)
            if short:
                # euro that never lay on the exchange: the buy was paid straight from the bank
                # (MEXC sells USDT for SEPA or a bank card, without a deposit row; 1,600 € of
                # Vanixxx's, 2026-10-17)
                text = (r.comment or "").lower()
                kind = "card" if "card" in text or "karte" in text else "bank"
                leaf = self._leaf(kind, (*here, oa), short, short, at, "direct")
                parents += Trace.spread(leaf, short)
        node = self.trace.add("buy", r.id, at, r.source_id, ia, got, cost or oq, parents)
        return ((node.id, Decimal(1)),)

    def futures(self, r: RawTransaction) -> None:
        """§ 20: results, funding and fees of the futures account (ADR 0042, Blockpit check
        2024). What the account credits arrives as a lot of the margin coin; what it spends
        leaves the lots WITHOUT a sale under § 23 — the money is counted under § 20 already
        (as Blockpit does: over 1,000 tiny USDT sales a year otherwise).

        A bonus of the exchange (MEXC "BONUS") is no income under § 22: credited and
        expired it nets out, used it covered futures losses — so both sides are § 20."""
        at, here = r.timestamp, (r.source_id, r.market)
        bonus = r.kind == "income" or (r.comment or "").strip().upper() == "BONUS"
        kind = (
            "bonus"
            if bonus
            else "funding"
            if r.kind == "funding"
            else ("fee" if r.kind == "fee" else "pnl")
        )
        for asset, qty, sign, what in (
            (r.incoming_asset, r.incoming_amount, 1, kind),
            (r.outgoing_asset, r.outgoing_amount, -1, kind),
            (r.fee_asset, r.fee_amount, -1, "bonus" if bonus else "fee"),
        ):
            if not asset or not qty:
                continue
            a = self._a(asset)
            v = self.value(a, qty, at)
            signed = None if v is None else v * sign
            self.out.futures.append(FuturesFlow(r.source_id, at, what, a, qty * sign, signed, r.id))
            if sign > 0:
                self.acquire(
                    (*here, a), qty, v, at, parts=self._leaf("futures", (*here, a), qty, v, at)
                )
            elif not self.money(a):
                self.lots.take((*here, a), qty)
