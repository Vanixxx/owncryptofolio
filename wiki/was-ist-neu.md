---
titel: Was ist neu
aktualisiert: 2026-10-25
---

# Was ist neu

Änderungen in Anwendersprache — nur das, was dir beim Benutzen auffällt. Neueste zuerst.

Die technische Fassung mit allen Änderungen steht in [`CHANGELOG.md`](../CHANGELOG.md) und in den
Changelogs der einzelnen Programmteile.

---

## v1.8.0.0 — 25. Oktober 2026

**owncryptofolio ist öffentlich.**

- Das fertige Abbild gibt es auf GitHub: `ghcr.io/vanixxx/owncryptofolio`, auch für den
  Raspberry Pi (64 Bit). Selbst bauen ist nicht mehr nötig.
- **Updates mit einem Klick:** Auf Unraid meldet der Docker-Reiter „update ready“, mit Docker
  Compose genügt `docker compose pull` und `docker compose up -d`. Siehe
  [Installation auf Unraid](anleitungen/installation-unraid.md) und
  [Installation mit Docker](anleitungen/installation-docker.md).
- Fragen und Fehler kannst du auf GitHub als Issue melden, Sicherheitslücken privat.

## v1.7.6.0 — 25. Oktober 2026

**Prüfungen: viele Korrekturen bei Abruf, Bewertung, Sicherheit und Sicherung.**

- **Sicherheit:** Ein neues Passwort meldet alle anderen Browser ab — nach dem Update einmal neu
  anmelden. Token-Namen aus fremden Quellen (z. B. aus Airdrops) richten weder in der Oberfläche
  noch in Excel etwas an (ein Name wie `=HYPERLINK(...)` wird keine Formel mehr).
- **Zurückspielen einer Sicherung:** Eine kaputte Datei lässt deine Daten unberührt, und der Weg
  zurück bleibt auch nach einer Sicherung von einer anderen Installation offen.
- **Bewertung und Steuer:** Vorgänge kurz nach Mitternacht (bis 1 bzw. 2 Uhr) wurden mit dem Kurs
  des nächsten Tages bewertet. Werte und Steuer solcher Vorgänge können sich dadurch leicht ändern;
  ein festgehaltener Steuerbericht zeigt dann „geändert“.
- **Portfolio:** Eine Gebühr in Euro beim Verkauf senkt jetzt auch hier den Gewinn; eine
  Futures-Gebühr zählt als Gebühr statt als Ergebnis.
- **Steuer:** Ein Jahr nur mit Verkäufen ohne erfassten Kauf erscheint jetzt in der Jahresauswahl.
- **Abruf vollständiger:** Bei Börsen, MEXC, EVM-Netzwerken, Cosmos, Dogecoin und Solana konnten
  in Sonderfällen einzelne Vorgänge fehlen (z. B. zwei gleiche Token-Überweisungen in einer
  Transaktion, viele Trades in derselben Millisekunde, lange ausstehende Auszahlungen). Ein Abruf,
  der nicht alles bekommt, meldet jetzt einen Fehler statt still Lücken zu lassen.
- **Blockchain-Dienste:** Ein abgelehnter Schlüssel wird als solcher gemeldet, mit Hinweis auf die
  Einstellungen. Fällt der Wechselkurs-Dienst aus, läuft der Kursabruf trotzdem weiter.
- **Bestandsabgleich:** Ein von Hand eingetragener Bestand wird nicht mehr zum abgerufenen
  dazugezählt; es gilt der neuere.
- **Sicherung:** Läuft während der Sicherung ein Abruf, scheitert die Probe-Wiederherstellung nicht
  mehr. Das Bau-Skript gibt Sonderzeichen im Datenbank-Passwort richtig an den Container weiter.
- **Transaktionen:** Filter springen nicht mehr auf alte Ergebnisse zurück; beim Weiterblättern
  fehlen keine Zeilen mit demselben Zeitpunkt mehr; „Alle als Spam ausblenden“ beim Staub nimmt
  wirklich alle.
- **Behoben:** Futures-Werte im Export (bei Dollar doppelt umgerechnet); eine angehängte Gebühr
  verschwand nach dem Trennen eines Transfers; Zeilen in der doppelten Stunde der Zeitumstellung
  verrutschten beim Speichern; Zahlen aus der Excel-Vorlage mit Rundungsresten.
- **Oberfläche:** „steuerfrei ab“ zeigt auch in anderen Zeitzonen den richtigen Tag; eine alte
  Fehlermeldung verschwindet, sobald es wieder klappt; Diagramme wechseln die Farben sofort mit
  Stil und hell/dunkel.

---

## v1.7.5.0 — 24. Oktober 2026

**Handbuch auf Englisch, Sicherheitsupdate, Steuerbericht mit Kopf.**

- **Handbuch auf Englisch:** das ganze Wiki gibt es jetzt auch auf Englisch
  ([English manual](en/README.md)), mit Bildern der englischen Oberfläche.
- **Bilder im Handbuch:** Ausschnitte direkt an den Erklärungen und eine
  [Bildergalerie](bilder.md); dazu Beispiel-PDFs für Steuerbericht und Mittelherkunft.
