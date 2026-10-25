---
titel: Steuerbericht
aktualisiert: 2026-10-25
---

# Steuerbericht

Unter **Berichte** steht die Steuerauswertung eines Jahres nach deutschem Recht. Was
dahinter steckt (FIFO, Haltefrist, Freigrenzen, Gebühren), erklärt
[Haltefrist und Steuer](../konzepte/haltefrist-und-steuer.md).

> Eine Auswertung, keine Steuerberatung. Prüfe das Ergebnis mit deinem Steuerberater.

## Vorher: die Daten prüfen

Der Bericht ist nur so gut wie die Transaktionen. Auf **Transaktionen** unter
**Hinweise** sollten **Kein Gegenstück** und **Bestand negativ** leer sein, und unter
**Bestände → Lücken** sollte nichts offen stehen.

## Den Bericht ansehen

Oben im PDF und im Excel stehen, wenn eingetragen, dein Name, deine Anschrift und deine
Steuernummer (**Einstellungen → Steuer → Kopf der Berichte**). Ein festgehaltener Bericht
behält den Kopf, der beim Festhalten galt.

Gerechnet wird **je Wallet und Börse**: Ein Verkauf greift auf die Käufe an diesem Ort zurück,
Transfers nehmen ihr Kaufdatum mit — Einzelheiten und ein Beispiel unter
[Haltefrist und Steuer](../konzepte/haltefrist-und-steuer.md#je-wallet-und-börse-gerechnet).

1. **Berichte** öffnen. Gewählt ist das letzte abgeschlossene Jahr; oben wählst du ein
   anderes.
2. **FIFO** oder **LIFO**: FIFO ist der Standard. LIFO zeigt dir zum Vergleich, was das
   andere Verfahren ergäbe. Den Standard stellst du unter **Einstellungen → Steuer** ein.
<p>
  <img src="../bilder/details/steuer-23.png" alt="§ 23 EStG" width="348">
  <img src="../bilder/details/steuer-ertraege.png" alt="§ 22 Nr. 3 EStG" width="348">
</p>

3. Die Karten:

| Karte | Was sie zeigt |
|---|---|
| **Private Veräußerungen (§ 23 EStG)** | Gewinne und Verluste aus Verkäufen innerhalb eines Jahres nach dem Kauf, den Saldo und ob er unter der Freigrenze liegt (600 € bis 2023, 1.000 € ab 2024) |
| *(bei beiden)* | ein Balken, wie weit die Freigrenze ausgeschöpft ist: ab 80 % gelb, ab der Grenze rot; im Dashboard erscheint dann ein Hinweis |
| **Verlustvortrag § 23** | was aus Verlusten früherer Jahre übrig ist: Vortrag zu Jahresbeginn, Verrechnung, Rücktrag, Verlust des Jahres, Vortrag zum Jahresende; **Alle Jahre** zeigt die Entwicklung. Den Wert aus dem Bescheid des Finanzamts trägst du hier ein (siehe unten) |
| **Erträge (§ 22 Nr. 3 EStG)** | Staking, Belohnungen und als „Ertrag“ markierte Eingänge, mit der Freigrenze von 256 € |
| **Futures (§ 20 EStG)** | Gewinne, Verluste, Funding und Gebühren getrennt, für die Anlage KAP |
| **Verluste durch Pleite oder Betrug** | was du als „verloren“ markiert hast, mit den Kosten der verlorenen Coins; nicht verrechnet |

<p>
  <img src="../bilder/details/steuer-verkaeufe.png" alt="Reiter Verkäufe" width="640">
</p>

4. Darunter die Einzelposten in Reitern:
   - **Verkäufe**: jeder Verkauf je Kauf, mit Kaufdatum, Tagen, Erlös, Kosten und
     Gewinn. **Nur innerhalb der Haltefrist** blendet die steuerfreien aus;
     **Futures-Konto zeigen** zeigt die kleinen USDT-Bewegungen des Futures-Kontos.
   - **Erträge**, **Futures**, **Verluste**.
   - **Offene Punkte**: Mengen ohne erfassten Kauf. Steht hier etwas, fehlen Daten.
   - **Je Quelle**: Gewinne und Verluste je Börse oder Wallet.
   - **Bestandsveränderungen**: je Börse/Wallet und Coin der Bestand am 01.01., Zufluss,
     Abfluss, Bestand am 31.12. und sein Wert.
   - **Bestand 31.12.**: was am Jahresende lag, mit Kaufdatum, Kosten und ab wann
     steuerfrei.
   - **Steuerfrei**: Stand **heute**, egal welches Jahr oben gewählt ist. Je Coin, wie viel
     schon über ein Jahr gehalten wird (steuerfrei verkaufbar) und wie viel noch in der
     Haltefrist liegt, jeweils mit Wert und Gewinn/Verlust in deiner Anzeigewährung
     (Einstellungen), dazu wann der nächste Teil frei wird. Unten die Summen.
   - **Ausfüllhilfe** (ganz hinten): welche Summe in welche Zeile der Anlage SO und der
     Anlage KAP gehört (Zeilennummern für 2024; in anderen Jahren im Formular nachsehen).

<p>
  <img src="../bilder/details/steuer-steuerfrei.png" alt="Reiter Steuerfrei" width="640">
  <img src="../bilder/details/steuer-ausfuellhilfe.png" alt="Reiter Ausfüllhilfe" width="640">
  <img src="../bilder/details/steuer-bestand.png" alt="Reiter Bestand 31.12." width="500">
</p>

## Verlustvortrag und Bescheid

Verluste aus privaten Veräußerungen darfst du nur mit Gewinnen aus privaten Veräußerungen
verrechnen. Die App rechnet einen **Vorschlag**: Ein Verlust geht zuerst ein Jahr zurück, der
Rest in die Folgejahre. Verrechnet wird nur mit Gewinnen eines Jahres, die die Freigrenze
erreichen — ein Gewinn darunter ist ohnehin steuerfrei und lässt den Vortrag stehen.

Verbindlich ist, was das Finanzamt im **Feststellungsbescheid** festhält. Trag den Betrag
zum 31.12. eines Jahres mit **Wert aus dem Bescheid eintragen** ein (gern mit Notiz, z. B.
dem Datum des Bescheids). Ab dann rechnet die App mit diesem Wert weiter und zeigt, falls
es eine gibt, die Abweichung zu ihrer eigenen Rechnung. Hattest du schon vor deinem ersten
Jahr in der App einen Verlustvortrag, trägst du ihn im ersten Jahr unter **Vortrag aus
früheren Jahren** ein.

Excel und PDF enthalten den Vortrag des Jahres in der Zusammenfassung und alle Jahre im
Blatt **Verlustvortrag**.

## Für den Steuerberater

**Beispiel:** [Steuerbericht 2025 als PDF](../beispiele/steuerbericht-2025.pdf) — aus den
Beispieldaten (erfundenes Portfolio), so wie die App ihn erzeugt.

- **Excel**: alle Einzelposten auf eigenen Blättern, dazu eine Zusammenfassung mit
  Verfahren und Einstellungen.
- **PDF**: die Zusammenfassung auf der ersten Seite, danach dieselben Tabellen wie im
  Excel (Verkäufe, Erträge, Futures, Verluste, Offene Punkte, Bestand 31.12.).

Die Spalte **Kosten geschätzt** (im PDF ein Sternchen * am Kostenbetrag mit Fußnote unter
der Tabelle) steht auf „ja“, wenn für die verkauften Coins kein Kauf in
den Daten steht, etwa bei einem Eingang ohne Gegenstück. Als Kosten gilt dann ersatzweise
ihr Marktwert beim Eingang.

Beide nehmen das oben gewählte Jahr und Verfahren. Text von außen (etwa Token-Namen aus
Airdrops oder Notizen) steht im Excel immer als Text da, nie als Formel.

## Festhalten und Versionsverlauf

Jede Fassung hat ein Feld **Kommentar** (steht dann auch in ihrer ersten Zeile) und lässt sich
mit **Fassung löschen** wieder entfernen; deine Transaktionen bleiben dabei unberührt.

**Festhalten** speichert den Stand des Jahres mit allen Einzelposten und erzeugt dabei
gleich **PDF** und **Excel**. Beide bleiben so, wie sie beim Festhalten waren, und du
lädst sie im Versionsverlauf jederzeit wieder herunter. Du kannst eine
**Notiz** dazuschreiben, z. B. „an den Steuerberater“. Halte den Bericht fest, den du
abgibst.

Unter **Versionsverlauf** stehen alle festgehaltenen Fassungen des Jahres, die neueste
oben, jeweils mit **unverändert** oder **geändert**. „Geändert“ heißt: Seitdem hat sich
etwas geändert, das dieses Jahr betrifft, etwa eine Korrektur, ein Nachimport oder ein
verbundener Transfer. Auch eine Korrektur in einem früheren Jahr kann das sein.

- **Mit jetzt vergleichen** zeigt, was sich seit dieser Fassung geändert hat.
- **Mit vorheriger Fassung vergleichen** stellt zwei festgehaltene Fassungen
  gegenüber.

Der Vergleich zeigt zuerst die Kennzahlen mit damals, jetzt und Differenz. Darunter
stehen alle Vorgänge, die **neu**, **entfallen** oder **geändert** sind, jeweils mit Menge
und Betrag vorher → nachher.

## Steuer bei einer einzelnen Transaktion

Auf **Transaktionen** hat jede Zeile beim Aufklappen den Reiter **Steuer**, auch über
**⋯ → Steuer**:

- **Verkauf oder Tausch**: aus welchen Käufen verkauft wurde, mit Kaufdatum, Tagen,
  Erlös, Kosten und Gewinn, getrennt nach „innerhalb der Haltefrist“ und „steuerfrei“.
- **Kauf**: das neue Los und **was daraus wurde**: noch gehalten (wo, steuerfrei nach
  dem …), später verkauft (mit Gewinn) oder verloren.
- **Transfer**: „kein Steuervorgang“ und welche Käufe mit ihrem Datum mitgewandert sind.
- **Ertrag**, **Futures**, **Verlust**: die Zuordnung zu § 22, § 20 oder zur Verlustliste.

## Haltefrist in den Beständen

Unter **Bestände** klappst du einen Coin auf. Bei **Haltefrist** steht, wie viel Prozent
schon länger als ein Jahr gehalten werden, und ab wann der nächste Teil steuerfrei ist.
Gut zu wissen, bevor du verkaufst.

## Verwandte Seiten

- [Haltefrist und Steuer](../konzepte/haltefrist-und-steuer.md)
- [Transaktionen](transaktionen.md), darin das Markieren von Abgängen und Eingängen
