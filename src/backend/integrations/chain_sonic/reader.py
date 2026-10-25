"""Sonic through Etherscan V2 (chainid 146). No Blockscout instance, Routescan
answers "chain not supported" (measured 2026-10-03): the free Etherscan key is the way.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import datetime

from app.modules.plugins import evm
from app.modules.plugins.contract import Movement

API = "https://api.etherscan.io/v2/api"
NATIVE, DECIMALS = "S", 18


def fetch(
    address: str,
    since: datetime | None,
    progress: Callable[[dict], None] | None = None,
    key: str | None = None,
) -> Iterator[Movement]:
    yield from evm.fetch(
        evm.Explorer(API, {"chainid": 146}, key=key, pause=0.35),
        address,
        since,
        progress,
        NATIVE,
        DECIMALS,
    )


BALANCE_RPC = "https://sonic-rpc.publicnode.com"


def balance(address: str, key: str | None = None, tokens: dict | None = None) -> list:
    return evm.balances(BALANCE_RPC, address, NATIVE, DECIMALS, tokens)
