"""MEXC — API sync (research 2026-08-23).

* **No history**: from 90 days back MEXC answers `75008 Exceeded the queryable
  time range`. This plugin keeps the account current; the past comes from files.
* Every query (trades, deposits, withdrawals) may span at most **7 days**
  (`33333 start time and end time diff cannot exceed 7 days`, measured 2026-10-03).
* Windows must be *below* 90 days and need `endTime`, otherwise MEXC queries
  from `since` to now and rejects it.
* **Trades are per pair**, there is no "all trades" call. Pairs: every asset of
  the current balance or of a deposit/withdrawal in the period, against USDT and USDC
  (a coin bought and sold again in between is only found through the money moved).
* A trade page holds at most `TRADE_LIMIT` rows: within a window it is paged on from the
  newest millisecond until a page comes back short (review 2026-10-24).
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.modules.plugins.ccxt_map import trade, transfer
from app.modules.plugins.contract import Movement

HISTORY_DAYS = 89
# trades, deposits, withdrawals: "start time and end time diff cannot exceed 7 days"
WINDOW_DAYS = 7
QUOTES = ("USDT", "USDC")
TRADE_LIMIT = 100  # MEXC myTrades: default and maximum page size


def _client(credentials: dict[str, str]):
    import ccxt

    return ccxt.mexc(
        {
            "apiKey": credentials["api_key"],
            "secret": credentials["api_secret"],
            "enableRateLimit": True,
        }
    )


def check(credentials: dict[str, str]) -> None:
    _client(credentials).fetch_balance()


def _windows(start: datetime, end: datetime, days: int = WINDOW_DAYS):
    step = timedelta(days=days)
    while start < end:
        yield start, min(start + step, end)
        start += step


def _ms(d: datetime) -> int:
    return int(d.timestamp() * 1000)


def fetch(
    credentials: dict[str, str],
    since: datetime | None,
    progress: Callable[[dict], None] | None = None,
) -> Iterator[Movement]:
    client = _client(credentials)
    end = datetime.now(UTC)
    start = max(since or end - timedelta(days=HISTORY_DAYS), end - timedelta(days=HISTORY_DAYS))
    client.load_markets()
    moved: list[Movement] = []
    coins = {c for c, v in (client.fetch_balance().get("total") or {}).items() if v}
    for fetch_fn, incoming in ((client.fetch_deposits, True), (client.fetch_withdrawals, False)):
        for a, b in _windows(start, end):
            for t in fetch_fn(since=_ms(a), params={"endTime": _ms(b)}):
                if t.get("status") in (None, "ok"):
                    moved.append(transfer(t, incoming))
                    coins.add(t.get("currency") or "")
    pairs = sorted(f"{c}/{q}" for c in coins for q in QUOTES if f"{c}/{q}" in client.markets)
    for i, pair in enumerate(pairs, 1):
        for a, b in _windows(start, end):
            yield from (trade(t) for t in _trades(client, pair, _ms(a), _ms(b)))
        if progress:
            progress({"step": "trades", "done": i, "total": len(pairs)})
    yield from moved


def _trades(client, pair: str, since: int, until: int) -> list[dict]:
    """All trades of one pair in one window, page by page."""
    rows: list[dict] = []
    seen: set = set()
    while True:
        page = client.fetch_my_trades(
            pair, since=since, limit=TRADE_LIMIT, params={"endTime": until}
        )
        new = [t for t in page if (t.get("id"), t.get("timestamp")) not in seen]
        rows += new
        seen.update((t.get("id"), t.get("timestamp")) for t in new)
        if len(page) < TRADE_LIMIT or not new:
            return rows
        since = max((t["timestamp"] for t in new if t.get("timestamp")), default=since)


def _amounts(total: dict, market: str) -> list:

    return [(market, asset, Decimal(str(v))) for asset, v in (total or {}).items() if v]


def balance(credentials: dict[str, str]) -> list:
    """Current balances (ADR 0039): spot, plus the USDT-M futures account (like Bitget;
    the futures account answers with the same key, measured 2026-10-10)."""
    client = _client(credentials)
    out = _amounts(client.fetch_balance().get("total"), "spot")
    out += _amounts(client.fetch_balance({"type": "swap"}).get("total"), "futures")
    return out
