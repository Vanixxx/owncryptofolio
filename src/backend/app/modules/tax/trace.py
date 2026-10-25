"""Source of funds trace (ADR 0046): while the tax pass walks, every deposit, purchase, sale,
transfer and withdrawal becomes a node, linked to the nodes its money came from. Lots carry
(node, weight) parts; euro sit in a pot per source that keeps its parts too.

Weights are relative: a node's children share its value in proportion to them. Nothing
here changes a tax figure — the pass runs with the trace only for the source of funds."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from app.modules.tax.lots import DUST, ZERO

LEAVES = ("bank", "card", "gain", "income", "futures", "unknown", "money_unknown", "loss")
"""Where money finally comes from: own bank deposits, card purchases, price gains, income
(staking, rewards, airdrops), futures results, coins without a recorded purchase, euro
without a recorded deposit."""

Parts = tuple[tuple[int, Decimal], ...]


@dataclass
class Node:
    id: int
    kind: str
    """A leaf kind, or sale · buy · transfer · withdrawal · payment."""
    row: int
    at: datetime
    source: int
    asset: str
    qty: Decimal
    value: Decimal
    """Euro: what the step was worth (a sale's proceeds, a buy's price, a leaf's amount)."""
    parents: list[tuple[int, Decimal]] = field(default_factory=list)
    to_source: int | None = None
    detail: str | None = None
    """A leaf's sub kind (staking, airdrop …)."""
    row_in: int | None = None
    """A transfer: the arriving row (its own source and channel)."""
    into: tuple[str, Decimal] | None = None
    """A swap: the coin and quantity it bought (USDT → LTC shows both sides)."""


@dataclass
class Slice:
    amount: Decimal
    parts: Parts


class Trace:
    def __init__(self) -> None:
        self.nodes: list[Node] = []
        self.by_row: dict[int, int] = {}
        """A row's main step: what the source of funds starts from."""
        self.pots: dict[tuple[int, str], list[Slice]] = {}

    def add(self, kind: str, row: int, at, source: int, asset: str, qty, value, parents=()):
        node = Node(
            len(self.nodes), kind, row, at, source, asset, qty, value or ZERO, list(parents)
        )
        self.nodes.append(node)
        return node

    def leaf(self, kind: str, row: int, at, source: int, asset: str, qty, value, detail=None):
        node = self.add(kind, row, at, source, asset, qty, value)
        node.detail = detail
        return ((node.id, Decimal(1)),)

    @staticmethod
    def spread(parts: Parts, weight: Decimal) -> list[tuple[int, Decimal]]:
        """`weight` shared over the parts in their proportion."""
        total = sum((w for _, w in parts), ZERO)
        if total <= 0 or weight <= 0:
            return []
        return [(n, weight * w / total) for n, w in parts]

    # --- euro pots -----------------------------------------------------------------------

    def pot_add(self, source: int, currency: str, amount: Decimal, parts: Parts) -> None:
        if amount > DUST and parts:
            self.pots.setdefault((source, currency), []).append(Slice(amount, parts))

    def pot_take(self, source: int, currency: str, amount: Decimal):
        """Oldest euro first. Returns the parents taken and the part not in the pot."""
        pot = self.pots.get((source, currency), [])
        left, taken = amount, []
        while pot and left > DUST:
            s = pot[0]
            used = min(left, s.amount)
            taken += self.spread(s.parts, used)
            s.amount -= used
            left -= used
            if s.amount <= DUST:
                pot.pop(0)
        return taken, (left if left > DUST else ZERO)
