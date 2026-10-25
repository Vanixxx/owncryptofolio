---
title: Source of funds
updated: 2026-10-25
---

# Proving the source of funds

Banks, notaries and some exchanges want to know **where the money comes from** before they
accept a larger sum. For this, owncryptofolio traces every transaction back to your
deposits and creates a proof as a PDF.

**Example:** [proof for a withdrawal as PDF](../../beispiele/mittelherkunft-auszahlung.pdf)
(German, as the app creates it) — from the demo data (invented name and addresses).

## How to do it

1. Open **Reports** and choose **Source of funds** at the top.
2. The list shows all **sales**, **transfers** (also between your own wallets),
   **withdrawals** and **payments** to others, newest at the top. With the selection at the
   top you narrow down the kind; the search finds coin, place or year.
3. Click a transaction. At the top you get a short text in words and an **overview**
   (period of the chain, number of transactions, exchanges/wallets involved, kind of data).
   In addition:
   - the **split**: how much of the amount comes from which origin (bar and list);
   - the **chain**: every step back, the latest at the top, with date, place and
     transaction ID. You expand and collapse branches with the arrow;
   - expandable **Deposits in detail** (every bank transfer or card payment with date,
     amount, the share used here and ID — to match against your bank statement) and
     **Data sources** (exchanges and wallets with address and kind of data);
   - the **diagram** of the money flow: **Simple** (one box per exchange/wallet, the origin
     on the left, the transaction on the right, price losses in red), **Full** (every
     step) or **Off**. Hovering with the mouse or tapping makes a box or stream show its amounts and
     links; a box can be dragged aside. Large diagrams scroll; on a phone the simple one
     usually fits completely without scrolling;
   - **PDF** (at the end the diagram simple and full, a large full one on A3) and **Excel**
     to download.

<p>
  <img src="../../bilder/en/details/herkunft.png" alt="Source of a withdrawal with overview and flow" width="640">
</p>

## Source of today's holdings

Choose **Today's holdings** at the top. You see where all your holdings come from — every
coin and the euro on the exchanges, valued at the current price. Whatever is above the cost
is called **Price gain (not yet sold)**; if the value is below it, the shares shrink in the
same proportion. Below are the coins with a small bar of their origin; a click shows the
chain of that coin. PDF and Excel are available for all holdings and for each coin.

## Planned transaction

You still want to make a withdrawal or a larger transfer and need the proof beforehand
(e.g. because the bank or exchange asks for it)? Choose **Planned transaction** at the top,
fill in **Date**, **From** (exchange or wallet), **Coin** and **Quantity** (**All** takes the
whole holding there) and **Create proof**. The app shows which holdings the transaction
would take now according to your tax setting and where their money came from, valued at
today's price. **Nothing is booked.** If your holdings change before you carry it out, the
source can change — the PDF says so too.

You can also get there straight from a single transaction: expand the transaction → **Tax**
tab → **Show source of funds**.

## What the kinds of origin mean

| Origin | Meaning | Proof you attach |
|---|---|---|
| **Bank deposit** | your own money sent to the exchange by bank transfer, or a buy paid directly by SEPA ("Paid straight from the bank account") | bank statement |
| **Card purchase** | coins bought directly with your card (also "Paid straight by card", e.g. MEXC) | card statement |
| **Price gain** | increase in value between buy and sale (or transfer) | the exchange's transaction history |
| **Income** | staking, rewards, airdrops | the exchange's statement |
| **Futures result** | gains from the futures account | the exchange's statement |
| **Inflow without recorded purchase** | coins came in, no buy is recorded | your own proof needed |
| **Price loss** | loss in value between buy and sale, as a **negative** share: the origin shows the full money put in, the loss is deducted from it (shares over 100 % are possible) | – |
| **Euro without recorded deposit** | euro were spent, the deposit is missing from the data | your own proof needed |

The last two kinds show **where something is still missing in your data**. Usually it helps
to import the missing source or to mark the transaction (see
[Transactions](transactions.md)).

## Good to know

- **Order**: which holdings a sale uses follows your tax setting (FIFO or LIFO). That way
  the tax report and the source-of-funds proof match.
- **Transfers** do not change the origin, but they appear in the chain — with the
  transaction ID as proof. A transfer counts at its value on the day; whatever is above the
  cost is "Price gain up to the transfer".
- **Swap** (e.g. USDT → LTC) appears as one step with both sides in the chain.
- **Rebookings spot ↔ futures** appear as a step of their own. Some exchanges book the
  arrival before the departure; the chain still leads to the real buys.
- **Kind of data**: API (fetched from the exchange), blockchain, file (export) or by hand.
  Steps entered by hand are more likely to need a proof of their own.
- **Small shares**: the proof sums up branches below 1 % of the amount and names their
  origin. The **Excel file** contains every single step.
- **Losses from insolvency or fraud** are not part of the chain; lost holdings contribute
  to no later amount. The proof points this out.
- **Name and address** in the header of the PDF are entered under **Settings → Tax**.
  Leaving them empty works too. The tax number appears only in the tax report, not in the
  proof.
- In the **Excel** file, token names and notes always appear as text, never as a formula.

The proof evaluates the data you have recorded. It is not legal or tax advice.

## Related pages

- [Tax report](tax-report.md)
- [Holding period and tax](../concepts/holding-period-and-tax.md)
- [Transactions](transactions.md)
