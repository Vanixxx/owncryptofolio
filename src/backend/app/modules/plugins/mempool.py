"""Shared reader for UTXO networks on the mempool.space software (research 2026-08-27).

Bitcoin (mempool.space) and Litecoin (litecoinspace.org) run the same explorer.

A UTXO transaction has inputs and outputs, no sender and receiver. Whoever spends
5 LTC to send 1 gets about 4 back as change. One movement per output would book a
disposal of 5 and a receipt of 4 that never happened. **So each transaction is
netted**: what left my address minus what came back.

* The fee is already inside that net amount and is taken out before it is booked
  on its own, otherwise it counts twice: sent + fee == what left the wallet.
* All inputs of a transaction that spends from my address are assumed mine (a
  personal wallet). If foreign inputs show up (CoinJoin), the fee would be wrong,
  so such a transaction is booked as `other` with a comment, never guessed.
* Unconfirmed transactions are skipped: they may still vanish.
* Paging: `/txs` gives the newest confirmed 25 (plus mempool), `/txs/chain/<last>`
  the next 25.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from decimal import Decimal

from app.modules.plugins.contract import Kind, Movement
from app.modules.plugins.evm import ChainUnavailable, http_json, since_only

PAGE = 25


def transactions(api: str, address: str) -> list[dict]:
    rows: list[dict] = []
    url = f"{api}/address/{address}/txs"
    while True:
        batch = http_json(url)
        if not isinstance(batch, list):
            raise ChainUnavailable("invalid answer")
        confirmed = [t for t in batch if (t.get("status") or {}).get("confirmed")]
        rows.extend(confirmed)
        if len(confirmed) < PAGE:
            return rows
        url = f"{api}/address/{address}/txs/chain/{confirmed[-1]['txid']}"


def fetch(
    api: str,
    address: str,
    since: datetime | None,
    progress: Callable[[dict], None] | None,
    native: str,
    decimals: int = 8,
) -> Iterator[Movement]:
    txs = transactions(api, address)
    if progress:
        progress({"step": "txs", "done": 1, "total": 1, "rows": len(txs)})
    yield from since_only(convert(address, txs, native=native, decimals=decimals), since)


def convert(address: str, txs: list[dict], *, native: str, decimals: int = 8) -> list[Movement]:
    """Pure conversion — no network, testable."""
    out: list[Movement] = []
    for t in txs:
        m = _movement(address, t, native, decimals)
        if m:
            out.append(m)
    return out


def _movement(me: str, t: dict, native: str, decimals: int) -> Movement | None:
    status = t.get("status") or {}
    if not status.get("confirmed") or not status.get("block_time"):
        return None
    ins = [(v.get("prevout") or {}) for v in t.get("vin") or []]
    return netted(
        me,
        [(p.get("scriptpubkey_address"), p.get("value")) for p in ins],
        [(o.get("scriptpubkey_address"), o.get("value")) for o in t.get("vout") or []],
        fee=int(t.get("fee") or 0),
        timestamp=datetime.fromtimestamp(int(status["block_time"]), tz=UTC),
        external_id=t.get("txid"),
        raw=t,
        native=native,
        decimals=decimals,
    )


def netted(
    me: str,
    inputs: list[tuple[str | None, int | None]],
    outputs: list[tuple[str | None, int | None]],
    *,
    fee: int | None,
    timestamp: datetime,
    external_id: str | None,
    raw: dict,
    native: str,
    decimals: int,
) -> Movement | None:
    """One UTXO transaction, netted for my address. Shared by Bitcoin, Litecoin, Kaspa,
    Cardano: they differ in field names, not in the logic. `fee=None`: unknown."""
    spent = sum(int(v or 0) for a, v in inputs if a == me)
    back = sum(int(v or 0) for a, v in outputs if a == me)
    if not spent and not back:
        return None
    unit = lambda sats: Decimal(sats).scaleb(-decimals)  # noqa: E731
    base = {"timestamp": timestamp, "external_id": external_id, "raw": raw}
    if not spent:
        payer = next((a for a, _ in inputs if a), None)
        # The sender pays the fee: none on receipt.
        return Movement(
            kind=Kind.RECEIVE,
            incoming_asset=native,
            incoming_amount=unit(back),
            counterparty=payer,
            **base,
        )
    if any(a != me for a, _ in inputs):
        return Movement(
            kind=Kind.OTHER,
            comment="inputs from other addresses",
            incoming_asset=native,
            incoming_amount=unit(back),
            outgoing_asset=native,
            outgoing_amount=unit(spent),
            **base,
        )
    fee = fee or 0
    sent = spent - back - fee
    fee_part = {"fee_asset": native, "fee_amount": unit(fee)} if fee else {}
    if sent <= 0:
        # Everything came back to me (consolidation): only the fee left the wallet.
        return Movement(kind=Kind.FEE, comment="consolidation", **fee_part, **base)
    to = next((a for a, _ in outputs if a != me), None)
    return Movement(
        kind=Kind.SEND,
        outgoing_asset=native,
        outgoing_amount=unit(sent),
        counterparty=to,
        **fee_part,
        **base,
    )


def balance(
    api: str, address: str, native: str, decimals: int = 8
) -> list[tuple[str, str, Decimal]]:
    stats = (http_json(f"{api}/address/{address}") or {}).get("chain_stats") or {}
    sats = int(stats.get("funded_txo_sum") or 0) - int(stats.get("spent_txo_sum") or 0)
    return [("spot", native, Decimal(sats).scaleb(-decimals))]
