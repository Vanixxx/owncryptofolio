---
title: Installing with Docker
updated: 2026-10-25
---

# Installing with Docker

owncryptofolio is **one container**. It needs a **PostgreSQL** database (its own container or
an existing server) and two folders on the computer: one for the data (keys, original files,
logs) and one for the backups. It runs anywhere Docker runs: NAS, home server, 64-bit
Raspberry Pi, PC.

For Unraid there is a separate guide with a template: [Installing on Unraid](install-unraid.md).

## With Docker Compose (database included)

Create a file `docker-compose.yml`:

```yaml
services:
  db:
    image: postgres:17
    environment:
      POSTGRES_PASSWORD: ein-langes-passwort
    volumes:
      - ./postgres:/var/lib/postgresql/data
    restart: unless-stopped

  owncryptofolio:
    image: ghcr.io/vanixxx/owncryptofolio:latest
    ports:
      - "8085:8080"                   # left: port on your home network, your choice
    environment:
      DB_HOST: db
      DB_PORT: "5432"
      DB_NAME: owncryptofolio         # created on first start
      DB_USER: postgres
      DB_PASSWORD: ein-langes-passwort
      TZ: Europe/Berlin
    volumes:
      - ./data:/data                  # keys, originals, logs — back this up too!
      - ./backups:/backups            # encrypted backups
    depends_on:
      - db
    restart: unless-stopped
```

Then:

```
docker compose up -d
```

After about a minute owncryptofolio is reachable at `http://<computer>:8085`. Continue with
the [first start](first-start.md).

Instead of the individual `DB_…` settings, a single line works too:
`DATABASE_URL: postgresql+psycopg://benutzer:passwort@host:5432/owncryptofolio`.

## Without Compose: individual containers

The same with `docker run`. First a shared network, so the containers find each other by name:

```
docker network create owncryptofolio-net
```

**1. Database** (skip this if you already have a PostgreSQL server):

```
docker run -d --name owncryptofolio-db --network owncryptofolio-net \
  -e POSTGRES_PASSWORD=ein-langes-passwort \
  -v "$PWD/postgres:/var/lib/postgresql/data" \
  --restart unless-stopped postgres:17
```

**2. owncryptofolio:**

```
docker run -d --name owncryptofolio --network owncryptofolio-net \
  -p 8085:8080 \
  -e DB_HOST=owncryptofolio-db -e DB_PORT=5432 -e DB_NAME=owncryptofolio \
  -e DB_USER=postgres -e DB_PASSWORD=ein-langes-passwort \
  -e TZ=Europe/Berlin \
  -v "$PWD/data:/data" -v "$PWD/backups:/backups" \
  --restart unless-stopped ghcr.io/vanixxx/owncryptofolio:latest
```

If the database is on another computer, leave out `--network`; `DB_HOST` then holds that
computer's address.

**Update:** `docker pull ghcr.io/vanixxx/owncryptofolio:latest`, then `docker rm -f
owncryptofolio` and run the `docker run` command from above again. Data, keys and backups live in the folders and stay.

## The container's settings

Everything else you set in the interface. At start, the container only needs these:

| Variable | Required | Default | Meaning |
|---|---|---|---|
| `DB_HOST` | yes¹ | — | host of the database (name or IP) |
| `DB_USER` | yes¹ | — | database user |
| `DB_PASSWORD` | usually | — | the user's password |
| `DB_PORT` | no | `5432` | database port |
| `DB_NAME` | no | `owncryptofolio` | database name; if it does not exist, it is created on first start |
| `DATABASE_URL` | yes¹ | — | one line instead of the five settings above: `postgresql+psycopg://benutzer:passwort@host:5432/owncryptofolio`; takes precedence |
| `BACKUP_DIR` | no | `/backups` | fixed in the image — do not change it; mount a folder at `/backups` instead |
| `TZ` | no | UTC | the container's time zone (timestamps in the log); the interface's time zone is set in the settings |
| `DB_WAIT_SECONDS` | no | `60` | how long the start waits for a database that is not ready yet |
| `CREDENTIALS_KEY`, `SESSION_KEY`, `BACKUP_KEY` | no | generated | your own keys instead of the ones generated on first start (advanced users only; otherwise they live in the data folder) |

¹ Either `DB_HOST` and `DB_USER` (plus password) **or** `DATABASE_URL`. If both are missing,
the start stops with a clear message in the log.

**Tip – a database user of its own:** for simplicity the examples use `postgres`, the database
administrator. Safer is a user just for owncryptofolio that may create databases but is no
administrator – then even a tampered backup file can do nothing outside its own database:
`CREATE ROLE owncryptofolio LOGIN CREATEDB PASSWORD 'a-long-password';` and enter it as `DB_USER`
(owncryptofolio then creates the database itself).

**Folders:**

| In the container | Contents | Important |
|---|---|---|
| `/data` | keys, original files of imports, exchange icons, logs | **mounting it is required**, and back it up too — without the keys, stored API credentials cannot be read |
| `/backups` | encrypted backups | **mounting it is required**: otherwise the backups live inside the container and are lost at the next update (the app then warns under Settings → Backup); also keep a copy off-site |

**Port:** `8080` inside; on the left of `-p` or `ports` you choose the port under which you
reach the interface.

## The image

The ready-made image is on GitHub: `ghcr.io/vanixxx/owncryptofolio`, for amd64 (PC, NAS) and
arm64 (64-bit Raspberry Pi). `:latest` is always the newest version; a fixed version is
available under its number, e.g. `:1.8.0.0`. Which versions exist and what changed is listed
under [Releases](https://github.com/Vanixxx/owncryptofolio/releases).

Prefer to build it yourself? In the downloaded source code:

```
docker build -f src/Dockerfile -t owncryptofolio:latest .
```

## Update

1. `docker compose pull` — fetches the new image.
2. `docker compose up -d` — the container is recreated with the new image. Data, keys and
   backups stay in the folders.

The database is brought up to date automatically at start. Which version is running is shown
under **System status**.

## Good to know

- **Back up the data folder too** (`./data`). You need the keys in it for backups and stored
  API credentials. The app also shows you the recovery key.
- **Run it on your home network only.** If owncryptofolio should be reachable from outside,
  put a reverse proxy with HTTPS in front of it (e.g. Caddy, Traefik, Nginx Proxy Manager) —
  better still, a VPN.
- The container does not run as root and listens on port **8080** inside.
- **PostgreSQL up to version 18**: the backup tools in the image belong to version 18. If the
  database server is newer, System status reports them as too old, and no backup is made.
- The **setup code** (only needed if there are already keys in the data folder) is shown by
  `docker logs owncryptofolio`.
