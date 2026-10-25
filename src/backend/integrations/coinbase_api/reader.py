"""Coinbase — API import through the account ledger (research 2026-09-06).

**Why the ledger.** Coinbase's CSV converts every money amount into the display
currency (USD) and keeps no field in the currency actually paid. The account
has exactly one fiat wallet, the Euro Wallet; a SOL purchase shows as 203.76 USD
(fee 1.93) in the CSV and as 180.00 EUR (fee 2.99) in the ledger. `native_amount`
in the API is USD too (display setting) and is never used.

* A purchase appears in the ledger of both wallets involved, a card purchase
  even three times (EUR in, EUR out, crypto in). The halves share the id of the
  `buy`/`sell`/`trade` block; each movement is emitted once, from its crypto side.
* A coin-to-coin conversion carries neither total nor fee: both halves are the
  two sides.
* The trade's fiat side is `subtotal`, the fee its own: `total` already holds the fee
  (buy: subtotal + fee, sell: subtotal − fee).
* `advanced_trade_fill` has no linking id; the counter amount is size × price.
* **Staking/unstaking transfers are not emitted**: the ledger shows one leg, which
  created balance from nothing (+0.0353 SOL, +0.0687 DOT); the CSV has both legs
  netting to exactly zero.
* Income carries no fee: the CSV's "spread" on rewards is not a cost.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from datetime import UTC, datetime
from decimal import Decimal

from app.modules.plugins.contract import IncomeKind, Kind, Movement

EARLIEST = datetime(2012, 1, 1, tzinfo=UTC)
LINKED = ("buy", "sell", "trade")
INCOME = {
    "interest": IncomeKind.STAKING,
    "staking_reward": IncomeKind.STAKING,
    "inflation_reward": IncomeKind.STAKING,
    "earn_payout": IncomeKind.REWARD,
    "earn_task": IncomeKind.REWARD,
}
STAKING_TRANSFERS = ("staking_transfer", "unstaking_transfer")


def _secret(raw: str) -> str:
    """Two key formats: an ECDSA key as PEM (BEGIN/END lines) and an Ed25519 key as
    one base64 line of 88 characters. ccxt tells them apart by exactly that shape,
    so only a PEM key gets its trailing line break."""
    # A key pasted from JSON often arrives with literal "\n" instead of line breaks.
    key = raw.replace("\\n", "\n").strip()
    return key + "\n" if key.startswith("-----BEGIN") else key


def key_pair(credentials: dict[str, str]) -> tuple[str, str]:
    """The key file wins: it is what Coinbase hands out. It carries the key name as
    `name` (older CDP keys) or `id` (newer ones) and the private key."""
    import json

    raw = (credentials.get("key_file") or "").strip()
    if raw:
        try:
            data = json.loads(raw)
        except ValueError as exc:
            raise ValueError("key file is not valid JSON") from exc
        name, private = data.get("name") or data.get("id"), data.get("privateKey")
        if not name or not private:
            raise ValueError("key file lacks name/id or privateKey")
        return str(name).strip(), _secret(str(private))
    return credentials["api_key"].strip(), _secret(credentials["api_secret"])


def _client(credentials: dict[str, str]):
    import ccxt

    name, private = key_pair(credentials)
    return ccxt.coinbase({"apiKey": name, "secret": private, "enableRateLimit": True})


def check(credentials: dict[str, str]) -> None:
    _client(credentials).fetch_accounts()


def fetch(
    credentials: dict[str, str],
    since: datetime | None,
    progress: Callable[[dict], None] | None = None,
) -> Iterator[Movement]:
    client = _client(credentials)
    accounts = client.fetch_accounts()
    start = int((since or EARLIEST).timestamp() * 1000)
    entries: list[dict] = []
    for i, account in enumerate(accounts, 1):
        info = account.get("info") or {}
        code = account.get("code") or account.get("currency") or str(info.get("currency") or "")
        if isinstance(code, dict):
            code = code.get("code")
        if code:
            entries.extend(client.fetch_ledger(code=code, since=start, params={"paginate": True}))
        if progress:
            progress({"step": "ledger", "done": i, "total": len(accounts), "rows": len(entries)})
    yield from convert(entries)


def _dec(v) -> Decimal | None:
    return None if v is None or v == "" else Decimal(str(v))


def _money(block) -> tuple[str | None, Decimal | None]:
    if not isinstance(block, dict):
        return None, None
    return block.get("currency") or None, _dec(block.get("amount"))


def _ts(entry: dict) -> datetime:
    return datetime.fromtimestamp(entry["timestamp"] / 1000, tz=UTC)


def _link(info: dict) -> tuple[str, str] | None:
    for field in LINKED:
        block = info.get(field)
        if isinstance(block, dict) and block.get("id"):
            return field, block["id"]
    return None


def _incoming(entry: dict) -> bool:
    if entry.get("direction"):
        return entry["direction"] == "in"
    return (_dec(entry.get("amount")) or Decimal(0)) > 0


def _side(asset, amount, incoming: bool) -> dict:
    return (
        {"incoming_asset": asset, "incoming_amount": amount}
        if incoming
        else {"outgoing_asset": asset, "outgoing_amount": amount}
    )


def convert(entries: Iterable[dict]) -> Iterator[Movement]:
    """Pure conversion of `fetch_ledger` entries over all wallets."""
    groups: dict[tuple[str, str], list[dict]] = {}
    singles: list[dict] = []
    for e in entries:
        link = _link(e.get("info") or {})
        if link is None:
            singles.append(e)
        else:
            groups.setdefault(link, []).append(e)
    for (field, _), halves in groups.items():
        if (m := _linked(field, halves)) is not None:
            yield m
    for e in singles:
        if (m := _single(e)) is not None:
            yield m


def _linked(field: str, halves: list[dict]) -> Movement | None:
    block = halves[0]["info"].get(field) or {}
    # `total` includes the fee (a buy: 177.01 + 2.99 = 180.00 paid; a sell: 55.00 − 2.99 =
    # 52.01 received); the fee is booked on its own, so the trade's side is `subtotal` —
    # with `total` the fee came off twice (Vanixxx, Coinbase 17.06.2023, 2026-10-10)
    counter_asset, counter = _money(block.get("subtotal"))
    if counter is None:
        counter_asset, counter = _money(block.get("total"))
    fee_asset, fee = _money(block.get("fee"))
    if counter is None and len(halves) == 2:
        return _conversion(halves)
    main = [h for h in halves if h.get("currency") != counter_asset] or [
        h for h in halves if _incoming(h)
    ]
    if not main:
        return None
    h = main[0]
    amount = abs(_dec(h.get("amount")) or Decimal(0))
    asset, inc = h.get("currency"), _incoming(h)
    sides = {
        **_side(asset, amount, inc),
        **_side(counter_asset, abs(counter) if counter else None, not inc),
    }
    return Movement(
        timestamp=_ts(h),
        kind=Kind.TRADE,
        fee_asset=fee_asset if fee else None,
        fee_amount=abs(fee) if fee else None,
        external_id=h["id"],
        comment=_paid_from_outside(block),
        raw=h,
        **sides,
    )


def _paid_from_outside(block: dict) -> str | None:
    """A buy paid by card or PayPal, not from a wallet here: the money came straight from
    outside — the app counts it as paid in (Vanixxx's Coinbase PayPal buys, 2026-10-10)."""
    method = str(block.get("payment_method_name") or "")
    if not method or "wallet" in method.lower():
        return None
    return "Paid by PayPal" if "paypal" in method.lower() else "Paid by card"


def _conversion(halves: list[dict]) -> Movement | None:
    ins = [h for h in halves if _incoming(h)]
    outs = [h for h in halves if not _incoming(h)]
    if not ins or not outs:
        return None
    i, o = ins[0], outs[0]
    return Movement(
        timestamp=_ts(o),
        kind=Kind.TRADE,
        incoming_asset=i.get("currency"),
        incoming_amount=abs(_dec(i.get("amount"))),
        outgoing_asset=o.get("currency"),
        outgoing_amount=abs(_dec(o.get("amount"))),
        external_id=o["id"],
        raw=o,
    )


def _single(e: dict) -> Movement | None:
    info = e.get("info") or {}
    typ = info.get("type")
    asset = e.get("currency")
    amount = abs(_dec(e.get("amount")) or Decimal(0))
    base = {"timestamp": _ts(e), "external_id": e["id"], "raw": e}
    inc = _incoming(e)
    if typ in INCOME:
        return Movement(
            kind=Kind.INCOME,
            income_kind=INCOME[typ],
            incoming_asset=asset,
            incoming_amount=amount,
            **base,
        )
    if typ == "advanced_trade_fill":
        return _fill(e, asset, amount, base)
    if typ in STAKING_TRANSFERS:
        return None  # one leg only - the file brings both (see module doc)
    if typ == "fiat_deposit":
        return Movement(
            kind=Kind.FIAT_DEPOSIT, incoming_asset=asset, incoming_amount=amount, **base
        )
    if typ == "fiat_withdrawal":
        return Movement(
            kind=Kind.FIAT_WITHDRAWAL, outgoing_asset=asset, outgoing_amount=amount, **base
        )
    if typ in ("send", "tx"):
        # the chain's transaction id and the address on the other side (Vanixxx,
        # 2026-10-11: details showed no address, a send to his own Metamask stayed open)
        net = info.get("network") or {}
        other = (info.get("from") if inc else info.get("to")) or {}
        return Movement(
            kind=Kind.RECEIVE if inc else Kind.SEND,
            **_side(asset, amount, inc),
            **{**base, "external_id": net.get("hash") or e["id"]},
            counterparty=other.get("address") or None,
        )
    return Movement(
        kind=Kind.OTHER, comment=f"Coinbase type {typ!r}", **_side(asset, amount, inc), **base
    )


def _fill(e: dict, asset, amount: Decimal, base: dict) -> Movement | None:
    """Advanced-trade fill: no linking id; counter = size × fill price. Only the base
    side is emitted, the quote side in the other wallet would duplicate it."""
    block = e["info"].get("advanced_trade_fill") or {}
    product = str(block.get("product_id") or "")
    if "-" not in product:
        return None
    b, q = product.split("-", 1)
    if asset != b:
        return None
    price = _dec(block.get("fill_price"))
    counter = amount * price if price is not None else None
    fee = _dec(block.get("commission"))
    buy = str(block.get("order_side")).lower() == "buy"
    return Movement(
        kind=Kind.TRADE,
        **_side(b, amount, buy),
        **_side(q, counter, not buy),
        fee_asset=q if fee else None,
        fee_amount=fee or None,
        **base,
    )


def _amounts(total: dict, market: str) -> list:
    from decimal import Decimal

    return [(market, asset, Decimal(str(v))) for asset, v in (total or {}).items() if v]


def balance(credentials: dict[str, str]) -> list:
    """Current balances (ADR 0039): spot."""
    client = _client(credentials)
    out = _amounts(client.fetch_balance().get("total"), "spot")
    return out
