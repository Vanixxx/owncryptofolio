---
title: Troubleshooting
updated: 2026-10-25
---

# Troubleshooting

The first place to look is [System status](system-health.md): it shows the database,
fetches, backups and the log. The most common cases:

## The page is not reachable

- Is the container running? `docker ps`, or your system's Docker tab.
- Are the address and port right (`http://<computer>:<port>`)?
- After an update, the start takes about a minute.

## “No connection to the database”

owncryptofolio is running but cannot reach PostgreSQL. Start the database server or
container; the page keeps trying on its own and then opens. If it stays that way: check the
database host, port, user and password in the container settings.

## Forgot your password

In the server's terminal:

```
docker exec -it owncryptofolio python -m app.modules.auth reset-password
```

Enter the new password twice (at least 10 characters), then sign in with it. Every
existing sign-in ends with it; you sign in again on each device. Anyone who may
run commands in the container controls the server anyway — the web interface itself
deliberately offers no way around the password.

## Looking for the setup code

Only needed if there are already keys in the data folder. It is in the log:
`docker logs owncryptofolio`. Every restart generates a new one — take the latest
([First start](first-start.md)). After a wrong code the answer takes a moment on
purpose, after ten failed attempts longer.

## A fetch fails

- **Key rejected**: exchanges often let API keys without an IP restriction expire after
  90 days. Create a new key and enter it under [Sources](sources.md).
- **Timeout**: some free explorers are slow at times; the next run catches up.
- At the top of the Sources page you see which source is affected and since when.

## The balance differs

The [balance check](sources.md#balance-check) compares what owncryptofolio calculates with
what the exchange or network reports. Common causes: a missing period (load another file), a
movement that was not read (e.g. DEX trading, staking — shown with the network under
“Not read”), and for Cosmos networks a history older than what the nodes keep. You add
what is missing [by hand](sources.md#entering-by-hand).

## A coin has no price

In [Statistics](statistics.md), tap **Coins without price**: the coin opens on the
[Prices](prices.md) page. There, choose another source, mark it as worthless, or end its
prices (for a coin that was converted).

## An exchange changed an entry

It appears at the top of the Sources page as **Changed by the source** — you decide whether
the new values apply ([Sources](sources.md#when-the-source-changes-a-booking)).

## Anything else unclear?

The log in [System status](system-health.md#log) shows what happened most recently —
addresses and keys in it are shortened.
