"""Ethereum through Blockscout's Etherscan-compatible API (research 2026-08-27).

At the user's address 20 of 23 movements are tokens (`tokentx`). The reading
itself is shared with the other EVM networks: `app.modules.plugins.evm`.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import datetime

from app.modules.plugins import evm
from app.modules.plugins.contract import Movement
from app.modules.plugins.evm import ChainUnavailable, amount  # noqa: F401  (tests, callers)

API = "https://eth.blockscout.com/api"
NATIVE, DECIMALS = "ETH", 18


def convert(address: str, txlist: list, tokentx: list, internal: list) -> list[Movement]:
    return evm.convert(address, txlist, tokentx, internal, native=NATIVE, decimals=DECIMALS)


def fetch(
    address: str,
    since: datetime | None,
    progress: Callable[[dict], None] | None = None,
    key: str | None = None,
) -> Iterator[Movement]:
    yield from evm.fetch(evm.Explorer(API), address, since, progress, NATIVE, DECIMALS)


BALANCE_RPC = "https://ethereum-rpc.publicnode.com"


def balance(address: str, key: str | None = None, tokens: dict | None = None) -> list:
    return evm.balances(BALANCE_RPC, address, NATIVE, DECIMALS, tokens)
