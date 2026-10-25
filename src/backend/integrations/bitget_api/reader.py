"""Bitget — API import through the tax endpoints.

`/api/v2/tax/spot-record` and `/api/v2/tax/future-record` instead of
`fetch_my_trades`: the trade endpoint ends after ~100 days ("43111 param error
time range illegal"), the tax endpoints reach back to the first
  spot record (2024-02 for this account, measured 2026-10-03); windows before
  that come back empty, not as an error. Futures reach less far (2024-09). They need no trading
pair and return everything in one stream.

* A window may span at most 30 days ("interval cannot be greater than 30 days",
  measured, undocumented). Pages of up to 500, continued with `idLessThan`.
* A spot trade is two rows linked by `bizOrderId`, one positive, one negative.
  Booked separately each purchase would become two half movements.
* The tax endpoints are strictly rate limited: 44 calls in 46 s ended in
  `429 Too Many Requests` (measured 2026-10-03). Calls are spaced and a 429 is
  retried with growing pauses instead of failing the whole fetch.
* Futures records use the same type names as the futures ledger file, so both
  plugins map them through one function.
"""

from __future__ import annotations

import time
from collections import defaultdict
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.modules.plugins.contract import Kind, Market, Movement
from integrations.bitget_file.reader import FUTURES_NO_CASH, futures_kind

EARLIEST = datetime(2018, 1, 1, tzinfo=UTC)  # Bitget's founding; older windows come back empty
WINDOW_DAYS = 30
PAGE = 500
PRODUCT_TYPES = ("USDT-FUTURES", "COIN-FUTURES", "USDC-FUTURES")
MIGRATION_TYPES = {"Reduce exchange rate", "Increase exchange rate"}
SINGLE = {
    "Deposit": Kind.RECEIVE,
    "Withdrawal": Kind.SEND,
    "fiat_recharge_in": Kind.FIAT_DEPOSIT,
    "Transfer in": Kind.INTERNAL_TRANSFER,
    "Transfer out": Kind.INTERNAL_TRANSFER,
}
Progress = Callable[[dict], None]
MIN_INTERVAL = 1.1  # seconds between tax calls
RETRIES = (2, 5, 10, 20, 40)  # pauses after a 429, then give up
_sleep = time.sleep  # replaced in tests
_last_call = 0.0


def _rate_limited(exc: Exception) -> bool:
    text = str(exc)
    return type(exc).__name__ in ("RateLimitExceeded", "DDoSProtection") or "429" in text


def _call(fn, params: dict) -> dict:
    """One tax call: spaced from the previous one, retried on 429."""
    global _last_call
    for pause in (*RETRIES, None):
        wait = MIN_INTERVAL - (time.monotonic() - _last_call)
        if wait > 0:
            _sleep(wait)
        _last_call = time.monotonic()
        try:
            return fn(params)
        except Exception as exc:
            if pause is None or not _rate_limited(exc):
                raise
            _sleep(pause)
    raise AssertionError("unreachable")


def _client(credentials: dict[str, str]):
    import ccxt  # imported lazily: only API plugins need it

    return ccxt.bitget(
        {
            "apiKey": credentials["api_key"],
            "secret": credentials["api_secret"],
            "password": credentials["api_passphrase"],
            "enableRateLimit": True,
        }
    )


def check(credentials: dict[str, str]) -> None:
    """Building the client validates nothing; a private call does."""
    _client(credentials).fetch_balance()


def windows(start: datetime, end: datetime, days: int = WINDOW_DAYS):
    step = timedelta(days=days)
    while start < end:
        yield start, min(start + step, end)
        start += step


def _paged(call, params: dict) -> list[dict]:
    out: list[dict] = []
    cursor = None
    while True:
        query = {**params, "limit": str(PAGE), **({"idLessThan": cursor} if cursor else {})}
        page = _call(call, query).get("data") or []
        out.extend(page)
        if len(page) < PAGE:
            return out
        cursor = page[-1].get("id")


