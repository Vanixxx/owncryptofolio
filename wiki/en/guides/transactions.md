---
title: Transactions
updated: 2026-10-25
---

# Transactions

The **Transactions** page lists every transaction from all sources: buys, sells, deposits
and withdrawals, income, fees and futures. This is where you find, check, add to and
correct your data. Whatever you change here takes effect right away on holdings and the
dashboard.

A transfer between your own exchanges and wallets shows up as **one** row, not as a
separate send and receive. The reason is explained in
[Merging transactions](../concepts/merging-transactions.md).

## The list

<p>
  <img src="../../bilder/en/details/tx-karte-handel.png" alt="A trade" width="640">
  <img src="../../bilder/en/details/tx-karte-transfer.png" alt="A transfer between Kraken and Ledger" width="640">
</p>

Each row is a card with the kind, the date, the amounts (with coin symbol and approximate
euro value) and the source. Small badges tell you more:

| Badge | Meaning |
|---|---|
| ✋ **by hand** | You entered this transaction yourself. |
| ✏️ (pencil next to the time) | A transaction from a source that you corrected. |
| **no counterpart** | A send or receive for which the app finds no other side. |
| **Balance below zero: …** | After this transaction the balance is below zero: something is missing before it. |
| **Card deposit (assumed)** | More money was spent here than lay on the exchange. The app assumes it came by card. |
| **dust** | A tiny, unsolicited receive, often advertising. |
| **Card purchase without euro amount** | The exchange only delivers the coin, not the amount paid (Bitget). Add it: **Edit** → Trade, enter the euro amount under *Spent*, tick **Paid by card**. Otherwise the card fee is missing from the cost. |
| purple frame | a futures transaction |

For a **Trade**, the rate is shown the way exchanges write it: "Rate 25,848 BTC/USDT".

At the top you see the number of matches and **Newest first** or **Oldest first**. Next to
it you choose how many entries a page shows (**per page**); at the end of the list **Load more**
fetches the next ones, without gaps even when many transactions share the same moment. The app remembers your filters and position
when you leave the page.

<p>
  <img src="../../bilder/en/details/handy-kompakt.png" alt="Compact list on a phone" width="340">
</p>

**Compact** or **Cards**: Compact shows one line per transaction (kind, date, place, what came
in and what went out); a futures position shows the pair, long/short and its result. You can
tell futures entries by the purple ring around the symbol, like the purple frame in the card
view. On a PC (wide screen) the compact line shows more: time, places with logo, out and in
each with value, rate and fee, your note. Tapping opens the line as a card with all details;
tapping again turns it back into a line. On a phone the compact view comes first; your choice
is remembered. While **Pick** is on, cards are always shown.

The **Raw data** switch shows the rows as the sources delivered them, without merging. You
rarely need it.

## Search and filter

<p>
  <img src="../../bilder/en/details/tx-filter.png" alt="Filters" width="640">
</p>

On a phone you open the filters with **Filters**.

- **Search**: a coin, a name, a transaction ID, an address, a note or a date
  ("17.06.2023"). Several words must all match; "bch|ltc" finds one *or* the other.
- **Source**, **Kind**, **Origin** (API, file, blockchain, by hand) and **Coin**: you can
  pick several of each. Whatever does not fit the rest of your selection is dimmed.
- **Notes**: only the rows with a particular badge, e.g. **No counterpart**, **Balance below
  zero**, **Dust**, **Edited**, **With a note** or **Marked**. The number after it follows
  your other filters.
- **from / to** and **Spot / Futures**.

**Reset filters** clears everything. **Export** saves exactly the list shown as an Excel or
CSV file. Token names and notes always appear there as text, never as a formula.

## Opening a row

<p>
  <img src="../../bilder/en/details/tx-details.png" alt="An opened transaction" width="640">
</p>

Tapping the card expands it. Tabs sit at the top; on a phone you swipe through them sideways:

- **Details**: source, origin, transaction ID (for chains a link to the block explorer, for
  an exchange when the other side carries the same ID), addresses, "Balance after", your
  **Note** (with **Add note**) and, for a transfer, how it was linked.
