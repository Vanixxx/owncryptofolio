# Changelog

Technische Fassung. Die Anwendersicht steht in [`wiki/was-ist-neu.md`](wiki/was-ist-neu.md).
Versionsschema `0.MAJOR.MINOR.PATCH` (ADR 0007, ADR 0009). Neustart am 2026-10-02
(ADR 0024); die Fassung davor bis `v0.7.0.0` ist nicht Teil dieses Repos.

## v1.8.1.0 — 2026-10-28 · Bestände als Betrag, erster Start, Updates

**Neu**

- Bestände: Ein Tipp auf die Veränderung im Zeitraum schaltet bei allen Coins zwischen % und
  Betrag um (Kursänderung auf den heutigen Bestand, in der Anzeigewährung; gemerkt im Browser).
  Neue Sortierung „Wertänderung im Zeitraum“.

**Behoben**

- Erster Start ohne vorhandene Ordner: Docker bzw. Unraid legen fehlende Ordner für `/data` und
  `/backups` als root an, die App (Benutzer 1000) konnte dort ihre Schlüssel nicht schreiben und
  startete nicht. Ein Startschritt übergibt die Ordner jetzt an den App-Benutzer und gibt root
  danach ab (`setpriv`). Neu: `PUID`/`PGID` (Unraid-Vorlage: 99/100). Bestehende Installationen
  ändern sich nicht. Die CI startet das Abbild jetzt einmal echt mit frischen Ordnern.

**Geändert**

- Abhängigkeiten (Dependabot): Vite 8.3.5 (behebt 6 Warnungen, nur Entwicklungsserver), React
  19.3.1, react-router 8.5, i18next 26.5, lucide 1.61, vitest 5.0.5, oxlint 1.89; FastAPI 0.161,
  SQLAlchemy 2.1.6, Alembic 1.20.1, pydantic-settings 2.16.1, httpx2 2.16, ruff 0.17.2; GitHub
  Actions checkout/setup-node v7, buildx/QEMU v4, build-push v7. Zurückgehalten: TypeScript 7,
  `@types/node` 26, Node 26 im Bau.
- Unraid: Das App-Icon im Docker-Reiter kommt von GitHub (192 px), auch wenn der Container
  gerade nicht läuft; `build.sh` nimmt das in den Einstellungen gewählte Icon.

## v1.8.0.0 — 2026-10-25 · Veröffentlichung

**Neu**

- Öffentlich auf GitHub: `github.com/Vanixxx/owncryptofolio`, fertiges Abbild
  `ghcr.io/vanixxx/owncryptofolio` für amd64 und arm64 (`:<version>` und `:latest`).
- GitHub Actions: Tests (pytest gegen PostgreSQL 18, ruff, oxlint, vitest, Build) und Probebau des
  Abbilds bei jedem Push und Pull Request; ein Versions-Tag baut und veröffentlicht das Abbild und
  legt ein Release mit diesem Changelog-Abschnitt an. Dependabot schlägt monatlich Updates vor.
- Unraid-Vorlage für das fertige Abbild (`src/deploy/unraid/template.xml`), für Community
  Applications vorbereitet.
- `SECURITY.md`: Sicherheitslücken privat über GitHub melden.

**Geändert**

- Das Abbild wird aus der Projektwurzel gebaut (`docker build -f src/Dockerfile .`); LICENSE und
  THIRD-PARTY-NOTICES liegen jetzt im Abbild unter `/app/`, dazu OCI-Labels (Quelle, Lizenz,
  Version). Die `.dockerignore` an der Wurzel lässt nur `src/backend`, `src/frontend` und die
  Lizenzen durch. Das Frontend wird einmal auf der Bau-Maschine gebaut, auch für arm64.
- Wiki: Installation mit Docker und auf Unraid für das fertige Abbild (Update per
  `docker compose pull` bzw. „update ready“ im Docker-Reiter); README mit Schnellstart aus dem
  Abbild, Hinweis zu Issues und Copyright.

## v1.7.6.0 — 2026-10-25 · Prüfungen: Code, Sicherheit, Dokumentation

**Behoben** (Code-Prüfung 1: Steuer, Portfolio, Statistik, Bestände)

- Zeitzone: Die Datenbank lief in Europe/Berlin, die App rechnet Tageskurse nach UTC-Tag. Ein
  Vorgang zwischen 0 und 1/2 Uhr Berliner Zeit wurde mit dem Kurs des Folgetags bewertet
  (Portfolio, Steuer, Herkunft, Statistik). Die Verbindung arbeitet jetzt immer in UTC.
- Portfolio: Eine Gebühr in Euro beim Verkauf gegen Euro senkte den realisierten Gewinn nicht
  (die Steuer rechnete richtig).
- Bestandsabgleich: Handeingabe und Abruf für denselben Coin wurden addiert; jetzt gilt die neuere.
- Steuer: Ein Jahr, in dem es nur Verkäufe ohne erfassten Kauf gibt, fehlte in der Jahresliste.
- Statistik: Monate der Spot-Bilanz nach Berliner Tag; eine Einzahlung an einem Tag ohne
  BTC-Kurs ging im BTC-Vergleich verloren.
- Futures-Gebühr als Abgang gebucht zählte als Ergebnis statt als Gebühr (Portfolio).
- Verlustvortrag: das laufende Jahr nach Berliner Zeit; Teilen durch 0 bei einem Abgang ohne
  Menge; halbe Cents runden kaufmännisch auf; Dateiname der Herkunft-Datei ohne Sonderzeichen.

**Behoben** (Code-Prüfung 2: Integrationen, Import, Rohdaten, Quellen, Aufträge)

- EVM-Netzwerke: zwei gleiche Token-Überweisungen in einer Transaktion wurden als Doppel
  verworfen; jetzt `hash:2` … (die erste behält ihre Kennung, Bestehendes bleibt erkannt).
  Mehr als 10.000 Einträge je Liste: weiter ab dem letzten Block statt Abbruch.
- Cosmos: ein nicht erreichbarer Server ließ einen IBC-Coin stillschweigend weg (und verschob die
  Nummerierung); eine mitten im Blättern abgebrochene Historie gilt jetzt als Fehler.
- Börsen (ccxt): Trades derselben Millisekunde am Seitenrand wurden übersprungen; mehr als
  200 Seiten sind ein Fehler statt stiller Kürzung. Abruf liest zwei Wochen zurück (statt zwei
  Tagen), damit tagelang ausstehende Ein-/Auszahlungen nicht verloren gehen.
- MEXC: Trades werden je 7-Tage-Fenster weitergeblättert; Paare auch aus Ein-/Auszahlungen.
- Dogecoin: Block am Seitenrand wird ganz gelesen. Solana: vom Knoten nicht gelieferte
  Transaktionen sind ein Fehler statt einer Lücke.
- Transaktionsliste: Weiterblättern verlor Zeilen mit gleichem Zeitpunkt (Cursor jetzt mit Id).
- Sicherheit: Fehlertext einer Bestandsabfrage ohne Schlüssel (wie der Abruf); ZIP-/Excel-Dateien,
  die entpackt über 500 MB groß wären, werden abgelehnt.
- Abgelehnter Schlüssel eines Blockchain-Dienstes (HTTP 401/403) wird als solcher gemeldet;
  unlesbarer Dienst-Schlüssel nach Schlüsselwechsel mit klarer Meldung.
- Datei-Import: eine hochgeladene Datei namens `mapping.json` überschrieb die Zuordnung; eine
  unlesbare Datei hinterließ einen leeren Originale-Ordner.

**Sicherheit** (Code-Prüfung 3a: Login, MCP, Sicherung, Logos, Kern, Container)

- Sitzungen tragen einen Stempel des Passworts: ein neues Passwort (Oberfläche oder
  Kommandozeile) beendet alle älteren Sitzungen; die eigene bekommt ein neues Cookie. Nach dem
  Update einmal neu anmelden.
- Einrichtungscode: Fehlversuche warten nacheinander, ab dem zehnten zehnmal so lange; beim
  Hochladen einer Sicherung beim Einrichten kommt der Code als Header vor der Datei.
