---
title: Holding period and tax
updated: 2026-10-25
---

# Holding period and tax

> **owncryptofolio produces an evaluation, not legal advice.** The program calculates
> according to the rules you set. Whether the result is right for your situation is
> something you clarify with your tax advisor. Special cases such as staking rewards,
> airdrops or offsetting losses are not always clear-cut for tax purposes.

The evaluation follows **German tax law**.

## Every purchase is tracked individually

For tax, it is not enough to know how much Bitcoin you own. What counts is **when you
bought which part of it** — because both the holding period and the profit depend on it.

That is why owncryptofolio keeps every receive individually: with date, amount and
acquisition cost. When you sell, the sale is offset against these individual receives.

## FIFO or LIFO

Which receives are assigned to a sale depends on the method. You can switch:

| Method | Meaning |
|---|---|
| **FIFO** (*first in, first out*) | The **oldest** purchase is sold first |
| **LIFO** (*last in, first out*) | The **most recent** purchase is sold first |

**FIFO is the default**, and this is also how the BMF (Federal Ministry of Finance)
reads it. You can switch on LIFO for comparison (Settings → Tax or directly on the
report page). Whether LIFO is permissible for your return is something you clarify with
your tax advisor.

The two methods can lead to different results, both for the profit and for the holding
period. There is an example under
[Cost basis, profit and loss](cost-basis-profit-loss.md).

Because changing the method changes **all** results, the method used is noted in every
generated report. That way an old report stays traceable later.

## The one-year holding period

If you hold a position for more than a year, selling it is usually tax-free in Germany.
Days are counted by the German calendar: bought on 1 March 2024, a sale on 1 March 2025
is still taxable, from 2 March it is tax-free.

Crucially: the period applies **per receive**, not per coin. You can hold the same coin
at the same time in positions of which some have passed the period and others have not.

## The days display

Under **Holdings**, when you expand a coin, you see **what percentage** is already
tax-free and **from when** the next part becomes tax-free.

The overview of **all coins** is given by the **Tax-free** tab in the tax report: per
coin the tax-free amount and the amount still in the holding period, with value and
profit/loss in your currency, and the next date. The dashboard shows under "Tax-free
soon" what becomes free in the next 30 days.

This is not a statistic but a decision aid: if you are just before the end of the
period, you have a good reason to wait with the sale. That is exactly what the display
is for.

## The Freigrenze

If your taxable profit for a year stays below the Freigrenze (tax-free allowance), no
tax is due. You need to know two things about it:

**It is a Frei*grenze* (exemption limit), not a Freibetrag (deductible allowance).** One
euro above it makes the **entire** profit taxable, not just the part above it. The report
shows you for each year whether the balance is below the Freigrenze.

**The amount depends on the year.** It was 600 € for a long time and was raised to
1,000 € from 2024. A report for an earlier year therefore calculates with a different
value. For income (staking, rewards), a separate Freigrenze of 256 € applies.

A bar in the report shows how much of the Freigrenze has been used up in the year. From
80 % in the current year, a notice appears on the dashboard.

## Carrying losses forward

If a loss remains in a year, it is first carried back to the previous year, the rest
into the following years — with no expiry. It is offset only against profits from
private sales, and only in years whose profit reaches the Freigrenze. The app calculates
this as a suggestion; what counts is the notice of assessment from the Finanzamt (tax
office), whose value you enter in the tax report.

## When you swap coins for coins

This is the case that is overlooked most often. If you swap BTC for ETH — or BTC for
USDT — then for tax purposes this is **two things at once**: you disposed of BTC and
acquired ETH.

That means: even without any euros ever changing hands, a taxable profit may have
arisen. For this, the program values both sides at the euro price at the time of the
swap.

Anyone who trades a lot via USDT pairs constantly creates tax-relevant events this way.

## Staking rewards and airdrops

**Staking rewards** are recorded at their market value when they come in. For the
holding period, the reward counts as a **separate new receive** — it does not extend the
period of your existing holdings.

**Airdrops** are marked separately. How they should be treated depends on whether you
did something for them — only your tax advisor can judge that, which is why the
treatment is configurable: *Settings → Tax →* **Tax airdrops on inflow** (off by default).

## What goes into the calculation

