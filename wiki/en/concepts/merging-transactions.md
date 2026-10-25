---
title: Merging transactions
updated: 2026-10-25
---

# Merging transactions

## Why a transfer shows up twice

When you send coins from an exchange to your hardware wallet, that is **one** event —
but **two** sources report it:

- Bitget reports: "sent, 0.5 ETH"
- The Ethereum network reports: "received, 0.4998 ETH"

Unlinked, this looks like a sale at Bitget and a purchase in the wallet. Your balance
would be counted twice, your profit would be wrong, and your tax report would show a
disposal that never took place.

owncryptofolio detects such pairs and turns them into **one** line: a transfer.

## How the program finds the pairs

First by the **transaction ID**, if both sides report the same one — that is the safe
case. If a source delivers no usable ID, the program looks at **time, amount and
coin**: a send and a receive that match in time, concern the same amount and the same
coin.

The amounts never match exactly, because the network deducts a fee. The program
accounts for that.

When new transactions are added later, existing ones are checked again. This matters
because the two halves of a transfer are usually imported at different times — first
the exchange, weeks later the blockchain.

## Where you see this

The **Transactions** page shows the merged view by default. A transfer appears there as
one card "source → destination" with the amount sent, the amount received and the
**network fee** (sent minus received). Below it, you see how the program recognized the
pair: by the transaction ID, by amount and time, or because you linked it.

With the **Raw data** switch, you see every line as the source delivered it.

At the top you filter by **Source** (an exchange, an entire wallet or a network like
"Hardware wallet – Ethereum"), by **Kind** (e.g. only transfers, income or futures positions),
by **Coin** and by **Period**. You choose source and coin from a list; type a few
letters into the search field to narrow it down.

A closed **futures position** is one line: result, funding and fees of the position
together, with the bookings behind it expandable. "Reset filters" shows everything
again. You can sort by **Time** or by **Value** (euros at the daily price), ascending or
descending in each case.

## The filters and notices

| Filter / notice | Meaning | What you should do |
|---|---|---|
| **No counterpart** | Something was sent, but no matching receive was found | Check via **Actions → Find counterpart**, or mark it |
| **Ambiguous** | Several receives fit equally well; the program does not guess | Find counterpart and link the right one |
| **To others** | Marked by you: a real outgoing transfer (paid, given away) | Nothing |
| **Own wallet, not set up** | Marked by you: went to a wallet of your own that owncryptofolio does not know | Set up the wallet later, then it links itself |
| **Dust** | Tiny receive, typical of spam advertising | Hide as spam, or leave it |
| **Spam (hidden)** | Hidden, counts nowhere | See [Hiding spam](hiding-spam.md) |
| "delivered as …" | The source names the coin differently (NTGL instead of NGL) | Nothing |

**"No counterpart" is not an error message**, but a hint about the state of your data.
The most common reason is harmless: you have not connected the other side yet.

## When you have to step in yourself

The automatic matching does not catch every case. Under **Actions** you can:

- **Find counterpart** and link it if the program did not recognize the connection.
  Receives up to 24 hours and 5 % difference in amount are suggested.
- **Split** if a link is wrong. Both halves then stay separate: the program does not
  link them to anything else on its own, only you can, via "Find counterpart". That way
  nothing changes back without you noticing. A split pair is still offered when
  searching, marked "split by you", so you can undo it.
- **Edit** and **History** as in the raw data.

Your decisions are kept even when data is imported again — see
[How your data is stored](how-data-is-stored.md).

## What a single trade brought in

When you expand a trade, it shows what **exactly this** purchase is worth today: paid
(with fee), value today, price then and today, profit or loss. For a sale against euros
or dollars, the proceeds are set against what the sold coins would be worth today. This
is independent of the average price and of tax; it only answers: how good was this one
trade?

## Does the balance match?

On the **Sources** page, the **Balance check** verifies whether the balance of an
exchange or wallet matches your transactions. A difference means: transactions are
missing, see [Setting up and importing sources](../guides/sources.md#balance-check).

## Read more

- [Integrations](integrations.md) — the balance check shows you whether something is
  missing
- [Cost basis, profit and loss](cost-basis-profit-loss.md) — why an undetected transfer
  distorts your numbers