- Börsen-Icons: nur http(s) zu öffentlichen Adressen, Weiterleitungen geprüft (kein Zugriff aufs
  Heimnetz oder auf lokale Dateien).
- Zurückspielen: zuerst in eine eigene Datenbank, dann Tausch per Umbenennen — eine kaputte
  Sicherung lässt die laufende Datenbank unberührt; Schlüsseldatei vorher geprüft; nur Tabellen,
  Daten, Sequenzen, Indizes und Schlüssel aus der Datei (keine Funktionen, Trigger, Erweiterungen);
  die Sicherung vor dem Zurückspielen einer fremden Sicherung wird mit dem neuen Schlüssel neu
  verschlüsselt (sonst wäre der Weg zurück verschlossen).
- Sicherung: Dump und Probe aus derselben Momentaufnahme (ein Abruf währenddessen ließ die Probe
  scheitern); Wegwerf-Datenbanken mit eigenem Namen; Hochladen in Stücken, eindeutiger Name, erst
  vollständig an Ort und Stelle.
- Passwortprüfung außerhalb der Ereignisschleife; MCP-Plan nur mit dem Token, das ihn erstellt hat,
  jeder Fehler eines Schritts wird festgehalten; Protokoll zeigt den Tokennamen als `client=`.
- build.sh: Sonderzeichen im Datenbank-Passwort (`%40` …) kommen richtig im Container an.
- Wiki: Tipp für einen eigenen Datenbank-Benutzer statt `postgres`.

**Behoben** (Code-Prüfung 3b: Kurse, Zusammenführung, manuelle Eingabe, Export)

- Export (Transaktionen, Bestände, Steuer, Herkunft): Text von außen (Token-Namen aus Airdrops,
  Kommentare) wird nie zur Formel in Excel/CSV (`app/core/sheets.py`).
- Kurse: ein Ausfall des Wechselkurs-Dienstes bricht den Kursabruf nicht mehr ab; ein Kursende in
  der Zukunft hält die Kurse bis dahin; zusammengelegte Kürzel holen keine Feinkurse mehr; eine
  Lücke am Anfang wird höchstens wöchentlich neu erfragt statt bei jedem Lauf.
- Futures-Positionen im Export: Wert nicht mehr doppelt umgerechnet, Verlust behält sein Minus.
- Gebühr an Transfer hängen: der Server prüft dieselben Regeln wie die Oberfläche; eine angehängte
  Buchung, deren Transfer getrennt wurde, erscheint wieder als Zeile; eine Zeile kann nicht in
  zwei Transfers stehen.
- Zeitumstellung: die doppelte Stunde im Oktober — unverändertes Speichern verschiebt eine Zeile
  nicht mehr um eine Stunde; der Eingang zu einem Transfer bekommt den genauen Zeitpunkt.
- Vorlage: Zahlen aus Excel-Zellen ohne Gleitkomma-Rest (0,3 statt 0,30000000000000004).

**Behoben** (Code-Prüfung 4: Oberfläche)

- Sicherheit: der Tooltip des Verteilungsrings setzte Token-Symbole und Wallet-Namen ungefiltert
  als HTML ein (`<img onerror=…>` aus einem Airdrop); jetzt maskiert (`html()` in format.ts).
- Transaktionslisten: eine langsame ältere Antwort überschrieb einen neueren Filter; „Staub
  ausblenden“ nahm nur die ersten 500 Zeilen.
- Reine Tagesangaben („steuerfrei ab …“) erscheinen in jeder Zeitzone als derselbe Tag (westlich
  von UTC vorher einen Tag zu früh).
- Fehlermeldungen verschwinden, sobald ein späterer Abruf klappt (Dashboard, Kurse, Steuer).
- Diagramme übernehmen einen Wechsel von Stil oder hell/dunkel sofort.
- Eingabe-Vorschau liest `1,234.56` wie der Server; Zahlen in der Sprache der Oberfläche.
- Übersetzungstest prüft leere Texte je Sprache; zwei ungenutzte Komponenten entfernt.
- Bau: `tsc --noEmit -p .` prüfte nichts (nur Verweise); geprüft wird mit `npm run build`.

## v1.7.5.0 — 2026-10-24 · Handbuch auf Englisch, Sicherheitsupdate, Steuerbericht mit Kopf

**Neu**

- Wiki auf Englisch: `wiki/en/` (30 Seiten, englische Dateinamen `guides/`, `concepts/`,
  `whats-new.md`, `gallery.md`), Bedienbegriffe aus `en.json`, Bilder gemeinsam mit der deutschen
  Fassung. ADR 0054: jede Wiki-Änderung in beiden Fassungen. `test_wiki_sources` prüft die
  Quellentabelle in beiden. Haupt-README verlinkt die englische Fassung.
- Steuerbericht (PDF und Excel) mit Kopf: Name, Anschrift und neu eine optionale Steuernummer
  (`report.tax_number`, Einstellungen → Steuer → „Kopf der Berichte“). Gespeichert in der
  Zusammenfassung (`summary.holder`), daher behält ein festgehaltener Bericht seinen Kopf; die
  Prüfsumme bleibt unberührt.
- Bilder: 46 Screenshots (PC, Handy, alle Seiten, alle Stile) unter `wiki/bilder/`, Übersicht
  `wiki/bilder.md`, eine Auswahl im README. Erzeugt aus einer Beispiel-Datenbank mit erfundenen
  Daten (`src/backend/scripts/demo_data.py`, verweigert jede Datenbank, deren Name nicht auf
  `_demo` endet).

**Geändert**

- Englische Oberfläche: „Color“, „Licenses“ in US-Schreibweise (vorher „Colour“, „Licences“).
- Wiki: Beispiel-PDFs (Steuerbericht 2025, Mittelherkunft einer Auszahlung) aus den Beispieldaten
  in `wiki/beispiele/`, verlinkt in Steuerbericht, Mittelherkunft und Galerie (beide Sprachen).
- Bilder auf Englisch: `wiki/bilder/en/` (46 Galeriebilder, 44 Ausschnitte) für das englische Wiki
  und den englischen Teil des README.

**Sicherheit**

- Bibliotheken mit bekannten Lücken aktualisiert (pip-audit: 48 Meldungen in 5 Paketen → 0):
  pillow 12.3.0 → 13.0.0 (über fpdf2), aiohttp 3.14.3 → 3.14.5, multidict 6.7.1 → 6.9.1,
  certifi 2026.6.17 → 2026.10.19, opentelemetry-api 1.45.0 → 1.45.1; dafür ccxt 4.5.85 → 4.5.90
  (hatte certifi/multidict festgelegt). Frontend: npm audit 0.
- `build.sh` baut mit `docker build --pull`: immer das aktuelle Basis-Abbild (Python/Debian) mit
  Sicherheitskorrekturen; die Bibliotheken bleiben über die Lock-Dateien fest.

**Behoben**

- Steuerbericht-PDF: die Übersicht passt auf Seite 1 (vorher liefen ein paar Zeilen auf Seite 2
  über); engere Zeilen und Abstände, Test zählt die Seiten — auch für die längste mögliche
  Übersicht mit längstem Kopf.
- Beträge: das Vorzeichen bricht nicht mehr vom Betrag ab (im Englischen stand „+“ allein in
  einer Zeile, „€14,596.19“ darunter); `money()` hängt ein Word Joiner an das Vorzeichen.

- Wiki: 44 Ausschnitte (einzelne Karten und Bedienelemente, `wiki/bilder/details/`) direkt an
  den Absätzen von 11 Anleitungen, statt ganzer Seiten; die Galerie zeigt sie zusätzlich.

- Statistik/Kontogesundheit: offene Punkte zuerst; am Handy kleiner Ring neben dem Befund, offene
  Punkte als Zeilen, erledigte als Chips erst nach Tipp auf die Karte (`stats.health.cleanMore`); am PC Kacheln in drei Spalten und Summe im Ring
  (`Ring` mit Größe per `className`).

