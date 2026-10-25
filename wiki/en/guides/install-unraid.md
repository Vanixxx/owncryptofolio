---
title: Installing and updating on Unraid
updated: 2026-10-25
---

# Installing and updating on Unraid

owncryptofolio runs as **one container** in Unraid's Docker tab. It also needs a **PostgreSQL
database**, most simply as a container of its own.

## 1. Database (if you have none yet)

Under **Apps** (Community Applications), search for **postgresql18** and install it. Give
`POSTGRES_PASSWORD` a long password and keep port **5432**. Turn on autostart.

An existing PostgreSQL up to version 18 works just as well. owncryptofolio creates its database
itself on the first start.

## 2. Add owncryptofolio

**Through Apps:** search for **owncryptofolio** and click **Install**.

**As long as it is not listed there yet:** fetch the template once by hand. In the Unraid
terminal (the `>_` symbol at the top right):

```
wget -O /boot/config/plugins/dockerMan/templates-user/my-owncryptofolio.xml \
  https://raw.githubusercontent.com/Vanixxx/owncryptofolio/main/src/deploy/unraid/template.xml
```

Then **Docker tab → Add Container → template “owncryptofolio”**.

Either way, you fill in:

| Field | What goes in |
|---|---|
| Web UI port | `8085` or another free port |
| Data | `/mnt/user/appdata/owncryptofolio`: holds the **keys**, back it up! |
| Backups | a folder for the encrypted backups, ideally on a share you back up off the server |
| Database: host | the IP of your Unraid server (for a PostgreSQL container in *bridge* mode) |
| Database: port / name / user | `5432` / `owncryptofolio` / `postgres` |
| Database: password | the database password (shown masked) |

**Apply.** After about a minute owncryptofolio is reachable at `http://<unraid-ip>:8085`.
Continue with the [first start](first-start.md). If needed, the log shows the setup code
(Docker tab → click the owncryptofolio icon → *Logs*).

## Updating to a new version

Unraid checks for a new image on its own. The Docker tab then shows **“update ready”** for
owncryptofolio: click it → **Update**. To check by hand, use **Check for Updates** at the
bottom. Data, keys and backups stay where they are.

The database is brought up to date automatically at start. Which version is running is shown
under **System status**. What is new: [What's new](../whats-new.md).

## Good to know

- **Back up the `appdata/owncryptofolio` folder too.** You need the keys in it to read backups
  and stored API credentials.
- The Docker tab shows owncryptofolio as “healthy” as long as the database is reachable.
- Turn on **Autostart** for the PostgreSQL container and for owncryptofolio (Docker tab).
  Then everything comes back on its own after a power cut.
- **If owncryptofolio starts before the database**, the page shows “No connection to the
  database” and tries again every few seconds. As soon as the database is there, it opens on
  its own, and fetches, prices and backups run again. The same happens if the database goes
  away while running.
- A second owncryptofolio must not run on the same database: fetches and backups would be
  triggered twice.
- Every container setting is explained in [Installing with Docker](install-docker.md#the-containers-settings).
