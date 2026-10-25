---
titel: Transaktionen
aktualisiert: 2026-10-25
---

# Transaktionen

Auf der Seite **Transaktionen** steht jeder Vorgang aus allen Quellen: Käufe, Verkäufe,
Ein- und Auszahlungen, Erträge, Gebühren und Futures. Hier findest du, prüfst, ergänzt und
korrigierst du deine Daten. Was du hier änderst, wirkt sofort auf Bestände und Dashboard.

Ein Transfer zwischen deinen eigenen Börsen und Wallets steht als **eine** Zeile da, nicht
als Abgang und Eingang getrennt. Warum, steht in
[Transaktionen zusammenführen](../konzepte/transaktionen-zusammenfuehren.md).

## Die Liste

<p>
  <img src="../bilder/details/tx-karte-handel.png" alt="Ein Handel" width="640">
  <img src="../bilder/details/tx-karte-transfer.png" alt="Ein Transfer zwischen Kraken und Ledger" width="640">
</p>

Jede Zeile ist eine Karte mit Art, Datum, den Beträgen (mit Coin-Symbol und ungefährem
Euro-Wert) und der Quelle. Kleine Zeichen sagen dir mehr:

| Zeichen | Bedeutung |
|---|---|
| ✋ **von Hand** | Diesen Vorgang hast du selbst erfasst. |
| ✏️ (Stift neben der Uhrzeit) | Ein Vorgang einer Quelle, den du korrigiert hast. |
| **kein Gegenstück** | Ein Abgang oder Eingang, zu dem die App keine andere Seite findet. |
| **Bestand negativ: …** | Nach diesem Vorgang ist der Bestand unter null: Davor fehlt etwas. |
| **Einzahlung per Karte (automatisch)** | Hier wurde mehr Geld ausgegeben, als an der Börse lag. Die App nimmt an, es kam per Karte. |
| **Staub** | Ein winziger, unaufgeforderter Eingang, oft Werbung. |
| **Kartenkauf ohne Euro-Betrag** | Die Börse liefert nur den Coin, nicht den bezahlten Betrag (Bitget). Trag ihn nach: **Bearbeiten** → Handel, bei *Abgegeben* den Euro-Betrag, **Per Karte bezahlt**. Sonst fehlt die Kartengebühr in den Kosten. |
| violetter Rahmen | ein Futures-Vorgang |

Bei einem **Handel** steht der Kurs, wie Börsen ihn schreiben: „Kurs 25.848 BTC/USDT“.

Oben stehen die Anzahl der Treffer und **Neueste zuerst** bzw. **Älteste zuerst**. Wie viele
Einträge eine Seite zeigt, wählst du daneben (**pro Seite**); am Ende der Liste holt **Mehr laden**
die nächsten, auch bei vielen Vorgängen mit demselben Zeitpunkt lückenlos. Die App merkt sich Filter und Stelle, wenn du
die Seite verlässt.

<p>
  <img src="../bilder/details/handy-kompakt.png" alt="Kompakte Liste am Handy" width="340">
</p>

**Kompakt** oder **Karten**: Kompakt zeigt eine Zeile je Vorgang (Art, Datum, Ort, was rein und
was raus ging); eine Futures-Position zeigt Paar, Long/Short und ihr Ergebnis. Futures-Einträge erkennst du am
lila Ring um das Symbol, wie am lila Rahmen in der Kartenansicht. Am PC (breiter Bildschirm) zeigt die kompakte
Zeile mehr: Uhrzeit, Orte mit Logo, Aus- und Eingang je mit Wert, Kurs und Gebühr, deine Notiz. Ein Antippen öffnet die Zeile als Karte mit allen Details, nochmal antippen macht
wieder eine Zeile daraus. Am Handy startet die kompakte Ansicht; deine Wahl wird gemerkt. Beim
**Auswählen** stehen immer Karten da.

Der Schalter **Rohdaten** zeigt die Zeilen so, wie die Quellen sie geliefert haben, ohne
Zusammenführen. Das brauchst du selten.

## Suchen und filtern

<p>
  <img src="../bilder/details/tx-filter.png" alt="Filter" width="640">
</p>

Am Handy klappst du die Filter mit **Filter** auf.

- **Suchen**: ein Coin, ein Name, eine Transaktions-ID, eine Adresse, eine Notiz oder ein
  Datum („17.06.2023“). Mehrere Wörter müssen alle passen; „bch|ltc“ findet das eine
  *oder* das andere.
- **Quelle**, **Art**, **Herkunft** (API, Datei, Blockchain, von Hand) und **Coin**: Du kannst
  jeweils mehrere wählen. Was zu deiner übrigen Auswahl nicht passt, ist abgedunkelt.
- **Hinweise**: nur die Zeilen mit einem bestimmten Zeichen, z. B. **Kein Gegenstück**,
  **Bestand negativ**, **Staub**, **Bearbeitet**, **Mit Notiz** oder **Markiert**. Die Zahl
  dahinter richtet sich nach deinen übrigen Filtern.
