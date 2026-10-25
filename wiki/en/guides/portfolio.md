---
title: Dashboard and holdings
updated: 2026-10-25
---

# Dashboard and holdings

From your merged transactions and the prices, owncryptofolio works out what you own, what
it is worth and what you have gained or lost. None of this is stored: every correction to a
transaction takes effect on all figures right away.

## Dashboard

The start page shows your portfolio at a glance:

<p>
  <img src="../../bilder/en/details/dash-karte-0.png" alt="Total value and history" width="436">
</p>

- **Total value**: all coins at the current price plus cash on exchanges. While the page is
  open, it refreshes every minute. Next to it is the change in the chosen period.
- **History**: the value over time, for 24 hours, 7 days, 1 month, 6 months, 1 year or
  everything; with the slider below you choose a section. **24 h, 7 days and 1 month** show
  the fine values (every 5 minutes for 31 days, then hourly up to 90 days; the app
  recalculates them hourly from fine prices per coin, also for times when it was not
  running). Each time the next longer period is loaded so you can scroll back: for 24 h
  3 days, for 7 days 1 month, for 1 month 3 months. The slider sits on the chosen period.
  For the longer periods a **pale band** shows the daily high and low where fine values
  exist. Below the result you see the chosen period with dates. Tapping **Net deposited**
  under the chart hides or shows the dashed line.
  The dashed line is what you have deposited net. If the value is above it, you are in
  profit. The **high** is the highest daily value your portfolio has ever had.
<p>
  <img src="../../bilder/en/details/dash-karte-1.png" alt="Result" width="257">
  <img src="../../bilder/en/details/dash-karte-2.png" alt="Net deposited and high" width="257">
</p>

- **Total result**: unrealized plus realized plus futures. You also see the income, that
  is staking and rewards at their value on arrival.
- **Net deposited**: euro deposits minus withdrawals. If you bought by card (on an exchange
  without a balance, with "Paid by card", or on Coinbase by card/PayPal), the whole amount
  counts as deposited. The note "of which … by card" gives the total.
- **Below the high**: how far the value is now below the best day.
<p>
  <img src="../../bilder/en/details/dash-verteilung.png" alt="Allocation" width="346">
  <img src="../../bilder/en/details/dash-gewinner.png" alt="Winners and losers" width="346">
</p>

- **Allocation**: which share of the value falls on which coin, or, switched over, on which
  **exchange/wallet** (the networks of a wallet together).
- **Winners and losers**: the five coins with the highest and the lowest unrealized result.
<p>
  <img src="../../bilder/en/details/dash-steuerfrei.png" alt="Tax-free soon" width="346">
  <img src="../../bilder/en/details/dash-hinweise.png" alt="Notes" width="346">
</p>

- **Tax-free soon**: what reaches the holding period in the next 30 days, with its value
  and the gain that would then be tax-free.
- **Notes**: what makes the figures uncertain, e.g. a failed fetch, each with the way to fix
  it — and from 80 % the note that the Freigrenze (tax-free allowance) of the current year
  is getting close (sales 1,000 €, income 256 €).

## Holdings

<p>
  <img src="../../bilder/en/details/bestand-zeile.png" alt="A coin in the holdings" width="640">
</p>

The **Holdings** page has three tabs.

### Spot

For each coin you see the quantity, value, profit or loss in money and percent, and its
share of the portfolio as a bar. On a PC you also get the curve of the chosen period
(today, 24 h, 7, 30 or 90 days) with the change in %, the price and the DCA (avg. buy price)
in their own columns. At the top you find a coin through the search. Clicking the coin
opens it with three tabs:

<p>
  <img src="../../bilder/en/details/bestand-graph.png" alt="Expanded: chart" width="640">
</p>

**Chart**: the price over time and your **average buy price as a dashed step line**. Each
step is a buy that changed the average. If the curve is above the line, you are in profit
with this coin.

<p>
  <img src="../../bilder/en/details/bestand-transaktionen.png" alt="Expanded: transactions" width="520">
</p>

**Transactions**: all transactions with this coin, newest first. **Compact** shows one line
per transaction (kind, date, place, how much of the coin came in or went out, value);
tapping opens it as a card with all details (tap again: back to a line); **Cards** shows
them as on the Transactions page (expand, edit, note). On a phone the compact list comes
first; your choice is remembered. Below, a link leads to the Transactions page, already
filtered by the coin.

**Details**:

- **DCA (avg. buy price)**: from this price on you are in profit (see
  [Cost basis](../concepts/cost-basis-profit-loss.md)). Next to it **Price now** and the
  **Cost** of today's holding.
- **Realized**: the profit or loss from sales of this coin.
- **Income (market value on arrival)**: staking, rewards etc. of this coin, if there are any.
- **Held** (since): when today's holding last started from zero.
- **Holding period**: what percentage of the holding is already tax-free and from when the
  next part becomes tax-free.
- **Where**: on which exchange or wallet the coin sits, with logo. "Own wallet, not
  tracked" means: you marked a send that way.
- **Unclear**: more was given away than was there according to the data. No gain is booked
  for it, see Gaps.
- **Sent, open**: this much went out without a counterpart and no longer counts as held.

With **Sort by** you order the list by value, profit/loss (also in percent), realized,
price change in period, holding time or name; the arrow next to it reverses the order.

"Show sold" brings in coins you no longer hold, with their realized result.

### Futures

Here the futures result, the funding and the fees stand apart from the spot result, and
below them only the positions that are **still open**. A position counts as open when the
exchange still pays funding but has not delivered a final settlement.

**Closed positions** are under **Transactions**, each as one row with contract, long or
short, result, funding and fees. Expanded, you see the individual bookings. Choose
"Position" as the kind there to see only them.

### Gaps

Here you see **where transactions are missing**:

- **"missing from …"**: the balance calculated from your transactions drops below zero on
  this day. Before this day an addition is missing (buy, deposit, income). The small chart
  shows the balance over time; red is the missing part.
- **"balance differs"**: the balance never drops below zero but does not match the
  account balance of the source. When something is missing cannot be told in that case.

The list is sorted by the missing value, the most important at the top. **Show
transactions** opens the transactions with a matching filter (this source, this coin, up to
that day). Add the missing transactions, by file or by hand, and the gap disappears.

## How things are calculated

- **Average cost per coin across all sources.** A transfer between your exchanges and
  wallets takes its cost along; the network fee raises the cost basis.
- **A trade is a sale** at the value of the other side, i.e. euro if there is any,
  otherwise the daily price.
- **A send "to others"** counts like a sale at the daily price, a send marked **"lost"** as
  a total loss. An **open send** without a mark leaves the holdings without a gain. Mark it,
  and the program calculates correctly, see
  [Transactions](transactions.md#what-stays-without-a-counterpart-mark-it).
- **A receive without counterpart** counts as "from outside" at the daily value until you
  mark it: own wallet, bought outside or income.
- **A conversion** (token swap, e.g. 1:1000) only changes the quantity; purchase price and
  purchase date stay.
- **Euro and dollars** are cash, with no profit or loss.
- Everything is calculated in euro; the display in dollars uses the rate of the European
  Central Bank.

## Related pages

- [Cost basis, profit and loss](../concepts/cost-basis-profit-loss.md)
- [Merging transactions](../concepts/merging-transactions.md)
- [Setting up sources](sources.md), including the section on balance checks
- [Transactions](transactions.md): closing gaps, entering and marking transactions
