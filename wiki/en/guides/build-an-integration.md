---
title: Build your own integration
updated: 2026-10-25
---

# Build your own integration

A new exchange or a new network is **one folder** — without touching the rest of the
program. At startup, owncryptofolio finds every folder under `src/backend/integrations/` that
contains a `plugin.toml`. If something is missing or the code raises an error, only this
integration is not loaded; the reason is given in the
[Log in System status](system-health.md#log).

The bundled integrations are the best examples: `chain_stellar` (simple
network), `chain_xrp` (its own JSON-RPC), `chain_dogecoin` (UTXO), `bitget_api` (exchange with
key), `bitget_file` (file import).

## Structure of a folder

```
src/backend/integrations/chain_beispiel/
├── __init__.py      # empty
├── plugin.toml      # what the integration is and can do
└── reader.py        # reads and converts
```

You choose the folder name freely (convention: `chain_<network>`, `<exchange>_api`,
`<exchange>_file`). API and file of the same exchange are **two** folders with the same `provider`.

## plugin.toml

```toml
[plugin]
name = "Beispiel"
author = "dein-name"
version = "1.0.0"
description = "Liest XYZ-Überweisungen einer Adresse über explorer.example (kostenlos)."
status = "beta"              # "tested" only once checked against a real account

[source]
provider = "beispiel"        # key of the source, lowercase, no spaces
provider_name = "Beispiel"   # how it appears in the interface
kind = "wallet"              # "wallet" (network) or "exchange"
channel = "chain"            # "chain", "api", "file" or "manual"
provides_balance = true      # there is a balance() function for the balance check
provides_id = true           # rows carry a transaction ID
not_read = ["NFTs"]          # what is deliberately not read — shown in the interface

[chain]                      # only for channel = "chain"
native_asset = "XYZ"
decimals = 8
address_pattern = "^xyz1[0-9a-z]{38}$"   # regular expression for valid addresses
explorer = "https://explorer.example/api"
# service = "etherscan"      # needs a service key (Settings → Blockchain services)
# service_optional = true    # … that only raises the limits
```

An exchange with an API key describes the input fields:

```toml
[credentials]
fields = ["api_key", "api_secret"]
secret = ["api_secret"]      # shown hidden, stored encrypted
```

With `channel = "file"`, `expected_files = [...]` names the files the user uploads.

## reader.py

Depending on the channel, the file provides these functions:

| Channel | Function | Meaning |
|---|---|---|
| `chain` | `fetch(address, since, progress=None, key=None)` | returns movements from `since` on (or all) |
| `chain` | `balance(address, key=None, tokens=None)` | current holdings: list of `("spot", coin, amount)` |
| `api` | `fetch(credentials, since, progress=None)` | as above, with the fields from `[credentials]` |
| `api` | `balance(credentials)` | as above |
| `file` | `read(path, options=None)` | reads an uploaded file |

`progress({"step": "…", "done": 1, "total": 3, "rows": 120})` shows the progress in the
live log. A network error is reported as `chain.ChainUnavailable` — the fetch then
fails and runs again next time, instead of silently leaving out data. The same goes for a
history that breaks off while paging, or a page limit that does not deliver everything: better
an error than a gap. Nothing is stored until `fetch` has run through completely. If a service
refuses the key, report `ChainUnavailable("HTTP 401")` or `"HTTP 403"` (`http_json` does this by
itself) — the app then names it as a refused key, pointing to Settings → Blockchain services.

## The data format: `Movement`

Every row is a `Movement` from `app.modules.plugins.contract`:

| Field | Content |
|---|---|
| `timestamp` | point in time (with time zone) |
| `kind` | `trade`, `send`, `receive`, `fiat_deposit`, `fiat_withdrawal`, `income`, `internal_transfer`, `migration`, `fee`, `realized_pnl`, `funding`, `futures_position`, `other` |
| `income_kind` | for `income`: `staking`, `reward`, `interest` or `airdrop` |
| `market` | `spot` (default) or `futures` |
| `incoming_asset`, `incoming_amount` | what came in |
| `outgoing_asset`, `outgoing_amount` | what went out |
| `fee_asset`, `fee_amount` | the fee |
| `external_id` | transaction ID — important for recognition and transfers |
| `counterparty` | address of the other side |
| `comment`, `instrument`, `raw` | note, futures contract, the original as a dictionary |

Rules that owncryptofolio enforces:

- **Amounts are `Decimal`, never `float`.** Smallest units are converted exactly
  (`chain.units(value, places)`).
- Asset and amount always come **together**; a trade has both sides.
- Nothing is left out: what the integration does not understand becomes `other` — it appears in
  the interface and can be classified by hand.
- The same row delivered twice is recognized and stored only once (fingerprint from
  time, kind, amounts and ID).

Helpers in `app.modules.plugins.chain`: `transfer(...)` decides from sender and receiver
by itself whether it is `send`, `receive` or `internal_transfer`; `since_only(...)` filters by
point in time; `http_json(url, body=None, headers=None)` queries an interface, with
retry on overload. For UTXO networks, `mempool.netted(...)` nets inputs,
change and fee.

## Testing

1. **Without network:** a test with made-up responses in the shape of the interface (examples
   in `src/backend/tests/test_chains_nonevm.py`) — it checks conversion, fees and
   special cases.
2. **Against a public address:** fetch and compare the sum of all movements with the
   account balance that `balance()` reports. If it matches to the last digit, the
   model is right.
3. **In the app:** create a wallet, add the network, fetch — the
   [Balance check](sources.md#balance-check) must show "matches".
4. Only when this matches on an account **of your own**, `status = "tested"`.

After that, add the new source to the table under [Sources](sources.md#all-sources-at-a-glance)
— a test reminds you if it is missing.

## Complete example

A made-up network "Beispiel" (coin `XYZ`, 8 decimal places), whose explorer answers
`GET /address/<address>/txs?page=N` with `{"txs": [{"hash", "time", "from", "to", "value",
"fee", "ok"}]}` and `GET /address/<address>` with `{"balance": "…"}` (amounts in
smallest units as text, time in Unix seconds):

```python
"""Beispiel through explorer.example (written from its docs, 2026-10-23)."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import datetime

from app.modules.plugins import chain
from app.modules.plugins.contract import Kind, Movement

API = "https://explorer.example/api"
NATIVE, DECIMALS = "XYZ", 8


def transactions(address: str) -> list[dict]:
    rows: list[dict] = []
    page = 1
    while True:
        body = chain.http_json(f"{API}/address/{address}/txs?page={page}")
        txs = (body or {}).get("txs")
        if not isinstance(txs, list):
            raise chain.ChainUnavailable("invalid answer")  # never guess on a broken answer
        rows += txs
        if not txs:
            return rows
        page += 1


def convert(address: str, txs: list[dict]) -> list[Movement]:
    out: list[Movement] = []
    for t in txs:
        sent = t["from"] == address
        fee = chain.units(t.get("fee") or 0, DECIMALS) if sent else None
        base = {"timestamp": chain.seconds(t["time"]), "external_id": t["hash"], "raw": t}
        if not t.get("ok"):
            if fee:  # failed: only the fee left the address
                out.append(Movement(kind=Kind.FEE, fee_asset=NATIVE, fee_amount=fee, **base))
            continue
        out.append(
            chain.transfer(
                sent=sent,
                received=t["to"] == address,
                asset=NATIVE,
                amount=chain.units(t["value"], DECIMALS),
                sender=t["from"],
                receiver=t["to"],
                fee=fee,
                fee_asset=NATIVE,
                **base,
            )
        )
    return out


def fetch(
    address: str,
    since: datetime | None,
    progress: Callable[[dict], None] | None = None,
    key: str | None = None,
) -> Iterator[Movement]:
    txs = transactions(address)
    if progress:
        progress({"step": "transactions", "done": 1, "total": 1, "rows": len(txs)})
    yield from chain.since_only(convert(address, txs), since)


def balance(address: str, key: str | None = None, tokens: dict | None = None) -> list:
    body = chain.http_json(f"{API}/address/{address}")
    return [("spot", NATIVE, chain.units(body.get("balance") or 0, DECIMALS))]
```

And the test for it, without network (`src/backend/tests/test_beispiel.py`):

```python
from decimal import Decimal

from app.modules.plugins.contract import Kind


def test_beispiel_send_with_fee_receive_and_failed():
    from integrations.chain_beispiel import reader

    txs = [
        {"hash": "a", "time": 1, "from": "X", "to": "ME", "value": "150000000", "fee": "1000", "ok": True},
        {"hash": "b", "time": 2, "from": "ME", "to": "Y", "value": "50000000", "fee": "1000", "ok": True},
        {"hash": "c", "time": 3, "from": "ME", "to": "Y", "value": "1", "fee": "1000", "ok": False},
    ]
    got = reader.convert("ME", txs)
    assert [m.kind for m in got] == [Kind.RECEIVE, Kind.SEND, Kind.FEE]
    assert got[0].incoming_amount == Decimal("1.5")
    assert (got[1].outgoing_amount, got[1].fee_amount) == (Decimal("0.5"), Decimal("0.00001"))
```

Tests run in `src/backend` with `uv run pytest -q tests/test_beispiel.py`, formatting and
checks with `uv run ruff format` and `uv run ruff check`.

## Checklist (also for an AI that is to write an integration)

Give an AI this page and the documentation of the interface. An integration is done
when:

1. the folder `src/backend/integrations/<name>/` exists with `__init__.py`, `plugin.toml` and
   `reader.py`, and **nothing outside** this folder was changed (except the
   new test and the row in the sources table);
2. `plugin.toml` has all required fields (`[plugin]` name, author, version, description,
   status; `[source]` provider, provider_name, kind, channel; for networks `[chain]`
   native_asset, decimals, address_pattern, explorer) — unknown fields are forbidden;
3. `reader.py` has the channel's functions with **exactly these names and parameters**
   (table above) and returns a `Movement` for every row;
4. all amounts are `Decimal` (`chain.units` from smallest units, `Decimal(text)` from
   decimal text), never `float`;
5. only the sender bears fees, a failed transaction is only its fee,
   anything not understood becomes `Kind.OTHER` and nothing is lost;
6. every row has a stable `external_id` (hash; with several rows per transaction, with a
   suffix: the first keeps the plain hash, further ones get `hash:2`, `hash:3` …, so that two
   equal movements in one transaction stay two rows);
7. a broken or missing response raises `chain.ChainUnavailable` instead of leaving out
   data;
8. a test without network checks the conversion and `uv run pytest`, `uv run ruff check` and
   `uv run ruff format --check` run without errors;
9. on a public address **sum of all movements = `balance()`** holds — only then is
   the model right;
10. `status = "beta"` stays until someone has checked it against an account of their own.

What an integration is and how it behaves in the program: [Integrations](../concepts/integrations.md).
