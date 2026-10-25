---
titel: Erster Start und Einrichtung
aktualisiert: 2026-10-25
---

# Erster Start und Einrichtung

Beim allerersten Start richtet sich owncryptofolio selbst ein: Es legt die Datenbank an,
bereitet sie vor und erzeugt seine Schlüssel. Du musst dafür nichts im Terminal tippen.
Danach führt dich ein Assistent in vier Schritten durch den Rest.

## Was du brauchst

- Nur in einem Sonderfall (siehe Schritt 1) Zugriff auf das **Protokoll (Log)** des
  Containers: `docker logs owncryptofolio` oder die Log-Ansicht deiner Docker-Oberfläche
  (auf Unraid: [Installation auf Unraid](installation-unraid.md)).
- Einen Ort für den **Wiederherstellungsschlüssel**, getrennt vom Server, z. B. deinen
  Passwort-Manager.

## Neuer Server, alte Daten?

Hast du schon eine Sicherung (z. B. nach einem Serverwechsel), wähle **„Stattdessen aus einer Sicherung wiederherstellen“** — siehe
[Sicherung → Beim ersten Start](sicherung.md#beim-ersten-start-neuer-server). Die Schritte
unten entfallen dann.

## Schritt 1 von 4: Willkommen oder Einrichtungscode

Öffne owncryptofolio im Browser. Statt der Anmeldung siehst du den Assistenten.

**Ganz neue Installation:** Du siehst „Willkommen“ und tippst **Neu einrichten** (oder
„Stattdessen aus einer Sicherung wiederherstellen“). Ein Code ist nicht nötig: Auf dem Server
liegt noch nichts, was jemand anderes sehen könnte.

**Auf dem Server liegen schon Schlüssel** — etwa weil die Datenbank neu aufgesetzt wurde, die
Daten im Datenordner des Containers aber noch da sind. Dann fragt der Assistent nach dem
**Einrichtungscode**. Er schützt deinen Wiederherstellungsschlüssel und deine Sicherungen:
Ohne ihn könnte jemand anderes in deinem Netz die Einrichtung abschließen und den Schlüssel
angezeigt bekommen. Den Code findest du im Protokoll des Containers (`docker logs owncryptofolio`
oder die Log-Ansicht deiner Docker-Oberfläche), in einer Zeile wie:

```
First start: open the web UI and enter the setup code  233-010
```

Gib ihn ein und tippe **Weiter**. Aufschreiben musst du ihn nicht: Er gilt nur, bis die
Einrichtung fertig ist, und jeder Neustart davor erzeugt einen neuen. Stimmt er nicht, steht
*„Der Einrichtungscode stimmt nicht."* darunter — nimm den aus der **jüngsten** Zeile. Jeder
Fehlversuch wartet einen Moment, ab dem zehnten deutlich länger, und Versuche kommen nur
nacheinander dran — Durchprobieren lohnt sich so nicht.

## Schritt 2 von 4: Passwort festlegen

Wähle ein Passwort mit mindestens 10 Zeichen und gib es zweimal ein. Damit meldest du dich
künftig an. Es gibt keinen Benutzernamen — owncryptofolio hat genau einen Nutzer: dich.

## Schritt 3 von 4: Wiederherstellungsschlüssel sichern

**Das ist der einzige Schritt, bei dem du wirklich etwas aufbewahren musst.**

Der Schlüssel verschlüsselt deine Sicherungen. Geht dein Server verloren, holst du mit
diesem einen Schlüssel alles aus einer Sicherung zurück — auch die Börsen-Zugänge. Ohne ihn
ist sie wertlos.

- **Kopieren** oder **Herunterladen** und im Passwort-Manager ablegen.
- Den Haken *„Ich habe den Schlüssel getrennt vom Server aufbewahrt."* setzen, dann
  **Weiter**.

Du findest den Schlüssel später jederzeit wieder unter *Einstellungen → Sicherung →
Schlüssel anzeigen*.

## Schritt 4 von 4: Grundeinstellungen

Sprache, Stil (dieselbe Auswahl wie unter *Einstellungen → Darstellung*), Thema (System, Hell, Dunkel) und Anzeigewährung.
Jede Wahl wirkt sofort. Alles lässt sich später unter *Einstellungen* ändern. Mit
**Fertig** landest du im Dashboard.

## Danach

- Die Einrichtung läuft nur einmal. Bei jedem weiteren Start siehst du die Anmeldung.
- Passwort ändern: *Einstellungen → Sicherheit*.
- Ob alles läuft: *Systemzustand* (am Handy unter *Mehr*).

Wie owncryptofolio deine Daten ablegt, steht unter
[Wie deine Daten abgelegt werden](../konzepte/daten-in-owncryptofolio.md).
