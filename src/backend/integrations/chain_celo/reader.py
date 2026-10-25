"""Celo through Blockscout (celo.blockscout.com), no key (measured 2026-10-20). The native coin is
CELO.

Beta (ADR 0048): added 2026-10-20 without a real wallet to check against. The reading
itself is shared with the other EVM networks: `app.modules.plugins.evm`.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import datetime

from app.modules.plugins import evm
from app.modules.plugins.contract import Movement

API = "https://celo.blockscout.com/api"
NATIVE, DECIMALS = "CELO", 18


def fetch(
    address: str,
    since: datetime | None,
    progress: Callable[[dict], None] | None = None,
    key: str | None = None,
) -> Iterator[Movement]:
    yield from evm.fetch(
        evm.Explorer(API, {}, key=key),
        address,
        since,
        progress,
        NATIVE,
        DECIMALS,
    )


BALANCE_RPC = "https://forno.celo.org"


def balance(address: str, key: str | None = None, tokens: dict | None = None) -> list:
    return evm.balances(BALANCE_RPC, address, NATIVE, DECIMALS, tokens)
