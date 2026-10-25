---
title: Settings
updated: 2026-10-25
---

# Settings

Under **Settings** (on the phone via **More**) all sections are listed one below the other;
each can be expanded and collapsed, and the app remembers which ones are open. Changes take
effect immediately.

## Appearance

<p>
  <img src="../../bilder/en/details/einst-darstellung.png" alt="Appearance" width="640">
</p>

All styles side by side: [Gallery](../gallery.md#styles).

- **Style**: Night, Neon, Terminal, Graphite, Rosé, High contrast, Amethyst, Sand and iOS
  (glass surfaces). Each tile shows a small preview.
- **Color**: an accent color of its own for every style (Petrol, Blue, Purple, Amber, Green,
  Rosé, Red) or **Default**, the style's own color.
- **Theme**: light, dark or like the device (**System**).

## App icon

The icon for the phone's home screen, also used as the icon in the browser tab and at the top
left. A new one applies the next time you add the app — see [On your phone](phone.md).

## Language and region

- **Language**: German or English. The tax report and the source of funds statement stay in
  German.
- **Display currency**: euro or dollar. The same switch sits at the top right of the pages;
  tax is always calculated in euros ([Prices and currencies](../concepts/prices-and-currencies.md)).
- **Time zone**: for times of day and for deciding which day a movement falls on.

## Security

Change the password: enter the old one, then the new one (at least 10 characters).
Afterwards every other sign-in (other devices, other browsers) has ended; this browser stays
signed in. Forgot it?
See [Troubleshooting](troubleshooting.md#forgot-your-password).

## Automatic fetch

<p>
  <img src="../../bilder/en/details/einst-abruf.png" alt="Automatic fetch" width="640">
</p>

**Fetch daily** (default: on, 04:00): once a day at the chosen time, all exchanges with an API key and all wallet networks are
fetched. You turn off individual sources on the [Sources](sources.md) page.

## Price fetch

- **Fetch prices daily** at the chosen time (default 04:30): the price history is extended.
- **Current prices**: how often the daily prices are updated (off, every 5, 15, 30 or
  60 minutes; default 5).
- **Default source order**: the order in which new coins look for their price.
  Coins that are already confirmed stay as they are — you change those one by one on the
  [Prices](prices.md) page.
- **New suggestions for unconfirmed**: every coin not yet confirmed gets a new suggestion by
  the current order, and the prices are fetched right away.

## Tax

<p>
  <img src="../../bilder/en/details/einst-steuer.png" alt="Tax" width="640">
</p>

- **Method**: FIFO (oldest first, default) or LIFO. It is applied **per wallet and exchange**
  ([why](../concepts/holding-period-and-tax.md#calculated-per-wallet-and-exchange)).
- **Tax airdrops on inflow**: whether an airdrop counts as income (default: off).
- **Head of the reports (PDF and Excel)**: **Name** and **Address** at the top of
  the [tax report](tax-report.md) and the [source of funds](source-of-funds.md) proof, the
  **Tax number** only on the tax report. All optional; empty fields are left out.

More on this: [Holding period and tax](../concepts/holding-period-and-tax.md).

## Blockchain services

<p>
  <img src="../../bilder/en/details/einst-dienste.png" alt="Blockchain services" width="640">
</p>

Some networks need a free key from a blockchain service (e.g. Etherscan for Arbitrum, Linea,
Mantle, Blast, Sonic; NodeReal for BNB Smart Chain); for others it only raises the limits
(TronGrid for Tron, toncenter for TON). The card shows what each one is needed for and links
to the sign-up.

## Claude (MCP) and API (JSON)

Two separate accesses with their own tokens: [Connect Claude](connect-claude.md) and
[API](api.md).

## Backup

<p>
  <img src="../../bilder/en/details/einst-sicherung.png" alt="Backup" width="640">
</p>

Schedule, how many daily and monthly backups are kept, “Back up now”, the recovery key and
restoring: [Backup](backup.md).