- **von / bis** und **Spot / Futures**.

**Filter zurücksetzen** hebt alles auf. **Export** speichert genau die angezeigte Liste als
Excel- oder CSV-Datei. Token-Namen und Notizen stehen darin immer als Text, nie als Formel.

## Eine Zeile öffnen

<p>
  <img src="../bilder/details/tx-details.png" alt="Eine geöffnete Transaktion" width="640">
</p>

Ein Tipp auf die Karte klappt sie auf. Oben stehen Reiter, am Handy wischst du sie seitlich:

- **Details**: Quelle, Herkunft, Transaktions-ID (bei Ketten ein Link zum Block-Explorer,
  bei einer Börse, wenn die andere Seite dieselbe ID trägt), Adressen, „Bestand danach“, deine
  **Notiz** (mit **Notiz hinzufügen**) und bei einem Transfer, wie er verbunden wurde.
- **Bearbeiten** bzw. **Transfer bearbeiten**: das Formular mit allen Werten.
- **Versionsverlauf**: jede Fassung mit dem, was sich geändert hat.
- **Steuer**: was der Vorgang steuerlich bedeutet, siehe [Steuerbericht](steuerbericht.md#steuer-bei-einer-einzelnen-transaktion).
- **Gegenstück suchen**: Vorschläge für einen Abgang oder Eingang ohne Partner.
- bei einem Transfer zusätzlich **Einzeltransaktionen**: Abgang, Eingang und Gebühren einzeln.

Rechts oben öffnet **⋯** alle Aktionen einer Zeile, ohne sie aufzuklappen.

## Korrigieren und zurücksetzen

Du kannst **jeden** Vorgang bearbeiten, auch einen von der Börse oder der Blockchain. Das
Original bleibt dabei immer gespeichert; deine Fassung gilt, bis du sie zurücknimmst.

- **⋯ → Bearbeiten**, Werte ändern, **Speichern**. Ändert sich nichts, entsteht keine neue
  Fassung.
- **⋯ → Versionsverlauf → Auf Original zurücksetzen**: Es gilt wieder, was die Quelle
  geliefert hat.
- **⋯ → Ausblenden** (Vorgänge einer Quelle) bzw. **Löschen** (deine eigenen): Der Vorgang
  zählt nicht mehr. Zurück holst du ihn über **Rohdaten** → **Ausgeblendete zeigen**. Bei einem
  Transfer nimmt **Transfer ausblenden/löschen** beide Seiten auf einmal heraus.

## Transfers

Die App erkennt einen Transfer selbst, wenn Abgang und Eingang zusammenpassen, am sichersten
über dieselbe Transaktions-ID. Wo das nicht reicht:

- **Verbinden**: Bei einem Abgang oder Eingang ohne Gegenstück → **Gegenstück suchen** und
  den passenden Vorschlag wählen. Oder oben **Auswählen**, Abgang und Eingang antippen, unten
  **Verbinden**.
- **Gebühr zuordnen**: Eine Gebühr, die die Börse getrennt bucht, gehört zum Transfer.
  Über die Gebühr → **Transfer suchen**, oder beim Auswählen Transfer und Gebühr antippen.
  Zuordnen lässt sich nur eine abgehende Buchung (Gebühr, Abzug, kleiner Abgang) der Börse oder
  Wallet einer der beiden Seiten, höchstens 2 Stunden vom Transfer entfernt und nicht schon Teil
  eines Transfers. **Lösen** nimmt sie wieder ab.
- **Transfer bearbeiten**: Datum und Uhrzeit einmal, dann Abgang, Eingang und Gebühren, jeweils
  mit Wallet oder Börse. Beim Abgang steht, wie viel zu diesem Zeitpunkt dort lag.
- **Trennen**: Die beiden Seiten gehören nicht zusammen. Sie stehen danach wieder einzeln und
  bleiben es: owncryptofolio verbindet sie nicht von selbst neu, nur du über **Gegenstück suchen**.
  Eine zugeordnete Gebühr steht danach wieder als eigene Zeile da.
- Ein Transfer verbindet immer **einen** Coin. Kam auf der anderen Seite etwas anderes an
  (z. B. BCH raus, USD rein), wurde dort umgetauscht: Trag den Eingang im gleichen Coin ein und
  dort einen Handel.

**Auswählen** hat unten eine Leiste mit **Alle im Filter auswählen**, **Auswahl aufheben** und
**Auswählen beenden**. Bei Staub-Vorschlägen bietet sie **Kein Staub** und **Als Spam
ausblenden** für alle gewählten.

## Was ohne Gegenstück bleibt: markieren

Nicht jeder Abgang hat ein Gegenstück bei dir. Sag der App, was passiert ist, über **⋯**:

**Bei einem Abgang:**

| Markierung | Wann | Wirkung |
|---|---|---|
| **An Fremde** | Du hast bezahlt oder verschenkt. | zählt wie ein Verkauf zum Tageskurs |
| **Eigene Wallet, nicht erfasst** | Die Coins liegen in einer Wallet, die nicht in owncryptofolio steht. | bleiben dein Bestand, Ort „außerhalb“ |
| **Verloren (z. B. Insolvenz)** | Das Geld ist weg, etwa bei einer Pleite oder einem Betrug. | der Einstand ist verloren, auch bei Euro oder Dollar |

**Bei einem Eingang:**

| Markierung | Wann | Wirkung |
|---|---|---|
| **Von eigener Wallet, nicht erfasst** | Die Coins waren schon deine. | kein Gewinn, sie kommen von „außerhalb“ zurück |
| **Gekauft (außerhalb, z. B. Karte)** | Du hast sie z. B. in der Wallet-App per Karte gekauft. | zählt als Einzahlung zum Tageswert |
| **Ertrag / Geschenk** | eine Belohnung, ein Airdrop, ein Geschenk | zählt als Ertrag zum Tageswert |

Kennst du den bezahlten Euro-Betrag, ist ein **Handel** genauer als „Gekauft
(außerhalb)“: **⋯ → Bearbeiten**, Art **Handel**, bei *Abgegeben* den Euro-Betrag und
**Per Karte bezahlt** anhaken.

**Markierung entfernen** macht es rückgängig.

## Einen Vorgang erfassen

Der runde **+** oben rechts öffnet **Vorgang hinzufügen**:

1. **Börse oder Wallet-Netzwerk** wählen.
2. **Spot** oder **Futures**, dann die **Art**, z. B. *Handel*, *Krypto-Einzahlung*,
   *Ertrag*, *Umbuchung* oder *Transfer (eigene Wallet/Börse)*.
3. **Datum** und **Uhrzeit** in deiner Ortszeit; die Doppelpunkte setzt die App selbst.
4. Die Beträge: **Erhalten**, **Abgegeben**, **Gebühr**. Den Coin wählst du aus der Liste oder
   tippst ihn ein. Beim Abgegebenen steht grau **max. …**: so viel lag zu diesem Zeitpunkt
   dort. **übernehmen** setzt genau diese Menge ein.
   Unter jedem Coin steht sein **Marktpreis** als Tageskurs des eingegebenen Datums (ohne
   Datum der aktuelle; die Uhrzeit spielt keine Rolle, die App kennt je Coin einen Kurs pro Tag) und was die Menge wert ist; bei Handel zusätzlich der **Kurs** aus
   Erhalten und Abgegeben.
5. **Speichern**.

Gut zu wissen:

- **Gebühr extra**: Wurden 83 USD ausgezahlt und 2,49 USD Gebühr berechnet, trägst du bei
  *Abgegeben* **83** ein und bei *Gebühr* **2,49**.
- **Gebühr im gekauften Coin**: *Erhalten* ist die Menge **vor** Abzug der Gebühr. Die App
  zeigt dir darunter, was nach der Gebühr ankommt.
- **Per Karte bezahlt**: Beim Kauf mit Euro oder Dollar anhaken, wenn das Geld direkt von der
  Bank kam. Dann zählt der ganze Betrag als Einzahlung.
- **Transfer (eigene Wallet/Börse)** hat **Von** und **Nach**. Startest du von einem Eingang
  ohne Gegenstück (**⋯ → Bearbeiten**, Art Transfer), steht *Nach* schon fest. Du wählst nur
  *Von*; der Eingang bleibt, wie er ist, und wird gleich verbunden.
- **Kopieren** (⋯) öffnet das Formular mit den Werten eines vorhandenen Vorgangs, auch eines
  Transfers.
- **Mit MCP geändert** (Hinweise): was z. B. Claude über MCP geändert hat, siehe
  [Claude anbinden](claude-anbinden.md#bearbeiten-claude-ändert-du-bestätigst).
- **Viele auf einmal**: **Importieren**: wähle zwischen
  - *Vorlage (alle Quellen)*: Vorlage herunterladen, in Excel ausfüllen, hochladen. Eine
    Vorschau zeigt zuerst, was nicht passt.
  - *Eigene Datei (CSV/Excel)*: den Export einer Börse direkt hochladen und die Spalten
    zuordnen — wie auf der Karte der Börse, siehe
    [Quellen](quellen.md#eigene-datei-csvexcel--für-jede-börse).
- **Ertrag im Futures-Konto** (z. B. eine Gutschrift der Börse) geht unter **Futures → Ertrag**.

## Verwandte Seiten

- [Transaktionen zusammenführen](../konzepte/transaktionen-zusammenfuehren.md)
- [Spam ausblenden](../konzepte/spam-ausblenden.md)
- [Dashboard und Bestände](portfolio.md), darin die Lücken
- [Quellen einrichten](quellen.md)
