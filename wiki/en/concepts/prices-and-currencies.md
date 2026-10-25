---
title: Prices and currencies
updated: 2026-10-25
---

# Prices and currencies

## Why prices are stored

To know what your portfolio is worth **today**, the current price is enough. To know
what a purchase cost **back then**, you need the price from back then — and no exchange
gives you that retroactively at the push of a button.

That is why owncryptofolio builds its own price history:

- **Ongoing**: At an adjustable interval, the current prices of all coins you own are
  stored.
- **Retroactively**: When a new coin is added, prices are fetched back to your first
  transaction with that coin.
- **At the time of every transaction**: For every transaction, the price valid at that
  time is recorded.

The last point is the decisive one. Because the price is attached to the transaction,
you can change your display later without historical valuations changing
retroactively.

If you add a transaction that lies further back than anything so far, the history is
automatically extended further back.

## Euro or dollar

You can switch the whole display between **euro and US dollar** — at any time, even
afterwards. For this, the program stores not only coin prices but also exchange rates
(EUR/USD, USDT/EUR and so on), also with history.

For **tax** in Germany, the euro value is what counts, regardless of what you are
currently displaying.

## Where the prices come from

Free sources, no sign-up needed:

- **Yahoo Finance** for most coins, with a long history.
- **Bitget** and **Binance** for coins Yahoo does not know.
- **CoinGecko** can be added per coin on the Prices page as a further source.

The order in which new coins are looked up is set under *Settings → Price fetch*
(**Default source order**, preset Yahoo, Bitget, Binance).

The calculation goes through the dollar price and the ECB euro reference rate. That
sounds more roundabout than "just fetch it in euros", but it is more complete: the sources
list far more coins against the dollar than against the euro.

## Why you have to confirm price mappings

On the **Prices** page, each coin shows where its price comes from — and a checkmark
you use to confirm it. This is not a formality.

A ticker is not an identity. At the price providers, **dozens** of coins carry the same
ticker: `BTC` matches eleven, one of which is Bitcoin and one is called `batcat`. If the
wrong one is picked, you do not get a missing price — you get a **wrong** one. A missing
price is noticed immediately. A wrong one slips unnoticed into cost basis, profit and
the tax report.

That is why owncryptofolio makes a suggestion and checks whether the series really
covers your period. You have to confirm it.

**"until …"** with a date next to a series means: it ends on that day. That can be correct —
MATIC and FTM were migrated and are no longer traded. But it can also be a wrong match.
Only a human can tell the difference.

## What happens when there is no price

Then it shows **no price** — and the position is not included in the portfolio value.

Setting it at 0 would be more convenient and wrong: a zero would look like a total loss
and could not be told apart from a real one. Better a visible gap than an invisible
false statement.

## When a coin was migrated

Some coins merge into another one (AGIX became FET in 2024, FTM became S). The old
series often lives on at the price sources, but hardly anyone trades it — the prices
then jump wildly back and forth. With **End prices** you set the last day: until then
the series applies, after that the app fetches nothing more. That is something different
from **worthless**: a worthless coin counts at 0 from that day (the loss becomes
visible), an ended one simply has no price afterwards.

There is deliberately no automatic filter against "implausible" jumps: in crypto, a
price can double or triple in a day, and such a filter would discard real values in
exactly those moments.

## Daily prices, not minute prices

Valuation uses the **daily closing price**. A sale at 2:00 pm is therefore valued at
the price for the whole day, not the one at 2:00 pm.

For the display, this is irrelevant. For tax, it is a simplification, and that is why
it is stated in the report. Minute prices over four years and forty coins would be over
a hundred million data points for a difference nobody sees.

For the **display**, there are also fine-grained prices: every 5 minutes for the last
31 days and hourly for 90 days. They feed the short time ranges on the dashboard and the
curves on the prices page. They are not used for tax.

## Weekends have no official euro rate

The ECB euro reference rate is published on working days. Crypto trades every day.

So for a sale on a Sunday, there is no official daily rate. owncryptofolio takes the
last one before it and **marks** the line as an approximation. Either alternative would
be worse: leaving the gap would hide a transaction that took place. Silently passing off
Friday's rate as Sunday's would pretend an accuracy that does not exist.

## Stablecoins are not constant

USDT is not by definition exactly one dollar. The real price fluctuates slightly. The
program calculates with the actual price, not with an assumption — for tax, this
difference can matter.

## What a price gap means

Sometimes no price source delivers a value: for very small coins, for very old points in
time, or when a provider is currently unreachable.

Such gaps are **shown, not silently filled with zero**. A missing price would otherwise
make your portfolio value look too low without you noticing.

If you find a price gap, you choose another source on the [Prices](../guides/prices.md) page
(**Add source**), mark the coin as worthless or end its prices.

## Read more

- [Cost basis, profit and loss](cost-basis-profit-loss.md) — what is calculated with
  the prices
- [Holding period and tax](holding-period-and-tax.md) — why the euro value at the time
  of the transaction counts
