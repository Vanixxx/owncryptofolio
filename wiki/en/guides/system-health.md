---
title: System status
updated: 2026-10-25
---

# System status

The **System status** page (on the phone under **More**) answers one question: **Is everything
running?** If something is not right, the row turns yellow.

## Database

<p>
  <img src="../../bilder/en/details/system-datenbank.png" alt="Database" width="346">
</p>

- **Database**: *connected* when owncryptofolio reaches the database.
- **Server**: the PostgreSQL version.
- **Schema**: *up to date* when the database matches the program version. After an update,
  the start brings it up to date on its own.

## owncryptofolio

<p>
  <img src="../../bilder/en/details/system-app.png" alt="owncryptofolio" width="346">
</p>

- **Version** and **Running for**.
- **Claude and API**: whether Claude and the API are on or off, how many tokens there are, and
  the last call — see [Connect Claude](connect-claude.md) and [API](api.md).
- **Data directory**: where keys, imported original files and logs are kept.
- **Keys**: whether the three keys (Credentials, Session, Backup) come from a file or from
  the environment.

## Operations

<p>
  <img src="../../bilder/en/details/system-betrieb.png" alt="Operations" width="640">
</p>

What should run on its own, and when it last ran:

| Row | What it says | When it is yellow |
|---|---|---|
| **Last backup** | time, below it the next scheduled one | The backup or its test restore failed. The reason is shown below; see [Backup](backup.md). |
| **Last fetch** | the last fetch of all sources, the next round | With *n failed*, at least one source did not work. Which one is shown on the Sources page and on the dashboard under Notes. Often it works on its own next time. |
| **Last price run** | the daily fetch of the daily prices | The price fetch failed. **Fetch prices** on the Prices page tries again. |
| **Current prices from** | when current prices were last fetched | – |
| **Backup tools** | whether the PostgreSQL tools are there and match the database | No backup can be made. In the container: rebuild (see [Installation](install-docker.md)). |
| **Disk database** | how big the database is | – |
| **Disk data / Disk backups** | what owncryptofolio uses there, below it the free space | Less than 5 % free. Make room, otherwise backups stop. |
| **owncryptofolio in total** | database, data and backups together | – |

You set the times under **Settings**: fetch (default 04:00), prices (04:30), backup (03:00).

**Fine values (hourly)**: fetches fine-grained prices per coin and recalculates the values for
the short periods on the dashboard — also right after a start, so that gaps from the time the
app was not running get filled.

## Background jobs

The latest fetches, price runs, fine prices and backups with source, time and result.
If there is an error, the message is shown below.

## Log

The card is **collapsed** at first; a click on *Log* opens it. Then you see what
owncryptofolio is doing right now, **live**: new lines are added every two seconds.
If you scroll up, the view stays put; at the very bottom it follows again.

- **Log level**: how much is written. *Info* is normal. *Debug* writes a lot — turn it on to
  hunt down an error, then set it back to *Info*. The setting applies immediately and is kept
  after a restart.
- **Show**: only hides lines in the view, e.g. *from warning*.
- **Origin**: *Backend* is the server, *Frontend* are errors and warnings from your browser
  (for instance when a page does not load).
- **Search**, **Live** (pause), **Clear view** and **As file** (saves the lines shown as text,
  e.g. to pass on).

The last 2,000 lines since the last start are shown. **Addresses are shortened, keys and
passwords hidden** — you can pass on a saved file. The container has the full history
(`docker logs`).

## Licenses

Whose free works owncryptofolio uses (icons, fonts, libraries) and under which license, plus
the note on trademarks: [Licenses and trademarks](../concepts/licenses.md).
