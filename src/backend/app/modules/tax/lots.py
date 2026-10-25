"""Lot tracking (ADR 0004, 0042): every acquisition is its own lot with day, quantity and
cost, kept per place (source, market, coin) because the BMF counts per wallet.

FIFO and LIFO differ in nothing but the order lots are taken in. Pure arithmetic: no
database, no prices — what comes in is valued in euro already.
"""

from __future__ import annotations

import enum
from collections import defaultdict
from dataclasses import dataclass, replace
from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

ZERO = Decimal(0)
DUST = Decimal("0.00000001")
"""Below this a lot counts as empty: partial fills leave rests like 1E-20 otherwise."""
ROUNDING = Decimal("0.0001")
"""A shortfall up to 0.01 % of what is taken is rounding in the data, not missing history
(0.28 of 11.4 million QUBIC, a hand entry, 2026-10-13): the same tolerance as the
portfolio's gap search, so the tax report and the transactions list agree."""
BERLIN = ZoneInfo("Europe/Berlin")

Place = tuple[int, str, str]  # source id (0 = outside), market, coin


class Method(enum.StrEnum):
    FIFO = "fifo"
    LIFO = "lifo"


def local_day(at: datetime) -> date:
    """The German calendar day: a sale at 00:30 on 1 January belongs to the new year."""
    return at.astimezone(BERLIN).date()


def one_year_after(day: date) -> date:
    """The day the holding period ends (§ 23 EStG with §§ 187/188 BGB): a sale ON it is still
    taxable, a day later not. 29 February has no match in the next year — then the 28th."""
    try:
        return day.replace(year=day.year + 1)
    except ValueError:
        return day.replace(year=day.year + 1, day=28)


def tax_free(acquired: datetime, sold: datetime) -> bool:
    return local_day(sold) > one_year_after(local_day(acquired))


@dataclass
class Lot:
    asset: str
    qty: Decimal
    acquired: datetime
    cost: Decimal
    """EUR for the quantity still open."""
    estimated: bool = False
    """The cost is a market value standing in for an unknown purchase."""
    origin: int = 0
    """The row that bought it: kept through transfers, for the tax tab of a transaction."""
    seq: int = 0
    """Order of arrival: breaks ties of lots from the same second (LIFO must not fall back
    to FIFO there — Bitget books pairs in one second)."""
    parts: tuple = ()
    """Where the money in it came from (ADR 0046): (node id, weight) of the source of funds
    trace; empty when the pass runs without it."""


@dataclass
class Piece:
    """What one taking removed from one lot."""

    asset: str
    qty: Decimal
    cost: Decimal
    acquired: datetime
    estimated: bool
    origin: int = 0
    parts: tuple = ()


class Lots:
    def __init__(self, method: Method) -> None:
        self.method = method
        self.lots: dict[Place, list[Lot]] = defaultdict(list)
        self._seq = 0

    def add(self, place: Place, lot: Lot) -> None:
        if lot.qty <= DUST:
            return
        self._seq += 1
        lot.seq = self._seq
        self.lots[place].append(lot)

    def take(self, place: Place, qty: Decimal) -> tuple[list[Piece], Decimal]:
        """Takes qty in method order. Second value: the part no lot covered."""
        left = qty
        pieces: list[Piece] = []
        ordered = sorted(
            self.lots[place],
            key=lambda lot: (lot.acquired, lot.seq),
            reverse=self.method is Method.LIFO,
        )
        for lot in ordered:
            if left <= DUST:
                break
            if lot.qty <= DUST:
                continue  # emptied from outside (a stand-in replaced by real lots)
            used = min(left, lot.qty)
            cost = lot.cost * used / lot.qty
            pieces.append(
                Piece(lot.asset, used, cost, lot.acquired, lot.estimated, lot.origin, lot.parts)
            )
            lot.qty -= used
            lot.cost -= cost
            left -= used
        self.lots[place] = [lot for lot in self.lots[place] if lot.qty > DUST]
        return pieces, (left if left > max(DUST, qty * ROUNDING) else ZERO)

    def put(self, place: Place, pieces: list[Piece], factor: Decimal = Decimal(1), asset=None):
        """Puts taken pieces down elsewhere with their day and full cost: a transfer, a
        rebooking or a migration (then `asset` and `factor` change name and quantity)."""
        for p in pieces:
            self.add(
                place,
                Lot(
                    asset or p.asset,
                    p.qty * factor,
                    p.acquired,
                    p.cost,
                    p.estimated,
                    p.origin,
                    parts=p.parts,
                ),
            )

    def shrink(self, place: Place, qty: Decimal) -> Decimal:
        """A network fee: the quantity leaves, its cost stays with what is left there (no
        disposal, ADR 0042). Returns the part no lot covered."""
        pieces, short = self.take(place, qty)
        cost = sum((p.cost for p in pieces), ZERO)
        rest = self.lots[place]
        held = sum((lot.qty for lot in rest), ZERO)
        if held > 0:
            for lot in rest:
                lot.cost += cost * lot.qty / held
        return short

    def open(self) -> list[tuple[Place, Lot]]:
        return [(pl, lot) for pl, lots in self.lots.items() for lot in lots if lot.qty > DUST]

    def snapshot(self) -> list[tuple[Place, Lot]]:
        """Copies, not references: the walk keeps taking from the lots afterwards (the old
        year-end sheet showed lots sold only in the next year with quantity 0)."""
        return [(pl, replace(lot)) for pl, lot in self.open()]
