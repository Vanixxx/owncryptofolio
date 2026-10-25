"""Every exchange ccxt reads, through one reader (ADR 0048).

ccxt gives each exchange the same calls and the same rows. What still differs is kept in
plugin.toml ([ccxt]): untested exchanges carry the beta badge, a fee inside the withdrawal
amount is set per exchange, and an exchange that needs more gets its own plugin.

* Trades: all at once where the exchange allows it; otherwise per pair, for every coin held
  now or ever moved in or out, against the usual quote coins. A coin bought and sold out
  completely at the exchange may be missing.
* Paging by time from 2017 on; an exchange that refuses a start that far back is asked
  without one and answers its recent rows only.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from decimal import Decimal
from functools import partial
from types import SimpleNamespace

from app.modules.plugins.ccxt_map import trade, transfer
from app.modules.plugins.contract import Movement
from app.modules.plugins.manifest import CcxtInfo, Credentials, Manifest

# ccxt's credential names -> ours (the form and the vault); order = order in the form
FIELDS = {
    "apiKey": "api_key",
    "secret": "api_secret",
    "password": "api_passphrase",
    "uid": "api_uid",
    "login": "api_login",
}
PUBLIC = {"api_key", "api_uid", "api_login"}
START = datetime(2017, 1, 1, tzinfo=UTC)
PAGES = 200  # per call: enough for years, a stop if an exchange pages in circles


def catalog(info: CcxtInfo) -> Iterator[tuple[str, str, list[str]]]:
    """(ccxt id, name, our credential fields) of every exchange this reader can serve."""
    import ccxt

    for eid in ccxt.exchanges:
        if eid in info.exclude:
            continue
        ex = getattr(ccxt, eid)()
        has = ex.has
        if getattr(ex, "dex", False) or not (
            has.get("fetchMyTrades")
            and has.get("fetchBalance")
            and (has.get("fetchDeposits") or has.get("fetchDepositsWithdrawals"))
        ):
            continue
        need = {k for k, v in ex.requiredCredentials.items() if v}
        if need - set(FIELDS):  # wallet keys and the like: not an API key
            continue
        yield eid, ex.name, [ours for theirs, ours in FIELDS.items() if theirs in need]


def expand(manifest: Manifest) -> Iterator[tuple[str, Manifest, SimpleNamespace]]:
    """One plugin per exchange, built from this folder's manifest."""
    info = manifest.ccxt or CcxtInfo()
    for eid, name, fields in catalog(info):
        m = manifest.model_copy(deep=True)
        m.plugin.name = f"{name} (API)"
        m.plugin.status = "tested" if eid in info.tested else "beta"
        m.source.provider, m.source.provider_name = eid, name
        m.credentials = Credentials(fields=fields, secret=[f for f in fields if f not in PUBLIC])
        module = SimpleNamespace(
            check=partial(check, eid),
            fetch=partial(fetch, eid, info),
            balance=partial(balance, eid),
        )
        yield eid, m, module


def _client(eid: str, credentials: dict[str, str]):
    import ccxt

    config = {theirs: credentials[ours] for theirs, ours in FIELDS.items() if credentials.get(ours)}
    return getattr(ccxt, eid)(config | {"enableRateLimit": True})


def check(eid: str, credentials: dict[str, str]) -> None:
    _client(eid, credentials).fetch_balance()


def _ms(d: datetime) -> int:
    return int(d.timestamp() * 1000)


def _paged(fn: Callable, start: int, *args) -> list[dict]:
    """All rows from `start` on, page by page; without a start if the exchange refuses it."""
    import ccxt

    rows: list[dict] = []
    seen: set = set()
    since: int | None = start
    for _ in range(PAGES):
        try:
            page = fn(*args, since=since)
        except ccxt.NotSupported:
            return rows
        except (ccxt.AuthenticationError, ccxt.PermissionDenied, ccxt.AccountSuspended):
            raise
        except ccxt.ExchangeError:
            if since is None or rows:
                raise
            since, page = None, fn(*args)
        new = [r for r in page if (r.get("id"), r.get("timestamp")) not in seen]
        if not new:
            break
        rows += new
        seen.update((r.get("id"), r.get("timestamp")) for r in new)
        if since is None:
            break
        # from the newest millisecond again, not the next one: rows of the same millisecond
        # beyond the page edge would be skipped (review 2026-10-24); `seen` drops the repeats
        since = max((r["timestamp"] for r in new if r.get("timestamp")), default=since)
    else:
        raise RuntimeError(f"more than {PAGES} pages: history not read to the end")
    return rows


def _transfers(client, start: int) -> tuple[list[dict], list[dict]]:
    if client.has.get("fetchDeposits"):
        deposits = _paged(client.fetch_deposits, start, None)
        withdrawals = (
            _paged(client.fetch_withdrawals, start, None)
            if client.has.get("fetchWithdrawals")
            else []
        )
    else:
        both = _paged(client.fetch_deposits_withdrawals, start, None)
        deposits = [t for t in both if t.get("type") == "deposit"]
        withdrawals = [t for t in both if t.get("type") == "withdrawal"]
    ok = (None, "ok")
    return (
        [t for t in deposits if t.get("status") in ok],
        [t for t in withdrawals if t.get("status") in ok],
    )


def fetch(
    eid: str,
    info: CcxtInfo,
    credentials: dict[str, str],
    since: datetime | None,
    progress: Callable[[dict], None] | None = None,
) -> Iterator[Movement]:
    import ccxt

    client = _client(eid, credentials)
    client.load_markets()
    start = _ms(since or START)
    deposits, withdrawals = _transfers(client, start)
    yield from (transfer(t, True) for t in deposits)
    yield from (transfer(t, False, eid in info.fee_in_amount) for t in withdrawals)
    try:
        trades = _paged(client.fetch_my_trades, start, None)
    except ccxt.ArgumentsRequired:  # only per pair
        coins = {c for c, v in (client.fetch_balance().get("total") or {}).items() if v}
        coins |= {t.get("currency") for t in deposits + withdrawals if t.get("currency")}
        pairs = sorted(
            f"{c}/{q}"
            for c in coins
            for q in info.quotes
            if (client.markets.get(f"{c}/{q}") or {}).get("spot")
        )
        trades = []
        for i, pair in enumerate(pairs, 1):
            trades += _paged(client.fetch_my_trades, start, pair)
            if progress:
                progress({"step": "trades", "done": i, "total": len(pairs)})
    yield from (trade(t) for t in trades)


def balance(eid: str, credentials: dict[str, str]) -> list:
    total = _client(eid, credentials).fetch_balance().get("total") or {}
    return [("spot", asset, Decimal(str(v))) for asset, v in total.items() if v]
