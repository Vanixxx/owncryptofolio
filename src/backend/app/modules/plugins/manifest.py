"""plugin.toml — what a plugin is and what it can do (ADR 0017).

TOML because Python reads it without extra libraries and it allows comments.
One file, so there is one place where something can be missing, not two.
"""

from __future__ import annotations

import enum
import tomllib
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Channel(enum.StrEnum):
    API = "api"  # exchange API with credentials
    FILE = "file"  # export files uploaded by the user
    CHAIN = "chain"  # public blockchain, needs an address
    MANUAL = "manual"  # entered by the user: form or template (ADR 0036)


class SourceKind(enum.StrEnum):
    EXCHANGE = "exchange"
    WALLET = "wallet"


class PluginInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    author: str
    version: str
    description: str
    status: Literal["tested", "beta"] = "beta"
    """"tested": checked against a real account. Anything else is beta, shown with a badge
    and a note on what may go wrong (ADR 0048); a plugin dropped in by someone else is beta
    until said otherwise."""


class SourceInfo(BaseModel):
    """Which source this plugin reads and through which channel. API and file
    of the same exchange are separate plugins with the same provider: they have
    provably different capabilities (ADR 0017)."""

    model_config = ConfigDict(extra="forbid")
    provider: str  # "bitget", "ethereum" — groups plugins of one source
    provider_name: str  # shown in the UI
    kind: SourceKind
    channel: Channel
    provides_balance: bool = False
    provides_id: bool = False
    history_days: int | None = None  # None = unlimited (files)
    window_max_days: int | None = None
    futures: bool = False
    overlap: str = "period"
    """How API rows supersede file rows of the same exchange (ADR 0033):
    "period" - from the first API row per market on, the API is complete (Bitget);
    "event"  - only file rows the API also knows are superseded (Coinbase: the API
               lacks old staking income, the file lacks the real fiat currency)."""
    expected_files: list[str] = Field(default_factory=list)
    not_read: list[str] = Field(default_factory=list)
    """What the plugin deliberately skips (ADR 0020): a skipped file must be
    distinguishable from an empty one."""


class Credentials(BaseModel):
    """Fields the UI renders as a form. Declared, not hard-wired."""

    model_config = ConfigDict(extra="forbid")
    fields: list[str]
    secret: list[str] = Field(default_factory=list)
    multiline: list[str] = Field(default_factory=list)  # e.g. a PEM private key
    alternatives: list[list[str]] = Field(default_factory=list)
    """Groups of which ONE must be complete, e.g. Coinbase: key file or key pair."""


class ChainInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    native_asset: str
    decimals: int
    address_pattern: str  # regex the address must match
    explorer: str  # base URL of the API used
    family: str = ""  # "evm": same address on all EVM networks (ADR 0034)
    service: str = ""  # key needed from a blockchain service, e.g. "etherscan" (ADR 0035)
    service_optional: bool = False  # works without, the key only raises limits
    accrues: list[str] = Field(default_factory=list)
    """Coins that grow by holding another one, without any transfer (VTHO from VET): after a
    fetch, what the balance holds beyond the transactions is booked as income."""


class CcxtInfo(BaseModel):
    """One plugin for every exchange ccxt reads (ADR 0048). Per exchange what differs."""

    model_config = ConfigDict(extra="forbid")
    tested: list[str] = Field(default_factory=list)  # ccxt ids checked with a real account
    exclude: list[str] = Field(default_factory=list)  # futures only, wallet keys, ...
    quotes: list[str] = Field(default_factory=lambda: ["USDT", "USDC", "EUR", "USD", "BTC", "ETH"])
    fee_in_amount: list[str] = Field(default_factory=list)
    """Exchanges whose withdrawal amount already holds the fee (else: sent = amount + fee)."""


class Manifest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    plugin: PluginInfo
    source: SourceInfo
    credentials: Credentials | None = None
    chain: ChainInfo | None = None
    ccxt: CcxtInfo | None = None

    @classmethod
    def load(cls, path: Path) -> Manifest:
        with path.open("rb") as fh:
            return cls.model_validate(tomllib.load(fh))
