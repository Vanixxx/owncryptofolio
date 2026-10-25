---
title: API (JSON)
updated: 2026-10-25
---

# API (JSON)

owncryptofolio also hands out your data as **simple web addresses** that another
program can query: a widget on your phone, a sensor in Home Assistant, an Excel sheet,
an automation (n8n, Node-RED) or a small script of your own.

The API **only reads**. There is no address that changes, creates or deletes anything. To
change things, there is [Claude with the "Edit" level](connect-claude.md) or the interface.

## At a glance

| | |
|---|---|
| Address | `http://<your-server>:<port>/api/v1/…` (the port you exposed for the container, 8085 in the examples) |
| Sign-in | header `Authorization: Bearer <Token>` |
| Token | separate **API tokens** (starting with `ocf_api_`), created under Settings → API (JSON) |
| On/off | Settings → API (JSON) → **Enable the API** (default: off) |
| Method | `GET` only |
| Response | JSON, UTF-8 |
| Reachable | only in your home network (on the go via a VPN to your home) |
| Log | every call appears in the [Log](system-health.md#log) (logger `api`) |

## Setting up

1. Expand **Settings → API (JSON)** and **Enable the API**.
2. Enter a name, e.g. "Home Assistant", and **Create token**.
3. The token appears **only this one time** — copy it right away. Only a fingerprint is
   stored; lost is lost, then create a new one.
4. Expand **Use the API**: the examples already contain the new token and the right
   address.

**A separate token for each application.** Then you see in the list which one asked
last, and you can **revoke** one on its own without touching the others.

### API tokens and Claude tokens are separate

An API token opens **only** the API, a Claude token **only** Claude (MCP). A token that
you give to a spreadsheet or a widget can therefore never change anything through Claude — not even
if someone gets hold of it. If you turn off the API, Claude is not affected,
and vice versa.

## A first call

In the terminal (Linux, macOS, Windows PowerShell with `curl.exe`):

```
curl -H "Authorization: Bearer ocf_api_…" http://192.168.1.10:8085/api/v1
```

The response lists **all addresses** with description and parameters — the API describes
itself. After that, for example:

```
curl -H "Authorization: Bearer ocf_api_…" http://192.168.1.10:8085/api/v1/portfolio
curl -H "Authorization: Bearer ocf_api_…" "http://192.168.1.10:8085/api/v1/prices?asset=BTC&days=7"
```

Parameters go after `?` as usual, several joined with `&`. Put quotes around the address
as soon as it contains an `&`.

## What the responses contain

- **Amounts are text**, e.g. `"5274.48"` — that way all decimal places stay exact. For a
  calculation in Excel or Home Assistant, convert them to a number.
- **Values in your display currency** (EUR or USD, as set under Settings or with the
  EUR/USD switch). Which one is given in the `currency` field for holdings and prices.
- **Times** in ISO 8601 format with time zone, e.g. `2026-10-20T08:15:00+00:00`.
  Date parameters (`date_from`, `date_to`) apply in the time zone you have set.
- **Field names are English** (`value`, `qty`, `cost` …) — as is usual in programming.
- **Addresses are shortened** (`0x5290…9EE7`), keys and passwords never appear. Neither do the name,
  address and tax number from the head of the reports.
- **At most 200 rows** per call. Lists say with `total` and `more` whether there are more;
  then page on with `offset` or narrow the period.

## Errors

| Status | `error.code` | Meaning |
|---|---|---|
| 401 | `api.token_invalid` | no token, wrong token, revoked — or a Claude token |
| 403 | `api.off` | the API is turned off |
| 400 | `api.invalid_params` | parameter missing or not valid (e.g. `days=abc`); `error.params.reason` says which |
| 404 | `api.unknown` | this address does not exist |
| 503 | `db.unavailable` | the database cannot be reached right now |

An error always comes as `{"error": {"code": "…", "params": {…}}}`.

## All addresses

The examples show made-up values; lists are shortened to one or two entries. `…` stands for omitted fields.

### `/api/v1` — directory

All addresses with description (in English) and parameters — the API describes itself.

No parameters.

**Request**

```
curl -H "Authorization: Bearer ocf_api_…" http://192.168.1.10:8085/api/v1
```

**Response** (shortened, example values)

```json
{
  "endpoints": [
    {
      "path": "/api/v1/prices",
      "description": "Current price and the daily closes of the last `days` days, in the display currency.",
      "params": {
        "asset": {"type": "string", "description": "Coin, e.g. BTC"},
        "days": {"type": "integer", "default": 30}
      }
    }
  ]
}
```

### `/api/v1/portfolio` — holdings and total value

Today's state, as the Dashboard and Holdings show it.

No parameters.

**Request**

```
curl -H "Authorization: Bearer ocf_api_…" http://192.168.1.10:8085/api/v1/portfolio
```

**Response** (shortened, example values)

```json
{
  "summary": {
    "currency": "EUR",
    "value": "5274.48",
    "crypto": "5201.10",
    "cash": "73.38",
    "cost": "14778.79",
    "unrealized": "-9505.17",
    "unrealized_pct": "-64.3",
    "realized": "-296.88",
    "realized_pct": "-1.7",
    "futures": {"pnl": "-120.10", "funding": "-8.40", "fees": "-16.00", "result": "-144.50"},
    "result": "-9946.55",
    "income": "138.60",
    "net_deposited": "15754.26",
    "high": {"day": "2024-12-06", "value": "19954.81", "cost": "15102.00", "deposited": "15200.00"},
    "first": "2021-03-14"
  },
  "coins": [
    {
      "asset": "BTC", "name": "Bitcoin",
      "qty": "0.0213", "price": "92450.10", "value": "1969.19",
      "cost": "1500.00", "avg_price": "70422.53",
      "realized": "0", "unrealized": "469.19", "unrealized_pct": "31.3",
      "income": "0", "since": "2023-02-01", "days_held": 992, "fiat": false,
      "places": [{"source": "Tangem – Bitcoin", "market": "spot", "qty": "0.0213"}]
    }
  ]
}
```

`summary`: `value` total value (= `crypto` + `cash`), `cost` cost basis, `unrealized` / `realized`
(+ `_pct` in percent), `futures` futures result broken down, `result` total result,
`income` income, `net_deposited` net deposited, `high` the all-time high, `first` the first
transaction. `coins[]`: per coin amount, price, value, cost basis, average price, result, since when
it has been held and where it is (`places`).

### `/api/v1/sources` — sources and notices

All exchanges and wallet networks, plus open notices.

No parameters.

**Request**

```
curl -H "Authorization: Bearer ocf_api_…" http://192.168.1.10:8085/api/v1/sources
```

**Response** (shortened, example values)

```json
{
  "sources": [
    {
      "id": 4, "label": "Bitget", "provider": "bitget", "kind": "exchange",
      "rows": 1943, "last_fetch": "2026-10-20T04:00:12+00:00",
      "last_check": {"at": "2026-10-20T04:00:05+00:00", "ok": true, "message": null},
      "auto_fetch": true, "wallet_id": null, "address": null
    },
    {
      "id": 9, "label": "Ethereum", "provider": "ethereum", "kind": "wallet",
      "rows": 33, "last_fetch": "2026-10-20T04:01:40+00:00", "last_check": null,
      "auto_fetch": true, "wallet_id": 2, "address": "0x5290…9EE7"
    }
  ],
  "alerts": [
    {"source_id": 12, "kind": "fetch_failed", "date": "2026-10-19", "days": 1, "message": "timeout"}
  ]
}
```

`alerts[].kind`: `key_rejected` (API key rejected), `fetch_failed` (fetch
failed), `history_at_risk` (the exchange will soon stop providing older data). You need the `id`
for `search_transactions?source_id=…`.

### `/api/v1/balance_check` — balance check per source

Per source: the holdings computed from the transactions against those reported by the exchange or blockchain.

No parameters.

**Request**

```
curl -H "Authorization: Bearer ocf_api_…" http://192.168.1.10:8085/api/v1/balance_check
```

**Response** (shortened, example values)

```json
{
  "sources": [
    {"source": "Bitget", "source_id": 4, "status": "ok", "at": "2026-10-20T04:00:20+00:00",
     "differences": 0, "coins": []},
    {"source": "MEXC", "source_id": 6, "status": "differences", "at": "2026-10-20T04:00:31+00:00",
     "differences": 1,
     "coins": [{"asset": "USDT", "market": "spot", "computed": "12.40", "actual": "12.95",
                "diff": "0.55", "ok": false}]}
  ]
}
```

`status`: `ok`, `differences` (at least one coin differs) or `none` (the source reports
no balance). `coins[]` only lists coins that differ.

### `/api/v1/holdings_by_source` — what is where

Per source, coin and market the computed amount.

| Parameter | Required | Meaning |
|---|---|---|
| `asset` | no | only this coin, e.g. `BTC` |

**Request**

```
curl -H "Authorization: Bearer ocf_api_…" "http://192.168.1.10:8085/api/v1/holdings_by_source?asset=ETH"
```

**Response** (shortened, example values)

```json
{
  "holdings": [
    {"source": "Bitget", "asset": "ETH", "market": "spot", "qty": "0.15"},
    {"source": "Tangem – Ethereum", "asset": "ETH", "market": "spot", "qty": "0.042"}
  ]
}
```

### `/api/v1/search_transactions` — search transactions

Like the Transactions page: one row per trade, deposit/withdrawal or linked transfer, newest first.

| Parameter | Required | Meaning |
|---|---|---|
| `date_from` | no | first day, `YYYY-MM-DD`, your time zone |
| `date_to` | no | last day |
| `asset` | no | coin(s), several separated by commas: `BTC,ETH` |
| `kind` | no | kind: `trade`, `send`, `receive`, `transfer`, `income`, `fiat_deposit`, `fiat_withdrawal`, `fee` … |
| `source_id` | no | source(s), several separated by commas (ids from `/sources`) |
| `text` | no | words in coin, transaction ID, comment or note |
| `show` | no | `normal` (default), `open` (without counterpart), `edited`, `noted`, `spam`, `dust`, `short` (negative holdings), `mcp` (changed through MCP) |
| `limit` | no | rows, 1–200, default 50 |
| `offset` | no | starting from which row (for paging), default 0 |

**Request**

```
curl -H "Authorization: Bearer ocf_api_…" "http://192.168.1.10:8085/api/v1/search_transactions?asset=BTC&date_from=2025-01-01&date_to=2025-12-31&limit=2"
```

**Response** (shortened, example values)

```json
{
  "total": 37, "shown": 2, "more": true,
  "items": [
    {
      "type": "row", "id": 2210, "at": "2025-11-03T09:12:44+00:00",
      "source": "Bitget", "kind": "trade", "market": "spot",
      "incoming": "0.002 BTC", "outgoing": "180.50 USDT", "fee": "0.18 USDT",
      "external_id": "1189…4471",
      "values": {"incoming": "171.30", "outgoing": "171.30", "fee": "0.17"}
    },
    {
      "type": "transfer", "at": "2025-10-28T18:02:10+00:00",
      "send": {"id": 2190, "source": "Bitget", "kind": "send", "outgoing": "0.005 BTC", "fee": "0.0001 BTC", "…": "…"},
      "receive": {"id": 2191, "source": "Tangem – Bitcoin", "kind": "receive", "incoming": "0.005 BTC", "…": "…"},
      "network_fee": null
    }
  ]
}
```

A row (`type: row`) has `id`, time `at`, `source`, `kind`, the sides `incoming`,
`outgoing`, `fee` as text, the values at the time of the transaction `values` (display currency), and
depending on the case `note`, `comment`, `income_kind`, `counterparty` (shortened) as well as flags like
`open`, `edited`, `spam`, `dust`. A trade can have `result` (profit/loss). A transfer
(`type: transfer`) has `send` and `receive`. With `more: true` there are more hits: increase `offset`
by `shown`.

### `/api/v1/transaction` — one transaction in detail

The stored row with its raw data (addresses shortened) and its tax side.

| Parameter | Required | Meaning |
|---|---|---|
| `row_id` | yes | id of the row (from `search_transactions`) |

**Request**

```
curl -H "Authorization: Bearer ocf_api_…" "http://192.168.1.10:8085/api/v1/transaction?row_id=2190"
```

**Response** (shortened, example values)

```json
{
  "row": {
    "id": 2190, "source": "Bitget", "source_id": 4, "channel": "api",
    "timestamp": "2025-10-28T18:02:10+00:00", "kind": "send", "market": "spot",
    "outgoing_asset": "BTC", "outgoing_amount": "0.005",
    "fee_asset": "BTC", "fee_amount": "0.0001",
    "external_id": "a3f2…9c10", "counterparty": "bc1qar…5mdq",
    "raw": {"coin": "BTC", "size": "0.005", "toAddress": "bc1qar…5mdq", "…": "…"},
    "imported_at": "2025-10-29T04:00:15+00:00"
  },
  "tax": {
    "method": "fifo", "sold": [], "incomes": [],
    "moved": [{"asset": "BTC", "qty": "0.005", "acquired": "2023-02-01T10:00:00+00:00",
               "cost": "120.00", "origin": 1830, "free_from": "2024-02-01"}],
    "later": {"sold": [], "losses": [], "open": []}
  }
}
```

`raw` is the original data of the source — different for every exchange or blockchain. `tax`: what
the tax report makes of this row — `sold` (disposals with gain), `incomes`,
`moved` (moved lots with acquisition date and from when they are tax-free).

### `/api/v1/open_transfers` — outgoing and incoming without counterpart

Like `search_transactions?show=open`.

| Parameter | Required | Meaning |
|---|---|---|
| `limit` | no | 1–200, default 100 |

**Request**

```
curl -H "Authorization: Bearer ocf_api_…" "http://192.168.1.10:8085/api/v1/open_transfers?limit=1"
```

**Response** (shortened, example values)

```json
{
  "total": 3, "shown": 1, "more": true,
  "items": [
    {"type": "row", "id": 1907, "at": "2025-06-11T14:20:00+00:00", "source": "MEXC",
     "kind": "send", "market": "spot", "outgoing": "250 USDT", "fee": "1 USDT",
     "counterparty": "TLa2f6…YjU7", "open": true}
  ]
}
```

### `/api/v1/prices` — price of a coin

Current price and daily prices of the last days, in the display currency.

| Parameter | Required | Meaning |
|---|---|---|
| `asset` | yes | coin, e.g. `BTC` |
| `days` | no | days of history, 7–3650, default 30 |

**Request**

```
curl -H "Authorization: Bearer ocf_api_…" "http://192.168.1.10:8085/api/v1/prices?asset=BTC&days=7"
```

**Response** (shortened, example values)

```json
{
  "now": {"asset": "BTC", "price": "92450.10", "currency": "EUR", "day": "2026-10-20", "latest": true},
  "days": [
    {"day": "2026-10-14", "close": "90310.00", "high": "91200.00", "low": "89120.00"},
    {"day": "2026-10-15", "close": "91022.50", "high": "91880.00", "low": "89900.00"}
  ]
}
```

### `/api/v1/tax_year` — tax year

Like the tax report under Reports.

| Parameter | Required | Meaning |
|---|---|---|
| `year` | yes | e.g. `2025` |
| `method` | no | `fifo` or `lifo`; empty = setting |
| `lines` | no | `true`: also the individual sales and income (at most 200 each) |

**Request**

```
curl -H "Authorization: Bearer ocf_api_…" "http://192.168.1.10:8085/api/v1/tax_year?year=2025&lines=true"
```

**Response** (shortened, example values)

```json
{
  "summary": {
    "year": 2025, "method": "fifo", "airdrop_taxable": false,
    "s23": {"gains": "219.86", "losses": "-79.96", "net": "139.90", "limit": "1000",
            "taxable": false, "share": "14", "tax_free_gain": "-1.27", "count": 187, "count_taxed": 185, "…": "…"},
    "s22": {"total": "0", "limit": "256", "taxable": false, "share": "0", "count": 0, "…": "…"},
    "s20": {"gains": "83.23", "losses": "-141.59", "fees": "-9.09", "net": "-67.45", "…": "…"},
    "lost": {"cost": "0", "count": 0, "unknown_cost": 0},
    "forms": [{"form": "SO", "line": null, "key": "s23_net", "value": "139.90"}],
    "carry": {"year": {"year": 2025, "start": "303.67", "end": "303.67", "…": "…"}, "rows": ["…"], "opening": null},
    "open": {"uncovered": 0, "open_sends": 0, "unvalued_assets": []}
  },
  "counts": {"disposals": 187, "incomes": 0, "futures": 12, "losses": 0, "…": "…"},
  "disposals": [
    {"asset": "SOL", "place": "Bitget", "sold": "2025-03-02T11:00:00+00:00",
     "acquired": "2024-11-20T08:30:00+00:00", "days": 102, "qty": "1.5",
     "proceeds": "210.00", "cost": "180.00", "gain": "30.00", "tax_free": false,
     "estimated": false, "how": "fifo", "row": 1702, "origin": 1550}
  ],
  "incomes": []
}
```

`s23` private sales (§ 23 EStG) with Freigrenze (tax-free allowance) `limit` and share `share` in percent,
`s22` other income (§ 22 Nr. 3 EStG), `s20` futures (§ 20 EStG), `lost` total losses, `forms`
the values for the Anlagen (tax return annexes), `carry` the loss carryforward (like `/loss_carry`), `open`
unresolved items. `disposals[]` (only with `lines=true`): per sale coin, place, sale and
acquisition date, holding period `days`, proceeds, cost basis, gain, tax-free yes/no.

### `/api/v1/loss_carry` — loss carryforward

Per year the loss carryforward under § 23 Abs. 3 EStG.

No parameters.

**Request**

```
curl -H "Authorization: Bearer ocf_api_…" http://192.168.1.10:8085/api/v1/loss_carry
```

**Response** (shortened, example values)

```json
{
  "year": {"year": 2026, "net": "-40.00", "limit": "1000", "taxable": false,
           "start": "303.67", "used": "0", "loss": "40.00", "end": "343.67", "running": true, "…": "…"},
  "rows": [
    {"year": 2024, "net": "-303.67", "limit": "600", "taxable": false, "start": "0",
     "used": "0", "back_in": "0", "back_out": "0", "loss": "303.67", "remaining": "0",
     "end": "303.67", "assessed": null, "note": null, "diff": null, "running": false}
  ],
  "opening": null
}
```

Per year: `net` result under § 23, `limit` Freigrenze, `start` carryforward at the start of the year, `used`
used, `back_out`/`back_in` carryback into the previous year, `loss` new loss, `end` carryforward at the
end of the year, `assessed` the value from the Bescheid (tax assessment notice, if entered) and `diff` the
difference. `running: true` = current year.

### `/api/v1/tax_free_soon` — tax-free soon

Which amounts pass the one-year holding period in the coming days — and what is already tax-free today.

| Parameter | Required | Meaning |
|---|---|---|
| `days` | no | look-ahead, 1–366 days, default 90 |

**Request**

```
curl -H "Authorization: Bearer ocf_api_…" "http://192.168.1.10:8085/api/v1/tax_free_soon?days=30"
```

**Response** (shortened, example values)

```json
{
  "upcoming": [
    {"asset": "HBAR", "free_on": "2026-10-22", "qty": "595.7736", "value": "43.42", "gain": "-12.10"}
  ],
  "today": {
    "currency": "EUR",
    "coins": [{"asset": "BTC", "free": "0.0150", "taxed": "0.0063", "value_free": "1386.75",
               "value_taxed": "582.44", "gain_free": "420.00", "gain_taxed": "49.19",
               "next_free": "2027-01-15", "next_qty": "0.0063"}],
    "total": {"value_free": "2950.10", "value_taxed": "2251.00", "gain_free": "390.00", "gain_taxed": "-10012.00"}
  },
  "limits": {"year": 2026,
             "s23": {"value": "-40.00", "limit": "1000", "share": "0", "level": "ok"},
             "s22": {"value": "12.30", "limit": "256", "share": "5", "level": "ok"}}
}
```

`limits.*.level`: `ok`, `near` (Freigrenze reached soon) or `over`.

### `/api/v1/origin` — source of funds

Where the money of a sale, transfer or withdrawal comes from — or that of today's holdings.

| Parameter | Required | Meaning |
|---|---|---|
| `row_id` | no | sale, transfer or withdrawal (id from `/origin_candidates`); empty = today's holdings |
| `asset` | no | without `row_id`: only this coin |

**Request**

```
curl -H "Authorization: Bearer ocf_api_…" "http://192.168.1.10:8085/api/v1/origin?row_id=2190"
```

**Response** (shortened, example values)

```json
{
  "target": {"kind": "send", "at": "2025-10-28T18:02:10+00:00", "asset": "BTC",
             "qty": "0.005", "amount": "0.005", "value": "450.00", "place": "Bitget", "to": "Tangem – Bitcoin"},
  "method": "fifo",
  "mix": [
    {"kind": "bank", "value": "380.00", "share": "84.4"},
    {"kind": "gain", "value": "70.00", "share": "15.6"}
  ],
  "overview": {"from": "2023-02-01", "to": "2025-10-28", "transactions": 6,
               "sources": [{"place": "Bitget", "kind": "exchange", "address": null, "count": 6,
                            "channels": {"api": 5, "file": 1, "manual": 0}}],
               "channels": {"api": 5, "file": 1, "manual": 0, "chain": 0}},
  "lost": {"count": 0, "assets": []},
  "deposits": [
    {"kind": "bank", "at": "2023-01-30T09:00:00+00:00", "place": "Bitget", "to": null,
     "asset": "EUR", "qty": "380.00", "value": "380.00", "row": 1801, "share": "84.4",
     "tx": "SEPA…", "channel": "api"}
  ]
}
```

`mix[].kind`: `bank` (deposit from the bank account), `card` (card purchase), `gain` (price gain),
`income` (income), `futures`, `unknown` / `money_unknown` (cannot be attributed), `loss`.
`deposits[]` the deposits the money comes from, with share `share` in percent.

### `/api/v1/origin_candidates` — transactions for the source of funds

Sales, transfers and withdrawals, newest first — their `row` is the `row_id` for `/origin`.

| Parameter | Required | Meaning |
|---|---|---|
| `limit` | no | 1–200, default 50 |

**Request**

```
curl -H "Authorization: Bearer ocf_api_…" "http://192.168.1.10:8085/api/v1/origin_candidates?limit=1"
```

**Response** (shortened, example values)

```json
{
  "total": 350,
  "items": [
    {"kind": "send", "at": "2025-10-28T18:02:10+00:00", "place": "Bitget",
     "to": "Tangem – Bitcoin", "asset": "BTC", "qty": "0.005", "value": "450.00", "row": 2190}
  ]
}
```

### `/api/v1/system_status` — system status

Is everything running? Good for monitoring.

No parameters.

**Request**

```
curl -H "Authorization: Bearer ocf_api_…" http://192.168.1.10:8085/api/v1/system_status
```

**Response** (shortened, example values)

```json
{
  "version": "1.6.1.0",
  "uptime_seconds": 86400,
  "operations": {
    "backup": {"enabled": true, "next_at": "2026-10-21T03:00:00+02:00",
               "last_at": "2026-10-20T03:00:41+02:00", "status": "done", "probe_ok": true, "message": null},
    "fetch": {"enabled": true, "next_at": "2026-10-21T04:00:00+02:00",
              "last_at": "2026-10-20T04:02:10+02:00", "status": "done", "failed": 0},
    "prices": {"enabled": true, "live_at": "2026-10-20T21:55:00+02:00", "status": "done", "failed": 0, "…": "…"},
    "fine": {"enabled": true, "last_at": "2026-10-20T21:00:12+02:00", "status": "done", "failed": 0, "…": "…"},
    "tools": {"pg_dump": 18, "server": 18, "ok": true},
    "disk": {"data": {"path": "/data", "free": 1209462790144, "total": 9452620791808, "used": 5242880},
             "backups": {"path": "/backups", "free": 1209462790144, "total": 9452620791808, "used": 41943040},
             "database": 52428800}
  },
  "log_level": "INFO"
}
```

Example for monitoring: `operations.backup.status` is not `done`, or
`operations.backup.last_at` is more than two days ago → report it. Storage values in bytes.

### `/api/v1/log_excerpt` — log excerpt

The last lines of the log (server and browser), from a given level up.

| Parameter | Required | Meaning |
|---|---|---|
| `level` | no | from `DEBUG`, `INFO`, `WARNING` (default) or `ERROR` up |
| `limit` | no | 1–200 lines, default 50 |

**Request**

```
curl -H "Authorization: Bearer ocf_api_…" "http://192.168.1.10:8085/api/v1/log_excerpt?level=WARNING&limit=2"
```

**Response** (shortened, example values)

```json
{
  "lines": [
    {"seq": 812, "at": "2026-10-20T04:00:31+00:00", "level": "WARNING",
     "logger": "app.modules.jobs.service", "origin": "backend",
     "message": "fetch 12 failed: timeout"},
    {"seq": 815, "at": "2026-10-20T08:14:02+00:00", "level": "ERROR",
     "logger": "frontend", "origin": "frontend",
     "message": "GET /api/stats: 500 http_500 (/stats)"}
  ]
}
```

## Examples

### Home Assistant: total value as a sensor

In `configuration.yaml` (the card under **Use the API** has the example with your token):

```yaml
rest:
  - resource: http://192.168.1.10:8085/api/v1/portfolio
    headers:
      Authorization: Bearer ocf_api_…
    scan_interval: 900
    sensor:
      - name: owncryptofolio Wert
        value_template: "{{ value_json.summary.value }}"
        unit_of_measurement: "EUR"
      - name: owncryptofolio Ergebnis
        value_template: "{{ value_json.summary.result }}"
        unit_of_measurement: "EUR"
```

`scan_interval: 900` asks every 15 minutes — more often brings nothing, prices come every
5 minutes.

### iPhone widget with the "Scriptable" app

Scriptable (free in the App Store) can build small widgets from web data:

```javascript
const req = new Request("http://192.168.1.10:8085/api/v1/portfolio")
req.headers = { Authorization: "Bearer ocf_api_…" }
const data = await req.loadJSON()
const w = new ListWidget()
w.addText("Portfolio").font = Font.boldSystemFont(14)
const v = Number(data.summary.value).toLocaleString("de-DE", { style: "currency", currency: data.summary.currency })
w.addText(v).font = Font.boldSystemFont(22)
Script.setWidget(w)
Script.complete()
```

The widget updates when the iPhone is in the home network or on the VPN.

### Excel (Windows): get data

**Data → From Web → Advanced**: address `http://192.168.1.10:8085/api/v1/portfolio`,
as header `Authorization` with `Bearer ocf_api_…`. Power Query shows the JSON as a table;
expand `coins`. **Refresh** fetches new values.

Google Sheets does **not** work: it asks from Google's servers, and those cannot reach your
home network.

### Python

```python
import requests
H = {"Authorization": "Bearer ocf_api_…"}
B = "http://192.168.1.10:8085/api/v1"
soon = requests.get(f"{B}/tax_free_soon", headers=H, params={"days": 30}).json()
for x in soon["upcoming"]:
    print(x["free_on"], x["asset"], x["qty"], x["value"])
```

### Automation (n8n, Node-RED)

An **HTTP Request** node with method GET, address as above and the header
`Authorization: Bearer ocf_api_…`. For example, ask `/system_status` every morning and
report when the last backup is older than two days.

## Security

- The API is reachable **only in your home network**. Do not casually make owncryptofolio reachable from the
  internet (port forwarding) — on the go, use the VPN.
- A token is as good as a key to your numbers: do not copy it into public forums, screenshots
  or shared spreadsheets. When in doubt, **revoke** it and create a new one.
- **Turning it off** (Settings → API (JSON)) blocks all API tokens immediately; they are kept and
  work again when you turn it back on.

## Related pages

- [Connect Claude](connect-claude.md) — the same data for Claude, with editing there too
- [System status](system-health.md) — the log with all API calls
