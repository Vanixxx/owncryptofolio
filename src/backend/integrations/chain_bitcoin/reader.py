"""Bitcoin through the mempool.space software; netting per transaction in
`app.modules.plugins.mempool`."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import datetime

from app.modules.plugins import mempool
from app.modules.plugins.contract import Movement

API = "https://mempool.space/api"
NATIVE, DECIMALS = "BTC", 8


def fetch(
    address: str,
    since: datetime | None,
    progress: Callable[[dict], None] | None = None,
    key: str | None = None,
) -> Iterator[Movement]:
    yield from mempool.fetch(API, address, since, progress, NATIVE, DECIMALS)


def balance(address: str, key: str | None = None, tokens: dict | None = None) -> list:
    return mempool.balance(API, address, NATIVE, DECIMALS)
