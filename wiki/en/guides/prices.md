---
title: Prices
updated: 2026-10-25
---

# Prices

## In one sentence

Every morning owncryptofolio fetches the daily prices of all your coins. You check once per
coin whether the mapping is right, and confirm it.

## Why you need to check

A ticker symbol is not unique. "BTC" stands for eleven different coins. A wrong mapping
does not give *no* price but a **wrong** one, and that would flow unnoticed into profit and
loss. That is why owncryptofolio only makes a **suggestion**, and you confirm it.

## How to check a coin

<p>
  <img src="../../bilder/en/details/kurs-zeile.png" alt="A coin in the price list" width="640">
  <img src="../../bilder/en/details/kurs-graph.png" alt="Expanded: history, sources and tools" width="640">
</p>

1. **Prices** page → filter **To check**.
2. Tap the coin. You see:
   - the **curve**. Does it match what you know about the coin?
   - the **sources** in order of rank and how many days each one delivered;
   - the **current price**.
3. **Cross-check** compares two sources (Yahoo and Bitget) over 90 days. A difference below
   2 % is unremarkable. With more, there is often a different coin behind it.
4. If everything fits: **Confirm**.

## If something is wrong

- **Edit**: change the full name and the sources. If a source changes, you need a
  **Reason**. The Finanzamt (tax office) requires a documented, consistent valuation.
  Under **History** you see every change with its reason.
- On **Yahoo** some coins have a number in the symbol, e.g. The Graph `GRT6719-USD`.
  Search for the name on finance.yahoo.com.
- **CoinGecko** needs the ID from the address bar (e.g. `vara-network`) and only reaches
  back about one year.
- **Ignore**: for spam tokens someone sent you. They get no price and count nowhere. You find
  them under the filter **Ignored**; **Stop ignoring** brings a coin back.
- The filter **No price** shows all coins for which no source has delivered a daily price
  yet.

## Same coin, other symbol

Some exchanges call the same coin differently, e.g. MEXC "NTGL" and Bitget "NGL" (Entangle).
Expand the coin → **Same coin, other symbol** → enter the symbol it is kept under, plus the
full name and a reason. Your imported rows stay unchanged; for prices and later for
holdings both count as one coin. Under **Also as** you can split them again.

## Worthless from a date

If a project has gone dormant, its coin often has no price any more. Expand the coin →
**Mark as worthless (price 0)**, enter the date and a reason. From that day the coin counts
as 0, and its loss shows up in the result. The list then shows *"worthless from …"* instead
of a warning. **Undo worthless** reverses it.

## End prices (coin converted)

If a coin was converted into another one (e.g. AGIX → FET in 2024), the price sources often
only deliver nonsense for the old coin. Expand the coin → **End prices**, enter the last day
with a price and a reason. Up to that day the prices apply as before; after it the app
fetches none and removes later ones. Unlike "worthless", the coin does not count as 0
afterwards. The list shows *"until …"*. **Fetch prices again** reverses it.

## Fetching a single coin

After changing the sources of a coin you do not have to wait for the next morning: expand
the coin → **Fetch this coin only**. Below it you see how many daily prices were added.

## Symbol

If the logo is missing or wrong, enter under **Edit → Icon** the symbol under which the icon
pack lists the coin (e.g. RNDR for RENDER). The preview shows it right away.

## Live prices

While the Prices page is open, the current prices refresh every 30 seconds. A price that
has moved briefly flashes green or red. With **Search** and **Sort by** (usage, name, price,
change) you find a coin quickly.

## What "no price" means

If no source finds a price, the coin stays **unvalued**, never at 0. A 0 would look like a
total loss. The Prices page shows for which period the price is missing. If the coin really
is worth nothing any more, mark it as worthless (see above).

## Settings

Under **Settings → Price fetch**: the daily fetch (default 04:30, after the sources are
fetched), how often the current price is refreshed in the background (default every
5 minutes) and the **default ranking of the sources** for new suggestions. The default is
**Yahoo**, then Bitget, then Binance: that way all coins are valued from the same source as
far as possible. Another source only comes first where Yahoo has no usable history (e.g.
RON, QUBIC). After a change, **New suggestions for unconfirmed** redoes the coins that are
still open. **Fetch prices** at the top of the page starts a run right away.

## Change

Next to the price you see the change in percent. You choose the period above the list:
**today** (compared with the last daily close), **24 h**, **7 days**, **30 days** or
**90 days**. The app remembers your choice. For 24 hours it uses the fine prices it fetches
every hour (every 5 minutes for 31 days, hourly for 90 days).

The **curve** next to the price shows the same period: today and 24 h from the 5-minute
prices, 7 and 30 days from the hourly prices, 90 days from the daily prices. Its color
follows the change next to it (green = up, red = down).