## v1.7.4.0 — 2026-10-23 · Vorbereitung zur Veröffentlichung

**Neu**

- Lizenz: GNU Affero General Public License v3.0 (`LICENSE`).
- Passwort vergessen: `docker exec -it owncryptofolio python -m app.modules.auth reset-password`
  setzt im Terminal des Servers ein neues (bisher gab es keinen Weg zurück).
- Wiki: neue Seiten „Einstellungen“, „Auf dem Handy“ und „Hilfe bei Problemen“; Statistik,
  Systemzustand und Quellen um die Neuerungen ergänzt.
- Wiki: Quellen mit einer Tabelle aller Börsen und Netzwerke (Status, nötiger Schlüssel), ein
  Test hält sie vollständig; Docker-Anleitung auch ohne Compose, mit allen Variablen und Ordnern.
- Wiki: „Erweitern“ beschreibt jetzt, wie man eine eigene Integration baut (Ordner, plugin.toml,
  Funktionen, Datenformat, Testen) — jetzt unter Anleitungen als „Eigene Integration bauen“ mit
  vollständigem, geprüftem Beispiel und Checkliste; die Steuer je Wallet und Börse ist mit Beispiel
  erklärt.
- Haupt-README (englisch) mit Hinweis, dass das Projekt mit Claude Code entstanden ist.
- Lizenzhinweise: `THIRD-PARTY-NOTICES.md`, Wiki-Seite „Lizenzen und Marken“, Karte „Lizenzen“ unter
  Systemzustand (Symbole, Schriften, Bibliotheken, Hinweis zu Marken).
- Börsen-Icons, die das freie Symbol-Set nicht hat, liefert das Projekt nicht mehr mit: jede
  Installation holt sie beim ersten Anzeigen von der Webseite der Börse und speichert sie im
  Datenordner (`site-icons`). Bereits geholte bleiben erhalten (Bau-Skript übernimmt sie).

**Behoben**

- Sicherungen: das Abbild hat den Sicherungsordner fest auf `/backups` (`BACKUP_DIR` muss niemand
  mehr setzen); ist dort kein Ordner eingebunden, warnt Einstellungen → Sicherung.
- Steuerbericht (Excel/PDF): Hinweis ohne interne Verweise, verständlich für Steuerberatung und
  Finanzamt; der Hinweis in der App erklärt den Unterschied zur Seite Bestände in Worten.
- Steuerbericht (Excel/PDF): Zeile „Betrachtung“ nennt „walletbezogen“.
- Systemzustand: Feinkurs-Aufträge hießen „system.jobKinds.fine“ statt „Feinkurse“.

**Geändert**

- In Code, Wiki und CHANGELOG steht „Vanixxx“ statt des Vornamens.
- Texte allgemein statt Unraid-bezogen: Hinweise zu Einrichtungscode, Datenbank, Sicherung und
  Claude-Adresse; neue Wiki-Seite „Installation mit Docker“ (Docker Compose mit PostgreSQL), die
  Unraid-Anleitung bleibt als eigene Variante.

## v1.7.3.0 — 2026-10-23 · NEAR und Cosmos

**Neu**

- Vier weitere Netzwerke (Beta): NEAR (FastNEAR, Token über Ereignisse, Bestand auf das
  yoctoNEAR geprüft) sowie Cosmos Hub, Osmosis und Celestia über einen gemeinsamen Cosmos-Leser
  (Überweisungen, IBC-Coins, Staking-Erträge als Einkommen; gestakte Coins bleiben im Bestand).
  Grenze: kostenlose Cosmos-Knoten behalten nur wenige Monate Geschichte.

## v1.7.2.0 — 2026-10-23 · Sieben weitere Netzwerke

**Neu**

- Sieben weitere Netzwerke (Beta), alle ohne Pflicht-Schlüssel: XRP Ledger (Ripple-Server), Tezos
  (TzKT, mit Token und Baker-Auszahlungen), Algorand (AlgoNode, mit ASA und Belohnungen), Tron
  (TronGrid, TRC-10/TRC-20, gestaktes TRX im Bestand), TON (toncenter, Jettons), Dogecoin
  (BlockCypher), Bitcoin Cash (Haskoin). Optionale Schlüssel für TronGrid und toncenter unter
  Dienste. NEAR verschoben (NearBlocks ohne Schlüssel nicht verlässlich).

## v1.7.1.0 — 2026-10-23 · Kleine Ideen

**Neu**

- Liefert eine Quelle eine schon eingelesene Zeile mit anderen Werten (gleiche ID und Zeit),
  wird sie nicht still verdoppelt: Hinweis in der Kontogesundheit, auf der Seite Quellen
  „Neue Werte übernehmen“ oder „Bisherige behalten“ (ADR 0053).
- Getrennte Transfers bleiben getrennt: Beide Hälften werden nicht mehr von selbst mit einem
  anderen Gegenstück verbunden, nur von Hand.
- BNB Smart Chain: AXS und SLP werden im Bestandsabgleich wieder geprüft (auch bei alten Zeilen
  ohne Token-Vertrag).
- Unraid: Der Container zeigt im Docker-Reiter das App-Icon (Vorlage zeigt auf das Icon der
  App, das Bau-Skript legt es Unraid gleich bereit).

## v1.7.0.0 — 2026-10-22 · Netzwerke, API, Stile, Wiederherstellung

**Neu**

- Erster Start (ADR 0052): Eine ganz neue Installation braucht keinen Einrichtungscode mehr
  („Willkommen“). Nur wenn auf dem Server schon Schlüssel liegen (z. B. Datenbank neu), fragt
  der Assistent danach und erklärt, wo der Code im Container-Protokoll steht.
- Statistik: „Coins ohne Kurs“ nennt die Coins; jeder Name führt direkt zu seinem Kurs
  (Kurse öffnet den Coin). Auch der Hinweis im Dashboard führt bei einem Coin direkt hin.
- Sieben weitere EVM-Netzwerke (Beta): Arbitrum One, Linea, Mantle, Blast über Etherscan V2
  (kostenloser Schlüssel), Optimism (explorer.optimism.io), zkSync Era und Celo über Blockscout
  ohne Schlüssel; Kontostand über öffentliche RPC-Knoten. Base fehlt: Etherscan nur bezahlt,
  Blockscout hinter Cloudflare (gemessen 2026-10-20).

- JSON-API `/api/v1` (ADR 0050): die 15 lesenden MCP-Funktionen als `GET`-Adressen, eigener
  Schalter `api.enabled`, Verzeichnis unter `/api/v1`; Karte „API (JSON)“ mit Beispielen
  (curl, Home Assistant); Wiki-Seite „API (JSON)“ mit allen Adressen.
- Tokens je Tür (`kind` mcp/api, Präfix `ocf_mcp_`/`ocf_api_`): ein API-Token öffnet Claude
  nicht und umgekehrt. Claude: Schalter `mcp.enabled` statt `mcp.mode`, Stufe Nur lesen /
  Bearbeiten **je Token** (`level`); Migration `f3b8d1e5a9c4` übernimmt die alte Einstellung.

- Stile Graphit, Rosé, Hoher Kontrast, Amethyst, Sand (`graphite`, `rose`, `contrast`,
  `amethyst`, `sand`) und `ios`, je hell und dunkel; Farbauswahl je Stil
  (`appearance.accents` {Stil: Farbe}, Attribut `data-accent`); jede Stil-Kachel mit kleiner
  Kurve, am Handy zweispaltig.
- App-Icon wählbar (`appearance.icon`, 16, Standard E5): `/apple-touch-icon.png` und
  `/manifest.webmanifest` liefern das gewählte; PNGs in `public/app-icons/` (180/192/512). Das
  Icon ist zugleich Favicon und Logo oben links (`Brand`), vor der Anmeldung aus dem Browser-Cache.
- Neon behält in jeder Farbe seinen Farbverlauf (zwei Töne je Farbe, auch im Hintergrund-Leuchten
  und in der Kurve der Stil-Kachel).
