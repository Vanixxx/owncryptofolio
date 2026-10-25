"""Linea through Etherscan V2 (chainid 59144), free key (measured 2026-10-20).

Beta (ADR 0048): added 2026-10-20 without a real wallet to check against. The reading
itself is shared with the other EVM networks: `app.modules.plugins.evm`.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import datetime

from app.modules.plugins import evm
from app.modules.plugins.contract import Movement

API = "https://api.etherscan.io/v2/api"
NATIVE, DECIMALS = "ETH", 18


def fetch(
    address: str,
    since: datetime | None,
    progress: Callable[[dict], None] | None = None,
    key: str | None = None,
) -> Iterator[Movement]:
    yield from evm.fetch(
        evm.Explorer(API, {"chainid": 59144}, key=key, pause=0.35),
        address,
        since,
        progress,
        NATIVE,
        DECIMALS,
    )


BALANCE_RPC = "https://linea-rpc.publicnode.com"


def balance(address: str, key: str | None = None, tokens: dict | None = None) -> list:
    return evm.balances(BALANCE_RPC, address, NATIVE, DECIMALS, tokens)
