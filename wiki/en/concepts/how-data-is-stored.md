---
title: How your data is stored
updated: 2026-10-25
---

# How your data is stored

owncryptofolio keeps your transactions on **two levels**. This is the most important
point for understanding what you see in the interface.

## The raw data

Everything that comes in first lands unchanged in the raw data: every line exactly as
the exchange, the blockchain or your file delivered it. This level is **never changed**.
Nothing is corrected, combined or deleted there. The only exception: you can undo the latest
file import of a source as long as no row from it is corrected or hidden — its rows then
disappear again.

The raw data is your evidence. If you want to know where a number comes from, you find
it here — in its original state.

## The display level

From the raw data, the program calculates the table you actually use. Here, related
events are linked, spam is hidden and marks are set. You can **correct** this level —
it is there for you to work with.

## Why the separation matters to you

**You cannot break anything.** If you wrongly merge or hide something on the display
level, your original data is untouched. The program can rebuild the display level
completely from the raw data at any time.

**Your corrections are kept.** Such a rebuild does not throw away your manual changes —
they are stored separately and applied again afterwards.

**Rules are allowed to change.** If it later becomes possible to detect better which
transactions belong together, you do not have to import anything again. The raw data is
already there; it is simply recalculated.

## What this means day to day

- You almost always work on the **display level**.
- You look at the **raw data** when a number puzzles you and you want to know what the
  source really delivered: the **Raw data** switch on the
  [Transactions](../guides/transactions.md) page.
- You can export both levels.

## Read more

- [Merging transactions](merging-transactions.md) — what happens to your data on the
  display level
- [Integrations](integrations.md) — where the raw data comes from
