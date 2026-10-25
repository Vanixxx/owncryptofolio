"""Shared building blocks for networks with their own answer form (M3b).

A reader only re-sorts a record: who sent, who received, which asset, how much.
`transfer` decides the kind from that, the same way on every network:

| case | kind |
|---|---|
| I received | receive (the sender pays the fee: none on receipt) |
| I sent | send + fee |
| both are me | internal_transfer + fee |
| neither | other — shown, never dropped |
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from app.modules.plugins.contract import Kind, Movement
from app.modules.plugins.evm import ChainUnavailable, http_json, since_only  # noqa: F401


def units(raw: int | str, decimals: int) -> Decimal:
    """Smallest unit → amount, exact (`scaleb`, never a float division)."""
    return Decimal(int(raw)).scaleb(-decimals)


def seconds(value) -> datetime:
    return datetime.fromtimestamp(int(value), tz=UTC)


def transfer(
    *,
    sent: bool,
    received: bool,
    asset: str,
    amount: Decimal,
    timestamp: datetime,
    external_id: str | None,
    raw: dict,
    sender: str | None = None,
    receiver: str | None = None,
    fee: Decimal | None = None,
    fee_asset: str | None = None,
    comment: str | None = None,
) -> Movement:
    base = {"timestamp": timestamp, "external_id": external_id, "raw": raw, "comment": comment}
    paid = {"fee_asset": fee_asset or asset, "fee_amount": fee} if sent and fee else {}
    if sent and received:
        return Movement(
            kind=Kind.INTERNAL_TRANSFER,
            incoming_asset=asset,
            incoming_amount=amount,
            outgoing_asset=asset,
            outgoing_amount=amount,
            **paid,
            **base,
        )
    if sent:
        return Movement(
            kind=Kind.SEND,
            outgoing_asset=asset,
            outgoing_amount=amount,
            counterparty=receiver,
            **paid,
            **base,
        )
    if received:
        return Movement(
            kind=Kind.RECEIVE,
            incoming_asset=asset,
            incoming_amount=amount,
            counterparty=sender,
            **base,
        )
    return Movement(kind=Kind.OTHER, incoming_asset=asset, incoming_amount=amount, **base)