| Event | Treatment |
|---|---|
| Buy, sell, swap | Sale at the euro value at that time, the new coin bought at that value |
| Transfer between your sources, moving between spot ↔ futures | **not a sale**: the purchases move along with their date and their cost |
| Migration (e.g. FTM → S, Fantom to Sonic) | **not a sale**: purchase date and purchase price carry over to the new coins |
| Outgoing "To others" (payment) | Sale at the euro value at that time |
| Outgoing "Own wallet, not set up" | not a sale, the coins come back with their date |
| Outgoing "Lost" (insolvency, fraud) | separate list, **not** offset against the profits |
| Income, incoming "Income" | Inflow at the euro value (§ 22 EStG, other income), then a separate purchase with its own holding period |
| Card purchase with euro amount | Purchase at the amount paid, card fee included |
| Incoming "Bought outside", card purchase without euro amount | Purchase at market value, marked as **cost estimated**: add the amount you paid (Edit → Buy/Sell, "Paid by card") |
| Futures | separate sheet under § 20 EStG (capital income) |
| Hidden spam | does not count |

**A transfer is not a sale.** If it is not recognized as one, it appears as a sale.
That is why you should check the notices **No counterpart** and **Balance below zero**
before the report — see [Merging transactions](merging-transactions.md).

### Calculated per wallet and exchange

owncryptofolio keeps the purchases (lots) **separately per location**: per exchange
account, per wallet network, and there separately for spot and futures. This corresponds
to the **wallet-based view** described in the BMF letter on crypto assets.

- A **sale** only draws on the lots that are **at this location** — with FIFO on the
  oldest one there, not the oldest one overall.
- A **transfer** between your own locations is not a sale: the lots move along, with
  their **original purchase date** and the full cost. So the holding period keeps
  running.
- The network fee of a transfer only reduces the amount; the cost stays with the rest.

**Example:** In January you buy 1 ETH at exchange A, in March 1 ETH at exchange B. In
June you sell 1 ETH at B. The calculation uses the **March purchase** (it is at B) — with
a view across all locations, it would be the January purchase. If you had sent the
January ETH from A to B beforehand, it is at B, and FIFO takes it first.

That is why it is important that transfers are recognized as transfers: an unlinked
transfer looks like a sale at one location and a purchase without cost at the other
(see [Merging transactions](merging-transactions.md)). Whether a view across all
locations would also be permissible for you is best clarified with your tax advisor.

### Fees

A fee counts **once**, for the event it belongs to (as in the BMF letter):

- on a **purchase** with euros it increases the cost,
- on a **sale or swap** it reduces the proceeds, even if it is charged in the coin
  bought (the usual case at Bitget),
- if it is paid in a **third coin** (e.g. BNB), that is at the same time a small sale of
  that coin,
- the **network fee** of a transfer only reduces the amount; the cost stays with the
  rest.

### Futures

Futures are forward transactions and belong to capital income (§ 20 EStG, Anlage KAP,
the capital income form). The report shows profits, losses, funding and fees
separately, plus an **exchange bonus** (credited minus expired). Such a bonus is not
income under § 22, but belongs to the futures result. What the futures account spends in
USDT only counts here, not additionally as a sale under § 23 (private sales).

## When history is missing

If you sell coins for which there is no purchase in your data, owncryptofolio cannot
calculate a profit for them. These amounts are listed under **Open points**, with the
share of proceeds that falls on them and **without** a cost basis — it is unknown, not
zero. The way to close this is through the data: load missing exports, link transfers,
mark outgoing transfers.

## The reports

The report is created **per year**, as a view, as an **Excel** file with all individual
items and as a **PDF** summary. Each one names its method and its settings. How to
create it is described in the guide [Tax report](../guides/tax-report.md).

**A report is a document, not a view.** With **Keep** you save the state of a year. If
something changes later that affects this year, the kept report shows **changed** — even
if the cause is a correction in an **earlier** year (a purchase from 2021 carries the
cost of a sale in 2024). What follows from that, you decide with your tax advisor.

## Read more

- [Cost basis, profit and loss](cost-basis-profit-loss.md) — why DCA and the tax
  calculation give different numbers
- [Prices and currencies](prices-and-currencies.md) — why the euro value from back then
  counts
