"""ATOM through public REST nodes: the shared Cosmos SDK reader (app.modules.plugins.cosmos)."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import datetime

from app.modules.plugins import cosmos
from app.modules.plugins.contract import Movement

SPEC = cosmos.Chain(
    asset="ATOM",
    denom="uatom",
    servers=(
        "https://rest.cosmos.directory/cosmoshub",
        "https://cosmos-rest.publicnode.com",
    ),
)


def fetch(
    address: str,
    since: datetime | None,
    progress: Callable[[dict], None] | None = None,
    key: str | None = None,
) -> Iterator[Movement]:
    yield from cosmos.fetch(SPEC, address, since, progress)


def balance(address: str, key: str | None = None, tokens: dict | None = None) -> list:
    return cosmos.balance(SPEC, address)
