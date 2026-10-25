---
title: Tax report
updated: 2026-10-25
---

# Tax report

Under **Reports** you find the tax evaluation of a year under German law. What lies behind
it (FIFO, holding period, Freigrenzen (tax-free allowances), fees) is explained in
[Holding period and tax](../concepts/holding-period-and-tax.md).

> An evaluation, not tax advice. Check the result with your tax advisor.

## Before you start: check the data

The report is only as good as the transactions. On **Transactions**, under **Notes**,
**No counterpart** and **Balance below zero** should be empty, and under
**Holdings → Gaps** nothing should be open.

## Viewing the report

If filled in, your name, address and tax number appear at the top of the PDF and the Excel
file (**Settings → Tax → Head of the reports**). A kept report keeps the head it was made
with.

The calculation is **per wallet and exchange**: a sale draws on the buys at that place,
transfers take their purchase date along — details and an example under
[Holding period and tax](../concepts/holding-period-and-tax.md#calculated-per-wallet-and-exchange).

1. Open **Reports**. The last completed year is selected; at the top you choose another.
2. **FIFO** or **LIFO**: FIFO is the default. LIFO shows you, for comparison, what the other
   method would give. You set the default under **Settings → Tax**.
<p>
  <img src="../../bilder/en/details/steuer-23.png" alt="§ 23 EStG" width="348">
  <img src="../../bilder/en/details/steuer-ertraege.png" alt="§ 22 Nr. 3 EStG" width="348">
</p>

3. The cards:

| Card | What it shows |
|---|---|
| **Private disposals (§ 23 EStG)** | gains and losses from sales within one year after the purchase, the balance and whether it is below the Freigrenze (tax-free allowance; 600 € up to 2023, 1,000 € from 2024) |
| *(for both)* | a bar showing how much of the Freigrenze is used: yellow from 80 %, red from the limit; the dashboard then shows a note |
| **Loss carry-forward § 23** | what is left of losses from earlier years: carry-forward at the start of the year, offsetting, carry-back, loss of the year, carry-forward at the end of the year; **All years** shows how it developed. You enter the figure from the Finanzamt's (tax office's) notice here (see below) |
| **Income (§ 22 no. 3 EStG)** | staking, rewards and receives marked as "income", with the Freigrenze of 256 € |
| **Futures (§ 20 EStG)** | gains, losses, funding and fees separately, for the Anlage KAP (capital income form) |
| **Losses from insolvency or fraud** | what you marked as "lost", with the cost of the lost coins; not offset |

<p>
  <img src="../../bilder/en/details/steuer-verkaeufe.png" alt="Sales tab" width="640">
</p>

4. Below, the individual items in tabs:
   - **Sales**: every sale per buy, with purchase date, days, proceeds, cost and gain.
     **Only within the holding period** hides the tax-free ones; **Show futures account**
     shows the small USDT movements of the futures account.
   - **Income**, **Futures**, **Losses**.
   - **Open points**: quantities without a recorded buy. If anything is listed here, data
     is missing.
   - **Per source**: gains and losses per exchange or wallet.
   - **Holding changes**: per exchange/wallet and coin, the holding on 1 Jan, inflow,
     outflow, the holding on 31 Dec and its value.
   - **Holdings 31 Dec**: what was held at the end of the year, with purchase date, cost
     and the date from which it is tax-free.
   - **Tax-free**: as of **today**, whatever year is selected at the top. Per coin, how much
     has already been held for over a year (can be sold tax-free) and how much is still
     within the holding period, each with value and profit/loss in your display currency
     (Settings), plus when the next part becomes free. The totals are at the bottom.
   - **Filling-in help** (at the very end): which total goes into which line of the
     Anlage SO (other income form) and the Anlage KAP (line numbers for 2024; for other
     years check the form).

<p>
  <img src="../../bilder/en/details/steuer-steuerfrei.png" alt="Tax-free tab" width="640">
  <img src="../../bilder/en/details/steuer-ausfuellhilfe.png" alt="Filling-in help tab" width="640">
  <img src="../../bilder/en/details/steuer-bestand.png" alt="Holdings 31 Dec tab" width="640">
</p>

## Loss carry-forward and the tax office's notice

Losses from private disposals may only be offset against gains from private disposals.
The app calculates a **suggestion**: a loss first goes back one year, the rest into the
following years. It is only offset against gains of a year that reach the Freigrenze — a
gain below it is tax-free anyway and leaves the carry-forward untouched.

What is binding is what the Finanzamt records in the **Feststellungsbescheid** (notice of
assessment of the loss). Enter the amount as of 31 Dec of a year with **Enter the assessed
figure** (ideally with a note, e.g. the date of the notice). From then on the app keeps
calculating with this figure and, if there is one, shows the difference to its own
calculation. If you already had a loss carry-forward before your first year in the app,
enter it in the first year under **Carry from earlier years**.

Excel and PDF contain the carry-forward of the year in the summary and all years on the
**Verlustvortrag** (loss carry-forward) sheet.

## For your tax advisor

**Example:** [tax report 2025 as PDF](../../beispiele/steuerbericht-2025.pdf) (German, as the app
creates it) — from the demo data, an invented portfolio.

- **Excel**: all individual items on their own sheets, plus a summary with the method and
  settings.
- **PDF**: the summary on the first page, then the same tables as in the Excel file (sales,
  income, futures, losses, open points, holdings 31 Dec).

The **cost estimated** column (in the PDF an asterisk * on the cost amount, with a footnote
below the table) says "yes" when there is no buy in the data for the coins sold, for
example with a receive without counterpart. Their market value on arrival is then used as
the cost instead.

Both use the year and method selected at the top. Text from outside (such as token names from
airdrops or notes) always stays plain text in the Excel file, never a formula.

## Keeping a version and the version history

Each version has a **Comment** field (it then also appears in its first line) and can be
removed again with **Delete version**; your transactions stay untouched.

**Keep** saves the state of the year with all individual items and creates the **PDF** and
**Excel** at the same time. Both stay as they were when kept, and you can download them
again from the version history at any time. You can add a **note**, e.g. "for the tax
advisor". Keep the report that you hand in.

**Version history** lists all kept versions of the year, newest at the top, each marked
**unchanged** or **changed**. "Changed" means: since then something has changed that affects
this year, such as a correction, a later import or a linked transfer. A correction in an
earlier year can be the cause too.

- **Compare with now** shows what has changed since this version.
- **Compare with the version before** puts two kept versions side by side.

The comparison first shows the key figures with then, now and difference. Below are all
transactions that are **new**, **gone** or **changed**, each with quantity and amount
before → after.

## Tax on a single transaction

On **Transactions**, every row has the **Tax** tab when expanded, also via **⋯ → Tax**:

- **Sale or swap**: from which buys it was sold, with purchase date, days, proceeds, cost
  and gain, split into "within the holding period" and "tax-free".
- **Buy**: the new lot and **what became of it**: still held (where, tax-free after …),
  sold later (with gain) or lost.
- **Transfer**: "no taxable event" and which buys moved along with their dates.
- **Income**, **Futures**, **Loss**: the assignment to § 22, § 20 or the list of losses.

## Holding period in the holdings

Under **Holdings** you expand a coin. **Holding period** shows what percentage has already
been held for more than a year, and from when the next part is tax-free. Good to know
before you sell.

## Related pages

- [Holding period and tax](../concepts/holding-period-and-tax.md)
- [Transactions](transactions.md), including how to mark sends and receives
