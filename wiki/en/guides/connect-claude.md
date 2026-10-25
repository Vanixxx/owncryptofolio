---
title: Connect Claude
updated: 2026-10-25
---

# Connect Claude

owncryptofolio can let **Claude Code** and **Claude Desktop** read your data — through MCP,
an interface for AI assistants. Then you can ask Claude: “How much BTC do I have, and
where?”, “Which withdrawals have no counterpart?”, “What becomes tax-free by Christmas?”,
“Where does the money of the withdrawal on 3 March come from?”.

Claude gets a **token**, and every token has its **level**: **Read only**, or **Edit** — then
Claude may also make changes, but only after your OK to a complete list (see below). One
switch turns Claude on or off for all tokens.

## What Claude sees

Holdings and value per coin, sources and their fetch, balance check, transactions (search by
period, coin, source, type, text), transfers without a counterpart, prices, tax year, loss
carryforward, what will soon become tax-free, source of funds, system status and the latest
log lines.

**Not** included: API keys and passwords, the backup key, the name, address and tax
number from the head of the reports. **Addresses** are shortened (`0x5290…9EE7`). At most 200 rows per
question. Every call is recorded in the [log](system-health.md#log).

## Setting up

1. **Settings → Claude (MCP)**: **Enable Claude access**.
2. Enter a name, e.g. “Claude Code laptop”, choose the **Level** (Read only or Edit) and
   **Create token**. The token is shown **only once** — copy it right away.
   One token per device; the level can be changed per token later, and each can be revoked
   on its own.
3. Expand **Connect Claude** and copy the matching command (token and address are already
   filled in):
   - **Claude Code**: run the command `claude mcp add --transport http owncryptofolio …` in
     the terminal. Then in Claude Code, `/mcp` — owncryptofolio is listed as connected.
   - **Claude Desktop**: add the JSON block to `claude_desktop_config.json` (Claude
     Desktop → Settings → Developer → Edit Config), restart Claude Desktop. Needs
     **Node.js** on the PC (for the small bridge `mcp-remote`).

## Edit: Claude changes, you confirm

Set a token's level to **Edit**. With this token Claude can, for example:

- **link** withdrawals and deposits **as a transfer** (or unlink them again),
- set **notes**, **mark** outgoing/incoming movements (to others, own wallet, income …),
- hide **spam**, **hide** movements or **bring them back**,
- create **manual entries** and **correct** movements (the original stays stored),
- **start a fetch**.

This is how it works: you write, for example, “Link all open transfers that clearly match.”
Claude creates a **plan** — owncryptofolio checks every entry and returns the **complete
list**: what changes, what is skipped (with the reason), and for entries and corrections also
how the holdings per coin change. Claude shows you the list. **Only when you say OK** does
Claude carry out the plan — exactly this list, once.
You can also confirm just a part: “Do 1–14, leave out 44.” Then Claude carries out only those
numbers. Going beyond what was on the list is never possible; anything else needs a new plan.

- **Nothing is deleted.** Corrections are new versions; the original can be brought back.
- Everything changed through MCP is under **Transactions → Notice → “Changed through
  MCP”**; every change is also in the log.
- Up to 50 entries per plan. A plan waits 30 minutes for your OK; after that it takes a new
  one. Look at the list — and there is the daily backup.

## The API for other programs

The same data is also available as simple web addresses for a widget, Home Assistant or a
spreadsheet — with **their own** tokens and their own switch, read only. See
[API (JSON)](api.md).

## Where it works

Only on the **home network**. On the go, through a **VPN** to your home (e.g. WireGuard or
the router's VPN feature): once connected, it is like being at home. owncryptofolio is not reachable from the internet — and
it stays that way until public access is explicitly set up.

If the address or port of owncryptofolio changes, copy the commands from the settings again.

## Turning it off

- **Claude access off** — immediately Claude cannot get in with any token; the tokens remain.
- **Set a token's level to “Read only”** — with this token Claude can no longer change
  anything.
- **Revoke** — this one token is no longer valid.

**System status** shows whether Claude is connected and when it last asked.

## Related pages

- [API (JSON)](api.md) — the same data for other programs
- [System status](system-health.md) — log, including the Claude calls
- [Source of funds](source-of-funds.md)
- [Tax report](tax-report.md)
