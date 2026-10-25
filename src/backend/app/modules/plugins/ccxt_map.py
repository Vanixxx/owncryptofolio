"""ccxt's unified rows as movements: shared by the ccxt based plugins (MEXC, ADR 0048).

ccxt gives every exchange's trades and transfers the same shape; what differs per exchange
(a fee inside the amount) is passed in, not guessed."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from app.modules.plugins.contract import Kind, Movement


def _dec(v) -> Decimal | None:
    return None if v in (None, "") else Decimal(str(v))  # via str: Decimal(0.1) is not 0.1


def _ts(ms) -> datetime:
    return datetime.fromtimestamp(int(ms) / 1000, tz=UTC)


def trade(t: dict) -> Movement:
    base, _, quote = str(t.get("symbol") or "").partition("/")
    qty, cost = _dec(t.get("amount")), _dec(t.get("cost"))
    buy = t.get("side") == "buy"
    fee = t.get("fee") or {}
    return Movement(
        timestamp=_ts(t["timestamp"]),
        kind=Kind.TRADE,
        incoming_asset=base if buy else quote,
        incoming_amount=qty if buy else cost,
        outgoing_asset=quote if buy else base,
        outgoing_amount=cost if buy else qty,
        fee_asset=fee.get("currency") if _dec(fee.get("cost")) else None,
        fee_amount=_dec(fee.get("cost")) or None,
        external_id=t.get("id"),
        comment=f"{t.get('symbol')} {t.get('side')}",
        raw=t.get("info") or {},
    )


def transfer(t: dict, incoming: bool, fee_in_amount: bool = False) -> Movement:
    """A deposit or withdrawal; a withdrawal leaves with amount + fee, unless the exchange
    counts the fee inside the amount (`fee_in_amount`)."""
    amount = _dec(t.get("amount"))
    fee = t.get("fee") or {}
    if (
        fee_in_amount
        and not incoming
        and amount is not None
        and fee.get("currency") == t.get("currency")
    ):
        amount -= _dec(fee.get("cost")) or 0
    return Movement(
        timestamp=_ts(t["timestamp"]),
        kind=Kind.RECEIVE if incoming else Kind.SEND,
        **(
            {"incoming_asset": t.get("currency"), "incoming_amount": amount}
            if incoming
            else {"outgoing_asset": t.get("currency"), "outgoing_amount": amount}
        ),
        fee_asset=None if incoming or not _dec(fee.get("cost")) else fee.get("currency"),
        fee_amount=None if incoming else (_dec(fee.get("cost")) or None),
        external_id=t.get("txid") or t.get("id"),
        counterparty=t.get("address"),
        raw=t.get("info") or {},
    )
