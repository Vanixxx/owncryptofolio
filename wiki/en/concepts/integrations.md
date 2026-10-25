---
title: Integrations
updated: 2026-10-25
---

# Integrations

An **integration** is a connection to a source your transactions come from. Each
source is its own integration:

- **Exchanges** — Bitget, Coinbase, MEXC. Connected via an API key that you create at
  the exchange. Kraken, KuCoin and some 50 more exchanges run through a shared interface
  (ccxt); whatever nobody has checked with a real account yet is marked as **Beta**
  ([list](../guides/sources.md)).
- **Blockchain networks** — for your hardware wallet. You enter your public address,
  and the program reads the movements from the network.
- **File import** — Excel or CSV files. Supported are the exports from Bitget,
  Coinbase, MEXC, **Kraken** and **KuCoin**; for Kraken the ledger file, for KuCoin the
  BillingHistory ZIP (you do not need to unzip it). For any other exchange there is
  **Own file (CSV/Excel)**: you map the columns yourself.
- **Manual entry** — transactions you enter yourself, also for an exchange without an API
  or a network without an integration.

File import and manual entry are integrations too. That way **every** transaction
carries the information where it comes from.

## The same source more than once

You can set up an integration several times — for example two Bitget accounts or
several wallet addresses on the same network. Each gets its own name and is kept
separately.

## API keys: read-only

When you create an API key at an exchange, give it **read permissions only**.
owncryptofolio does not trade and needs no trading permissions. A key without trading
permissions cannot do any damage even if it falls into the wrong hands.

Your keys are stored encrypted.

## The balance check

This is the most useful feature of this page. From your transactions, the program
calculates how much of each coin should be at a source — and compares that with what
the source actually reports.

**If both match, your transactions are probably complete.** This is the best
self-test you have.

If the balance differs, the program tells you. Common causes:

| Cause | How you can tell |
|---|---|
| A transaction is missing | The difference roughly matches a movement you know of |
| A transfer was not detected | With two sources, one is in the plus, the other in the minus |
| An area is deliberately left out | For example futures — the difference is then **quantified and named**, not hidden |
| Fees are missing | Small difference, always in the same direction |
| Spam token | Difference in a coin you never bought |

Small differences are normal — exchanges round their balances. A difference of up to
**0.1 %** of the reported balance therefore counts as matching, for euro, dollar and
stablecoins also up to **5 cents**.

## Read more

- [Merging transactions](merging-transactions.md) — what happens when you transfer
  between two integrations
- [Hiding spam](hiding-spam.md) — the normal case for blockchain integrations
- [How your data is stored](how-data-is-stored.md) — where the imported data goes
