---
title: What's new
updated: 2026-10-28
---

# What's new

Changes in plain language — only what you notice while using the app. Newest first.

The technical version with every change is in [`CHANGELOG.md`](../../CHANGELOG.md) and in the
changelogs of the individual parts of the program.

---

## v1.8.1.0 — 28 October 2026

**Holdings: price change as an amount too.**

- Tapping the change over the period (e.g. “+14.7 % · 24 h”) shows for every coin how much your
  holding gained or lost by it in euros or dollars; a clock then stands for the chosen period. New
  sort option **Value change in period**.
- **First start fixed:** if Docker or Unraid only created the folders for data and backups,
  owncryptofolio could not write there and did not start. New in the Unraid template:
  `PUID`/`PGID` (99/100).
- Unraid now shows the app icon even while the container is stopped.
- Updated libraries, including a security fix for the development tool Vite.

## v1.8.0.0 — 25 October 2026

**owncryptofolio is public.**

- The ready-made image is on GitHub: `ghcr.io/vanixxx/owncryptofolio`, also for the Raspberry Pi
  (64-bit). Building it yourself is no longer needed.
- **One-click updates:** on Unraid the Docker tab shows “update ready”; with Docker Compose,
  `docker compose pull` and `docker compose up -d` are enough. See
  [Installing on Unraid](guides/install-unraid.md) and
  [Installing with Docker](guides/install-docker.md).
- Questions and bugs can be reported on GitHub as an issue, security problems privately.

## v1.7.6.0 — 25 October 2026

**Reviews: many fixes in fetching, valuation, security and backups.**

- **Security:** a new password signs out every other browser — sign in once after the update.
  Token names from outside sources (e.g. from airdrops) can do no harm in the interface or in
  Excel (a name like `=HYPERLINK(...)` no longer becomes a formula).
- **Restoring a backup:** a broken file leaves your data untouched, and the way back stays open
  even after restoring a backup from another installation.
- **Valuation and tax:** transactions just after midnight (until 1 or 2 am) were valued with the
  next day's price. Values and tax of such transactions can change slightly; a kept tax report
  then shows "changed".
- **Portfolio:** a fee in euros on a sale now lowers the gain here too; a futures fee counts as a
  fee instead of a result.
- **Tax:** a year with only sales without a recorded purchase now appears in the year selection.
- **More complete fetching:** with exchanges, MEXC, EVM networks, Cosmos, Dogecoin and Solana
  single transactions could go missing in special cases (e.g. two equal token transfers in one
  transaction, many trades in the same millisecond, withdrawals pending for long). A fetch that
  does not get everything now reports an error instead of silently leaving gaps.
- **Blockchain services:** a refused key is reported as such, pointing to the settings. If the
  exchange-rate service is down, price fetching still carries on.
- **Balance check:** a balance entered by hand is no longer added to the fetched one; the newer
  one counts.
- **Backup:** a fetch running during the backup no longer makes the test restore fail. The build
  script passes special characters in the database password correctly to the container.
- **Transactions:** filters no longer jump back to older results; loading more no longer skips
  rows with the same moment; **Hide all as spam** for dust really takes all of them.
- **Fixed:** futures values in the export (converted twice in dollars); an attached fee vanished
  after splitting a transfer; rows in the repeated hour of the clock change moved when saved;
  numbers from the Excel template with rounding remains.
- **Interface:** "tax-free from" shows the right day in other time zones too; an old error
  message disappears once things work again; charts switch colors right away with the style and
  light/dark.

---

## v1.7.5.0 — 24 October 2026

**Manual in English, security update, tax report with a head.**

- **Manual in English:** the whole wiki is now also available in English
  ([English manual](README.md)), with pictures of the English interface.
- **Pictures in the manual:** excerpts right next to the explanations and a
  [gallery](gallery.md); plus example PDFs of the tax report and the source-of-funds proof.
- **Tax report with your name:** name, address and – new – your tax number appear at the top of
  the tax report when you enter them under **Settings → Tax**.
