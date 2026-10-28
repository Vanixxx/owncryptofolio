---
titel: Installation mit Docker
aktualisiert: 2026-10-28
---

# Installation mit Docker

owncryptofolio ist **ein Container**. Er braucht eine **PostgreSQL**-Datenbank (eigener
Container oder vorhandener Server) und zwei Ordner auf dem Rechner: einen für die Daten
(Schlüssel, Originaldateien, Protokolle) und einen für die Sicherungen. Es läuft überall, wo
Docker läuft: NAS, Heimserver, Raspberry Pi mit 64 Bit, PC.

Für Unraid gibt es eine eigene Anleitung mit Vorlage: [Installation auf Unraid](installation-unraid.md).

## Mit Docker Compose (Datenbank inklusive)

Eine Datei `docker-compose.yml` anlegen:

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
      - "8085:8080"                   # links: Port im Heimnetz, frei wählbar
    environment:
      DB_HOST: db
      DB_PORT: "5432"
      DB_NAME: owncryptofolio         # wird beim ersten Start angelegt
      DB_USER: postgres
      DB_PASSWORD: ein-langes-passwort
      TZ: Europe/Berlin
    volumes:
      - ./data:/data                  # Schlüssel, Originale, Protokolle — mit sichern!
      - ./backups:/backups            # verschlüsselte Sicherungen
    depends_on:
      - db
    restart: unless-stopped
```

Dann:

```
docker compose up -d
```

Nach etwa einer Minute ist owncryptofolio unter `http://<rechner>:8085` erreichbar. Weiter
geht es mit dem [ersten Start](erster-start.md).

Statt der einzelnen `DB_…`-Angaben geht auch eine Zeile
`DATABASE_URL: postgresql+psycopg://benutzer:passwort@host:5432/owncryptofolio`.

## Ohne Compose: einzelne Container

Dasselbe mit `docker run`. Zuerst ein gemeinsames Netz, damit sich die Container mit Namen finden:

```
docker network create owncryptofolio-net
```

**1. Datenbank** (entfällt, wenn du schon einen PostgreSQL-Server hast):

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

Liegt die Datenbank auf einem anderen Rechner, entfällt `--network`; bei `DB_HOST` steht dann
dessen Adresse.

**Update:** `docker pull ghcr.io/vanixxx/owncryptofolio:latest`, dann `docker rm -f
owncryptofolio` und den `docker run`-Befehl von oben noch einmal. Daten, Schlüssel und Sicherungen liegen in den Ordnern und bleiben.

## Die Einstellungen des Containers

Alles andere stellst du in der Oberfläche ein. Beim Start braucht der Container nur diese
Angaben:

| Variable | Pflicht | Standard | Bedeutung |
|---|---|---|---|
| `DB_HOST` | ja¹ | — | Rechner der Datenbank (Name oder IP) |
| `DB_USER` | ja¹ | — | Benutzer der Datenbank |
| `DB_PASSWORD` | meist | — | Passwort des Benutzers |
| `DB_PORT` | nein | `5432` | Port der Datenbank |
| `DB_NAME` | nein | `owncryptofolio` | Name der Datenbank; fehlt sie, wird sie beim ersten Start angelegt |
| `DATABASE_URL` | ja¹ | — | statt der fünf Angaben oben eine Zeile: `postgresql+psycopg://benutzer:passwort@host:5432/owncryptofolio`; geht vor |
| `BACKUP_DIR` | nein | `/backups` | im Abbild fest eingestellt — nicht ändern, sondern einen Ordner an `/backups` einbinden |
| `TZ` | nein | UTC | Zeitzone des Containers (Zeitstempel im Protokoll); die Zeitzone der Oberfläche stellst du in den Einstellungen ein |
| `PUID`, `PGID` | nein | `1000` | unter welchem Benutzer und welcher Gruppe die App läuft (auf Unraid üblich: `99` und `100`); die Ordner `/data` und `/backups` bekommt dieser Benutzer beim Start, wenn sie ihm noch nicht gehören |
| `DB_WAIT_SECONDS` | nein | `60` | so lange wartet der Start auf eine noch nicht bereite Datenbank |
| `CREDENTIALS_KEY`, `SESSION_KEY`, `BACKUP_KEY` | nein | erzeugt | eigene Schlüssel statt der beim ersten Start erzeugten (nur für Fortgeschrittene; sonst liegen sie im Datenordner) |

