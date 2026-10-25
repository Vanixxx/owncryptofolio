"""Ronin (chain id 2020) through its own Blockscout instance, Etherscan-compatible and
without key (measured 2026-10-05: Etherscan V2 and Routescan do not know Ronin). The
Ronin wallet shows addresses as `ronin:…`: the same 20 bytes as `0x…`.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import datetime

from app.modules.plugins import evm
from app.modules.plugins.contract import Movement

API = "https://explorer.roninchain.com/api"
NATIVE, DECIMALS = "RON", 18
BALANCE_RPC = "https://api.roninchain.com/rpc"


def hex_address(address: str) -> str:
    """`ronin:abc…` → `0xabc…`; a 0x address stays as it is."""
    a = address.strip()
    return "0x" + a[len("ronin:") :] if a.lower().startswith("ronin:") else a


def fetch(
    address: str,
    since: datetime | None,
    progress: Callable[[dict], None] | None = None,
    key: str | None = None,
) -> Iterator[Movement]:
    # Ronin's explorer answers 429 to quick series of calls (measured 2026-10-05)
    explorer = evm.Explorer(API, pause=1.0)
    yield from evm.fetch(explorer, hex_address(address), since, progress, NATIVE, DECIMALS)


def balance(address: str, key: str | None = None, tokens: dict | None = None) -> list:
    return evm.balances(BALANCE_RPC, hex_address(address), NATIVE, DECIMALS, tokens)