- **Steuerbericht mit deinem Namen:** Name, Anschrift und – neu – deine Steuernummer stehen oben
  im Steuerbericht, wenn du sie unter Einstellungen → Steuer einträgst.
- **Steuerbericht als PDF:** die Übersicht steht jetzt ganz auf der ersten Seite.
- **Sicherheit:** Programmbibliotheken mit bekannten Lücken sind aktualisiert; beim Neubau holt
  das Bau-Skript jetzt immer das aktuelle Grundsystem mit seinen Sicherheitskorrekturen.
- **Statistik:** die Kontogesundheit ist am Handy deutlich kürzer — nur die offenen Punkte stehen
  da; ein Tipp auf die Karte zeigt auch alles, was in Ordnung ist. Am PC steht jeder Punkt als
  eigene Kachel, und der Ring zeigt die Zahl der offenen Punkte.
- **Englische Oberfläche:** „Color“ und „Licenses“ in US-Schreibweise wie der Rest.
- **Behoben:** In der englischen Oberfläche stand das „+“ eines Betrags manchmal allein in einer
  Zeile.

---

## v1.7.4.0 — 23. Oktober 2026

**Vorbereitung zur Veröffentlichung.**

- **Passwort vergessen?** Ein Befehl im Terminal des Servers setzt ein neues
  ([Hilfe bei Problemen](anleitungen/hilfe.md#passwort-vergessen)).
- **Sicherungsordner fest auf `/backups`**: Ist dort kein Ordner eingebunden, warnt die App unter
  Einstellungen → Sicherung.
- **Börsen-Symbole**, die das freie Symbol-Set nicht hat, holt jede Installation selbst von der
  Webseite der Börse; deine bisherigen bleiben erhalten.
- **Lizenzen** unter Systemzustand; owncryptofolio selbst steht unter der AGPL-3.0.
- **Steuerbericht**: der Hinweis in Excel und PDF ist für Steuerberatung und Finanzamt verständlich.
- **Wiki**: neue Seiten Einstellungen, Auf dem Handy, Hilfe bei Problemen, Installation mit
  Docker (auch ohne Compose) und Eigene Integration bauen; Tabelle aller Quellen mit Status.
- **Behoben:** Unter Systemzustand stand bei den Feinkursen ein Platzhalter statt „Feinkurse“.

---

## v1.7.3.0 — 23. Oktober 2026

**NEAR und Cosmos.**

- **Vier weitere Netzwerke** (Beta): NEAR, Cosmos Hub, Osmosis und Celestia; bei Cosmos mit
  Staking-Erträgen. Dort fehlen ältere Vorgänge, wenn die kostenlosen Knoten sie nicht mehr
  haben — der Bestandsabgleich zeigt das. [Mehr](anleitungen/quellen.md#near-und-cosmos)

---

## v1.7.2.0 — 23. Oktober 2026

**Sieben weitere Netzwerke.**

- **Sieben neue Netzwerke** (Beta): XRP, Tezos, Algorand, Tron, TON, Dogecoin und Bitcoin Cash —
  mit Token (z. B. USDT auf Tron und TON) und Staking-Erträgen, ohne Pflicht-Schlüssel.
  [Mehr](anleitungen/quellen.md#neue-netzwerke-beta)
- Für Tron und TON kannst du unter Einstellungen → Blockchain-Dienste einen eigenen Schlüssel
  eintragen.

---

## v1.7.1.0 — 23. Oktober 2026

**Deine Entscheidungen bleiben.**

- **Was du änderst, bleibt**: Trennst du einen Transfer, verbindet owncryptofolio die beiden
  Hälften nicht mehr von selbst mit etwas anderem.
- **Ändert eine Börse eine schon eingelesene Buchung**, siehst du das unter Quellen und in der
  Statistik — und entscheidest selbst: neue Werte übernehmen oder die bisherigen behalten.
  Nichts wird verdoppelt. [Mehr](anleitungen/quellen.md)
- **Bestandsabgleich** prüft auf der BNB Smart Chain jetzt auch AXS und SLP.
- **Unraid**: der Container zeigt im Docker-Reiter das App-Icon.

---

## v1.7.0.0 — 22. Oktober 2026

**Mehr Netzwerke, eigene API, neue Stile, Wiederherstellen in der Oberfläche.**

- **Wiederherstellen aus einer Sicherung** direkt in der Oberfläche — unter Einstellungen →
  Sicherung und auf einem neuen Server schon bei der Einrichtung. Vorher siehst du, was in der
  Sicherung steckt, und owncryptofolio sichert den jetzigen Stand. **Ein Schlüssel reicht**:
  der Wiederherstellungsschlüssel (bisher „Sicherungsschlüssel“) bringt alles zurück, auch die
  Börsen-Zugänge. [Mehr](anleitungen/sicherung.md#zurückspielen)
- **Sieben weitere Netzwerke** (Beta): Arbitrum, Optimism, Linea, Mantle, Blast, zkSync Era
  und Celo. Dieselbe Adresse wie bei Ethereum schlägt owncryptofolio gleich vor.
- **API (JSON)**, nur lesen: deine Daten als Web-Adressen für ein Widget, Home Assistant, Excel
  oder Skripte — mit eigenen Tokens. [Ausführliche Anleitung](anleitungen/api.md)
- **Claude**: ein Schalter für alles, die Stufe „Nur lesen“ oder „Bearbeiten“ je Token.
- **Fünf neue Stile**: Graphit (Grau mit Limette), Rosé (warm, Weinrot), Amethyst (Violett),
  Sand (Terrakotta) und Hoher Kontrast (Schwarz/Weiß, gut lesbar bei Sonne) — je hell und
  dunkel, dazu ein **iOS-Stil** im „Liquid Glass“ des iPhones (Glasflächen über einem
  Farbverlauf). **Jeder Stil** lässt sich in einer eigenen Farbe zeigen (Petrol, Blau, Lila,
  Bernstein, Grün, Rosé, Rot); Neon behält dabei seinen Farbverlauf. Alles unter
  Einstellungen → Darstellung.
- **App-Icon** für den Home-Bildschirm: 16 zur Auswahl unter Einstellungen → App-Icon
  (Standard: Ring mit „c“). Gilt beim nächsten „Zum Home-Bildschirm“ und ist zugleich das
  Symbol im Browser-Tab und oben links in der App.
- **Transaktionen kompakt**: auf der Seite Transaktionen und bei Bestände eine Zeile je Vorgang
  (am Handy Standard, umschaltbar auf „Karten“). Antippen öffnet die volle Karte mit allen
  Details. Am PC zeigt die Zeile mehr: Uhrzeit, Orte mit Logo, Aus- und Eingang mit Wert, Kurs
  und Gebühr. Futures erkennst du am lila Ring. [Mehr](anleitungen/transaktionen.md)
- **Bestände → Coin aufklappen → Transaktionen**: alle Vorgänge dieses Coins direkt dort.
- **Bestände** wie Kurse: die kleine Kurve für heute, 24 Std., 7, 30 oder 90 Tage, darunter die
  Veränderung in %, und sortieren nach „Kursänderung im Zeitraum“.
- **Statistik**: „Coins ohne Kurs“ nennt die Coins, ein Klick öffnet den Kurs des Coins.
- **Erster Start** ohne Einrichtungscode auf einem ganz neuen Server; nur wenn dort schon
  Schlüssel liegen, wird er verlangt — mit Hinweis, wo er steht.
  [Mehr](anleitungen/erster-start.md)
- **Update auf Unraid**: „Bearbeiten → Anwenden“ statt „Neu starten“ — nur so kommt die neue
  Version in den Container.
- **Behoben:** Der EUR/USD-Schalter war im Stil Neon kaum zu erkennen.

---

## v1.6.0.0 — 19. Oktober 2026

**Claude anbinden.**

- **Claude anbinden**: Claude Code oder Claude Desktop können deine Daten lesen — Bestand,
  Transaktionen, Steuer, Mittelherkunft, Systemzustand. Nur im Heimnetz, mit eigenem Token,
  Adressen gekürzt, jeder Aufruf im Protokoll. [Mehr](anleitungen/claude-anbinden.md)
- **Claude darf bearbeiten** (wenn du es erlaubst): Transfers verbinden, Notizen, Markierungen,
  Handeinträge, Korrekturen … — immer erst als vollständige Liste, die du bestätigst. Unter
  Transaktionen → „Mit MCP geändert“ siehst du alles, was so geändert wurde. Du kannst auch nur
  einen Teil der Liste bestätigen („1–14, ohne 44“).
- **Einstellungen** einklappbar und untereinander; Kopieren klappt jetzt auch über http.
- **EUR/USD-Kippschalter** oben rechts auf Dashboard, Beständen, Transaktionen, Kursen, Statistik
  und Berichten (am Handy in der Kopfzeile) — dieselbe Einstellung wie unter Einstellungen.

---

## v1.5.0.0 — 19. Oktober 2026

**Quellen erweitern.**

- **Viel mehr Börsen**: über die Suche beim Hinzufügen rund 60 weitere Börsen per API, z. B.
  Binance, Bybit, OKX, Bitvavo, Gate, dazu die API von Kraken und KuCoin. Sie sind als
  **Beta** markiert; ein Hinweis sagt, was schiefgehen kann und was du prüfen solltest.
  Ohne Suche siehst du nur die getesteten Börsen. [Mehr](anleitungen/quellen.md#weitere-börsen-beta)
- **Eigene Datei für jede Börse**: einen CSV- oder Excel-Export hochladen, Spalten und Werte
  selbst zuordnen, jede Zeile vor dem Import ansehen. Die Zuordnung wird gemerkt. Zu finden
  auf der Karte der Börse und unter Transaktionen → + → **Importieren**.
  [Mehr](anleitungen/quellen.md#eigene-datei-csvexcel--für-jede-börse)
- **Protokoll im Systemzustand**: die Meldungen von Server und Browser live mitlesen, filtern,
  durchsuchen und als Datei speichern. Das **Loglevel** stellst du dort ein (Info, Debug, …).
  Adressen und Schlüssel werden dabei gekürzt bzw. ausgeblendet.
  [Mehr](anleitungen/systemzustand.md#protokoll)

---

## v1.4.0.0 — 18. Oktober 2026

**Verlustvortrag und Mittelherkunft.**

- **Mittelherkunft**: Unter Berichte siehst du für jeden Verkauf, Transfer (auch zwischen
  eigenen Wallets) oder jede Auszahlung, woher das Geld stammt — aufgeteilt nach Herkunft und
  als Kette bis zu den Einzahlungen, als PDF und Excel. Auch für deinen **heutigen Bestand**,
  gesamt und je Coin, und für eine **geplante Transaktion** (Nachweis vorab, ohne Buchung).
  [Mehr](anleitungen/mittelherkunft.md)
- **Mittelherkunft als Diagramm**: der Geldfluss vereinfacht (je Börse/Wallet) oder komplett
  (jeder Schritt), mit Hovern für Beträge.
- **Mittelherkunft ausführlich**: Kursverluste stehen als eigener (negativer) Posten da, dazu
  Übersicht, Einzahlungen im Detail, Datenquellen mit Datenart und ein kurzer Text in Worten.
- **Verlustvortrag**: Der Steuerbericht zeigt, was aus Verlusten früherer Jahre übrig ist,
  wie es verrechnet wird und was ins Vorjahr zurückgeht. Den Wert aus dem Bescheid des
  Finanzamts kannst du eintragen; er geht dann vor. Auch in Excel und PDF.
- **Kurse beenden**: Für einen umgestellten Coin (z. B. AGIX → FET) legst du den letzten Tag
  mit Kurs fest; danach holt die App nichts mehr. AGIX endet am 05.07.2024.
- Der Kursgraph eines beendeten Coins öffnet auf „Alles“; ein Zeitraum ohne Kurse sagt das,
  statt endlos zu laden.
- **Quellen**: Im Hinweis auf einen fehlgeschlagenen Abruf steht jetzt gleich **Erneut abrufen**.

---

## v1.3.0.0 — 16. Oktober 2026

**Feinwerte: Kurse und Portfoliowert alle 5 Minuten.**

- **Dashboard**: 24 Std., 7 Tage und 1 Monat zeigen den Portfoliowert alle 5 Minuten (31
  Tage), davor stündlich. Lücken durch Ausfälle füllen sich von selbst nach.
- **Kurse**: Veränderung auch über 24 Std.; die Kurve je Coin zeigt den gewählten Zeitraum.
- **Berichte**: Reiter **Steuerfrei** — je Coin, wie viel heute steuerfrei ist und wie viel
  noch in der Haltefrist liegt, mit Wert in deiner Währung. Ein Balken zeigt, wie weit die
  Freigrenze ausgeschöpft ist; ab 80 % erscheint ein Hinweis im Dashboard.
- **Systemzustand**: Zeile „Feinwerte (stündlich)“.

---

## v1.2.0.0 — 15. Oktober 2026

**Statistik.**

- Neue Seite **Statistik**: Rendite je Monat und Jahr, Vergleich „alles in BTC“, Gebühren,
  Erträge, Futures-Bilanz, Aktivität, Kontogesundheit und Spot-Bilanz.
- **Dashboard**: Verteilung nach Coin oder Börse/Wallet, Gewinner und Verlierer, „Steuerfrei
  demnächst“, Abstand zum Höchststand, Tageshoch/-tief als Band, Zurückscrollen.
- **Kurse**: Veränderung über heute, 7, 30 oder 90 Tage. **Bestände**: Kurve je Coin (PC).
- **Transaktionen**: Transaktions-ID führt zum Block-Explorer.
- Läuft die **Datenbank** nicht, sagt die Seite das und verbindet sich von selbst neu.
- Ein fehlgeschlagener automatischer Abruf wird nach 15 Minuten wiederholt.

---

## v1.1.0.0 — 13. Oktober 2026

**Steuer: der Steuerbericht nach deutschem Recht.**

- **Berichte** zeigt je Jahr private Veräußerungen (§ 23) mit Freigrenze, Erträge (§ 22),
  Futures (§ 20, Anlage KAP) und Verluste durch Pleite oder Betrug, mit allen Einzelposten,
  Summen je Börse/Wallet, Bestandsveränderungen, Bestand zum 31.12. und einer Ausfüllhilfe
  für Anlage SO und KAP. FIFO ist Standard, LIFO zum Vergleich.
- **Excel und PDF** mit allen Tabellen. **Festhalten** speichert eine Fassung samt PDF und
  Excel; der Versionsverlauf meldet später Änderungen, vergleicht Fassungen Posten für
  Posten, nimmt einen Kommentar auf und lässt Fassungen löschen.
- **Transaktionen**: Reiter **Steuer** je Zeile (aus welchen Käufen verkauft wurde, was aus
  einem Kauf wurde), **Kurs** bei jedem Handel, Hinweis **Kartenkauf ohne Euro-Betrag**.
- **Bestände**: wie viel eines Coins schon steuerfrei ist und ab wann der nächste Teil.
- **Vorgang hinzufügen**: Marktpreis unter jedem Coin, Kurs bei einem Handel.
- **Systemzustand**: wie viel Speicher owncryptofolio selbst belegt.
- Im Abgleich mit Blockpit geprüft; ein Kartenkauf ohne Euro-Betrag zählt mit geschätzten
  Kosten.

---

## v1.0.0.0 — 12. Oktober 2026

**Tracking rund: owncryptofolio ist fertig für den Alltag.**

- **Als Container auf Unraid**: ein Skript baut ihn, die Vorlage im Docker-Reiter ist
  ausgefüllt, die Datenbank trägst du in einzelnen Feldern ein. Siehe „Installation und
  Update auf Unraid“.
- **Systemzustand → Betrieb** zeigt auf einen Blick, ob Sicherung, Abrufe und Kurse von
  selbst laufen und ob genug Speicher frei ist.
- **Dashboard**: Tipp auf „Netto eingezahlt“ blendet die Linie aus; der Zeitschieber zeigt
  deinen Wert.
- **Handbuch**: neue Anleitungen zu Transaktionen und Systemzustand, alle anderen auf dem
  aktuellen Stand.
- Kleinigkeiten: wertlose Coins ohne Warnung, ruhigere Kursachse, Litecoin-Abruf hält kurze
  Aussetzer aus.

**Als Nächstes:** Steuer — Haltefrist, FIFO/LIFO und der Bericht fürs Finanzamt.

---

## v0.7.0.0 — 11. Oktober 2026

**Feinschliff: alles an seinem Platz, jede Lücke erklärt.**

- **Transaktionen aufklappen** wie Registerkarten: Details, Bearbeiten, Verlauf, Gegenstück
  suchen. Alles Weitere über „⋯“.
- **Suchen und filtern** nach Coin, Datum, Notiz, Adresse, Hinweis und mehreren Quellen
  oder Arten auf einmal. Was nicht passt, wird abgedunkelt.
- **Erfassen** im eigenen Fenster: Coin aus der Liste, Kopieren, Transfer mit „Von“ und
  „Nach“, und das Feld zeigt dir, wie viel du zu dem Zeitpunkt dort hattest.
- **Markieren**, was keinen Partner hat: Abgang an Fremde, an eine eigene Wallet oder
  verloren (z. B. Insolvenz); Eingang von eigener Wallet, außerhalb gekauft oder Ertrag.
- **Kartenkäufe** zählen als Einzahlung, auch bei Coinbase per Karte oder PayPal.
- **Quellen** aufgeräumt: Bestandsabgleich und Abruf einklappbar, Verbindungszustand auf
  einen Blick, Netzwerke ohne Anbindung (z. B. Optimism) für Einträge von Hand.
- **Bestände** mit Kursgraph und deinem Durchschnittspreis als Linie.
- **Kurse**: einzelnen Coin abrufen, Coins als wertlos ab einem Datum markieren.
- **Export** als Excel oder CSV, Dashboard mit „24 Std.“ und „7 Tage“, eigene Logos.
- **Warnungen**, wenn eine Börse den API-Schlüssel ablehnt (z. B. nach 90 Tagen abgelaufen),
  ein Abruf fehlschlägt oder der Rückblick der API ausläuft.
- **Behoben:** Die Veränderung im Dashboard zählte Einzahlungen als Gewinn; bei Coinbase wurde
  die Gebühr doppelt abgezogen.

**Als Nächstes:** Tracking rund: der fertige Container, Sicherung im Zeitplan, alles am
Handy geprüft.

---

## v0.6.0.0 — 5. Oktober 2026

**Was du besitzt, was es wert ist und was du verdient hast.**

- **Dashboard**: Gesamtwert, Verlauf seit dem ersten Vorgang mit dem eingezahlten Geld
  dahinter, Höchststand, Ergebnis gesamt, Verteilung auf deine Coins und Hinweise, was die
  Zahlen unsicher macht.
- **Bestände**: jeder Coin mit Menge, Einstand, Wert und Gewinn oder Verlust, dazu deine
  Futures-Positionen.
- **Lücken**: Wo Vorgänge fehlen und ab wann, mit einem Klick zu den passenden Transaktionen.
- **Je Handel**: Klappst du einen Kauf auf, siehst du, was genau dieser Kauf heute wert ist.
- **Futures**: Abgeschlossene Positionen stehen als je eine Zeile in den Transaktionen.
- **Finden statt Suchen**: Sortieren und Suchen in Beständen und Transaktionen, Coin und
  Quelle aus einer Liste mit Suchfeld.
- **Ronin** als neues Netzwerk.
- **Schöner**: Symbole für jede Art von Vorgang, Coin-Logos an den Beträgen, aufgeräumte
  Ansichten am PC und am Handy, kein Zoomen mehr am Handy.

**Als Nächstes:** Tracking rund machen: Verlauf der letzten 24 Stunden, Sicherung im
Zeitplan, Export als Tabelle, alles am Handy geprüft und der fertige Container.

---

## v0.5.1.0 — 4. Oktober 2026

**Filter für Transaktionen.**

- **Transaktionen filtern** nach Quelle, Art, Coin und Zeitraum. Eine ganze Wallet ist auf
  einmal wählbar.
- Netzwerke heißen jetzt mit ihrer Wallet, z. B. **„Tangem – Ethereum“**.

---

## v0.5.0.0 — 4. Oktober 2026

**Aus vielen Zeilen wird eine Wahrheit.**

- **Überweisungen als eine Zeile**: Schickst du Coins von einer Börse auf deine Wallet,
  steht das unter Transaktionen jetzt einmal da, mit „gesendet“, „angekommen“ und der
  Netzgebühr. Falsches trennst du, Fehlendes verbindest du selbst.
- **Offene Abgänge**: Was ohne Gegenstück weggegangen ist, siehst du unter „Offen“ und
  markierst es als „an Fremde“ oder „eigene Wallet, nicht erfasst“.
- **Spam und Staub**: Ein auf der Kurs-Seite ignorierter Coin verschwindet überall.
  Winzige Zugänge schlägt das Programm als Staub vor; du blendest sie mit einem Klick aus.
- **Bestandsabgleich**: Auf der Seite Quellen siehst du je Börse, Wallet und Netzwerk, ob
  der Kontostand zu deinen Vorgängen passt. Bei Gate.io und SafeTrade trägst du ihn von
  Hand ein.
- Die bisherige Liste gibt es weiter über den Schalter **Rohdaten**.

**Als Nächstes:** Portfolio und Gewinn/Verlust — was du besitzt, was es wert ist und was
du verdient hast. Dazu eine übersichtlichere Suche, ab wann bei einem Coin etwas fehlt.

---

## v0.4.0.1 — 4. Oktober 2026

**Kurse nachgebessert.**

- Coins mit sehr kleinem Kurs (z. B. SHIB, XEN) bekommen ihren Kurs aus einer genaueren Quelle.
- Ein beendeter Coin (z. B. FTM nach der Umstellung auf S) zeigt „bis <Datum>“ statt eines
  veralteten aktuellen Kurses.

---

## v0.4.0.0 — 4. Oktober 2026

**Jeder Coin hat seinen Preis.**

- **Seite Kurse**: alle deine Coins mit echtem Logo, aktuellem Kurs und Verlauf, auch für
  die Vergangenheit ab 2021. Der Kurs erneuert sich, solange die Seite offen ist, und
  blinkt bei einer Bewegung.
- **Du hast die Kontrolle**: Jede Zuordnung ist ein Vorschlag, den du prüfst und bestätigst.
  Eine Gegenprobe vergleicht zwei Quellen. Falsches korrigierst du selbst, mit Grund im
  Verlauf. Spam blendest du aus. Gleiche Coins mit verschiedenen Kürzeln führst du zusammen.
- **Euro oder Dollar**, umstellbar in den Einstellungen.
- **Jeden Morgen** werden die Kurse automatisch ergänzt.

**Als Nächstes:** Aus vielen Zeilen wird eine Wahrheit: Überweisungen zwischen deinen
Börsen und Wallets werden zusammengeführt, Spam ausgeblendet und der Bestand je Quelle
geprüft.

---

## v0.3.0.0 — 4. Oktober 2026

**Alle deine Quellen sind da.**

- **Börsen:** Coinbase, MEXC (per API und Datei), dazu Kraken und KuCoin als Archiv-Dateien.
- **16 Netzwerke** für deine Wallet: Ethereum, Polygon, Avalanche, Sonic, Cronos, BNB,
  Bitcoin, Litecoin, Solana (mit RENDER), VeChain (mit VTHO), Cardano, Sui, Polkadot,
  Hedera, Kaspa, Stellar. Drei brauchen einen kostenlosen Schlüssel, den du unter
  Einstellungen → Blockchain-Dienste einträgst.
- **Jeden Morgen um 4 Uhr** werden alle Quellen automatisch abgerufen. Oder du drückst
  **Alle abrufen**.
- **Von Hand erfassen:** für Börsen ohne API wie Gate.io oder SafeTrade, einzeln oder mit
  einer Excel-Vorlage, auch Futures.
- **Jeden Vorgang bearbeiten**, auch die aus einer Börse. Das Original bleibt erhalten, der
  Verlauf zeigt, was du geändert hast, und mit einem Tipp setzt du es zurück.
- Übersichtlicher: Quellen lassen sich einklappen, Zeiten mit Sekunden.

**Als Nächstes:** Kurse. Jede Münze bekommt ihren Preis, auch für die Vergangenheit, und ihr
echtes Symbol.

---

## v0.2.0.0 — 3. Oktober 2026

**Deine Daten kommen herein.**

- **Börsen anbinden**: API-Schlüssel eintragen, prüfen, abrufen — für Bitget samt Futures.
  Die API holt die ganze erreichbare Historie, danach nur noch Neues.
- **Wallets als Geräte**: z. B. „Tangem Cold Wallet“ anlegen und darunter die Netzwerke mit
  Adresse eintragen. Zum Start: Ethereum.
- **Dateien einlesen** mit Vorschau: Du siehst vorher, was neu ist und was die API schon
  abdeckt — es wird nichts doppelt gezählt. Jeder Import lässt sich zurücknehmen.
- **Transaktionen**: alle eingelesenen Vorgänge, am Handy als Karten, filterbar nach Quelle
  und Spot/Futures.
- **Sicherung jede Nacht** mit Probe-Wiederherstellung, einstellbar unter Einstellungen.

**Als Nächstes:** Coinbase, MEXC, Kraken, KuCoin und die übrigen Netzwerke, plus
automatischer Abruf jeden Tag.

---

## v0.1.0.0 — 3. Oktober 2026

**Die neue Oberfläche steht.** Noch ohne deine Daten, aber vollständig im Aufbau:

- **Erster Start ohne Terminal:** owncryptofolio richtet seine Datenbank selbst ein und
  führt dich durch einen Assistenten — Einrichtungscode, Passwort, Sicherungsschlüssel,
  Grundeinstellungen. Wie das geht: [Erster Start und Einrichtung](anleitungen/erster-start.md).
- **Drei Stile zur Wahl:** Nacht, Neon und Terminal, jeweils hell oder dunkel — unter
  *Einstellungen → Darstellung*, mit Vorschau.
- **Deutsch oder Englisch**, umschaltbar unter *Einstellungen → Sprache und Region*.
- **Am Handy** eine Leiste unten, am PC eine Seitenleiste.
- **Alle Seiten sind schon da.** Was noch nicht fertig ist, siehst du als „noch nicht
  verfügbar" mit dem Hinweis, wann es kommt.
- Passwort ändern, Sicherungsschlüssel anzeigen und den **Systemzustand** prüfen geht
  bereits.

**Als Nächstes:** deine Quellen anbinden — zuerst die Sicherung, dann Börsen, Wallets und
Datei-Import.

---

## Neustart — 2. Oktober 2026

**owncryptofolio wird neu aufgebaut.** Das Programm zieht auf den Unraid-Server um, der
rund um die Uhr läuft, und wird dabei von Grund auf neu programmiert. Deine Daten und alle
bisherigen Erkenntnisse bleiben erhalten.

Was sich für dich ändert:

- **Zuerst kommt der Überblick:** Quellen einlesen, zusammenführen, Kurse, Bestände,
  Gewinn und Verlust. Der **Steuerbericht kommt später** wieder dazu.
- **Alles im Browser von Anfang an:** Jede Funktion bringt ihre Seite und ihre
  Einstellungen gleich mit. Was noch nicht fertig ist, siehst du als „noch nicht
  verfügbar" — nichts ist versteckt.
- **Zuerst wird das Aussehen festgelegt**, damit alle Seiten zusammenpassen.
- **Futures sind dabei:** Deine Futures-Positionen von Bitget, MEXC und KuCoin werden mit
  eingelesen und getrennt von deinen Spot-Beständen angezeigt. Dadurch gehen auch die
  Bestände an diesen Börsen wieder auf.

Die Versionsnummern beginnen wieder bei `v0.1.0.0`. Die Einträge unten beschreiben den
alten Stand bis `v0.7.0.0`.

---

## v0.7.0.0 — 12. September 2026

**owncryptofolio ist jetzt durch ein Passwort geschützt.** Ohne das richtige Passwort
siehst du nur noch den Anmeldebildschirm. Einrichten brauchst du dafür einmalig ein
Terminal — danach nicht mehr. Wie das geht, steht in
[Quellen einrichten und einlesen](anleitungen/quellen.md).

**Der neue Reiter „Quellen" ersetzt das Terminal für fast alles andere.** Bisher
musstest du für jede Börse, jede Wallet-Adresse und jeden Datei-Import einen Befehl auf
der Kommandozeile eintippen. Jetzt geht das im Browser:

- **Börsen-Zugänge** anlegen, prüfen und wieder entfernen — inklusive einer Kontrolle,
  ob der eingetragene Schlüssel tatsächlich funktioniert. Wann zuletzt geprüft wurde
  und was dabei herauskam, bleibt an der Karte stehen.
- **Wallet-Adressen** hinzufügen und entfernen, mit sofortiger Prüfung, ob die Adresse
  zur gewählten Kette passt.
- **Ausfuhrdateien einlesen** — erst eine Vorschau, dann die Übernahme — und einen
  Import bei Bedarf **zurücknehmen**.
- **Ketten und Kurse abrufen** per Knopfdruck, mit Fortschrittsanzeige je Kette. Der
  Kettenabruf nimmt die Adressen aus dem Reiter selbst; was er bringt, steht je Kette
  als eigener Lauf in der Import-Liste und lässt sich dort zurücknehmen.

**Was noch nicht geht:** Der Knopf „Börsen abrufen" meldet bewusst einen Fehler — der
automatische Abruf direkt von der Börse kommt mit einem späteren Baustein. Bis dahin
bringst du Börsendaten über den Datei-Import herein oder prüfst mit „Verbindung prüfen",
ob dein Zugang funktioniert.

---

## v0.6.0.0 — 30. August 2026

**Der Steuerbericht ist da.** Unter **Steuer** steht je Jahr, was nach § 23 EStG
als privates Veräußerungsgeschäft anfällt und was nach § 22 Nr. 3 EStG als
sonstige Einkünfte. Beides mit eigener Freigrenze, beides getrennt — die
Freigrenze ist kein Freibetrag: Ein Euro darüber, und der ganze Betrag zählt.

Gerechnet wird mit **Losen**: Jeder Zugang behält sein eigenes Anschaffungsdatum
und seinen eigenen Einstand. Beim Verkauf wird nach FIFO oder LIFO entnommen —
du kannst umschalten. Eine Überweisung auf deine eigene Wallet verkauft nichts;
das Los wandert mit, die Haltefrist läuft weiter.

**Was der Bericht nicht kann, sagt er dir.** Neben der Zahl stehen gleichrangig
die ungeklärten Vorgänge, die Abgänge ohne deckenden Bestand und die Posten, die
auf einem geschätzten Einstand ruhen. Steht die Steuerzahl auf lückenhafter Geschichte,
sollst du das sehen, statt es zu erraten.

Den Bericht kannst du als **Excel** ausgeben und **festhalten**. Ein
festgehaltener Bericht merkt, wenn sich das Jahr später anders rechnet — weil du
eine Spam-Zeile bestätigt, eine Überweisung korrigiert oder das Verfahren
gewechselt hast. Dann sagt er dir, was sich geändert hat.

Was noch **nicht** geht: kein PDF (Excel steht), kein Verlustvortrag, und keine
Bestandsliste zum Jahresende für deinen Steuerberater.

---

## v0.5.0.0 — 29. August 2026

**Alles ist angebunden.** Siebzehn Blockchains, drei Börsen über ihre Schnittstelle und
sechs Ausfuhrdateien. Neu dabei sind **Kraken** und **KuCoin**.

Was noch fehlt: **BNB Smart Chain** (dafür gibt es keine kostenlose Quelle) und **Bitcoin
Cash**. Bei **VeChain und Solana** wird bisher nur die Hauptwährung gelesen — VTHO und RENDER
fehlen deshalb.

---

## v0.4.0.0 — 28. August 2026

**Überweisungen zwischen deinen eigenen Konten sind jetzt eine Zeile, nicht
zwei.** Schickst du Coins von der Börse auf deine Wallet, erkennt
owncryptofolio das und führt beide Seiten zusammen — **und keine Verbindung ist
geraten.** Was sich nicht belegen lässt, bleibt
offen und sichtbar, statt zu einem plausiblen Paar zusammengeschoben zu werden.

Neu ist auch die **Spam-Markierung**: Wertlose Token, die dir jemand
ungefragt geschickt hat, kannst du kennzeichnen — einzeln oder gleich für die
ganze Münze.

**Deine Rohdaten bleiben dabei unberührt.** Jede Korrektur, die du machst, legt
sich als eigene Ebene darüber. Nichts wird überschrieben, alles ist umkehrbar.

---

## v0.3.0.0 — 25. August 2026

**Du siehst, was deine Coins wert sind.** Die Startseite zeigt jetzt
Portfolio-Wert, Kostenbasis, Gewinn und Verlust sowie deinen Höchststand — dazu
einen Verlauf über die letzten Jahre, in den du hineinzoomen kannst. Alles
umschaltbar zwischen Euro und Dollar.

Neu ist auch die Seite **Kurse**: Dort steht je Coin, woher sein Kurs kommt. Prüfe die
Zuordnung einmal und bestätige sie — die Begründung steht unter
[Kurse und Währungen](konzepte/kurse-und-waehrungen.md). Kurz: Dutzende Münzen
teilen sich dasselbe Kürzel, und eine Verwechslung liefert keinen fehlenden
Kurs, sondern einen falschen.

**Was oben auf der Startseite steht, ist genauso wichtig wie die Zahlen.** Dort
sagt owncryptofolio dir, was es noch nicht weiß — zum Beispiel, dass Coins per
Überweisung abgeflossen sind, deren Ziel noch nicht angebunden ist. Solange das
so ist, ist dein Portfolio-Wert zu niedrig, und du sollst das wissen, statt es
zu erraten.

Was noch **nicht** geht: Überweisungen zwischen deinen eigenen Konten werden noch
nicht zusammengeführt, und Wallets sind noch nicht angebunden. Beides kommt.

---

## v0.2.0.0 — 25. August 2026

**Deine Transaktionen sind da.** Vorgänge aus Coinbase, MEXC und Bitget — eingelesen aus den
Ausfuhrdateien der Börsen und in einer Liste sichtbar.

Was du damit tun kannst:

- nach Quelle, Art und Asset filtern, nach Zeitpunkt, Quelle oder Art sortieren
- eine Zeile aufklappen und sehen, was die Börse **wirklich** geliefert hat
- auf dem Handy dieselbe Liste als Karten statt als gequetschte Tabelle lesen

**Dieselbe Datei zweimal einlesen schadet nicht.** owncryptofolio erkennt bereits bekannte
Vorgänge und überspringt sie — und sagt dir, wie viele es waren.

**Deine Daten sind gesichert.** Ein Befehl schreibt einen verschlüsselten Abzug, einen
lesbaren Export, und prüft sofort, ob sich der Abzug wirklich zurückspielen lässt.
Wie das geht, steht in [Sicherung einrichten und prüfen](anleitungen/sicherung.md).

Was noch **nicht** geht: Kurse, Werte, Gewinne. Und die Börsen werden noch nicht direkt
abgefragt — bisher liest owncryptofolio ihre Ausfuhrdateien. Beides kommt.

---

## v0.1.0.0 — 23. August 2026

Das Programm startet und ist mit deiner Datenbank verbunden. Mehr kann es noch nicht:
Es gibt keine Transaktionen, keine Kurse und keine Auswertung. Die Startseite zeigt dir,
ob die Verbindung steht — das ist der Zweck dieser Version.