- Stil iOS als „Liquid Glass“ (iOS 26): Glaskarten mit Unschärfe über einem Farbfeld, helle
  Kanten, runde Ecken.
- Wiederherstellen in der Oberfläche (ADR 0051): Einstellungen → Sicherung und beim ersten Start;
  Sicherung prüfen (Wegwerf-Datenbank), Warnhinweis mit Bestätigung, vorher automatische
  Sicherung des Stands (nie automatisch gelöscht), Schlüssel aus der Sicherung. Jede Sicherung
  enthält jetzt `….keys.enc`; „Sicherungsschlüssel“ heißt „Wiederherstellungsschlüssel“.
- Bestände: Kurve wählbar wie bei Kurse (heute, 24 Std., 7/30/90 Tage) mit der Veränderung in %
  darunter (Handy: unter der Menge), Sortierung „Kursänderung im Zeitraum“.
- Bestände: aufgeklappter Coin hat einen dritten Reiter „Transaktionen“ mit allen Transaktionen
  dieses Coins und einem Link zur gefilterten Seite Transaktionen; Ansicht „Kompakt“ (eine Zeile je
  Transaktion, Standard am Handy, Antippen öffnet die Karte samt Details an ihrer Stelle) oder „Karten“.
- Transaktionen: dieselbe Wahl „Kompakt“/„Karten“ für die ganze Liste (Standard am Handy kompakt).
  Am PC ist die kompakte Zeile eine Tabellenzeile (Zeit, Orte mit Logo, Aus/Ein mit Wert, Kurs,
  Gebühr, Notiz); Futures mit lila Ring ums Symbol.

**Behoben**

- EUR/USD-Schalter bei Neon kaum erkennbar (gläserner Knopf): Knopf jetzt in der Textfarbe des
  Akzents.

**Geändert**

- Update auf Unraid: „Bearbeiten → Anwenden“ statt „Neu starten“ (ein Neustart behält das alte
  Abbild); Bau-Skript und Wiki „Installation und Update“ entsprechend, mit Hinweis für einen
  schon vorhandenen Container.

- Kurse: Sortierung heißt „Veränderung im Zeitraum“ (folgt dem gewählten Zeitraum, nicht fest 90 Tage).
- Bau-Skript: neu eingelesene Originale bei jedem Lauf ergänzen, Warnung bei abweichenden
  Schlüsseln.

## v1.6.0.0 — 2026-10-19 · Claude-MCP (M14)

**Behoben**

- Zwei Sicherungen in derselben Sekunde überschrieben einander; jetzt eindeutige Namen.
- EUR/USD-Schalter: die Seite lud ihre Zahlen, bevor der Server die neue Währung gespeichert
  hatte, und zeigte so die alte; jetzt erst nach der Bestätigung.
- Kopieren-Knöpfe (MCP-Befehle, Sicherungsschlüssel) taten über http://IP nichts; jetzt mit
  Rückfall ohne Clipboard-API.

**Neu**

- Alle Karten der Einstellungen ein-/ausklappbar (zu beim ersten Öffnen, gemerkt je Browser;
  eine geschlossene öffnet per Klick irgendwo in den Rahmen), untereinander statt in zwei
  Spalten; die doppelte Karte „Quellen und Zugänge“ ist entfallen.

- M14 Stufe 2 (ADR 0049): `mcp.mode` = edit; Werkzeuge `plan_*` (Transfers, Notizen,
  Markierungen, Spam, Ausblenden/Zurückholen, Handeinträge, Korrekturen; je ≤ 50) mit Probe in
  zurückgerollter Transaktion, vollständiger Liste und Bestandswirkung; `apply_plan` führt den
  Plan genau einmal aus; `start_fetch`; Tabelle `mcp_change` (Migration `e7a2c9d4b1f6`);
  Filter „Mit MCP geändert“ (`show=mcp`); `apply_plan(only=[…])` führt einen gewählten Teil
  der Vorschau aus; Werkzeugfehler lesbar (`ToolError`).
- EUR/USD-Kippschalter (`components/CurrencySwitch.tsx`) in den Seitenköpfen und der Handy-Kopfzeile
  (Kurse: rechts neben „Kurse abrufen“; am Handy beide in der Kopfzeile, der Knopf als Symbol);
  ein Wechsel lädt die Seite neu (`Outlet key=currency`). `PageHeader` mit `aside`.
- M14 Stufe 1 (ADR 0049): MCP-Server für Claude im Backend (`app/modules/mcp`, SDK `mcp` 2.x,
  Streamable HTTP zustandslos, Route `/mcp`), 15 lesende Werkzeuge als Hüllen um die
  vorhandenen Services; Prüfer mit Bearer-Token (sha256 in `mcp_token`, Migration
  `d5f1b3a7c2e8`) getrennt vom Web-Login; Einstellung `mcp.mode` (off/read); jede Zeichenkette
  maskiert, max. 200 Zeilen, jeder Aufruf im Logger `mcp`. Karte „Claude (MCP)“ mit Tokens und
  fertigen Befehlen für Claude Code und Claude Desktop (`mcp-remote`); Zeile im Systemzustand.

## v1.5.0.0 — 2026-10-19 · Quellen erweitern (M13)

**Neu**

- M13 A (ADR 0048): allgemeine Anbindung `ccxt_api` für jede ccxt-Börse mit Trades, Bestand und
  Ein-/Auszahlungen (58 Börsen, eigene Anbindungen gewinnen); Zugangsfelder je Börse aus ccxt,
  `fee_in_amount`, `tested`, `exclude`, `quotes` in `[ccxt]`; Trades je Paar, wenn nötig;
  Blättern ab 2017 mit Rückfall ohne Start. Gemeinsame Zuordnung in `plugins/ccxt_map.py`.
- M13 B (ADR 0048): eigener CSV/Excel-Import mit Spalten- und Wertezuordnung
  (`app/modules/imports/mapped.py`, `/api/imports/mapped/inspect|preview`, `/api/imports/mapped`):
  zwei Aufbauten (je Bewegung, je Trade), Trade in einer Zeile mit Gegenwert oder in zwei Zeilen
  mit gleicher ID, Liste einer Art ohne Art-Spalte; Trennzeichen, Dezimalzeichen, Kopfzeile,
  Datumsformat erkannt; Vorschau je Zeile; Zuordnung je Quelle gespeichert (Tabelle
  `import_mapping`, Migration `c4e8a2d61f37`) und neben der Originaldatei als `mapping.json`.
- Transaktionen → „Importieren“ (vorher „Mehrere per Vorlage einlesen“) bietet neben der Vorlage die eigene Datei an (nur Börsen).
- Logos für die ccxt-Börsen (Icon-Set bzw. eingecheckte Website-Icons in `public/exchange-logos/`).
- Eigene Datei: Originalzeilen aufklappbar mit Zuordnung je Spalte; Arten *Tausch* (aus der
  Notiz) und *Umbuchung*; Trade-Hälften an gemeinsamer ID erkannt; Notiz „Bought … for …“
  vor Gegenwert-Spalten; Währungszeichen als Einheit. Probe gegen Kraken/Coinbase-Anbindungen.
- `[plugin] status = "tested" | "beta"` (fehlt = beta); Bitcoin und Stellar beta. Badge,
  Hinweis beim Hinzufügen und auf der Karte; „Börse hinzufügen“ zeigt ohne Suche nur Getestete.

- Protokoll live im Systemzustand (ADR 0047): Ringpuffer der letzten 2.000 Log-Zeilen im
  Backend (`app/core/logs.py`), `GET /api/system/logs?after=`, Browser-Fehler und -Warnungen
  über `POST /api/system/logs/client` unter Logger `frontend`. Karte standardmäßig eingeklappt, fragt nur offen ab. Anzeige mit Filter nach Stufe,
  Herkunft und Text, Pause, Leeren, Speichern als Textdatei. Zeilen werden maskiert
  (Schlüssel, Tokens, Adressen).
- Einstellung `system.log_level` (DEBUG/INFO/WARNING/ERROR), wirkt sofort und nach dem Start.

