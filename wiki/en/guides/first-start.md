---
title: First start and setup
updated: 2026-10-25
---

# First start and setup

On the very first start, owncryptofolio sets itself up: it creates the database, prepares it
and generates its keys. You do not have to type anything in a terminal for this.
After that, a wizard guides you through the rest in four steps.

## What you need

- Only in one special case (see step 1): access to the container's **log**:
  `docker logs owncryptofolio` or the log view of your Docker interface
  (on Unraid: [Install on Unraid](install-unraid.md)).
- A place for the **recovery key**, separate from the server, e.g. your password manager.

## New server, old data?

If you already have a backup (e.g. after moving to a new server), choose **“Restore from a
backup instead”** — see
[Backup → At first start](backup.md#at-first-start-new-server). The steps below are then not
needed.

## Step 1 of 4: Welcome or setup code

Open owncryptofolio in the browser. Instead of the sign-in, you see the wizard.

**Brand-new installation:** you see “Welcome” and tap **Set up anew** (or “Restore from a
backup instead”). No code is needed: there is nothing on the server yet that anyone else
could see.

**There are already keys on the server** — for example because the database was set up
again but the data in the container's data folder is still there. Then the wizard asks for
the **setup code**. It protects your recovery key and your backups: without it, someone else
on your network could complete the setup and be shown the key. You find the code in the
container's log (`docker logs owncryptofolio` or the log view of your Docker interface), in a
line like:

```
First start: open the web UI and enter the setup code  233-010
```

Enter it and tap **Next**. You do not need to write it down: it is only valid until setup is
finished, and every restart before that generates a new one. If it is wrong, you see
*“The setup code is wrong.”* below it — take the one from the **latest** line. Every
wrong attempt waits a moment, from the tenth on much longer, and attempts are taken one at a
time — trying codes at random does not pay off.

## Step 2 of 4: Choose a password

Choose a password with at least 10 characters and enter it twice. You will use it to sign in
from now on. There is no username — owncryptofolio has exactly one user: you.

## Step 3 of 4: Save your recovery key

**This is the only step where you really have to keep something.**

The key encrypts your backups. If your server is lost, this one key gets everything back from
a backup — including the exchange credentials. Without it, the backup is worthless.

- **Copy** or **Download** it and store it in your password manager.
- Tick *“I have stored the key apart from the server.”*, then **Next**.

You can find the key again at any time under *Settings → Backup → Show key*.

## Step 4 of 4: Basic settings

Language, style (the same choice as under *Settings → Appearance*), theme (System, Light, Dark) and display currency.
Every choice takes effect immediately. Everything can be changed later under *Settings*.
**Done** takes you to the dashboard.

## Afterwards

- Setup runs only once. On every later start you see the sign-in.
- Change your password: *Settings → Security*.
- Whether everything is running: *System status* (on the phone under *More*).

How owncryptofolio stores your data is described under
[How your data is stored](../concepts/how-data-is-stored.md).
