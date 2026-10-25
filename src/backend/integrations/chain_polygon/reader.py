"""Polygon PoS through Etherscan V2 (chainid 137). Blockscout put Polygon behind a
Cloudflare check in October 2026 ("Just a moment…", HTTP 403 for every server request,
measured 2026-10-09); Routescan does not serve chain 137. The free Etherscan key works.

The native coin is POL (renamed from MATIC in 2024, 1:1); Blockscout reports it as
POL for the whole history. Polygon sees many spam airdrops (fake token names with
links); they are kept in the raw layer like everything else.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import datetime

from app.modules.plugins import evm
from app.modules.plugins.contract import Movement

API = "https://api.etherscan.io/v2/api"
NATIVE, DECIMALS = "POL", 18


def fetch(
    address: str,
    since: datetime | None,
    progress: Callable[[dict], None] | None = None,
    key: str | None = None,
) -> Iterator[Movement]:
    yield from evm.fetch(
        evm.Explorer(API, {"chainid": 137}, key=key, pause=0.35),
        address,
        since,
        progress,
        NATIVE,
        DECIMALS,
    )


BALANCE_RPC = "https://polygon-bor-rpc.publicnode.com"


def balance(address: str, key: str | None = None, tokens: dict | None = None) -> list:
    return evm.balances(BALANCE_RPC, address, NATIVE, DECIMALS, tokens)