## v1.4.0.0 — 2026-10-18 · Verlustvortrag und Mittelherkunft (M12)

**Behoben**

- Mittelfluss-Diagramm am Handy leer (ein Kasten ohne Verbindung machte es Millionen Pixel
  breit); Diagramme jetzt als SVG. Am Handy ist das vereinfachte Diagramm schmal genug, um es
  meist ohne Scrollen zu sehen; das komplette etwa halb so breit wie am PC. Eigener, kleiner
  Tooltip an der getippten Stelle (wurde vorher im Scrollbereich abgeschnitten).

**Hinzugefügt**

- Mittelherkunft: **Mittelfluss-Diagramm** (Sankey), vereinfacht je Börse/Wallet und komplett je
  Schritt; Herkünfte vor, Verluste hinter ihrem Schritt platziert. Im PDF beide Diagramme auf
  eigenen Seiten (komplett bei vielen Schritten auf A3); der Vorgang in eigener Farbe.
- Mittelherkunft nach Blockpits Vorbild: Kursverluste als negativer Anteil, Übersicht (Zeitraum,
  Transaktionen, Börsen/Wallets, Datenart), Einzahlungen im Detail, Datenquellen, Text in Worten,
  Datenart je Schritt (PDF, Excel, Oberfläche).
- Mittelherkunft: ein Tausch Coin gegen Coin erscheint als „Tausch · 100 USDT → 1,5 LTC“
  statt als bloßer Verkauf.
- Quellen: Knopf **Erneut abrufen** direkt im Hinweis auf einen fehlgeschlagenen oder alternden
  Abruf (nicht bei abgelehntem Schlüssel).
- **Mittelherkunft** (M12 Teil B, ADR 0046): Spur im Steuerdurchlauf (`tax/trace.py`,
  `Lot.parts`, Euro-Töpfe je Quelle), Aufteilung und Kette für Verkäufe, Zahlungen, Transfers
  (auch eigene Wallets) und Auszahlungen (`/api/tax/origin…`), PDF und Excel, Berichte →
  Mittelherkunft, Link aus dem Steuer-Reiter, Einstellungen `report.name`/`report.address`.
- Mittelherkunft des **heutigen Bestands** (`/api/tax/origin/holdings`), gesamt und je Coin,
  mit nicht realisiertem Kursgewinn; PDF/Excel mit „Bestand je Coin“.
- Mittelherkunft einer **geplanten Transaktion** (`/api/tax/origin/planned`, Optionen, Datei):
  Ort, Coin/Euro, Menge, Datum; nimmt die heutigen Lose in Steuer-Reihenfolge, bucht nichts.
- **Verlustvortrag § 23** (M12 Teil A, ADR 0045): Rechenvorschlag je Jahr (ein Jahr Rücktrag,
  Rest vor, nur mit Gewinnen ab der Freigrenze), Wert laut Bescheid je Jahr und Vortrag aus
  früheren Jahren (Tabelle `tax_loss_assessed`, `PUT /api/tax/carry/{year}`), Karte im
  Steuerbericht mit „Alle Jahre“, Excel/PDF: Zusammenfassung und Blatt „Verlustvortrag“.
- Kurse: **Kurse beenden** je Coin (`price_asset.prices_until`, `POST /api/prices/assets/{asset}/until`)
  für umgestellte Coins: nach dem Tag nichts mehr abrufen, spätere Kurse entfernen, nicht
  mit 0 bewerten. AGIX endet am 05.07.2024 (umgestellt auf FET).
- Kurse → Coin: ein beendeter Coin öffnet den Graphen auf „Alles“; ein Zeitraum ohne Kurse
  zeigt „Keine Kurse in diesem Zeitraum“ statt endlos „Wird geladen“.

**Entfernt**

- Der allgemeine Ausreißer-Filter der Feinkurse (Faktor 2,5 zum Tagesmedian) — er hätte
  echte Kurssprünge kleiner Coins verworfen.

---

## v1.3.0.0 — 2026-10-16 · Feinwerte (M11)

**Hinzugefügt**

- Feinkurse je Coin (`price_fine`: 5 Min 31 Tage, stündlich 90 Tage; Yahoo, Bitget, Binance,
  CoinGecko), Auftrag „Feinwerte“ beim Start und stündlich; Portfolio-Feinwerte werden daraus
  neu gerechnet (Lücken aus Ausfällen füllen sich, verzerrte Werte 07.–11.10. behoben).
- Kurse: Veränderung über 24 Std.; die Kurve je Coin folgt dem gewählten Zeitraum
  (`/api/prices/sparks`).
- Steuerbericht: Reiter **Steuerfrei** — je Coin heute steuerfrei/in Haltefrist mit Wert
  und G/V in der Anzeigewährung, nächster Termin (`/api/tax/free`).
- Freigrenze: Ausschöpfung im Steuerbericht (Balken), Hinweis im Dashboard ab 80 %
  (`/api/tax/limits`). Systemzustand zeigt „Feinwerte (stündlich)“.

---

## v1.2.0.0 — 2026-10-15 · Statistik (M10)

**Hinzugefügt**

- Seite **Statistik** (`/api/stats`): Rendite je Monat/Jahr ohne Ein-/Auszahlungen,
  Vergleich „alles in BTC“, Gebühren je Jahr und Börse/Wallet, Erträge je Monat,
  Futures-Bilanz (Trefferquote, beste/schlechteste Position, je Monat), Aktivität.
- Dashboard: Verteilung nach Coin oder Börse/Wallet, Gewinner/Verlierer, „Steuerfrei
  demnächst“ (`/api/tax/upcoming`), Abstand zum Höchststand.
- Dashboard: 24 Std./7 Tage/1 Monat laden 3 Tage/1 Monat/3 Monate feine Werte zum
  Zurückscrollen, Zeitleiste startet auf dem Zeitraum; Tageshoch/-tief als Band.
- Statistik: Kontogesundheit (Lücken, abweichende Bestände, ohne Gegenstück, negativ,
  Sonstige, ohne Kurs, Kartenkauf ohne Euro, Abrufe) und Spot-Bilanz.
- Kurse: Veränderung über heute/7/30/90 Tage wählbar. Bestände: 90-Tage-Kurve je Coin (PC).
- Transaktionen: Transaktions-ID verlinkt zum Block-Explorer (17 Netzwerke).
- Start ohne Datenbank: die Seite zeigt „Keine Verbindung zur Datenbank“ und versucht es neu
  (API antwortet 503 `db.unavailable`); die App startet nach, sobald die Datenbank da ist,
  auch bei Ausfall im laufenden Betrieb.
- Abruf: automatischer Abruf wird nach Zeitüberschreitung/Verbindungsfehler nach 15 Minuten
  bis zu dreimal wiederholt.

**Geändert**

- Vorgang hinzufügen: Marktpreis als Tageskurs (nur das Datum zählt, Uhrzeit lädt nichts neu).
- Transaktionen am Handy: Kurs und Gebühr eines Handels in einer Zeile.

---

## v1.1.0.0 — 2026-10-13 · Steuer (M9)

**Hinzugefügt**

- Steuer (ADR 0042): Losverfolgung je Quelle × Markt × Coin, FIFO (Standard) und LIFO,
  Haltefrist nach deutschem Kalendertag, Gebühren wie das BMF, Umstellung ohne Veräußerung,
  Markierungen (an Fremde, eigene Wallet, verloren, gekauft, Ertrag), Futures nach § 20.
- Berichte → Steuer: Jahr, Verfahren, § 23 mit Freigrenze 600/1.000 €, § 22 mit 256 €,
  § 20, Verluste durch Pleite/Betrug getrennt, Reiter mit allen Einzelposten, Bestand
  31.12.; Excel (7 Blätter) und PDF; Festhalten mit Abweichungsmeldung (auch bei
  Korrekturen früherer Jahre). API `/api/tax/...`, Tabelle `tax_report`.
