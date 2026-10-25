---
titel: Sicherung
aktualisiert: 2026-10-25
---

# Sicherung

## In einem Satz

owncryptofolio sichert sich jede Nacht selbst, prüft jede Sicherung durch eine
Probe-Wiederherstellung, und du sorgst dafür, dass der Sicherungsordner zusätzlich
**außerhalb des Servers** liegt.

## Was gesichert wird

Jede Sicherung besteht aus drei verschlüsselten Dateien im Sicherungsordner:

| Datei | Inhalt |
|---|---|
| `….dump.enc` | die komplette Datenbank: Transaktionen, Korrekturen, Notizen, Einstellungen, Kurse, Steuerberichte, Börsen-Zugänge, dein Passwort (als Prüfwert) |
| `….keys.enc` | die beiden internen Schlüssel für Börsen-Zugänge und Anmeldung — damit der **Wiederherstellungsschlüssel allein** alles zurückbringt |
| `….raw.jsonl.gz.enc` | alle eingelesenen Vorgänge in einem einfachen Textformat, lesbar auch ohne owncryptofolio |

Sicherungen aus der Zeit vor Oktober 2026 haben noch keine `….keys.enc`: Stammen sie von
derselben Installation, bleiben die Börsen-Zugänge lesbar, sonst trägst du sie nach dem
Zurückspielen neu ein.

Dazu kommen die **Originaldateien** jedes Datei-Imports, die owncryptofolio unverändert
aufbewahrt.

Im Container liegen die Sicherungen im eingebundenen Sicherungsordner (`/backups`), die
Schlüssel und Originaldateien im Datenordner (`/data`) — auf dem Rechner also in den beiden
Ordnern, die du beim Einrichten angegeben hast. **Sichere beide Ordner mit.** Ist an `/backups`
kein Ordner eingebunden, warnt die Karte **Sicherung**: Die Sicherungen lägen dann im Container
selbst und wären beim nächsten Update weg.

## Einstellen

<p>
  <img src="../bilder/details/einst-sicherung.png" alt="Sicherung in den Einstellungen" width="640">
</p>

Unter **Einstellungen → Sicherung**:

- **Automatisch sichern**: ja oder nein, mit **Uhrzeit**. Voreingestellt ist 03:00.
- **Tagessicherungen behalten** (Standard 14) und **Monatssicherungen behalten**
  (Standard 12). Ältere Sicherungen löscht owncryptofolio selbst, aber nur seine eigenen
  Dateien.
- **Jetzt sichern** startet sofort eine Sicherung.

War der Server zur eingestellten Uhrzeit aus, holt owncryptofolio die Sicherung beim
nächsten Start nach.

Unter **Letzte Sicherungen** siehst du jede Sicherung mit **„Probe-Wiederherstellung
bestanden“**: Die Sicherung wurde testweise in eine Wegwerf-Datenbank zurückgespielt und
mit dem Original verglichen. Steht dort etwas anderes, ist diese Sicherung nicht
verwendbar. Auf einen Blick siehst du den Stand auch unter
[Systemzustand → Betrieb](systemzustand.md).

## Die zwei Dinge, die keine Software für dich erledigen kann

1. **Kopie außerhalb des Servers.** Eine Sicherung auf derselben Platte schützt gegen
   Bedienfehler, nicht gegen Geräteausfall. Sichere den angezeigten Ordner zusätzlich,
   z. B. mit dem Backup deines NAS, einem Backup-Programm oder einer Cloud-Synchronisierung.
2. **Den Wiederherstellungsschlüssel getrennt aufbewahren.** Du hast ihn bei der
   Einrichtung bekommen. Er steht auch unter *Einstellungen → Sicherung → Schlüssel
   anzeigen*. Mit ihm allein holst du alles zurück, ohne ihn lässt sich keine Sicherung
   öffnen.

## Zurückspielen

### In der Oberfläche

*Einstellungen → Sicherung → Wiederherstellen → Sicherung wiederherstellen …*

1. Eine Sicherung **aus dem Sicherungsordner** wählen oder eine **Datei hochladen** (die
   `….dump.enc`, wenn vorhanden mit der gleichnamigen `….keys.enc`), z. B. von einem anderen
   Gerät.
2. Stammt sie von einer anderen Installation, ihren **Wiederherstellungsschlüssel**
   eingeben; sonst bleibt das Feld leer.
3. **Sicherung prüfen**: owncryptofolio zeigt, was darin steckt — Zahl der Transaktionen,
   Quellen, Zeitraum, ob die Börsen-Zugänge mitkommen. Dabei ändert sich noch nichts.
4. **Der Warnhinweis**: Alle jetzigen Daten werden durch die Sicherung ersetzt, auch dein
   Passwort. Vorher legt owncryptofolio **automatisch eine Sicherung des jetzigen Stands**
   an — nur damit kommst du zurück. Haken setzen, **Jetzt wiederherstellen**.
5. Nach ein paar Minuten meldest du dich mit dem **Passwort aus der Sicherung** neu an.

Die Sicherung wird zuerst in eine eigene Kopie gespielt; erst wenn das gelingt, tritt sie an
die Stelle der laufenden Datenbank. Schlägt es fehl, bleibt alles, wie es war. Übernommen
werden nur Tabellen und Daten, nichts anderes, was in einer fremden Datei stecken könnte.

Die Sicherung des Stands davor steht danach in der Liste („vor Wiederherstellung“) und wird
nie automatisch gelöscht. Hast du eine Sicherung **mit ihrem eigenen Wiederherstellungsschlüssel**
zurückgespielt, gilt danach dieser Schlüssel für die Installation — auch die Sicherung „vor
Wiederherstellung“ ist dann damit verschlüsselt und nicht mehr mit dem alten.

### Beim ersten Start (neuer Server)

Auf der Einrichtungsseite den Einrichtungscode eingeben und **„Stattdessen aus einer
Sicherung wiederherstellen“** wählen. Dann wie oben: Sicherung wählen (der Sicherungsordner
ist im Container eingebunden) oder hochladen, Wiederherstellungsschlüssel eingeben, prüfen,
bestätigen. Danach anmelden mit dem alten Passwort — alles ist wieder da.

### Notfall: Kommandozeile

Läuft die Oberfläche gar nicht, geht es auch im Terminal des Servers:

```
docker exec -it owncryptofolio python -m app.modules.backup restore /backups/<datei>.dump.enc --database owncryptofolio_restore
```

Das spielt die Sicherung in eine **neue** Datenbank. Die laufende wird nie überschrieben.
Dieser Weg öffnet nur Sicherungen, die mit dem Schlüssel dieser Installation verschlüsselt
sind.
Erst danach entscheidest du, ob du auf die wiederhergestellte umstellst.

## Verwandte Seiten

- [Erster Start und Einrichtung](erster-start.md): wo der Wiederherstellungsschlüssel herkommt
- [Quellen einrichten und einlesen](quellen.md)
- [Installation mit Docker](installation-docker.md) · [auf Unraid](installation-unraid.md)
- [Systemzustand](systemzustand.md)
