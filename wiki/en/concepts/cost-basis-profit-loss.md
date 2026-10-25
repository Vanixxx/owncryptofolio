---
title: Cost basis, profit and loss
updated: 2026-10-25
---

# Cost basis, profit and loss

## Cost basis

The **cost basis** is what you actually put in — the purchase price including all
fees.

Example: You buy 1,000 € of Bitcoin and pay a 2 € fee. Your cost basis is 1,002 €, not
1,000 €.

## Why fees count

Fees raise your acquisition cost and reduce your proceeds. Leave them out, and every
profit looks better than it is — with many small purchases, this adds up considerably.

owncryptofolio always includes fees, even if they were charged in a coin instead of in
euros. In that case, the fee is converted at the price at the time of the transaction.

## Unrealized and realized

| Term | Meaning |
|---|---|
| **Unrealized profit/loss** | What your **still held** positions are currently worth, compared with their cost basis. A book value — it changes with every price swing. |
| **Realized profit/loss** | The result of the positions you have **sold**. It is fixed and no longer changes. |

Both are shown in euros or dollars **and in percent**.

For tax, as a rule only the **realized** part counts — as long as you hold, there is
nothing to tax.

## DCA — your average price

**DCA** stands for *dollar cost averaging*. The DCA value is the average price you paid
for a coin, weighted across all your purchases.

It answers the question: **From which price am I in the plus?**

Example: You buy 1 ETH for 2,000 € and later 1 ETH for 3,000 €. Your DCA is 2,500 € —
from this price on, your position as a whole is in profit.

## Why DCA and the tax calculation give different numbers

This is the point most likely to cause confusion — and it is **not an error**.

DCA combines all your purchases into one average. The tax calculation explicitly does
**not** do that: it keeps tracking each individual purchase separately and assigns
specific purchases to a sale, depending on the method.

If, in the example above, you sell 1 ETH for 3,500 €, then

- DCA says: 1,000 € profit (3,500 − 2,500),
- the tax calculation with FIFO says: 1,500 € profit (the first, cheaper purchase
  counts),
- the tax calculation with LIFO says: 500 € profit (the last purchase counts).

DCA is a **reference figure for you**. For tax, lot tracking applies —
see [Holding period and tax](holding-period-and-tax.md).

**The two values can be far apart.** That is not an error, but most people first believe
the wrong reason: **Often the bigger part does not come from the two calculation
methods**, but from the fact that some of your coins sit
in wallets the program cannot read yet — so the tax report keeps carrying them, while
the portfolio already shows them as gone. Only a smaller, genuine remainder is left
because DCA and lot tracking calculate differently — and it swings sometimes one way,
sometimes the other, so it does not make either number consistently higher or lower.

Portfolio and tax report therefore deliberately remain separate numbers instead of being
artificially aligned. Every generated tax report (Excel) states explicitly on the
"Zusammenfassung" (summary) sheet which method it uses, so the two numbers are never
mixed up.

## When transactions are missing

If, according to the data, you give away more than you had, a receive is missing: a
purchase before the first export, a deposit, a reward. owncryptofolio books **no
profit** for this, because selling something that apparently cost nothing would look
like pure profit. Instead, that part appears without a cost basis in the tax report under **Open points**. Where and from when it
is missing is shown on the Holdings page under **Gaps**, see
[Dashboard and holdings](../guides/portfolio.md).

## Staking rewards do not count as pure profit

When you receive coins as a staking reward, you paid nothing for them. Still, the
program does **not** set them at zero, but at their market value at the time they came
in.

The reason: this inflow already counts as income and is recorded as such. If it stood
at zero in the cost basis, its whole value would later appear once more as profit — a
profit you never made.

## Portfolio high

The highest value your portfolio has ever reached. Useful as a reference point: it
shows you how far you are from the high.

## What can distort your numbers

**An undetected transfer** is the most common cause of wrong numbers. It looks like a
sale plus a purchase and creates a profit that never existed. So check lines with the
notice **No counterpart** — see [Merging transactions](merging-transactions.md).

**A price gap** means a position enters the calculation with an unknown value. This is
shown too.

## Read more

- [Prices and currencies](prices-and-currencies.md) — where the values come from
- [Holding period and tax](holding-period-and-tax.md) — how the same sale is
  calculated for tax