- Versionsverlauf der festgehaltenen Berichte (mit Notiz und allen Einzelposten):
  Vergleich mit jetzt oder der vorherigen Fassung, Kennzahlen und jeder geänderte Vorgang.
  Die Prüfsumme läuft nur über steuerlich relevante Zahlen, nicht über das Format.
- Festhalten erzeugt PDF und Excel und speichert sie mit (Download im Versionsverlauf,
  `/api/tax/kept/{id}/file`); ältere Fassungen bekommen sie einmalig aus ihren Einzelposten.
- PDF mit allen Tabellen des Excel (Querformat, Kopfzeile auf jeder Seite), Erklärung zu
  „Kosten geschätzt“ in PDF und Excel.
- Nach dem Abgleich mit Blockpit 2024: Ausfüllhilfe (Anlage SO/KAP mit Zeilen 2024), Summen
  je Quelle, Bestandsveränderungen (01.01./Zufluss/Abfluss/31.12./Wert), Kauf-Zeile je
  Verkauf, § 22 nach Art – in Ansicht, Excel und PDF. Futures-USDT ohne § 23-Verkauf,
  Börsen-Bonus unter § 20, Kartenkauf ohne Euro = Kosten geschätzt.
- Transaktionen: Kurs bei Handel („Kurs 25.848 BTC/USDT“); Art „Kauf/Verkauf“ heißt überall
  „Handel“. Formular: Marktpreis
  unter jedem Coin (zum Zeitpunkt oder aktuell, Zeile springt beim Laden nicht) und Kurs aus
  Erhalten/Abgegeben (`/api/prices/at`).
- Steuer: Fehlmengen bis 0,01 % gelten als Rundung (wie die Lückensuche).
- Versionsverlauf aufklappbar; Kommentar je Fassung, Fassung löschen. Ausfüllhilfe als letzter Reiter.
- Transaktionen: Hinweis/Filter **Kartenkauf ohne Euro** (Bitget liefert nur den Coin).
- Transaktionen: Reiter **Steuer** je Zeile (Transfer, Position): verkauft aus welchen
  Käufen, Gewinn, was aus einem Kauf wurde, mitgewanderte Käufe. API `/api/tax/rows`.
- Einstellungen → Steuer (`tax.method`, `tax.airdrop_taxable`); Bestände zeigen je Coin
  den steuerfreien Anteil und ab wann der nächste Teil steuerfrei ist.
- Systemzustand: Speicher, den owncryptofolio belegt (Datenbank, Daten, Sicherungen,
  gesamt); große Freigaben in TB.
- Abhängigkeit `fpdf2` (PDF).

---

## v1.0.0.0 — 2026-10-12 · Tracking rund (M8)

**Hinzugefügt**

- **Auslieferung für Unraid**: `src/deploy/unraid/build.sh` baut das Image (Version aus git
  oder Changelog), kopiert beim ersten Mal Schlüssel und Originale nach `appdata` und
  installiert die Vorlage; `owncryptofolio.xml` mit Port 8085, Daten-/Sicherungsordner und der
  Datenbank als einzelne Felder (`DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`;
  `DATABASE_URL` hat weiter Vorrang). Image mit `postgresql-client-18` und `HEALTHCHECK`.
- **Systemzustand „Betrieb“** (`operations` in `/api/system/status`): letzte/nächste
  Sicherung mit Probe, Abruf mit Fehlschlägen, Kursabruf, aktuelle Kurse,
  Sicherungs-Werkzeuge (Version ≥ Server), freier Speicher.
- Dashboard: „Netto eingezahlt“ per Legende ausblendbar (gemerkt), Zeitschieber zeigt den
  Gesamtwert.
- Wiki: Anleitungen „Transaktionen“, „Systemzustand“, „Installation und Update auf Unraid“;
  übrige Anleitungen auf den Stand von M7.

**Geändert**

- Kurse: „wertlos ab …“ statt Warnung „ohne Kurs“; Kursachse ab 1.000 ohne Nachkommastellen.
- Registerleiste einer aufgeklappten Transaktion blendet rechts aus, solange Reiter folgen.
- Beschriftungen „Umstellung (Token-Umtausch)“ und Hinweis-Filter „Markiert“.

**Behoben**

- Ketten-Abrufe versuchen es bei Zeitüberschreitung/Verbindungsfehler dreimal erneut
  (Litecoin um 04:00).
- Fehlender Text „Kursabruf“ bei den Hintergrundaufträgen.

---

## v0.7.0.0 — 2026-10-11 · Feinschliff (M7)

**Hinzugefügt**

- Export Transaktionen (wie angezeigt) und Bestände als Excel und CSV (`/api/export/...`).
- Portfoliowert alle 5 Minuten (`portfolio_tick`, ausgedünnt), Dashboard „24 Std.“/„7 Tage“;
  aktuelle Kurse standardmäßig alle 5 Minuten.
- Eigene Logos hochladen (Wallet, Börse, Netzwerk, Coin), in der Datenbank gespeichert.
- Kurse und Bestände merken die zuletzt gewählte Sortierung (je Browser).
- Kurse: Suche und Sortierung (Nutzung, Name, Kurs, 90-Tage-Veränderung), 90-Tage-Veränderung
  unter dem Kurs.
- Logos für Börsen, Wallets und Netzwerke; Transfer als „von → nach“ mit Logos.
- Warnungen, wenn die Börse den API-Schlüssel ablehnt (z. B. nach 90 Tagen abgelaufen), ein
  Abruf fehlschlägt oder der API-Rückblick ausläuft (MEXC 89 Tage).
- **Transaktionen**: Karten mit Registerkarten (Details, Bearbeiten, Verlauf, Gegenstück
  suchen), ⋯-Menü mit allen Aktionen, mehrere Zeilen gleichzeitig offen; Suche (Coin, Name,
  ID, Notiz, Adresse, Datum, Hinweis, Art, Markt, „a|b“); Mehrfachfilter Quelle/Art/Coin/
  Herkunft, nicht passende Werte abgedunkelt (`/api/merged/facets`); Hinweis-Filter mit
  Zahlen nach den übrigen Filtern; Einträge pro Seite, Filter/Stelle gemerkt; Auswählen mit
  Sammelaktionen (verbinden, Gebühr zuordnen, kein Staub, Spam), „Auswählen beenden“.
- Korrekturen mit Versionsverlauf, Zurücksetzen, „bearbeitet“-Kennzeichen; eigene Notizen;
  Transfer bearbeiten (Datum einmal, Abgang/Eingang/Gebühren mit Wallet, Coin-Suche,
  Bestand zum Zeitpunkt); Transfer trennen, ausblenden, kopieren.
- Vorgang erfassen als Fenster: Symbole, Coin aus Liste oder frei, Uhrzeit mit
  Doppelpunkten, Kopieren, Transfer mit Von/Nach (auch vom Eingang aus), „max. …“ = Bestand
  zum Zeitpunkt (`/api/portfolio/balance-at`), „Per Karte bezahlt“, Ertrag auch im
  Futures-Konto.
- Markierungen: Abgang „verloren“ (Totalverlust, auch Fiat); Eingang ohne Gegenstück
  „eigene Wallet“, „außerhalb gekauft“, „Ertrag“; Eingänge zählen als „kein Gegenstück“.
- „Bestand negativ“ und „Bestand danach“ an der Zeile; automatische Karten-Einzahlung
  gekennzeichnet (ganzer Betrag, wenn die Börse nicht deckt oder per Karte bezahlt).
- Bestände: Registerkarten Details/Graph, Kursgraph mit DCA als Stufenlinie, Logos bei „Wo“.
- Quellen: Bestandsabgleich je Netzwerk/Börse aufklappbar (Coins eingerückt), „Abruf und
  Import“ einklappbar mit Verbindungszustand, Netzwerk ohne Anbindung (`manual_network`),
  Cent-Toleranz für EUR/USD/Dollar-Coins, Abgleich zählt Karten-Einzahlungen.
- Kurse: „wertlos ab“ Datum, einzelnen Coin abrufen (`/api/prices/assets/{asset}/fetch`),
  Spam-Ticker erkannt.