def fetch(
    credentials: dict[str, str], since: datetime | None, progress: Progress | None = None
) -> Iterator[Movement]:
    client = _client(credentials)
    end = datetime.now(UTC)
    start = since or EARLIEST
    spans = list(windows(start, end))
    spot: list[dict] = []
    futures: list[dict] = []
    for i, (a, b) in enumerate(spans, 1):
        params = {
            "startTime": str(int(a.timestamp() * 1000)),
            "endTime": str(int(b.timestamp() * 1000)),
        }
        spot.extend(_paged(client.privateTaxGetV2TaxSpotRecord, params))
        for product in PRODUCT_TYPES:
            futures.extend(
                _paged(client.privateTaxGetV2TaxFutureRecord, {**params, "productType": product})
            )
        if progress:
            progress(
                {"step": "fetch", "done": i, "total": len(spans), "rows": len(spot) + len(futures)}
            )
    yield from convert_spot(spot)
    yield from convert_futures(futures)


def _num(v: object) -> Decimal:
    return Decimal(str(v or "0"))


def _ts(ms: object) -> datetime:
    return datetime.fromtimestamp(int(ms) / 1000, tz=UTC)


def convert_spot(records: list[dict]) -> Iterator[Movement]:
    """Pure conversion, no network — testable."""
    by_order: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        by_order[r.get("bizOrderId") or r.get("id")].append(r)
    for rows in by_order.values():
        if len(rows) == 2 and (m := _pair(rows)) is not None:
            yield m
            continue
        for r in rows:
            yield _single(r)


def _pair(rows: list[dict]) -> Movement | None:
    ins = [r for r in rows if _num(r.get("amount")) > 0]
    outs = [r for r in rows if _num(r.get("amount")) < 0]
    if len(ins) != 1 or len(outs) != 1:
        return None  # not guessed: both go through as single rows and show up as 'other'
    i, o = ins[0], outs[0]
    types = {r.get("spotTaxType") for r in rows}
    fee_row = next((r for r in rows if _num(r.get("fee")) != 0), None)
    return Movement(
        timestamp=_ts(i.get("ts")),
        kind=Kind.MIGRATION if types <= MIGRATION_TYPES else Kind.TRADE,
        incoming_asset=i.get("coin"),
        incoming_amount=_num(i.get("amount")),
        outgoing_asset=o.get("coin"),
        outgoing_amount=-_num(o.get("amount")),
        fee_asset=fee_row.get("coin") if fee_row else None,
        fee_amount=abs(_num(fee_row.get("fee"))) if fee_row else None,
        external_id=i.get("bizOrderId"),
        comment=f"{o.get('spotTaxType')}/{i.get('spotTaxType')}",
        raw={"rows": rows},
    )


def _sides(coin: str | None, amount: Decimal) -> dict:
    if amount > 0:
        return {"incoming_asset": coin, "incoming_amount": amount}
    if amount < 0:
        return {"outgoing_asset": coin, "outgoing_amount": -amount}
    return {}


def _single(r: dict) -> Movement:
    fee = abs(_num(r.get("fee")))
    return Movement(
        timestamp=_ts(r.get("ts")),
        kind=SINGLE.get(r.get("spotTaxType"), Kind.OTHER),
        fee_asset=r.get("coin") if fee else None,
        fee_amount=fee or None,
        external_id=r.get("id"),
        comment=r.get("spotTaxType"),
        raw=r,
        **_sides(r.get("coin"), _num(r.get("amount"))),
    )


def convert_futures(records: list[dict]) -> Iterator[Movement]:
    for r in records:
        typ = str(r.get("futureTaxType") or r.get("taxType") or "")
        if typ in FUTURES_NO_CASH:
            continue
        coin = r.get("marginCoin") or r.get("coin")
        amount, fee = _num(r.get("amount")), _num(r.get("fee"))
        yield Movement(
            timestamp=_ts(r.get("ts")),
            kind=futures_kind(typ, amount),
            market=Market.FUTURES,
            instrument=r.get("symbol") or None,
            fee_asset=coin if fee else None,
            fee_amount=abs(fee) or None,
            external_id=r.get("id"),
            comment=typ,
            raw=r,
            **_sides(coin, amount),
        )


def _amounts(total: dict, market: str) -> list:
    from decimal import Decimal

    return [(market, asset, Decimal(str(v))) for asset, v in (total or {}).items() if v]


def balance(credentials: dict[str, str]) -> list:
    """Current balances (ADR 0039): spot, plus the USDT-M futures account."""
    client = _client(credentials)
    out = _amounts(client.fetch_balance().get("total"), "spot")
    out += _amounts(client.fetch_balance({"type": "swap"}).get("total"), "futures")
    return out
