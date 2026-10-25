"""zkSync Era through Blockscout (zksync.blockscout.com), no key; Etherscan V2 does not know chain
324 (measured 2026-10-20).

Beta (ADR 0048): added 2026-10-20 without a real wallet to check against. The reading
itself is shared with the other EVM networks: `app.modules.plugins.evm`.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import datetime

from app.modules.plugins import evm
from app.modules.plugins.contract import Movement

API = "https://zksync.blockscout.com/api"
NATIVE, DECIMALS = "ETH", 18


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


BALANCE_RPC = "https://mainnet.era.zksync.io"


def balance(address: str, key: str | None = None, tokens: dict | None = None) -> list:
    return evm.balances(BALANCE_RPC, address, NATIVE, DECIMALS, tokens)