- Leser: Coinbase (Karte/PayPal = Einzahlung, Zieladresse und Ketten-ID), MEXC
  (Futures-Kontostand, deutscher Futures-Mittelfluss/Positionsverlauf, Bonus = Ertrag,
  verfallener Bonus = Futures-Gebühr), KuCoin (Umbuchungen Spot↔Futures aus dem
  Kontoverlauf), Hedera (Systemkonten, Memo), Polygon über Etherscan V2, VTHO-Zuwachs aus
  VET als Ertrag.
- Standard-Kursquelle Yahoo (ADR 0041).

**Behoben**

- Live-Kurse missachteten die Rangfolge (CRO sprang um 23 %).
- Dashboard-Veränderung zählte Einzahlungen als Gewinn („Alles“ +39.000 %).
- Coinbase: Gebühr wurde doppelt abgezogen (`total` statt `subtotal`).
- Transfer verbindet nur noch einen Coin (verschiedene Coins werden abgelehnt).
- Ketten-IDs ohne „0x“ (Coinbase) werden der Kette zugeordnet.
- Verlorenes Fiat zählt nicht mehr als Auszahlung.

---

## v0.6.0.0 — 2026-10-05 · Portfolio und Gewinn/Verlust (M6)

**Hinzugefügt**

- **Portfolio-Rechnung** `app/modules/portfolio/` (ADR 0040): ein Durchlauf über die
  zusammengeführte Sicht, Durchschnittskosten je Coin über alle Quellen in EUR; Transfers
  verschieben mit Kosten, Netzgebühr erhöht den Einstand; Umbuchungen über einen
  Zwischenposten; Erträge zum Marktwert; „an Fremde“ = Verkauf, „eigene, nicht erfasst“ =
  Ort „außerhalb“; Abgang ohne Bestand = ungeklärt, bei Fiat = Kartenkauf; Futures-Ergebnis
  getrennt. Zwischengespeichert, bis sich Daten ändern. API `/api/portfolio`, `/history`,
  `/gaps`, `/futures`.
- **Lückensuche** je Quelle/Markt/Coin (erster Zeitpunkt unter null, Kontostand-Differenzen).
- **Futures-Positionen** aus Positionszeilen (Bitget, MEXC, KuCoin) mit Ergebnis, Funding,
  Gebühren; ohne Positionsdaten nach Pausen gruppiert.
- **Seiten Dashboard und Bestände** (Spot, Futures, Lücken).
- Transaktionsfilter aus der URL (Links aus der Lückensuche).
- Futures: abgeschlossene Positionen als eine Zeile in den Transaktionen (`type: position`),
  Bestände zeigen nur offene. Coin- und Quellenfilter als Auswahl mit Suche
  (`/api/merged/assets`). Netzwerk **Ronin** (`chain_ronin`, Blockscout ohne Schlüssel).
- Suche in Beständen, beim Hinzufügen von Netzwerken und Börsen. Am Handy kein Zoom mehr.
- Transfer-Erkennung: verbunden wird, was jede größtmögliche Zuordnung einer Gruppe enthält
  (Coin über zwei Stationen). Kürzel RONIN = RON.
- Gewinn/Verlust je Handel beim Aufklappen (Kauf: bezahlt vs. heute; Verkauf: Erlös vs. heute).
- Sortierung: Bestände (Wert, G/V, G/V %, realisiert, Besitzdauer, Name), Transaktionen
  (Zeit oder Wert, auf-/absteigend; `sort`, `desc`, Rohdaten `after`). Futures nach Kontrakt
  gruppiert.

**Geändert**

- Transaktionen: Art-Symbole, Coin-Logos an Beträgen, am PC einzeilig, Filter am Handy
  einklappbar. Bestände am PC in Spalten. Dunkle Logos bekommen im Dunkelmodus eine helle
  Unterlage. Zeitachsen deutsch. Hintergrundaufträge zeigen ihre Quelle.

**Behoben**

- „Netto eingezahlt“ in USD wackelte mit dem Wechselkurs; jede Einzahlung gilt jetzt zum
  Kurs ihres Tages.
- Gedrosselte Explorer (429): Der Abruf wartet die genannte Sperrzeit ab (bis 15 Minuten).
- Karten mit Titel rutschten bei ungleicher Höhe nebeneinander in die Mitte.

---

## v0.5.1.0 — 2026-10-04 · Filter für Transaktionen

**Hinzugefügt**

- Filter Quelle (ganze Wallet oder Netzwerk), Art (dazu „Transfer“), Coin (alle Kürzel des
  Coins), Zeitraum (Tage in der eingestellten Zeitzone) für `/api/raw` und `/api/merged`
  (`app/modules/raw/filters.py`) und auf der Transaktionsseite; „Filter zurücksetzen“.

**Geändert**

- Wallet-Netzwerke heißen in Auswahl und Liste „Wallet – Netzwerk“ (z. B. „Tangem – Ethereum“).

---

## v0.5.0.0 — 2026-10-04 · Eine Wahrheit (M5)

**Hinzugefügt**

- **Zusammengeführte Sicht** `app/modules/merged/` (ADR 0039): je Anfrage aus den gültigen
  Rohzeilen berechnet (ohne Vermerk, ohne API-Abdeckung, Kürzel als Coin). Transfers über
  Tx-ID, sonst ±1 h / ±1 %, nie innerhalb einer Quelle, nie geraten; Vorschläge ±24 h / ±5 %.
  Gespeichert werden nur Entscheidungen (`transfer_decision`, `open_send_mark`,
  `spam_mark`), verankert auf dem Fingerabdruck. Netzgebühr = gesendet − angekommen.
- **Spam**: auf der Kurs-Seite ignorierter Coin zählt nirgends; Spam je Vorgang;
  Staub-Vorschläge (Zugang unter 0,01 % der Zugänge des Coins in der Quelle).
- **Offene Abgänge** markierbar: „an Fremde“ oder „eigene Wallet, nicht erfasst“.
- **Bestandsabgleich** `app/modules/balances/` (`balance_snapshot`): Kontostand nach jedem
  Abruf über `balance()` in allen 16 Ketten und 3 Börsen, von Hand für Börsen ohne Anbindung;
  Vergleich je Quelle/Markt/Coin, Toleranz 0,1 %, Spam ausgenommen. API `/api/balances`.
- **Oberfläche**: Transaktionen zeigen standardmäßig die zusammengeführte Sicht (Filter
  Alle/Offen/Staub?/Spam, Gegenstück suchen, Verbinden/Trennen), Schalter „Rohdaten“;
  Quellen-Seite mit Abgleich-Badge je Börse, Wallet und Netzwerk und Tabelle.

**Behoben**

- Spam-Token-Namen über 40 Zeichen brachen das Speichern des Kontostands ab.
- Ein seit dem letzten Abruf verschwundener Coin behielt seinen alten Kontostand.

**Verschoben**

- Futures-Positionen gruppieren → M6.

---

## v0.4.0.1 — 2026-10-04 · Kurse nachgebessert

**Behoben**

- Yahoo speichert vergangene Kurse mit 6 Nachkommastellen: Reihen mit typischem Kurs unter
  0,0001 $ (XEN, QUBIC, SHIB) werden abgelehnt, die nächste Quelle übernimmt.
- Beendete Reihen (FTM nach der Umstellung auf S) zeigen keinen veralteten „aktuellen
  Kurs“ mehr, sondern „bis <Datum>“.
- CoinGecko-Kennungen werden klein geschrieben (`xen-crypto`).

---

## v0.4.0.0 — 2026-10-04 · Kurse (M4)

**Hinzugefügt**

- **Kursmodul** `app/modules/prices/` (ADR 0019, 0038): Zuordnung Coin → Quellen in
  Rangfolge (`price_source`) mit Verlauf und Pflicht-Grund (`price_mapping_change`),
  Tageskurse mit Hoch/Tief und Herkunft (`price_daily`), USD→EUR der EZB mit
  Wochenend-Näherung (`fx_daily`), Lücken (`price_gap`), aktuelle Kurse (`price_latest`),
  Kürzel-Zusammenführung (`asset_alias`), Symbol je Coin.
