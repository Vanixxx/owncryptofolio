"""The contract between core and plugin (ADR 0017, ADR 0029).

A plugin yields `Movement`s. The core knows only this shape, never the source.
Everything source specific (number format, header lines, time zones, fee
conventions) stays inside the plugin.
"""

from __future__ import annotations

import enum
import hashlib
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

ASSET_MAX = 40
"""Width of the asset columns. Scam tokens on public chains abuse the symbol
as an ad ("VISIT WEBSITE ... TO CLAIM REWARDS", 48 chars): cut, don't reject —
the movement happened and `raw` keeps the original (ADR 0001)."""

ALIASES = {"MNGL": "NTGL"}
"""Same asset under two tickers. MEXC lists Entangle as MNGL, the Ethereum
contract as NTGL; kept apart they produced a negative balance of -393.88.
Renames over time (MATIC -> POL) are NOT aliases: they are `migration` events."""


class Kind(enum.StrEnum):
    """Vocabulary from real data of six exchanges and 17 chains (ADR 0017)."""

    TRADE = "trade"  # buy, sell, swap: two sides, fiat is just an asset (ADR 0011)
    SEND = "send"  # crypto out to a foreign address — merge candidate
    RECEIVE = "receive"  # crypto in from a foreign address — merge candidate
    FIAT_DEPOSIT = "fiat_deposit"
    FIAT_WITHDRAWAL = "fiat_withdrawal"
    INCOME = "income"  # staking, rewards, interest, airdrops (needs income_kind)
    INTERNAL_TRANSFER = "internal_transfer"  # between own accounts/pots, no change of owner
    MIGRATION = "migration"  # token rename/swap 1:1 (MATIC -> POL), not a disposal
    FEE = "fee"  # fee without an underlying movement (e.g. failed tx gas)
    REALIZED_PNL = "realized_pnl"  # futures: settled profit or loss in margin asset
    FUNDING = "funding"  # futures: funding payments in margin asset
    FUTURES_POSITION = "futures_position"  # futures: closed position, no balance effect
    OTHER = "other"  # anything unrecognised — shown, never dropped


class IncomeKind(enum.StrEnum):
    STAKING = "staking"
    REWARD = "reward"
    INTEREST = "interest"
    AIRDROP = "airdrop"


class Market(enum.StrEnum):
    SPOT = "spot"
    FUTURES = "futures"


class Movement(BaseModel):
    """One normalised movement as a plugin returns it. Two sided (ADR 0011):
    either side may be empty — income has no outgoing side, a send no incoming."""

    model_config = ConfigDict(extra="forbid")

    timestamp: datetime
    kind: Kind
    income_kind: IncomeKind | None = None
    market: Market = Market.SPOT

    incoming_asset: str | None = None
    incoming_amount: Decimal | None = None
    outgoing_asset: str | None = None
    outgoing_amount: Decimal | None = None
    fee_asset: str | None = None
    fee_amount: Decimal | None = None

    external_id: str | None = None
    comment: str | None = None
    counterparty: str | None = None  # address on the other side, anchor for merging
    instrument: str | None = None  # futures contract, e.g. BTCUSDT
    raw: dict[str, Any] = Field(default_factory=dict)

    @field_validator("timestamp")
    @classmethod
    def _utc(cls, value: datetime) -> datetime:
        # Naive timestamps look right and are hours off — the most common silent
        # import error. The plugin must know its source's time zone.
        if value.tzinfo is None:
            raise ValueError("timestamp without time zone; convert to UTC in the plugin")
        return value.astimezone(UTC)

    @field_validator("incoming_asset", "outgoing_asset", "fee_asset")
    @classmethod
    def _asset(cls, value: str | None) -> str | None:
        if not value or not value.strip():
            return None
        symbol = value.strip().upper()[:ASSET_MAX]
        return ALIASES.get(symbol, symbol)

    def check(self) -> None:
        """What pydantic alone cannot see. The core checks, not the plugin:
        a faulty plugin must not write broken rows into the raw layer."""
        for side in ("incoming", "outgoing", "fee"):
            asset, amount = getattr(self, f"{side}_asset"), getattr(self, f"{side}_amount")
            if (asset is None) != (amount is None):
                raise ValueError(f"{side}: asset and amount must be set together")
            if amount is not None and amount < 0:
                raise ValueError(f"{side}_amount is negative; direction is the side, not the sign")
        if self.kind is Kind.TRADE and (self.incoming_asset is None or self.outgoing_asset is None):
            raise ValueError("trade needs both sides")
        if self.kind is Kind.INCOME and self.income_kind is None:
            raise ValueError("income needs income_kind (staking, reward, interest, airdrop)")
        futures_only = (Kind.REALIZED_PNL, Kind.FUNDING, Kind.FUTURES_POSITION)
        if self.kind in futures_only and self.market is not Market.FUTURES:
            raise ValueError(f"{self.kind.value} belongs to the futures market")
        if self.kind is Kind.FUTURES_POSITION:
            if not self.instrument:
                raise ValueError("futures_position needs the instrument")
            return  # informational row, no balance effect
        if not (self.incoming_asset or self.outgoing_asset or self.fee_asset):
            raise ValueError("movement without any side and without fee is empty")


def _number(value: Decimal | None) -> str:
    """1.50 and 1.5 must count as equal; normalize() writes 100 as 1E+2."""
    return "" if value is None else f"{value.normalize():f}"


def fingerprint(source_key: str, m: Movement) -> str:
    """Recognises the same row again, also without an id from the source.

    The normal case, not the fallback: Bitget and MEXC files carry no trade id
    (ADR 0017). Checked on all real data: no collision. The separator is
    mandatory, otherwise "AB"+"C" and "A"+"BC" would collide.
    """
    parts = [
        source_key,
        m.timestamp.isoformat(),
        m.kind.value,
        m.market.value,
        m.incoming_asset or "",
        _number(m.incoming_amount),
        m.outgoing_asset or "",
        _number(m.outgoing_amount),
        m.fee_asset or "",
        _number(m.fee_amount),
        m.instrument or "",
        m.external_id or "",
    ]
    return hashlib.sha256("|".join(parts).encode()).hexdigest()
