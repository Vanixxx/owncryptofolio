"""The price sources (ADR 0019, research 2026-08-25/26). Each delivers a list of daily
points; what differs is hidden here: Yahoo wants a period, Bitget pages backwards, the
ECB has no weekends.

Numbers never pass through float: `json.loads(..., parse_float=Decimal)` keeps the digits
as they stand in the answer.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation

TIMEOUT = 30
RETRY_PAUSES = (2, 5, 10)


class SourceUnavailable(RuntimeError):
    """Network, timeout or an answer that is none."""


@dataclass(frozen=True)
class Point:
    day: date
    close: Decimal
    high: Decimal | None = None
    low: Decimal | None = None


def get_json(url: str):
    for attempt in range(len(RETRY_PAUSES) + 1):
        req = urllib.request.Request(url, headers={"User-Agent": "owncryptofolio"})
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                return json.loads(resp.read(), parse_float=Decimal)
        except urllib.error.HTTPError as exc:
            if exc.code in (429, 503) and attempt < len(RETRY_PAUSES):
                time.sleep(RETRY_PAUSES[attempt])
                continue
            raise SourceUnavailable(f"HTTP {exc.code}") from exc
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            raise SourceUnavailable(type(exc).__name__) from exc
    raise SourceUnavailable("no answer")


def usable(value) -> Decimal | None:
    """A price, or a gap dressed as a number? Yahoo delivers literally 0.0 for tiny coins
    (XEN on 952 of 969 days, measured 2026-08-26) between real values like 5.5e-09: a
    placeholder, not a rounding. A 0 is no information, never a price."""
    if value is None:
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return number if number.is_finite() and number > 0 else None


# --- Yahoo Finance -------------------------------------------------------------

YAHOO = "https://query1.finance.yahoo.com/v8/finance/chart/"
ANCHOR = date(2015, 1, 1)
"""Always ask from here. Yahoo returns an EMPTY series without error when the period is
too short (POL-USD from 2024-01-01: 0 days, from 2023-01-01: 1,333 days); the limit
differs per ticker. Asking from far back and cutting ourselves is reliable."""


YAHOO_TINY = Decimal("0.0001")


def _ts(d: date) -> int:
    return int(datetime.combine(d, datetime.min.time(), UTC).timestamp())


def _yahoo_result(ticker: str, query: str) -> dict:
    body = get_json(f"{YAHOO}{urllib.parse.quote(ticker)}?{query}")
    result = ((body or {}).get("chart") or {}).get("result") if isinstance(body, dict) else None
    if not result:
        raise SourceUnavailable(f"Yahoo does not know {ticker}")
    return result[0]


def yahoo_daily(ticker: str, start: date, end: date) -> list[Point]:
    """Daily closes with high/low. period1/period2, not range=max: that silently gave
    144 days for BTC in the first measurement."""
    r = _yahoo_result(
        ticker, f"period1={_ts(ANCHOR)}&period2={_ts(end + timedelta(days=1))}&interval=1d"
    )
    stamps = r.get("timestamp") or []
    q = ((r.get("indicators") or {}).get("quote") or [{}])[0]
    closes, highs, lows = q.get("close") or [], q.get("high") or [], q.get("low") or []
    if len(stamps) != len(closes):
        # cutting to the shorter series would lose points without anyone noticing
        raise SourceUnavailable(f"Yahoo gave {len(stamps)} times for {len(closes)} prices")
    points = []
    for i, stamp in enumerate(stamps):
        close = usable(closes[i])
        day = datetime.fromtimestamp(int(stamp), UTC).date()
        if close is None or not start <= day <= end:
            continue
        high = usable(highs[i]) if i < len(highs) else None
        low = usable(lows[i]) if i < len(lows) else None
        points.append(Point(day, close, high, low))
    if points:
        typical = sorted(p.close for p in points)[len(points) // 2]
        if typical < YAHOO_TINY:
            # Yahoo keeps past closes as 32-bit numbers with six decimals: QUBIC became
            # 0.000001, XEN 0, SHIB 0.000006 instead of 0.0000057 (measured 2026-10-04).
            # Below 0.0001 USD that is off by more than 1 %: the next source takes over.
            raise SourceUnavailable(f"Yahoo rounds {ticker} to six decimals")
    return points


def yahoo_meta(ticker: str) -> tuple[str | None, Decimal | None]:
    """Long name (without the trailing quote currency) and the current price."""
    meta = _yahoo_result(ticker, "range=1d&interval=1d").get("meta") or {}
    name = meta.get("longName") or meta.get("shortName")
    if name:
        for tail in (" USD", " EUR"):
            name = name[: -len(tail)] if name.endswith(tail) else name
    return (name or None), usable(meta.get("regularMarketPrice"))


# --- Bitget ---------------------------------------------------------------------

BITGET = "https://api.bitget.com/api/v2/spot/market/"
BITGET_DAY = "1Dutc"
"""Day candles with the UTC boundary. Bitget's `1day` starts at 16:00 UTC (midnight
UTC+8): every price would carry a date that is not its own, 16 hours off Yahoo."""
BITGET_PAGE = 200


def bitget_daily(ticker: str, start: date, end: date) -> list[Point]:
    """Bitget pages backwards: `endTime` says up to where, it delivers the candles before."""
    found: dict[date, Point] = {}
    until = datetime.combine(end + timedelta(days=1), datetime.min.time(), UTC)
    while True:
        body = get_json(
            f"{BITGET}history-candles?symbol={ticker}&granularity={BITGET_DAY}"
            f"&limit={BITGET_PAGE}&endTime={int(until.timestamp() * 1000)}"
        )
        candles = body.get("data") if isinstance(body, dict) else None
        if not candles:
            break
        for c in candles:  # 0 time · 1 open · 2 high · 3 low · 4 close
            day = datetime.fromtimestamp(int(c[0]) / 1000, UTC).date()
            close = usable(c[4])
            if close is not None and start <= day <= end:
                found[day] = Point(day, close, usable(c[2]), usable(c[3]))
        oldest = datetime.fromtimestamp(int(candles[0][0]) / 1000, UTC)
        if oldest.date() <= start or oldest >= until:
            break
        until = oldest
        time.sleep(0.3)  # Bitget answered 429 when pushed
    return [found[d] for d in sorted(found)]


def bitget_pairs() -> dict[str, Decimal | None]:
    """All spot pairs with their last price."""
    body = get_json(f"{BITGET}tickers")
    data = body.get("data") if isinstance(body, dict) else None
    return {t["symbol"]: usable(t.get("lastPr")) for t in data or [] if t.get("symbol")}


# --- Binance --------------------------------------------------------------------

BINANCE = "https://data-api.binance.vision/api/v3/"
"""Binance's public market-data mirror, no key. Its day candles open at 00:00 UTC, and it
still serves the candles of delisted pairs: MATICUSDT and FTMUSDT, which Yahoo (404) and
Bitget (400) no longer have after the switch to POL and S (measured 2026-10-04)."""
BINANCE_PAGE = 1000


def binance_daily(ticker: str, start: date, end: date) -> list[Point]:
    found: dict[date, Point] = {}
    since = _ts(start) * 1000
    stop = _ts(end + timedelta(days=1)) * 1000
    while since < stop:
        body = get_json(
            f"{BINANCE}klines?symbol={ticker}&interval=1d"
            f"&startTime={since}&endTime={stop}&limit={BINANCE_PAGE}"
        )
        if not isinstance(body, list) or not body:
            break
        for k in body:  # 0 open time · 1 open · 2 high · 3 low · 4 close
            day = datetime.fromtimestamp(int(k[0]) / 1000, UTC).date()
            close = usable(k[4])
            if close is not None and start <= day <= end:
                found[day] = Point(day, close, usable(k[2]), usable(k[3]))
        if len(body) < BINANCE_PAGE:
            break
        since = int(body[-1][0]) + 86_400_000
    return [found[d] for d in sorted(found)]


def binance_prices() -> dict[str, Decimal | None]:
    """All Binance pairs with their last price, one call."""
    body = get_json(f"{BINANCE}ticker/price")
    return {
        t["symbol"]: usable(t.get("price"))
        for t in body or []
        if isinstance(t, dict) and t.get("symbol")
    }


def binance_latest(ticker: str) -> Decimal | None:
    body = get_json(f"{BINANCE}ticker/price?symbol={ticker}")
    return usable(body.get("price")) if isinstance(body, dict) else None


# --- CoinGecko: last rank, by hand only -----------------------------------------

COINGECKO = "https://api.coingecko.com/api/v3/"
COINGECKO_DAYS = 365
"""The free tier reaches back exactly 365 days (error 10012 from 366 on, measured).
Its ticker is the id from the address bar (`vara-network`), never guessed from a
symbol: `VARA` matches three coins there."""


def coingecko_daily(coin_id: str, start: date, end: date) -> list[Point]:
    body = get_json(
        f"{COINGECKO}coins/{urllib.parse.quote(coin_id)}/market_chart"
        f"?vs_currency=usd&days={COINGECKO_DAYS}&interval=daily"
    )
    rows = body.get("prices") if isinstance(body, dict) else None
    if not rows:
        raise SourceUnavailable(f"CoinGecko does not know {coin_id}")
    found: dict[date, Point] = {}
    for stamp, price in rows:
        day = datetime.fromtimestamp(int(stamp) / 1000, UTC).date()
        close = usable(price)
        if close is not None and start <= day <= end:
            found[day] = Point(day, close)
    return [found[d] for d in sorted(found)]


def coingecko_latest(coin_id: str) -> Decimal | None:
    body = get_json(f"{COINGECKO}simple/price?ids={urllib.parse.quote(coin_id)}&vs_currencies=usd")
    return usable(((body or {}).get(coin_id) or {}).get("usd")) if isinstance(body, dict) else None


# --- ECB via Frankfurter ---------------------------------------------------------

FRANKFURTER = "https://api.frankfurter.app/"


def ecb_usd_eur(start: date, end: date) -> list[tuple[date, Decimal, bool, date]]:
    """USD → EUR per day: (day, rate, approximated, source_day). Weekends and holidays take
    the last published rate, marked; before the first published one stays a gap."""
    body = get_json(f"{FRANKFURTER}{start.isoformat()}..{end.isoformat()}?from=USD&to=EUR")
    rates = body.get("rates") if isinstance(body, dict) else None
    if not rates:
        raise SourceUnavailable("ECB series empty")
    published = {
        date.fromisoformat(d): Decimal(str(v["EUR"])) for d, v in rates.items() if "EUR" in v
    }
    out, last = [], None
    day = start
    while day <= end:
        if day in published:
            last = (day, published[day])
            out.append((day, published[day], False, day))
        elif last is not None:
            out.append((day, last[1], True, last[0]))
        day += timedelta(days=1)
    return out


# --- fine prices (M11, ADR 0044) ---------------------------------------------------


@dataclass(frozen=True)
class Tick:
    at: datetime
    close: Decimal


STEP_SECONDS = {"5m": 300, "1h": 3600}


def yahoo_fine(ticker: str, step: str, start: datetime, end: datetime) -> list[Tick]:
    """5 minutes reach back 60 days at Yahoo, hours 730."""
    interval = "5m" if step == "5m" else "60m"
    r = _yahoo_result(
        ticker,
        f"period1={int(start.timestamp())}&period2={int(end.timestamp())}&interval={interval}",
    )
    stamps = r.get("timestamp") or []
    closes = (((r.get("indicators") or {}).get("quote") or [{}])[0]).get("close") or []
    out = []
    for i, stamp in enumerate(stamps[: len(closes)]):
        close = usable(closes[i])
        if close is not None:
            out.append(Tick(datetime.fromtimestamp(int(stamp), UTC), close))
    if out and sorted(t.close for t in out)[len(out) // 2] < YAHOO_TINY:
        raise SourceUnavailable(f"Yahoo rounds {ticker} to six decimals")
    return out


def binance_fine(ticker: str, step: str, start: datetime, end: datetime) -> list[Tick]:
    found: dict[datetime, Tick] = {}
    since, stop = int(start.timestamp() * 1000), int(end.timestamp() * 1000)
    while since < stop:
        body = get_json(
            f"{BINANCE}klines?symbol={ticker}&interval={step}"
            f"&startTime={since}&endTime={stop}&limit={BINANCE_PAGE}"
        )
        if not isinstance(body, list) or not body:
            break
        for k in body:
            close = usable(k[4])
            if close is not None:
                at = datetime.fromtimestamp(int(k[0]) / 1000, UTC)
                found[at] = Tick(at, close)
        if len(body) < BINANCE_PAGE:
            break
        since = int(body[-1][0]) + STEP_SECONDS[step] * 1000
    return [found[a] for a in sorted(found)]


def bitget_fine(ticker: str, step: str, start: datetime, end: datetime) -> list[Tick]:
    granularity = "5min" if step == "5m" else "1h"
    found: dict[datetime, Tick] = {}
    until = end
    while True:
        body = get_json(
            f"{BITGET}history-candles?symbol={ticker}&granularity={granularity}"
            f"&limit={BITGET_PAGE}&endTime={int(until.timestamp() * 1000)}"
        )
        candles = body.get("data") if isinstance(body, dict) else None
        if not candles:
            break
        for c in candles:
            close = usable(c[4])
            at = datetime.fromtimestamp(int(c[0]) / 1000, UTC)
            if close is not None and at >= start:
                found[at] = Tick(at, close)
        oldest = datetime.fromtimestamp(int(candles[0][0]) / 1000, UTC)
        if oldest <= start or oldest >= until:
            break
        until = oldest
        time.sleep(0.3)
    return [found[a] for a in sorted(found)]


def coingecko_fine(coin_id: str, step: str, start: datetime, end: datetime) -> list[Tick]:
    """Hours only: the free tier gives hourly points for 2–90 days back."""
    if step != "1h":
        raise SourceUnavailable("CoinGecko has no 5-minute history in the free tier")
    body = get_json(
        f"{COINGECKO}coins/{urllib.parse.quote(coin_id)}/market_chart?vs_currency=usd&days=90"
    )
    rows = body.get("prices") if isinstance(body, dict) else None
    if not rows:
        raise SourceUnavailable(f"CoinGecko does not know {coin_id}")
    out = []
    for stamp, price in rows:
        at = datetime.fromtimestamp(int(stamp) / 1000, UTC)
        close = usable(price)
        if close is not None and start <= at <= end:
            out.append(Tick(at, close))
    return out


FINE = {
    "yahoo": yahoo_fine,
    "bitget": bitget_fine,
    "binance": binance_fine,
    "coingecko": coingecko_fine,
}
