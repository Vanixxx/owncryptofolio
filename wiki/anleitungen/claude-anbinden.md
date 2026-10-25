---
titel: Claude anbinden
aktualisiert: 2026-10-25
---

# Claude anbinden

owncryptofolio kann **Claude Code** und **Claude Desktop** deine Daten lesen lassen — über
MCP, eine Schnittstelle für KI-Assistenten. Dann kannst du Claude fragen: „Wie viel BTC habe
ich wo?“, „Welche Auszahlungen haben keine Gegenseite?“, „Was wird bis Weihnachten
steuerfrei?“, „Woher kommt das Geld der Auszahlung vom 3. März?“.

Claude bekommt ein **Token**, und jedes Token hat seine **Stufe**: **Nur lesen**, oder
**Bearbeiten** — dann darf Claude auch ändern, aber nur nach deinem OK zu einer vollständigen
Liste (siehe unten). Ein Schalter schaltet Claude für alle Tokens ein oder aus.

## Was Claude sieht

Bestand und Wert je Coin, Quellen und ihr Abruf, Bestandsabgleich, Transaktionen (Suche nach
Zeitraum, Coin, Quelle, Art, Text), Transfers ohne Gegenseite, Kurse, Steuerjahr,
Verlustvortrag, was bald steuerfrei wird, Mittelherkunft, Systemzustand und die letzten
Protokollzeilen.

**Nicht** dabei: API-Schlüssel und Passwörter, der Sicherungsschlüssel, Name, Anschrift und
Steuernummer aus dem Kopf der Berichte. **Adressen** werden gekürzt (`0x5290…9EE7`). Je Frage höchstens
200 Zeilen. Jeder Aufruf steht im [Protokoll](systemzustand.md#protokoll).

## Einrichten

1. **Einstellungen → Claude (MCP)**: **Claude-Zugriff einschalten**.
2. Einen Namen eingeben, z. B. „Claude Code Laptop“, die **Stufe** wählen (Nur lesen oder
   Bearbeiten) und **Token anlegen**. Das Token erscheint **nur einmal** — gleich kopieren.
   Für jedes Gerät ein eigenes Token; die Stufe lässt sich später je Token umstellen, jedes
   einzeln widerrufen.
3. **Claude verbinden** aufklappen, den passenden Befehl kopieren (Token und Adresse sind
   schon eingetragen):
   - **Claude Code**: den Befehl `claude mcp add --transport http owncryptofolio …` im
     Terminal ausführen. Danach in Claude Code `/mcp` — owncryptofolio steht als verbunden da.
   - **Claude Desktop**: den JSON-Block in `claude_desktop_config.json` eintragen (Claude
     Desktop → Einstellungen → Entwickler → Konfiguration bearbeiten), Claude Desktop neu
     starten. Braucht **Node.js** auf dem PC (für die kleine Brücke `mcp-remote`).

## Bearbeiten: Claude ändert, du bestätigst

Stell bei einem Token die Stufe auf **Bearbeiten**. Mit diesem Token kann Claude zum Beispiel:

- Auszahlungen und Einzahlungen als **Transfer verbinden** (oder wieder trennen),
- **Notizen** setzen, Abgänge/Eingänge **markieren** (an Fremde, eigene Wallet, Ertrag …),
- **Spam** ausblenden, Vorgänge **ausblenden** oder **zurückholen**,
- **Handeinträge** anlegen und Vorgänge **korrigieren** (das Original bleibt gespeichert),
- einen **Abruf starten**.

So läuft es ab: Du schreibst z. B. „Verbinde alle offenen Transfers, die eindeutig
zusammenpassen.“ Claude erstellt einen **Plan** — owncryptofolio prüft jeden Eintrag und
liefert die **vollständige Liste**: was sich ändert, was übersprungen wird (mit Grund), bei
Einträgen und Korrekturen auch, wie sich der Bestand je Coin ändert. Claude zeigt dir die
Liste. **Erst wenn du OK sagst**, führt Claude den Plan aus — genau diese Liste, einmal.
Du kannst auch nur einen Teil bestätigen: „Setz 1–14 um, lass 44 aus.“ Dann führt Claude nur
diese Nummern aus. Mehr als in der Liste stand, geht nie; für anderes braucht es einen neuen Plan.

- **Gelöscht wird nichts.** Korrekturen sind neue Fassungen; das Original lässt sich
  zurückholen.
- Alles, was über MCP geändert wurde, findest du unter **Transaktionen → Hinweis → „Mit MCP
  geändert“**; jede Änderung steht auch im Protokoll.
- Bis zu 50 Einträge je Plan. Ein Plan wartet 30 Minuten auf dein OK, danach braucht es einen
  neuen. Sieh dir die Liste an — und es gibt die tägliche Sicherung.

## Die API für andere Programme

Dieselben Daten gibt es auch als einfache Web-Adressen für ein Widget, Home Assistant oder eine
Tabelle — mit **eigenen** Tokens und eigenem Schalter, nur lesend. Siehe [API (JSON)](api.md).

## Wo es geht

Nur im **Heimnetz**. Unterwegs über ein **VPN** nach Hause (z. B. WireGuard oder die
VPN-Funktion des Routers): verbunden, ist es wie zu Hause. Aus dem Internet ist owncryptofolio nicht erreichbar — das bleibt so, bis ein
öffentlicher Zugang ausdrücklich eingerichtet wird.

Ändern sich Adresse oder Port von owncryptofolio, die Befehle in den Einstellungen neu
kopieren.

## Abschalten

- **Claude-Zugriff aus** — sofort kommt Claude mit keinem Token mehr herein; die Tokens bleiben.
- **Stufe eines Tokens auf „Nur lesen“** — mit diesem Token kann Claude nichts mehr ändern.
- **Widerrufen** — dieses eine Token gilt nicht mehr.

Der **Systemzustand** zeigt, ob Claude angebunden ist und wann zuletzt gefragt wurde.

## Verwandte Seiten

- [API (JSON)](api.md) — dieselben Daten für andere Programme
- [Systemzustand](systemzustand.md) — Protokoll, auch der Claude-Aufrufe
- [Mittelherkunft](mittelherkunft.md)
- [Steuerbericht](steuerbericht.md)