- **Edit** or **Edit transfer**: the form with all values.
- **Version history**: every version with what changed.
- **Tax**: what the transaction means for tax, see [Tax report](tax-report.md#tax-on-a-single-transaction).
- **Find counterpart**: suggestions for a send or receive without a partner.
- for a transfer also **Single transactions**: send, receive and fees one by one.

At the top right, **⋯** opens all actions for a row without expanding it.

## Correcting and resetting

You can edit **any** transaction, including one from the exchange or the blockchain. The
original is always kept; your version applies until you take it back.

- **⋯ → Edit**, change values, **Save**. If nothing changes, no new version is created.
- **⋯ → Version history → Reset to original**: what the source delivered applies again.
- **⋯ → Hide** (transactions from a source) or **Delete** (your own): the transaction no
  longer counts. You bring it back via **Raw data** → **Show hidden**. For a transfer,
  **Hide/delete transfer** takes out both sides at once.

## Transfers

The app detects a transfer by itself when send and receive match, most reliably through the
same transaction ID. Where that is not enough:

- **Link**: for a send or receive without counterpart → **Find counterpart** and choose the
  matching suggestion. Or tap **Pick** at the top, tap the send and the receive, then **Link**
  at the bottom.
- **Assign a fee**: a fee that the exchange books separately belongs to the transfer.
  From the fee → **Find transfer**, or while picking, tap the transfer and the fee.
  Only an outgoing booking (fee, deduction, small send) of the exchange or wallet of one of the
  two sides can be attached, at most 2 hours from the transfer and not already part of a
  transfer. **Detach** removes it again.
- **Edit transfer**: date and time once, then send, receive and fees, each with its wallet or
  exchange. The send shows how much was there at that moment.
- **Split**: the two sides do not belong together. Afterwards they stand on their own again
  and stay that way: owncryptofolio does not relink them by itself, only you can, via
  **Find counterpart**. An attached fee shows up again as its own row.
- A transfer always links **one** coin. If something else arrived on the other side
  (e.g. BCH out, USD in), it was exchanged there: enter the receive in the same coin and a
  trade there.

**Pick** has a bar at the bottom with **Pick all in the filter**, **Clear picks** and
**Stop picking**. For dust suggestions it offers **Not dust** and **Hide as spam** for all
picked rows.

## What stays without a counterpart: mark it

Not every send has a counterpart on your side. Tell the app what happened, via **⋯**:

**For a send:**

| Mark | When | Effect |
|---|---|---|
| **To others** | You paid or gave it away. | counts like a sale at the daily price |
| **Own wallet, not set up** | The coins sit in a wallet that is not in owncryptofolio. | stay in your holdings, place "outside" |
| **Lost (e.g. insolvency)** | The money is gone, for example through a bankruptcy or a fraud. | the cost basis is lost, even for euro or dollars |

**For a receive:**

| Mark | When | Effect |
|---|---|---|
| **From an own wallet, not tracked** | The coins were already yours. | no gain, they come back from "outside" |
| **Bought outside (e.g. card)** | You bought them, e.g. by card in the wallet app. | counts as a deposit at the daily value |
| **Income / gift** | a reward, an airdrop, a gift | counts as income at the daily value |

If you know the euro amount you paid, a **Trade** is more accurate than "Bought outside":
**⋯ → Edit**, kind **Trade**, enter the euro amount under *Spent* and tick **Paid by card**.

**Remove mark** undoes it.

## Entering a transaction

The round **+** at the top right opens **Add transaction**:

1. Choose the **exchange or wallet network**.
2. **Spot** or **Futures**, then the **Type**, e.g. *Trade*, *Crypto deposit*, *Income*,
   *Transfer* (internal transfer) or *Transfer (own wallet/exchange)*.
3. **Date** and **Time** in your local time; the app adds the colons itself.
4. The amounts: **Received**, **Spent**, **Fee**. You choose the coin from the list or type
   it in. Next to Spent you see **max. …** in gray: that much was there at that moment.
   Tapping it fills in exactly that amount.
   Under each coin you see its **market price** as the daily price of the date entered
   (without a date the current one; the time does not matter, the app knows one price per
   coin per day) and what the amount is worth; for a trade also the **rate** from Received
   and Spent.
5. **Save**.

Good to know:

- **Fee on top**: if 83 USD were paid out and a fee of 2.49 USD was charged, enter **83**
  under *Spent* and **2.49** under *Fee*.
- **Fee in the coin bought**: *Received* is the amount **before** the fee is deducted. The
  app shows you below what arrives after the fee.
- **Paid by card**: tick this when buying with euro or dollars if the money came straight
  from the bank. Then the whole amount counts as a deposit.
- **Transfer (own wallet/exchange)** has **From** and **To**. If you start from a receive
  without counterpart (**⋯ → Edit**, type Transfer), *To* is already set. You only choose
  *From*; the receive stays as it is and is linked right away.
- **Copy** (⋯) opens the form with the values of an existing transaction, a transfer too.
- **Changed through MCP** (Notes): what, for example, Claude changed through MCP, see
  [Connect Claude](connect-claude.md#edit-claude-changes-you-confirm).
- **Many at once**: **Import**: choose between
  - *Template (any source)*: download the template, fill it in in Excel, upload it. A
    preview first shows what does not fit.
  - *Own file (CSV/Excel)*: upload an exchange's export directly and map the columns —
    as on the exchange's card, see
    [Sources](sources.md#own-file-csvexcel--for-any-exchange).
- **Income in the futures account** (e.g. a credit from the exchange) goes under
  **Futures → Income**.

## Related pages

- [Merging transactions](../concepts/merging-transactions.md)
- [Hiding spam](../concepts/hiding-spam.md)
- [Dashboard and holdings](portfolio.md), including the gaps
- [Setting up sources](sources.md)
