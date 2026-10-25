"""Avalanche C-Chain through Routescan's Etherscan-compatible endpoint (measured 2026-10-03).

Routescan's own `/v2` API answers with ISO times, `id` instead of `hash` and
`status` booleans; its `/etherscan/api` path speaks the Etherscan form, so the
shared reader serves it unchanged.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import datetime

from app.modules.plugins import evm
from app.modules.plugins.contract import Movement

API = "https://api.routescan.io/v2/network/mainnet/evm/43114/etherscan/api"
NATIVE, DECIMALS = "AVAX", 18


def fetch(
    address: str,
    since: datetime | None,
    progress: Callable[[dict], None] | None = None,
    key: str | None = None,
) -> Iterator[Movement]:
    yield from evm.fetch(evm.Explorer(API), address, since, progress, NATIVE, DECIMALS)


BALANCE_RPC = "https://api.avax.network/ext/bc/C/rpc"


def balance(address: str, key: str | None = None, tokens: dict | None = None) -> list:
    return evm.balances(BALANCE_RPC, address, NATIVE, DECIMALS, tokens)