¹ Entweder `DB_HOST` und `DB_USER` (plus Passwort) **oder** `DATABASE_URL`. Fehlt beides, bricht
der Start mit einer klaren Meldung im Protokoll ab.

**Tipp – eigener Datenbank-Benutzer:** Die Beispiele nutzen der Einfachheit halber `postgres`, den
Verwalter der Datenbank. Sicherer ist ein eigener Benutzer nur für owncryptofolio, der Datenbanken
anlegen darf, aber kein Verwalter ist – dann kann auch eine manipulierte Sicherungsdatei nichts
außerhalb der eigenen Datenbank anrichten:
`CREATE ROLE owncryptofolio LOGIN CREATEDB PASSWORD 'ein-langes-passwort';` und ihn als `DB_USER`
eintragen (die Datenbank legt owncryptofolio dann selbst an).

**Ordner:**

| Im Container | Inhalt | Wichtig |
|---|---|---|
| `/data` | Schlüssel, Originaldateien der Importe, Börsen-Symbole, Protokolle | **einbinden ist Pflicht** und mit sichern — ohne die Schlüssel sind gespeicherte API-Zugänge nicht lesbar |
| `/backups` | verschlüsselte Sicherungen | **einbinden ist Pflicht**: sonst liegen die Sicherungen im Container und gehen beim nächsten Update verloren (die App warnt dann unter Einstellungen → Sicherung); zusätzlich außer Haus sichern |

**Port:** intern `8080`; links bei `-p` bzw. `ports` wählst du, unter welchem Port du die
Oberfläche erreichst.

## Das Abbild

Das fertige Abbild liegt auf GitHub: `ghcr.io/vanixxx/owncryptofolio`, für amd64 (PC, NAS)
und arm64 (Raspberry Pi mit 64 Bit). `:latest` ist immer die neueste Version; eine feste Version
gibt es unter ihrer Nummer, etwa `:1.8.0.0`. Welche Versionen es gibt und was sich geändert hat,
steht unter [Releases](https://github.com/Vanixxx/owncryptofolio/releases).

Lieber selbst bauen? Im heruntergeladenen Quellcode:

```
docker build -f src/Dockerfile -t owncryptofolio:latest .
```

## Update

1. `docker compose pull` — holt das neue Abbild.
2. `docker compose up -d` — der Container wird mit dem neuen Abbild neu angelegt. Daten,
   Schlüssel und Sicherungen bleiben in den Ordnern.

Die Datenbank wird beim Start automatisch auf den neuen Stand gebracht. Welche Version läuft,
steht unter **Systemzustand**.

## Gut zu wissen

- **Sichere den Datenordner mit** (`./data`). Die Schlüssel darin brauchst du für Sicherungen
  und gespeicherte API-Zugänge. Den Wiederherstellungsschlüssel zeigt die App zusätzlich an.
- **Nur im Heimnetz betreiben.** Soll owncryptofolio von außen erreichbar sein, gehört ein
  Reverse Proxy mit HTTPS davor (z. B. Caddy, Traefik, Nginx Proxy Manager) — besser noch ein
  VPN.
- Die App läuft nicht als root (Benutzer `PUID`, Standard 1000) und hört intern auf Port **8080**.
  Nur der allererste Schritt beim Start läuft als root: Er übergibt die eingebundenen Ordner an
  diesen Benutzer.
- **PostgreSQL bis Version 18**: Die Sicherungs-Werkzeuge im Abbild gehören zu Version 18. Ist
  der Datenbank-Server neuer, meldet der Systemzustand sie als zu alt, und es entsteht keine
  Sicherung.
- Den **Einrichtungscode** (nur nötig, wenn im Datenordner schon Schlüssel liegen) zeigt
  `docker logs owncryptofolio`.
