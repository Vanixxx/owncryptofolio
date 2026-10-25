---
title: owncryptofolio — Manual
updated: 2026-10-25
---

Deutsch: [../README.md](../README.md)

# owncryptofolio

owncryptofolio collects your crypto transactions from all sources in one place: from
exchanges, from blockchain networks for your hardware wallet, from Excel and CSV files
and by hand. From this, it shows you what your portfolio is currently worth, how much
you have put in and where your profit or loss stands — and it produces the evaluation
you need for your taxes.

It runs on your own computer or server. Your data does not leave it.

The app is available in English and German (Settings → Language); the screenshots here show the English interface.

> **Note on the state of development:** The software is developed continuously. The
> concept pages below describe how owncryptofolio works. A **guide** is only written once
> the respective feature works, using the real interface.

---

**[Gallery](gallery.md)** — all pages on PC and phone, all styles (from demo data).

---

## Concepts — what the terms mean

Read these pages once before you start. They explain the terms you come across in the
interface and save you most follow-up questions.

| Page | Answers |
|---|---|
| [How your data is stored](concepts/how-data-is-stored.md) | Why there are two tables, which one you see and what the other one is for |
| [Integrations](concepts/integrations.md) | What an integration is, why you can set up the same one several times and what the balance check tells you |
| [Merging transactions](concepts/merging-transactions.md) | Why a transfer shows up twice, what the marks mean and when you have to step in yourself |
| [Hiding spam](concepts/hiding-spam.md) | What spam tokens are and what happens to your numbers when you hide them |
| [Prices and currencies](concepts/prices-and-currencies.md) | Why prices are stored, how you switch between euro and dollar and what a price gap means |
| [Licenses and trademarks](concepts/licenses.md) | Whose free works owncryptofolio uses and who owns the names and logos |
| [Cost basis, profit and loss](concepts/cost-basis-profit-loss.md) | What cost basis and DCA are, why realized and unrealized profit diverge and why fees count |
| [Holding period and tax](concepts/holding-period-and-tax.md) | FIFO and LIFO, holding period, Freigrenzen (tax-free allowances), fees, futures and losses: how the tax report calculates |

## Guides — what you press

[Overview](guides/README.md) — every guide with a short description.

- [Installation with Docker](guides/install-docker.md)
- [Settings](guides/settings.md)
- [On your phone](guides/phone.md)
- [Help with problems](guides/troubleshooting.md)
- [Installation and update on Unraid](guides/install-unraid.md)
- [First start and setup](guides/first-start.md)
- [Setting up and importing sources](guides/sources.md)
- [Transactions](guides/transactions.md)
- [Dashboard and holdings](guides/portfolio.md)
- [Prices](guides/prices.md)
- [Tax report](guides/tax-report.md)
- [Source of funds](guides/source-of-funds.md)
- [Statistics](guides/statistics.md)
- [Backup](guides/backup.md)
- [System status](guides/system-health.md)
- [Connect Claude](guides/connect-claude.md)
- [API (JSON)](guides/api.md)

## Extending

- [Build your own integration](guides/build-an-integration.md) — one folder per exchange or network,
  with a complete example and checklist (also for an AI)

## What's new

[Changes per version](whats-new.md), in plain user language.