- **Quellen**: Yahoo (Anker 2015, 0 = keine Angabe), Bitget `1Dutc` (auch nicht mehr
  gelistete Paare), **Binance** (neu, für MATIC/FTM), CoinGecko (von Hand), Frankfurter/EZB;
  Wiederholung bei 429/503; Decimal statt float.
- **Vorschlag** prüft die Abdeckung, nicht den Namen; Standard-Rangfolge einstellbar;
  Spam als „ignoriert“ vorgeschlagen; unbestätigte Coins ohne Quelle werden neu gefragt.
- **Bewertung** (`Valuer`): USDT als echtes Glied, 7 Tage Rückgriff, sonst unbewertet (nie 0);
  Anzeige in EUR oder USD.
- **Gegenprobe** Yahoo ↔ Bitget (90 Tage, ≤ 2 %).
- **Seite Kurse**: Liste mit echten Symbolen (web3icons MIT + cryptocurrency-icons CC0,
  lokal), Kurve, Live-Kurse alle 30 s mit Aufblinken; Diagramm mit Band und Zoom (ECharts,
  nachgeladen); Bestätigen, Bearbeiten, Ignorieren, Zusammenführen, Verlauf.
- **Einstellungen → Kursabruf**: täglich 04:30, aktuelle Kurse im Intervall, Rangfolge.

**Echtlauf**: 33 Coins ab 2021-11 bewertet, Gegenprobe BTC 0,02 %, SOL 0,04 %; QUBIC
umgestellt (Yahoo rundet auf 1e-6).

---

## v0.3.0.0 — 2026-10-04 · Alle meine Quellen (M3)

**Hinzugefügt**

- **Börsen** (ADR 0035): `coinbase_file`, `coinbase_api` (Kontobuch, CDP-Schlüsseldatei
  oder Schlüsselpaar, Ed25519), `mexc_file` (EN/DE, Futures), `mexc_api` (7-Tage-Fenster),
  `kraken_file`, `kucoin_file` (inkl. Futures). Abgleich API ↔ Datei je Anbieter
  (`overlap` = `period` | `event`), Mehrfach-Upload je Import.
- **16 Netzwerke**: gemeinsamer EVM-Leser (`plugins/evm.py`; Ethereum, Polygon,
  Avalanche, Sonic, Cronos, BNB über NodeReal), UTXO-Verrechnung (`plugins/mempool.py`;
  Bitcoin, Litecoin, Kaspa, Cardano), Polkadot (Relay + Asset Hub, Gebühren aus
  Ereignissen), VeChain (VET/VTHO), Hedera (Staking getrennt), Sui, Solana (inkl.
  Token-Konten), Stellar. Wiederholung bei HTTP 429/503.
- **Täglicher Abruf** (04:00, je Quelle abschaltbar) und **Blockchain-Dienste**
  (Etherscan, Cronos, NodeReal) in den Einstellungen.
- **Von Hand** (ADR 0036/0037): Kanal `manual`, Börse ohne Anbindung, Eingabemaske (Spot und
  Futures, Sekunden), xlsx-Vorlage DE/EN mit Vorschau; **Bearbeiten jeder Zeile** mit
  Verlauf (`raw_retraction`, Rohzeilen bleiben unberührt), Ausblenden, Zurücksetzen.
- **Oberfläche**: Quellen-Karten einklappbar mit letztem Abruf, „Alle abrufen“;
  Transaktionen mit „⋯“-Aktionen, Verlauf alt → neu, „Vorgang erfassen“, „Vorlage“;
  Zeiten mit Sekunden.

**Gegenproben** gegen den alten Stand (07.09.): Coinbase 460, MEXC Spot, Kraken, KuCoin,
alle 16 Netzwerke je Art identisch; BNB neu (10, Bestand stimmt).

---

## v0.2.0.0 — 2026-10-03 · Quellen verbinden (M2)

**Hinzugefügt**

- **Quellen** (ADR 0033): Börsen und Wallets in der Oberfläche anlegen; API-Schlüssel
  verschlüsselt (`source_credential`), Verbindungsprüfung ohne Geheimnisse in Meldungen.
- **Plugins** unter `src/backend/integrations/`: `bitget_file`, `bitget_api`,
  `chain_ethereum`; Register meldet kaputte Plugins statt abzustürzen.
- **Rohebene** `raw_transaction` mit `market`/`instrument` (Futures), Schutz gegen
  Löschen/Ändern, Importläufe mit Rücknahme des letzten Laufs, Duplikaterkennung per
  Fingerabdruck; „API vor Datei“ über `api_covered_from`.
- **Datei-Import** mit Vorschau (schreibt nichts) und Ablage der Originaldatei.
- **Hintergrundaufträge** (`job`) für Abrufe und Sicherungen, Fortschritt in der Oberfläche.
- **Sicherung** (ADR 0014/0018/0033): verschlüsselter Abzug und Export, Probe-
  Wiederherstellung je Lauf, Zeitplan mit Nachholen, Aufbewahrung, CLI.
- **Wallets als Behälter** (ADR 0034): Netzwerk-Adressen unter einer Wallet, EVM-Adressvorschlag.
- **Bitget-API** ab 2018, gebremst gegen 429; API-Abdeckung je Markt aus den gelieferten Daten.
- **Echttest**: Bitget API 598 Vorgänge (Spot ab 2024-02, Futures ab 2024-09), Bitget-Datei
  1.309 Zeilen (903 zählen, 406 durch API abgedeckt), Ethereum 23.
- **Oberfläche**: Seite Quellen, Transaktionen (Rohdaten), Einstellungen → Sicherung,
  Aufträge im Systemzustand.

---

## v0.1.0.0 — 2026-10-03 · Design und Rahmen (M1)

**Hinzugefügt**

- **Automatischer Erststart** (ADR 0030): auf PostgreSQL warten, fehlende Datenbank
  anlegen, migrieren, Schlüssel in `<data>/secrets/keys.json` (600) erzeugen,
  Einrichtungscode ins Log. Pflicht in der Umgebung ist nur `DATABASE_URL`.
- **Zugangsschutz**: Einrichtung mit Code, Passwort als `scrypt`-Hash in der Datenbank,
  Fernet-Sitzung, ein Wächter über `/api`, `/docs`, `/openapi.json`; `Secure`-Cookie
  hinter TLS-Proxy über `X-Forwarded-Proto`.
- **Einstellungen** als Register mit Validierung (`appearance.style`, `appearance.theme`,
  `general.language`, `general.currency`, `general.timezone`).
- **Health** (`/api/health` mit echtem `SELECT 1`) und **Systemzustand**
  (`/api/system/status`).
- **Oberfläche**: drei Stile Nacht/Neon/Terminal × Hell/Dunkel als Design-Tokens
  (ADR 0031), Schriften lokal, Deutsch und Englisch mit Gleichheitstest (ADR 0032),
  Seitenleiste bzw. Tab-Leiste, alle Seiten mit Platzhaltern, Einrichtungsassistent,
  Anmeldung, Einstellungen (Darstellung, Sprache und Region, Passwort,
  Sicherungsschlüssel), Systemzustand.
- `src/Dockerfile` (Port 8080, Volume `/data`, nicht root) — **noch nicht gebaut**.

**Geprüft**

- 28 Backend-Tests gegen PostgreSQL 18.6, Gegenprobe am Zugangswächter; `ruff`.
- Frontend: `tsc`, `oxlint`, `vitest`; Playwright-Durchlauf Handy/Desktop in allen sechs
  Stil-Kombinationen ohne Überlauf und Konsolenfehler.
- Erststart am echten Server gegen eine fehlende Datenbank; Einrichtung von Vanixxx am
  2026-10-03 durchgespielt und abgenommen.

**Offen**

- Docker-Image bauen und starten (ADR 0016, Abnahmepunkte 6–7).
