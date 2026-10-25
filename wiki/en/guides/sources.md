---
title: Setting up and reading sources
updated: 2026-10-25
---

# Setting up and reading sources

On the **Sources** page you set up everything owncryptofolio gets its data from:
your exchanges and your wallets. On the phone you find it under **More → Sources**.

The page has two sections:

- **Exchanges**: one card per exchange account, e.g. Bitget.
- **Wallets**: one card per device or app, e.g. "Tangem Cold Wallet". Below it are
  the **networks** with their addresses, such as Ethereum, Bitcoin, Solana, Tron or XRP. That way you
  later see at a glance what is on which device.

## All sources at a glance

**tested** means: checked against a real account, the sum of the transactions matches the
account balance. **beta** means: built from the documentation and checked against public addresses or
examples, but not yet against an account of our own — fetch and look at the
[Balance check](#balance-check). Every exchange can also be read in through an
[own file](#own-file-csvexcel--for-any-exchange) and completed by hand.

<!-- generated from the plugin registry; tests/test_wiki_sources.py checks it stays complete -->
| Exchange | Fetching | Status |
|---|---|---|
| Bitget | API + file | tested |
| Coinbase | API + file | tested |
| Kraken | API (ccxt) + own file | tested |
| KuCoin | API (ccxt) + own file | tested |
| MEXC | API + file | tested |
| Exchange without connection | by hand | tested |

| Network | Key | Status |
|---|---|---|
| Algorand | — | beta |
| Arbitrum One | Etherscan (free), required | beta |
| Avalanche C-Chain | — | tested |
| Bitcoin | — | beta |
| Bitcoin Cash | — | beta |
| Blast | Etherscan (free), required | beta |
| BNB Smart Chain | NodeReal (free), required | tested |
| Cardano | — | tested |
| Celestia | — | beta |
| Celo | — | beta |
| Cosmos Hub | — | beta |
| Cronos EVM | Cronos Explorer (free), required | tested |
| Dogecoin | — | beta |
| Ethereum | — | tested |
| Hedera | — | tested |
| Kaspa | — | tested |
| Linea | Etherscan (free), required | beta |
| Litecoin | — | tested |
| Mantle | Etherscan (free), required | beta |
| NEAR | — | beta |
| Optimism | — | beta |
| Osmosis | — | beta |
| Polkadot | — | tested |
| Polygon | Etherscan (free), required | tested |
| Ronin | — | tested |
| Solana | — | tested |
| Sonic | Etherscan (free), required | tested |
| Stellar | — | beta |
| Sui | — | tested |
| Tezos | — | beta |
| TON | toncenter, optional | beta |
| Tron | TronGrid, optional | beta |
| VeChain | — | tested |
| XRP Ledger | — | beta |
| zkSync Era | — | beta |
| Network without connection | — | tested |

**56 more exchanges through ccxt** (API fetching, all beta):

| | | | |
|---|---|---|---|
| Alpaca | Backpack | Bequant | BigONE |
| Binance | Binance US | BingX | BIT.TEAM |
| Bitbns | Bitfinex | bitFlyer | BitoPro |
| Bitrue | Bitso | Bitstamp | BitTrade |
| Bitvavo | Blockchain.com | BloFin | BTC Markets |
| BTSE | Bullish | Bybit | Bybit EU |
| Bybit Indonesia | BYDFi | Coinbase Exchange | Coincheck |
| CoinEx | CoinMate | Coins.ph | Crypto.com |
| DeepCoin | DigiFinex | FMFW.io | Foxbit |
| Gate | Gate EU | Gemini | HashKey Global |
| HitBTC | HollaEx | HTX | Latoken |
| LBank | MyOKX (EEA) | NDAX | OKX |
| OKX (US) | Phemex | Poloniex | Tokocrypto |
| Toobit | WhiteBit | WOO X | XT |

A "required" key is entered under [Settings → Blockchain services](settings.md#blockchain-services);
"optional" works without one, just more slowly.

## Adding an exchange

<p>
  <img src="../../bilder/en/details/quelle-hinzufuegen.png" alt="Add exchange" width="640">
</p>

1. Tap **Add exchange** and choose the provider, e.g. *Bitget*.
2. Enter a label, e.g. "Bitget main account", then **Create**.

### More exchanges (beta)

Most have a logo from a free icon set; if it is missing there, owncryptofolio fetches the
icon from the exchange's website the first time it is shown and stores it. Where none could be found,
the first letter is shown — you can upload your own logo on the card.

Without a search term you only see the **tested** exchanges (Bitget, Coinbase, Kraken, KuCoin,
MEXC) and **Exchange without connection**. Through the **search** you find 56 more, e.g.
Binance, Bybit, OKX, Bitvavo or Gate. They run through a shared interface and
carry the **Beta** badge: not yet checked with a real account.

When adding one, and later on the card (under **Fetching and import**), it says what can
go wrong, for example:

- fees deducted wrongly or twice,
- only a limited period can be fetched,
- trades of coins that you bought at the exchange **and** sold there completely again
  are missing (some exchanges only hand out trades per trading pair),
- futures, margin, earn/staking, transfers and euro deposits are not read.

**After the first fetch, check the [Balance check](#balance-check).** If it does not match,
complete it by file import or by hand. Depending on the exchange, the form asks for API key,
secret and additionally a passphrase or UID.

For Kraken and KuCoin the **file import is tested**, the API is beta; the badge then
shows "Beta · API".

## Adding a wallet

1. Tap **Add wallet** and enter a name, e.g. "Tangem Cold Wallet".
2. In the new card, **Add network**, choose the network and paste the **Address**.
   If it does not fit the network, *"This address does not fit …"* appears right
   below it.
3. Repeat for every further network. **Tip:** Ethereum, Polygon, BNB, Avalanche,
   Cronos and Sonic use **the same address** on Tangem and most wallets. If one of them
   is already in the wallet, owncryptofolio suggests it.
4. **Fetch all** fetches all networks of the wallet at once. One at a time works through the
   arrow icon next to the network.

A wallet can be renamed. Deleting is only possible once there are no networks left in it,
and a network only once its imports have been reverted.

**Network without connection:** If a network is not in the list or cannot be
fetched, choose the **Network without connection** tile under **Add network**.
You enter the name freely, the address is only a note. It is never
fetched; you enter the transactions on the [Transactions](transactions.md) page.

> **Ronin**: You can paste the address from the Ronin wallet (`ronin:…`) exactly as it
> appears there. Ronin's explorer only allows a few requests in a short time; a fetch then
> waits a few minutes and continues by itself.

## Exchange: entering the API key

**The API is the preferred way.** It fetches your history directly from the exchange.

1. At the exchange, create an **API key with read-only permissions**: without trading and
   without withdrawal. For Bitget you need API key, secret and passphrase.
2. Enter the values in the card under **Fetching and import → API access** and tap **Save
   key**.
3. owncryptofolio checks the connection right away. Below it you see *"Connection works"*
   or the exchange's answer why not.

The keys are stored **encrypted** and never shown again. You only see
that they are stored. Changing, checking again or removing is possible at any time.

## How a card is built

<p>
  <img src="../../bilder/en/details/quelle-boerse.png" alt="Card of an exchange" width="640">
  <img src="../../bilder/en/details/quelle-wallet.png" alt="Card of a wallet" width="640">
</p>

Exchanges and wallets are collapsed cards: you see the name, number of transactions, the
balance check, when it was last fetched, and the fetch button. Tapping the
name expands the card. Inside, the sections can be collapsed again; the app remembers
what you have open.

- **Exchange**: **Balance check** (open) and **Fetching and import** (closed). Inside it the note
  from when the API is enough, **fetch daily**, and separately **API access**, **File import**
  and **Imports**. Next to **API access** it says *Connection works* in green or
  *Connection failed* in yellow; an error is also shown on **Fetching and import**, so you see it
  while collapsed.
- **Wallet**: **Balance check** with one row per network (expandable) and below it
  **n networks** with address, fetch button and **fetch daily**.

## Fetching

If an **automatic** fetch fails because of a timeout or a
connection error (for example because the service is slow right now), the app starts it again by itself after
15 minutes, at most three times. A rejected key is not
retried, that one needs you.

If a fetch has failed, a yellow notice appears at the top of the page. Next to it,
**Fetch again** fetches exactly this source once more; if it works, the notice disappears.

**Fetch all** at the top of the page fetches all exchanges with an API key and all
wallet networks at once. This happens by itself every morning (Settings →
Automatic fetch).

**Fetch now** fetches the data in the background. You can leave the page in the
meantime. Next to the button you see the progress and at the end how many transactions were
**new** and how many **known**.

If a fetch cannot read everything (for example because a node breaks off while paging or does
not deliver transactions), **it fails with a message** and stores nothing, instead of silently
leaving gaps. If a blockchain service refuses your key, the message says exactly that; enter a
valid one under **Settings → Blockchain services**.

- The **first** fetch gets everything the source provides. For Bitget this takes about
  8 minutes, because Bitget only allows slow requests.
- Every further fetch only gets what has been added since, and reads a little back:
  exchanges two weeks (so deposits and withdrawals pending for days are not missed), wallets
  two days. Transactions that are already known are recognized and not stored twice.
- For a wallet you usually only need the address. Some networks need a
  **free key** from a blockchain service, entered under
  **Settings → Blockchain services**:

  | Network | Service |
  |---|---|
  | Ethereum, Avalanche, Bitcoin, Litecoin, Solana, Cardano, Kaspa, Polkadot, VeChain, Hedera, Sui, Stellar | none |
  | Polygon, Sonic, Arbitrum One, Blast, Linea, Mantle | Etherscan |
  | Cronos EVM | Cronos Explorer (only CRO, no tokens) |
  | BNB Smart Chain | NodeReal MegaNode |

  **Polkadot** automatically reads both parts of the chain (Relay Chain and Asset Hub, move
  on 4 Nov 2025). You add Polkadot only once. A **Stellar** account that has never
  received anything does not exist on the chain yet: the fetch then simply reports
  0 transactions.

## Reading a file (only if the API is not enough)

Some periods are out of the API's reach. For those there is the **File import**, e.g. the
ZIP export "Export order history" from Bitget.

1. In the card, **Fetching and import → File import → Choose file(s)**. owncryptofolio first shows
   a **Preview** and does not store anything yet:
   - how many transactions were **read**, **already imported from a file**, **covered by API**
     or **rejected**, and how many of them are new and count;
   - the period of the file;
   - the kinds, such as trade, send or futures funding.
2. If everything fits, **Import**. Otherwise **Cancel**.

The original file is kept unchanged with every import.

> **If the API already covers a period**, the card says so, separately for
> spot and futures (for Bitget the API reaches less far back for futures). File rows from this period are stored, **but do
> not count**. In the transaction list they appear faded with the note *"covered by
> API"*. That way no transaction counts twice, no matter whether you read the file or the
> API first.

## Own file (CSV/Excel) — for any exchange

If your exchange has no connection or something is missing, upload its export yourself: on the
exchange's card under **Fetching and import → Own file (CSV/Excel)** (beta). This works for
every exchange, including **Exchange without connection**.

1. **Choose file** (CSV or Excel). Under **View original file** (expandable) you see
   the first rows as they are in the file — the header marked, above it which
   field each column is mapped to. Separator, number format, header row and
   date format are detected; you can change them. The **Time zone of the file** is the one you
   have set; many exchanges write UTC — then switch it.
2. Choose the **Layout**:
   - *One row per movement*: date, kind, coin, amount. A purchase is either in **one**
     row with a counter value (Coinbase: amount BTC, counter value in EUR) or in **two** rows with
     the same ID (Kraken: plus row incoming, minus row outgoing).
   - *One row per trade*: date, trading pair, buy/sell, amount, price or total.
3. **Map columns**: suggestions are already filled in, required fields are red as long as they are missing.
4. **Map values**: every word in the kind column ("Buy", "Staking Income" …) gets a
   kind — buy, sell, swap (from the note, e.g. "Converted 0.1 ETH to 0.003 BTC"),
   trade half, deposit, withdrawal, income, transfer between your own accounts, fee
   or *Ignore*. Most words are already suggested correctly; owncryptofolio recognizes the halves of a
   trade by the shared ID with opposite sign. If the file has no kind column (e.g. a plain list of deposits), you choose
   what all rows are.
5. **Preview**: every row as it would be booked; rows that cannot be read are listed
   with row number and reason. Only then **Import**.

owncryptofolio remembers the mapping for the next file of this source. The original file
and the mapping are kept together; an import can be reverted like any other.
Duplicate rows are recognized.

## Entering by hand

For exchanges that no longer provide anything (e.g. Gate.io or SafeTrade, which only reach back 180 days):
**Add exchange** → **Exchange without connection**, enter a name. You then enter the transactions
on the **Transactions** page, one by one or from a template; that is also where you edit,
correct and mark everything else. See [Transactions](transactions.md).

An exchange without connection can be deleted as soon as all its transactions are deleted.

## New networks (beta)

Since v1.7.2 there are **XRP Ledger, Tezos, Algorand, Tron, TON, Dogecoin and Bitcoin Cash**, since v1.7.3 also **NEAR, Cosmos Hub, Osmosis and Celestia**. They
are checked against public addresses (sum of the transactions = account balance), but not yet against
a wallet of our own — hence "beta". A few special points:

- **Tron** and **TON** work without a key, just more slowly (short pauses between
  requests). If you have many transactions, add a free key from TronGrid or toncenter
  under Settings → Blockchain services.
- **Staked TRX** (frozen or delegated) still counts toward your holdings.
- **Staking rewards** come in as income: baker payouts on Tezos, participation rewards
  on Algorand, voting rewards on Tron.
- **Bitcoin Cash** needs the address in CashAddr format (`bitcoincash:q…` or without prefix).
- Not read are, among others, NFTs, DEX trading on the XRP Ledger and your own Tezos staking —
  this is listed for every network under "Not read".

### NEAR and Cosmos

- **NEAR** (beta): NEAR and tokens (NEP-141). The holdings match the account balance down to the
  yoctoNEAR. **Staking** appears as "sent to the pool" and "received from the pool";
  the rewards come back with the withdrawal and are not shown separately as income.
  Tokens that write nothing to the log cannot be read — then the
  balance check shows the gap. For very large accounts (thousands of transactions) the
  first fetch takes a long time, because the properties of every token are requested; after that it is only
  about what is new.
- **Cosmos Hub, Osmosis and Celestia** (beta): transfers, IBC coins and staking rewards as
  income. Staking itself (delegating, unstaking) moves nothing: staked coins stay in
  your holdings. **Important limit:** the free public nodes only keep a few
  months of history. Older transactions are then missing; the balance check shows the gap, and you enter the
  older part by hand or by file. If a node breaks off while reading, however, the fetch fails
  with a message instead of leaving transactions out.

## When the source changes a booking

Sometimes an exchange corrects a booking afterwards, for example an amount. On the next
fetch the same booking (same transaction ID and time) arrives with different values. owncryptofolio
then does **not** insert it a second time, but shows the card
**"n rows changed by the source"** at the top of this page — with the previous and the new values:

- **Take the new values**: the new booking replaces the old one. The old one stays stored and
  appears in the row's history.
- **Keep the current ones**: everything stays as it was. The same change is not shown to you again.

In Statistics, the account health counts such cases under "Changed by the source".
Bookings without a transaction ID (e.g. Bitget and MEXC files) cannot be
recognized again this way.

## Reverting an import

Under **Fetching and import → Imports** every fetch and every file is listed with date, count and period. The
**latest** import of a source has the **Revert** button. After a
confirmation, exactly the transactions of this import are removed, nothing else.

A source can only be deleted once all its imports have been reverted.

## What you see afterwards

Under **Transactions** you find all transactions that were read in. A transfer from the exchange to
your wallet appears there as **one** row, see
[Merging transactions](../concepts/merging-transactions.md).

## Balance check

With every fetch, owncryptofolio also requests the **current account balance** and compares it
with the holdings that result from your transactions. Every card shows the result:

- **Balance matches**: everything fits (tolerance 0.1%; for euro, dollar and dollar coins like
  USDT up to 5 cents, because exchanges only show cents).
- **n differences**: for n coins it does not fit. Expanded, a table shows coin,
  computed, account balance and difference.
- **not checked**: no account balance known yet, or this coin could not be requested
  (for wallets only tokens that appear in your transactions are requested).

Money that the app assumes as a deposit for a card purchase is included in the check.
For MEXC and Bitget the **futures account** is requested as well.

A difference almost always means: **transactions are missing**, for example an older period
without a file, a deposit in euros or income that the source does not report as a transaction
(VTHO is created on VeChain simply by holding VET). A negative computed
balance shows: more was sold or sent here than ever arrived. Where exactly is
shown in [Holdings → Gaps](portfolio.md#gaps).

For **exchanges without connection** (Gate.io, SafeTrade) you enter the account balance per coin below
the check yourself.

## Related pages

- [Integrations](../concepts/integrations.md): what a source can and cannot do
- [Backup](backup.md): before you read in a lot of data
