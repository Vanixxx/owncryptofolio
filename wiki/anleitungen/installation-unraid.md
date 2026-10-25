---
titel: Installation und Update auf Unraid
aktualisiert: 2026-10-25
---

# Installation und Update auf Unraid

owncryptofolio läuft als **ein Container** im Docker-Reiter von Unraid. Dazu kommt eine
**PostgreSQL-Datenbank**, am einfachsten als eigener Container.

## 1. Datenbank (falls noch keine da ist)

Unter **Apps** (Community Applications) nach **postgresql18** suchen und installieren. Dabei ein
langes Passwort für `POSTGRES_PASSWORD` vergeben und Port **5432** lassen. Autostart einschalten.

Eine vorhandene PostgreSQL bis Version 18 geht genauso. owncryptofolio legt seine Datenbank beim
ersten Start selbst an.

## 2. owncryptofolio anlegen

**Über Apps:** nach **owncryptofolio** suchen und **Installieren**.

**Solange es dort noch nicht steht:** die Vorlage einmal von Hand holen. Im Unraid-Terminal
(oben rechts das `>_`-Symbol):

```
wget -O /boot/config/plugins/dockerMan/templates-user/my-owncryptofolio.xml \
  https://raw.githubusercontent.com/Vanixxx/owncryptofolio/main/src/deploy/unraid/template.xml
```

Dann **Docker-Reiter → Container hinzufügen → Vorlage „owncryptofolio“**.

In beiden Fällen füllst du aus:

| Feld | Was hinein gehört |
|---|---|
| Port der Oberfläche | `8085` oder ein anderer freier Port |
| Daten | `/mnt/user/appdata/owncryptofolio`: enthält die **Schlüssel**, mit sichern! |
| Sicherungen | ein Ordner für die verschlüsselten Sicherungen, am besten auf einer Freigabe, die du außer Haus sicherst |
| Datenbank: Host | die IP deines Unraid-Servers (bei einem PostgreSQL-Container im Modus *bridge*) |
| Datenbank: Port / Name / Benutzer | `5432` / `owncryptofolio` / `postgres` |
| Datenbank: Passwort | das Passwort der Datenbank (wird verdeckt angezeigt) |

**Anwenden.** Nach etwa einer Minute ist owncryptofolio unter `http://<unraid-ip>:8085`
erreichbar. Weiter geht es mit dem [ersten Start](erster-start.md). Falls nötig zeigt das
Protokoll den Einrichtungscode (Docker-Reiter → auf das owncryptofolio-Symbol klicken → *Logs*).

## Update auf eine neue Version

Unraid prüft selbst, ob es ein neues Abbild gibt. Im Docker-Reiter steht dann bei owncryptofolio
**„update ready“**: daraufklicken → **Update**. Von Hand anstoßen: unten **Check for Updates**.
Daten, Schlüssel und Sicherungen bleiben, wo sie sind.

Die Datenbank wird beim Start automatisch auf den neuen Stand gebracht. Welche Version läuft,
steht unter **Systemzustand**. Was neu ist: [Was ist neu](../was-ist-neu.md).

## Gut zu wissen

- **Sichere den Ordner `appdata/owncryptofolio` mit.** Die Schlüssel darin brauchst du, um
  Sicherungen und gespeicherte API-Zugänge zu lesen.
- Der Docker-Reiter zeigt bei owncryptofolio „healthy“, solange die Datenbank erreichbar ist.
- **Autostart** für den PostgreSQL-Container und für owncryptofolio einschalten (Docker-Reiter),
  dann kommt nach einem Stromausfall alles von selbst wieder.
- **Startet owncryptofolio vor der Datenbank**, zeigt die Seite „Keine Verbindung zur
  Datenbank“ und versucht es alle paar Sekunden neu. Sobald die Datenbank da ist, öffnet sie
  sich von selbst, und Abrufe, Kurse und Sicherung laufen wieder. Dasselbe gilt, wenn die
  Datenbank im laufenden Betrieb wegfällt.
- Ein zweites owncryptofolio auf derselben Datenbank darf nicht laufen: Abrufe und
  Sicherungen würden doppelt angestoßen.
- Alle Einstellungen des Containers erklärt [Installation mit Docker](installation-docker.md#die-einstellungen-des-containers).