- **Tax report as PDF:** the summary now sits entirely on the first page.
- **Security:** libraries with known vulnerabilities are updated; when rebuilding, the build
  script now always fetches the current base system with its security fixes.
- **Statistics:** **Account health** is much shorter on the phone — only the open points are
  listed; tapping the card also shows everything that is fine. On the PC every point is its own
  tile, and the ring shows the number of open points.
- **English interface:** "Color" and "Licenses" now use US spelling like the rest.
- **Fixed:** in the English interface the "+" of an amount sometimes stood alone on its line.

---

## v1.7.4.0 — 23 October 2026

**Getting ready for release.**

- **Forgot your password?** One command in the server's terminal sets a new one
  ([Troubleshooting](guides/troubleshooting.md#forgot-your-password)).
- **Backup folder fixed to `/backups`**: if no folder is mounted there, the app warns you under
  **Settings → Backup**.
- **Exchange icons** that the free icon set doesn't have are fetched by each installation itself
  from the exchange's website; the ones you already have are kept.
- **Licenses** under **System status**; owncryptofolio itself is licensed under the AGPL-3.0.
- **Tax report**: the note in Excel and PDF is easy to understand for tax advisors and the
  Finanzamt (tax office).
- **Wiki**: new pages Settings, On your phone, Troubleshooting, Installing with Docker (also
  without Compose) and Build your own integration; a table of all sources with their status.
- **Fixed:** under **System status** the fine-price jobs showed a placeholder instead of
  **Fine prices**.

---

## v1.7.3.0 — 23 October 2026

**NEAR and Cosmos.**

- **Four more networks** (beta): NEAR, Cosmos Hub, Osmosis and Celestia; on Cosmos with staking
  rewards. There, older transactions are missing if the free nodes no longer have them — the
  **Balance check** shows this. [More](guides/sources.md#near-and-cosmos)

---

## v1.7.2.0 — 23 October 2026

**Seven more networks.**

- **Seven new networks** (beta): XRP, Tezos, Algorand, Tron, TON, Dogecoin and Bitcoin Cash —
  with tokens (e.g. USDT on Tron and TON) and staking rewards, no key required.
  [More](guides/sources.md#new-networks-beta)
- For Tron and TON you can enter your own key under **Settings → Blockchain services**.

---

## v1.7.1.0 — 23 October 2026

**Your decisions stay.**

- **What you change stays changed**: if you split a transfer, owncryptofolio no longer links the
  two halves to something else on its own.
- **If an exchange changes a booking that was already imported**, you see it under **Sources**
  and in **Statistics** — and you decide: take the new values or keep the old ones.
  Nothing is doubled. [More](guides/sources.md)
- **Balance check** now also checks AXS and SLP on BNB Smart Chain.
- **Unraid**: the container shows the app icon in the Docker tab.

---

## v1.7.0.0 — 22 October 2026

**More networks, your own API, new styles, restore from the interface.**

- **Restore from a backup** right in the interface — under **Settings → Backup**, and on a new
  server already during setup. Beforehand you see what is in the backup, and owncryptofolio
  backs up the current state. **One key is enough**: the **Recovery key** (formerly "backup
  key") brings everything back, including the exchange logins. [More](guides/backup.md#restoring)
- **Seven more networks** (beta): Arbitrum, Optimism, Linea, Mantle, Blast, zkSync Era
  and Celo. owncryptofolio suggests the same address as on Ethereum right away.
- **API (JSON)**, read only: your data as web addresses for a widget, Home Assistant, Excel
  or scripts — with your own tokens. [Detailed guide](guides/api.md)
- **Claude**: one switch for everything, the level **Read only** or **Edit** per token.
- **Five new styles**: Graphite (gray with lime), Rosé (warm, burgundy), Amethyst (violet),
  Sand (terracotta) and High contrast (black/white, easy to read in sunlight) — each light and
  dark, plus an **iOS style** in the iPhone's "Liquid Glass" (glass surfaces over a color
  gradient). **Every style** can be shown in its own color (Petrol, Blue, Purple, Amber, Green,
  Rosé, Red); Neon keeps its color gradient. All under **Settings → Appearance**.
- **App icon** for the home screen: 16 to choose from under **Settings → App icon**
  (default: ring with a "c"). It applies the next time you use "Add to Home Screen" and is also
  the icon in the browser tab and at the top left of the app.
- **Compact transactions**: on the **Transactions** page and in **Holdings**, one row per
  transaction (the default on the phone, switchable to **Cards**). Tapping opens the full card
  with all details. On the PC the row shows more: time, places with logo, out and in with value,
  price and fee. You can spot futures by the purple ring. [More](guides/transactions.md)
- **Holdings → expand a coin → Transactions**: all transactions of that coin right there.
- **Holdings** like **Prices**: the small chart for today, 24 h, 7, 30 or 90 days, below it the
  change in %, and sorting by **Price change in period**.
- **Statistics**: **Coins without price** names the coins; one click opens the coin's price.
- **First start** without a setup code on a brand-new server; it is only asked for if keys are
  already there — with a note on where to find it. [More](guides/first-start.md)
- **Updating on Unraid**: "Edit → Apply" instead of "Restart" — only that brings the new version
  into the container.
- **Fixed:** the EUR/USD switch was hard to see in the Neon style.

---

## v1.6.0.0 — 19 October 2026

**Connect Claude.**

- **Connect Claude**: Claude Code or Claude Desktop can read your data — holdings,
  transactions, tax, source of funds, system status. Only on your home network, with its own
  token, addresses shortened, every call logged. [More](guides/connect-claude.md)
- **Claude may edit** (if you allow it): link transfers, notes, marks, manual entries,
  corrections … — always first as a complete list that you confirm. Under
  **Transactions → Changed through MCP** you see everything that was changed this way. You can
  also confirm just part of the list ("1–14, without 44").
- **Settings** collapsible and stacked one below the other; copying now also works over http.
- **EUR/USD toggle** at the top right of **Dashboard**, **Holdings**, **Transactions**, **Prices**,
  **Statistics** and **Reports** (in the header on the phone) — the same setting as under
  **Settings**.

---

## v1.5.0.0 — 19 October 2026

**More sources.**

- **Many more exchanges**: through the search when adding a source, around 60 more exchanges
  via API, e.g. Binance, Bybit, OKX, Bitvavo, Gate, plus the API of Kraken and KuCoin. They are
  marked as **beta**; a note tells you what can go wrong and what you should check.
  Without searching, you only see the tested exchanges. [More](guides/sources.md#more-exchanges-beta)
- **Your own file for any exchange**: upload a CSV or Excel export, map columns and values
  yourself, look at every row before importing. The mapping is remembered. You find it on the
  exchange's card and under **Transactions → + → Import**.
  [More](guides/sources.md#own-file-csvexcel--for-any-exchange)
- **Log in System status**: follow the messages from the server and the browser live, filter,
  search and save them as a file. You set the **log level** there (Info, Debug, …).
  Addresses and keys are shortened or hidden.
  [More](guides/system-health.md#log)

---

## v1.4.0.0 — 18 October 2026

**Loss carry-forward and source of funds.**

- **Source of funds**: under **Reports** you see for every sale, transfer (also between your
  own wallets) or withdrawal where the money comes from — split by origin and as a chain back to
  the deposits, as PDF and Excel. Also for your **current holdings**, in total and per coin, and
  for a **planned transaction** (proof in advance, without booking it).
  [More](guides/source-of-funds.md)
- **Source of funds as a diagram**: the flow of money simplified (per exchange/wallet) or in full
  (every step), with hover for amounts.
- **Source of funds in detail**: price losses are shown as their own (negative) item, plus an
  overview, deposits in detail, data sources with their type of data and a short summary in
  words.
- **Loss carry-forward**: the tax report shows what is left of losses from earlier years,
  how it is offset and what goes back to the previous year. You can enter the value from the
  Finanzamt's (tax office's) notice; it then takes priority. Also in Excel and PDF.
- **End prices**: for a migrated coin (e.g. AGIX → FET) you set the last day with a price;
  after that the app fetches nothing more. AGIX ends on 2024-07-05.
- The price chart of an ended coin opens on **All**; a period without prices says so instead of
  loading forever.
- **Sources**: the note about a failed fetch now comes with **Fetch again** right there.

---

## v1.3.0.0 — 16 October 2026

**Fine values: prices and portfolio value every 5 minutes.**

- **Dashboard**: 24 h, 7 days and 1 month show the portfolio value every 5 minutes (31
  days), hourly before that. Gaps caused by outages fill in by themselves.
- **Prices**: change also over 24 h; the chart per coin shows the selected period.
- **Reports**: tab **Tax-free** — per coin, how much is tax-free today and how much is still
  within the holding period, with its value in your currency. A bar shows how much of the
  Freigrenze (tax-free allowance) is used up; from 80 % a note appears on the dashboard.
- **System status**: row **Fine values (hourly)**.

---

## v1.2.0.0 — 15 October 2026

**Statistics.**

- New page **Statistics**: returns per month and year, comparison "everything in BTC", fees,
  income, futures balance, activity, account health and spot balance.
- **Dashboard**: allocation by coin or exchange/wallet, winners and losers, **Tax-free soon**,
  distance to the high, daily high/low as a band, scrolling back.
- **Prices**: change over today, 7, 30 or 90 days. **Holdings**: chart per coin (PC).
- **Transactions**: the transaction ID leads to the block explorer.
- If the **database** is not running, the page says so and reconnects by itself.
- A failed automatic fetch is retried after 15 minutes.

---

## v1.1.0.0 — 13 October 2026

**Tax: the tax report under German law.**

- **Reports** shows per year private sales (§ 23 EStG) with the Freigrenze (tax-free
  allowance), income (§ 22), futures (§ 20, Anlage KAP) and losses through insolvency or
  fraud, with all individual items, totals per exchange/wallet, changes in holdings, holdings on
  31 Dec and a filling-in help for Anlage SO and KAP. FIFO is the default, LIFO for comparison.
- **Excel and PDF** with all tables. **Keep** saves a version including PDF and
  Excel; the version history later reports changes, compares versions item by
  item, takes a comment and lets you delete versions.
- **Transactions**: tab **Tax** per row (which purchases a sale came from, what became of
  a purchase), **price** for every trade, note **Card purchase without euro amount**.
- **Holdings**: how much of a coin is already tax-free and from when the next part is.
- **Add transaction**: market price under each coin, price for a trade.
- **System status**: how much storage owncryptofolio itself uses.
- Checked against Blockpit; a card purchase without a euro amount counts with estimated costs.

---

## v1.0.0.0 — 12 October 2026

**Tracking complete: owncryptofolio is ready for everyday use.**

- **As a container on Unraid**: a script builds it, the template in the Docker tab is
  filled in, you enter the database in separate fields. See "Installation and
  update on Unraid".
- **System status → Operations** shows at a glance whether backup, fetches and prices run by
  themselves and whether there is enough free storage.
- **Dashboard**: tapping **Net deposited** hides the line; the time slider shows
  your value.
- **Manual**: new guides on transactions and system status, all others brought up
  to date.
- Small things: worthless coins without a warning, a calmer price axis, the Litecoin fetch
  survives short outages.

**Next up:** tax — holding period, FIFO/LIFO and the report for the Finanzamt (tax office).

---

## v0.7.0.0 — 11 October 2026

**Polish: everything in its place, every gap explained.**

- **Expand transactions** like tabs: Details, Edit, History, Find counterpart.
  Everything else via "⋯".
- **Search and filter** by coin, date, note, address, hint and several sources
  or types at once. What doesn't match is dimmed.
- **Enter transactions** in their own window: coin from the list, copying, transfer with **From**
  and **To**, and the field shows you how much you had there at that time.
- **Mark** what has no partner: sent to others, to your own wallet or
  lost (e.g. insolvency); received from your own wallet, bought elsewhere or income.
- **Card purchases** count as a deposit, also at Coinbase by card or PayPal.
- **Sources** tidied up: balance check and fetching collapsible, connection status at
  a glance, networks without a connection (e.g. Optimism) for manual entries.
- **Holdings** with a price chart and your average price as a line.
- **Prices**: fetch a single coin, mark coins as worthless from a date.
- **Export** as Excel or CSV, dashboard with **24 h** and **7 days**, your own logos.
- **Warnings** when an exchange refuses the API key (e.g. expired after 90 days), a fetch
  fails or the API's look-back runs out.
- **Fixed:** the change on the dashboard counted deposits as profit; at Coinbase the fee was
  deducted twice.

**Next up:** tracking complete: the finished container, scheduled backup, everything checked
on the phone.

---

## v0.6.0.0 — 5 October 2026

**What you own, what it's worth and what you've earned.**

- **Dashboard**: total value, history since the first transaction with the money deposited
  behind it, high, total result, allocation across your coins and notes on what makes the
  numbers uncertain.
- **Holdings**: every coin with amount, cost, value and profit or loss, plus your
  futures positions.
- **Gaps**: where transactions are missing and from when, with one click to the matching
  transactions.
- **Per trade**: if you expand a purchase, you see what exactly this purchase is worth today.
- **Futures**: closed positions each appear as one row in the transactions.
- **Find instead of search**: sorting and searching in holdings and transactions, coin and
  source from a list with a search field.
- **Ronin** as a new network.
- **Nicer**: icons for every type of transaction, coin logos next to the amounts, tidy
  views on PC and phone, no more zooming on the phone.

**Next up:** making tracking complete: history of the last 24 hours, scheduled backup,
export as a spreadsheet, everything checked on the phone and the finished container.

---

## v0.5.1.0 — 4 October 2026

**Filters for transactions.**

- **Filter transactions** by source, type, coin and period. A whole wallet can be selected at
  once.
- Networks are now named together with their wallet, e.g. **"Tangem – Ethereum"**.

---

## v0.5.0.0 — 4 October 2026

**Many rows become one truth.**

- **Transfers as one row**: if you send coins from an exchange to your wallet, this now
  appears once under **Transactions**, with "sent", "arrived" and the
  network fee. You split what's wrong and link what's missing yourself.
- **Open sends**: what went out without a counterpart you see under "Open" and
  mark it as **To others** or **Own wallet, not set up**.
- **Spam and dust**: a coin ignored on the **Prices** page disappears everywhere.
  The program suggests tiny incoming amounts as dust; you hide them with one click.
- **Balance check**: on the **Sources** page you see per exchange, wallet and network whether
  the balance matches your transactions. For Gate.io and SafeTrade you enter it by
  hand.
- The previous list is still available via the **Raw data** switch.

**Next up:** portfolio and profit/loss — what you own, what it's worth and what
you've earned. Plus a clearer way to find from when something is missing for a coin.

---

## v0.4.0.1 — 4 October 2026

**Prices touched up.**

- Coins with a very small price (e.g. SHIB, XEN) get their price from a more precise source.
- An ended coin (e.g. FTM after the switch to S) shows "until <date>" instead of an outdated
  current price.

---

## v0.4.0.0 — 4 October 2026

**Every coin has its price.**

- **Prices page**: all your coins with their real logo, current price and history, also for
  the past back to 2021. The price refreshes while the page is open and
  flashes when it moves.
- **You're in control**: every mapping is a suggestion that you check and confirm.
  A cross-check compares two sources. You correct what's wrong yourself, with a reason in the
  history. You hide spam. You merge identical coins with different tickers.
- **Euro or dollar**, switchable in the settings.
- **Every morning** the prices are filled in automatically.

**Next up:** many rows become one truth: transfers between your
exchanges and wallets are merged, spam is hidden and the holdings per source are
checked.

---

## v0.3.0.0 — 4 October 2026

**All your sources are here.**

- **Exchanges:** Coinbase, MEXC (via API and file), plus Kraken and KuCoin as archive files.
- **16 networks** for your wallet: Ethereum, Polygon, Avalanche, Sonic, Cronos, BNB,
  Bitcoin, Litecoin, Solana (with RENDER), VeChain (with VTHO), Cardano, Sui, Polkadot,
  Hedera, Kaspa, Stellar. Three need a free key, which you enter under
  **Settings → Blockchain services**.
- **Every morning at 4 a.m.** all sources are fetched automatically. Or you press
  **Fetch all**.
- **Enter by hand:** for exchanges without an API such as Gate.io or SafeTrade, one by one or
  with an Excel template, futures too.
- **Edit any transaction**, including those from an exchange. The original is kept, the
  history shows what you changed, and one tap resets it.
- Clearer: sources can be collapsed, times with seconds.

**Next up:** prices. Every coin gets its price, also for the past, and its
real icon.

---

## v0.2.0.0 — 3 October 2026

**Your data comes in.**

- **Connect exchanges**: enter API keys, check, fetch — for Bitget including futures.
  The API fetches the whole reachable history, after that only what's new.
- **Wallets as devices**: e.g. create "Tangem Cold Wallet" and add the networks with their
  address underneath. To start with: Ethereum.
- **Import files** with a preview: you see beforehand what is new and what the API already
  covers — nothing is counted twice. Every import can be undone.
- **Transactions**: all imported transactions, as cards on the phone, filterable by source
  and spot/futures.
- **Backup every night** with a test restore, adjustable under **Settings**.

**Next up:** Coinbase, MEXC, Kraken, KuCoin and the remaining networks, plus
automatic fetching every day.

---

## v0.1.0.0 — 3 October 2026

**The new interface is in place.** Still without your data, but fully under construction:

- **First start without a terminal:** owncryptofolio sets up its database itself and
  guides you through a wizard — setup code, password, backup key,
  basic settings. How it works: [First start and setup](guides/first-start.md).
- **Three styles to choose from:** Night, Neon and Terminal, each light or dark — under
  *Settings → Appearance*, with a preview.
- **German or English**, switchable under *Settings → Language and region*.
- **On the phone** a bar at the bottom, on the PC a sidebar.
- **All pages are already there.** What isn't finished yet is shown as "not available
  yet" with a note on when it's coming.
- Changing the password, showing the backup key and checking the **System status** already
  work.

**Next up:** connecting your sources — first the backup, then exchanges, wallets and
file import.

---

## Restart — 2 October 2026

**owncryptofolio is being rebuilt.** The program moves to the Unraid server, which
runs around the clock, and is reprogrammed from scratch along the way. Your data and everything
learned so far are kept.

What changes for you:

- **The overview comes first:** importing sources, merging, prices, holdings,
  profit and loss. The **tax report comes back later**.
- **Everything in the browser from the start:** every feature brings its page and its
  settings right along. What isn't finished yet is shown as "not available
  yet" — nothing is hidden.
- **The look is settled first**, so that all pages fit together.
- **Futures are included:** your futures positions from Bitget, MEXC and KuCoin are
  imported too and shown separately from your spot holdings. This also makes the
  holdings at these exchanges add up again.

Version numbers start again at `v0.1.0.0`. The entries below describe the
old state up to `v0.7.0.0`.

---

## v0.7.0.0 — 12 September 2026

**owncryptofolio is now protected by a password.** Without the right password
you only see the sign-in screen. To set it up you need a terminal once —
never again after that. How it works is described in
[Setting up and importing sources](guides/sources.md).

**The new "Sources" tab replaces the terminal for almost everything else.** Until now
you had to type a command on the command line for every exchange, every wallet address and
every file import. Now you do it in the browser:

- **Exchange logins**: create, check and remove them again — including a check
  whether the key you entered actually works. When it was last checked
  and what the result was stays on the card.
- **Wallet addresses**: add and remove them, with an immediate check whether the address
  fits the selected chain.
- **Import export files** — first a preview, then the import — and **undo** an
  import if needed.
- **Fetch chains and prices** at the push of a button, with progress per chain. The
  chain fetch takes the addresses from the tab itself; what it brings in appears per chain
  as its own run in the import list and can be undone there.

**What doesn't work yet:** the "Fetch exchanges" button deliberately reports an error — the
automatic fetch directly from the exchange comes with a later building block. Until then
you bring exchange data in via file import, or use **Check connection** to see
whether your login works.

---

## v0.6.0.0 — 30 August 2026

**The tax report is here.** Under **Tax** you see per year what counts as a private
sale under § 23 EStG (private sales) and what counts as other income under
§ 22 Nr. 3 EStG (other income). Each with its own Freigrenze (tax-free allowance), each
separately — the Freigrenze is not an allowance you can deduct: one euro over it, and the
whole amount counts.

The calculation works with **lots**: every incoming amount keeps its own acquisition date
and its own cost. When you sell, lots are taken by FIFO or LIFO —
you can switch. A transfer to your own wallet sells nothing;
the lot moves along, the holding period keeps running.

**What the report can't do, it tells you.** Next to the number, with equal weight, are
the unresolved transactions, the sends without covering holdings and the items that
rest on an estimated cost. If the tax figure rests on an incomplete history, you should see
that instead of guessing.

You can export the report as **Excel** and **keep** it. A
kept report notices when the year calculates differently later — because you
confirmed a spam row, corrected a transfer or switched the
method. Then it tells you what has changed.

What does **not** work yet: no PDF (Excel is there), no loss carry-forward, and no
list of holdings at year end for your tax advisor.

---

## v0.5.0.0 — 29 August 2026

**Everything is connected.** Seventeen blockchains, three exchanges via their interface and
six export files. New are **Kraken** and **KuCoin**.

What's still missing: **BNB Smart Chain** (there is no free source for it) and **Bitcoin
Cash**. On **VeChain and Solana** only the main currency is read so far — that's why VTHO and
RENDER are missing.

---

## v0.4.0.0 — 28 August 2026

**Transfers between your own accounts are now one row, not
two.** If you send coins from the exchange to your wallet,
owncryptofolio recognizes this and merges both sides — **and no link is
guessed.** What can't be proven stays
open and visible instead of being pushed together into a plausible pair.

Also new is the **spam mark**: worthless tokens that someone
sent you unasked can be flagged — one by one or for the
whole coin at once.

**Your raw data stays untouched.** Every correction you make sits
on top as its own layer. Nothing is overwritten, everything can be undone.

---

## v0.3.0.0 — 25 August 2026

**You see what your coins are worth.** The home page now shows
portfolio value, cost basis, profit and loss as well as your high — plus
a history over the last few years that you can zoom into. Everything
switchable between euro and dollar.

Also new is the **Prices** page: there you see per coin where its price comes from. Check the
mapping once and confirm it — the reason is explained under
[Prices and currencies](concepts/prices-and-currencies.md). In short: dozens of coins
share the same ticker, and a mix-up doesn't give you a missing
price, but a wrong one.

**What's at the top of the home page is just as important as the numbers.** There
owncryptofolio tells you what it doesn't know yet — for example, that coins went out via a
transfer whose destination isn't connected yet. As long as that's
the case, your portfolio value is too low, and you should know that instead of
guessing.

What does **not** work yet: transfers between your own accounts aren't
merged yet, and wallets aren't connected yet. Both are coming.

---

## v0.2.0.0 — 25 August 2026

**Your transactions are here.** Transactions from Coinbase, MEXC and Bitget — imported from
the exchanges' export files and visible in a list.

What you can do with it:

- filter by source, type and asset, sort by time, source or type
- expand a row and see what the exchange **really** delivered
- read the same list on the phone as cards instead of a squeezed table

**Importing the same file twice does no harm.** owncryptofolio recognizes transactions it
already knows and skips them — and tells you how many there were.

**Your data is backed up.** One command writes an encrypted dump and a
readable export, and immediately checks whether the dump can really be restored.
How it works is described in [Setting up and checking backups](guides/backup.md).

What does **not** work yet: prices, values, profits. And the exchanges aren't queried
directly yet — so far owncryptofolio reads their export files. Both are coming.

---

## v0.1.0.0 — 23 August 2026

The program starts and is connected to your database. That's all it can do so far:
there are no transactions, no prices and no analysis. The home page shows you
whether the connection works — that is the purpose of this version.
