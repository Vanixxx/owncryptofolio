---
title: Backup
updated: 2026-10-25
---

# Backup

## In one sentence

owncryptofolio backs itself up every night, checks every backup with a test restore, and you
make sure the backup folder is also kept **outside the server**.

## What is backed up

Each backup consists of three encrypted files in the backup folder:

| File | Contents |
|---|---|
| `….dump.enc` | the complete database: transactions, corrections, notes, settings, prices, tax reports, exchange credentials, your password (as a check value) |
| `….keys.enc` | the two internal keys for exchange credentials and sign-in — so that the **recovery key alone** brings everything back |
| `….raw.jsonl.gz.enc` | all imported movements in a simple text format, readable even without owncryptofolio |

Backups from before October 2026 do not have a `….keys.enc` yet: if they come from the same
installation, the exchange credentials stay readable; otherwise you enter them again after
restoring.

On top of that come the **original files** of every file import, which owncryptofolio keeps
unchanged.

In the container, the backups are in the mounted backup folder (`/backups`), the keys and
original files in the data folder (`/data`) — so on the computer they are in the two folders
you gave during setup. **Back up both folders.** If no folder is mounted at `/backups`, the
**Backup** card warns you: the backups would then live inside the container itself and be gone
with the next update.

## Settings

<p>
  <img src="../../bilder/en/details/einst-sicherung.png" alt="Backup in the settings" width="640">
</p>

Under **Settings → Backup**:

- **Back up automatically**: yes or no, with a **Time**. The default is 03:00.
- **Daily backups to keep** (default 14) and **Monthly backups to keep**
  (default 12). owncryptofolio deletes older backups itself, but only its own files.
- **Back up now** starts a backup immediately.

If the server was off at the set time, owncryptofolio makes up for the backup at the next
start.

Under **Recent backups** you see each backup with **“Test restore passed”**: the backup was
restored as a test into a throwaway database and compared with the original. If it says
something else, that backup cannot be used. You can also see the status at a glance under
[System status → Operations](system-health.md).

## The two things no software can do for you

1. **A copy outside the server.** A backup on the same disk protects against operating
   mistakes, not against hardware failure. Back up the folder shown as well, e.g. with your
   NAS backup, a backup program or a cloud sync.
2. **Keep the recovery key separately.** You got it during setup. It is also under
   *Settings → Backup → Show key*. With it alone you get everything back; without it no
   backup can be opened.

## Restoring

### In the interface

*Settings → Backup → Restore → Restore a backup …*

1. Choose a backup **From the backup folder** or **Upload a file** (the `….dump.enc`, and if
   present the `….keys.enc` with the same name), e.g. from another device.
2. If it comes from another installation, enter its **recovery key**; otherwise leave the
   field empty.
3. **Check backup**: owncryptofolio shows what is in it — number of transactions, sources,
   period, whether the exchange credentials come along. Nothing changes yet.
4. **The warning**: all current data is replaced by the backup, including your password.
   Beforehand, owncryptofolio **automatically makes a backup of the current state** — that is
   your only way back. Tick the box, **Restore now**.
5. After a few minutes you sign in again with the **password from the backup**.

The backup is first restored into a copy of its own; only when that works does it take the
place of the running database. If it fails, everything stays as it was. Only tables and data
are taken over, nothing else a foreign file might contain.

The backup of the state before is then in the list (“before restore”) and is never deleted
automatically. If you restored a backup **with its own recovery key**, that key applies to the
installation afterwards — the “before restore” backup is then encrypted with it too, no longer
with the old one.

### At first start (new server)

On the setup page, enter the setup code and choose **“Restore from a backup instead”**.
Then as above: choose a backup (the backup folder is mounted in the container) or upload one,
enter the recovery key, check, confirm. Then sign in with the old password — everything is
back.

### Emergency: command line

If the interface does not run at all, you can also do it in the server's terminal:

```
docker exec -it owncryptofolio python -m app.modules.backup restore /backups/<datei>.dump.enc --database owncryptofolio_restore
```

This restores the backup into a **new** database. The running one is never overwritten.
This way only opens backups encrypted with this installation's key.
Only afterwards do you decide whether to switch to the restored one.

## Related pages

- [First start and setup](first-start.md): where the recovery key comes from
- [Setting up and importing sources](sources.md)
- [Installing with Docker](install-docker.md) · [on Unraid](install-unraid.md)
- [System status](system-health.md)
