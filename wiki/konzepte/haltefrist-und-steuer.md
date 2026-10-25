---
titel: Haltefrist und Steuer
aktualisiert: 2026-10-25
---

# Haltefrist und Steuer

> **owncryptofolio erzeugt eine Auswertung, keine Rechtsberatung.** Das Programm rechnet
> nach den Regeln, die du einstellst. Ob das Ergebnis für deine Situation richtig ist,
> klärst du mit deinem Steuerberater. Sonderfälle wie Staking-Erträge, Airdrops oder
> Verlustverrechnung sind steuerlich nicht immer eindeutig.

Die Auswertung richtet sich nach **deutschem Steuerrecht**.

## Jeder Kauf wird einzeln verfolgt

Für die Steuer genügt es nicht zu wissen, wie viel Bitcoin du besitzt. Es zählt, **wann
du welchen Teil davon gekauft hast** — denn davon hängen sowohl die Haltefrist als auch
der Gewinn ab.

owncryptofolio führt deshalb jeden Zugang einzeln: mit Datum, Menge und Einstandswert.
Verkaufst du, wird der Verkauf gegen diese einzelnen Zugänge verrechnet.

## FIFO oder LIFO

Welche Zugänge einem Verkauf zugeordnet werden, hängt vom Verfahren ab. Du kannst
umschalten:

| Verfahren | Bedeutung |
|---|---|
| **FIFO** (*first in, first out*) | Der **älteste** Kauf wird zuerst verkauft |
| **LIFO** (*last in, first out*) | Der **jüngste** Kauf wird zuerst verkauft |

**FIFO ist der Standard**, so liest es auch das BMF. LIFO kannst du zum Vergleich
einschalten (Einstellungen → Steuer oder direkt auf der Berichtsseite). Ob LIFO für deine
Erklärung zulässig ist, klärst du mit dem Steuerberater.

Die beiden Verfahren können zu unterschiedlichen Ergebnissen führen, beim Gewinn wie bei
der Haltefrist. Ein Beispiel steht unter
[Kostenbasis, Gewinn und Verlust](kostenbasis-gewinn-verlust.md).

Weil ein Wechsel des Verfahrens **alle** Ergebnisse verändert, wird das verwendete
Verfahren in jedem erzeugten Bericht vermerkt. So bleibt ein alter Bericht später
nachvollziehbar.

## Die Haltefrist von einem Jahr

Hältst du eine Position länger als ein Jahr, ist ihr Verkauf in Deutschland
üblicherweise steuerfrei. Gezählt wird nach deutschem Kalendertag: Gekauft am 1. März
2024, ist ein Verkauf am 1. März 2025 noch steuerpflichtig, ab dem 2. März steuerfrei.

Entscheidend: Die Frist gilt **je Zugang**, nicht je Coin. Du kannst denselben Coin
gleichzeitig in Positionen halten, von denen manche die Frist überschritten haben und
andere nicht.

## Die Tage-Anzeige

Unter **Bestände** siehst du beim Aufklappen eines Coins, **wie viel Prozent** schon
steuerfrei sind und **ab wann** der nächste Teil steuerfrei wird.

Den Überblick über **alle Coins** gibt der Reiter **Steuerfrei** im Steuerbericht: je Coin
die steuerfreie Menge und die in der Haltefrist, mit Wert und Gewinn/Verlust in deiner
Währung und dem nächsten Termin. Das Dashboard zeigt unter „Steuerfrei demnächst“, was in
den nächsten 30 Tagen frei wird.

Das ist keine Statistik, sondern eine Entscheidungshilfe: Wer kurz vor Ablauf der Frist
steht, hat einen guten Grund, mit dem Verkauf noch zu warten. Genau dafür ist die
Anzeige da.

## Die Freigrenze

Bleibt dein steuerpflichtiger Gewinn eines Jahres unter der Freigrenze, fällt keine Steuer
an. Zwei Dinge musst du dazu wissen:

**Es ist eine Frei*grenze*, kein Freibetrag.** Ein Euro darüber macht den **gesamten**
Gewinn steuerpflichtig, nicht nur den Teil oberhalb. Der Bericht zeigt dir je Jahr, ob
der Saldo unter der Freigrenze liegt.

**Der Betrag hängt vom Jahr ab.** Er lag lange bei 600 € und wurde ab 2024 auf 1.000 €
angehoben. Ein Bericht für ein älteres Jahr rechnet deshalb mit einem anderen Wert. Für
Erträge (Staking, Belohnungen) gilt eine eigene Freigrenze von 256 €.

Ein Balken im Bericht zeigt, wie weit die Freigrenze im Jahr ausgeschöpft ist. Ab 80 % im
laufenden Jahr erscheint ein Hinweis im Dashboard.

## Verluste vortragen

Bleibt in einem Jahr ein Verlust, geht er zuerst ins Vorjahr zurück, der Rest in die
Folgejahre — ohne Ablauf. Verrechnet wird er nur mit Gewinnen aus privaten
Veräußerungen, und nur in Jahren, deren Gewinn die Freigrenze erreicht. Die App rechnet das
als Vorschlag; maßgeblich ist der Bescheid des Finanzamts, dessen Wert du im Steuerbericht
einträgst.

## Wenn du Coins gegen Coins tauschst

Das ist der Fall, der am häufigsten übersehen wird. Tauschst du BTC gegen ETH — oder BTC
gegen USDT — dann ist das steuerlich **zweierlei zugleich**: Du hast BTC veräußert und ETH
angeschafft.

Das heißt: Auch ohne dass jemals Euro geflossen sind, kann ein steuerpflichtiger Gewinn
entstanden sein. Das Programm bewertet dafür beide Seiten mit dem Euro-Kurs des
Tauschzeitpunkts.

Wer viel über USDT-Paare handelt, erzeugt auf diese Weise laufend steuerlich relevante
Vorgänge.

## Staking-Erträge und Airdrops

**Staking-Erträge** werden bei Zufluss mit ihrem Marktwert erfasst. Für die Haltefrist
zählt der Ertrag als **eigener neuer Zugang** — er verlängert die Frist deines
vorhandenen Bestands nicht.

**Airdrops** werden eigens markiert. Wie sie zu behandeln sind, hängt davon ab, ob du
etwas dafür getan hast — das kann nur dein Steuerberater beurteilen, deshalb ist die
Behandlung einstellbar: *Einstellungen → Steuer →* **Airdrops bei Zufluss versteuern**
(voreingestellt aus).

## Was in die Berechnung eingeht

| Vorgang | Behandlung |
|---|---|
| Kauf, Verkauf, Tausch | Verkauf zum Euro-Wert des Zeitpunkts, der neue Coin mit diesem Wert gekauft |
| Transfer zwischen deinen Quellen, Umbuchung Spot ↔ Futures | **kein Verkauf**: Die Käufe wandern mit ihrem Datum und ihren Kosten mit |
| Umstellung (z. B. FTM → S, Fantom zu Sonic) | **kein Verkauf**: Kaufdatum und Kaufpreis gehen auf die neuen Coins über |
| Abgang „an Fremde“ (Zahlung) | Verkauf zum Euro-Wert des Zeitpunkts |
| Abgang „eigene Wallet, nicht erfasst“ | kein Verkauf, die Coins kommen mit ihrem Datum zurück |
| Abgang „verloren“ (Pleite, Betrug) | eigene Liste, **nicht** mit den Gewinnen verrechnet |
| Erträge, Eingang „Ertrag“ | Zufluss zum Euro-Wert (§ 22), danach ein eigener Kauf mit eigener Haltefrist |
| Kartenkauf mit Euro-Betrag | Kauf zum bezahlten Betrag, Kartengebühr eingeschlossen |
| Eingang „gekauft (außerhalb)“, Kartenkauf ohne Euro-Betrag | Kauf zum Marktwert, als **Kosten geschätzt** markiert: Trag den bezahlten Betrag nach (Bearbeiten → Handel, „Per Karte bezahlt“) |
| Futures | eigenes Blatt nach § 20 (Kapitalerträge) |
| Ausgeblendeter Spam | zählt nicht |

**Ein Transfer ist kein Verkauf.** Wird er nicht als solcher erkannt, erscheint er als
Verkauf. Deshalb vor dem Bericht die Hinweise **Kein Gegenstück** und **Bestand negativ**
prüfen — siehe [Transaktionen zusammenführen](transaktionen-zusammenfuehren.md).

### Je Wallet und Börse gerechnet

owncryptofolio führt die Käufe (Lose) **getrennt je Ort**: je Börsenkonto, je Wallet-Netzwerk
und dort getrennt nach Spot und Futures. Das entspricht der **walletbezogenen Betrachtung**,
die das BMF-Schreiben zu Kryptowerten beschreibt.

- Ein **Verkauf** greift nur auf die Lose zu, die **an diesem Ort** liegen — bei FIFO auf das
  älteste dort, nicht auf das älteste überhaupt.
- Ein **Transfer** zwischen deinen eigenen Orten ist kein Verkauf: Die Lose wandern mit, mit
  ihrem **ursprünglichen Kaufdatum** und den vollen Kosten. Die Haltefrist läuft also weiter.
- Die Netzwerkgebühr eines Transfers mindert nur die Menge, die Kosten bleiben beim Rest.

**Beispiel:** Im Januar 1 ETH bei Börse A gekauft, im März 1 ETH bei Börse B. Im Juni verkaufst
du 1 ETH bei B. Gerechnet wird mit dem **März-Kauf** (er liegt bei B) — bei einer Betrachtung
über alle Orte wäre es der Januar-Kauf. Hast du den Januar-ETH vorher von A nach B geschickt,
liegt er bei B, und FIFO nimmt ihn zuerst.

Darum ist es wichtig, dass Transfers als Transfers erkannt sind: Ein nicht verbundener
Transfer sieht aus wie ein Verkauf am einen und ein Kauf ohne Kosten am anderen Ort
(siehe [Transaktionen zusammenführen](transaktionen-zusammenfuehren.md)). Ob für dich auch
eine Betrachtung über alle Orte zulässig wäre, klärst du am besten mit deiner
Steuerberatung.

### Gebühren

Eine Gebühr zählt **einmal**, bei dem Vorgang, zu dem sie gehört (wie im BMF-Schreiben):

- beim **Kauf** mit Euro erhöht sie die Kosten,
- beim **Verkauf oder Tausch** mindert sie den Erlös, auch wenn sie im gekauften Coin
  abgerechnet wird (bei Bitget der Regelfall),
- wird sie in einem **dritten Coin** bezahlt (z. B. BNB), ist das zugleich ein kleiner
  Verkauf dieses Coins,
- die **Netzwerkgebühr** eines Transfers mindert nur die Menge; die Kosten bleiben beim
  Rest.

### Futures

Futures sind Termingeschäfte und gehören zu den Kapitalerträgen (§ 20 EStG, Anlage KAP).
Der Bericht weist Gewinne, Verluste, Funding und Gebühren getrennt aus, dazu einen
**Bonus der Börse** (gutgeschrieben minus verfallen). Ein solcher Bonus ist kein Ertrag
nach § 22, sondern gehört zum Futures-Ergebnis. Was das Futures-Konto an USDT ausgibt,
zählt nur hier, nicht zusätzlich als Verkauf nach § 23.

## Wenn dir Geschichte fehlt

Verkaufst du Coins, für die kein Kauf in deinen Daten steht, kann owncryptofolio dafür
keinen Gewinn ausrechnen. Diese Mengen stehen unter **Offene Punkte**, mit dem Erlösanteil,
der auf sie entfällt, und **ohne** Kostenbasis — die ist unbekannt, nicht null. Der Weg,
das zu schließen, sind die Daten: fehlende Ausfuhren nachladen, Transfers verbinden,
Abgänge markieren.

## Die Berichte

Der Bericht entsteht **pro Jahr**, als Ansicht, als **Excel** mit allen Einzelposten und
als **PDF**-Zusammenfassung. Jeder nennt sein Verfahren und seine Einstellungen. Wie du
ihn erstellst, steht in der Anleitung [Steuerbericht](../anleitungen/steuerbericht.md).

**Ein Bericht ist ein Dokument, keine Ansicht.** Mit **Festhalten** speicherst du den
Stand eines Jahres. Ändert sich später etwas, das dieses Jahr betrifft, steht beim
festgehaltenen Bericht **geändert** — auch wenn die Ursache eine Korrektur in einem
**früheren** Jahr ist (ein Kauf aus 2021 trägt die Kosten eines Verkaufs 2024). Was daraus
folgt, entscheidest du mit deinem Steuerberater.

## Weiterlesen

- [Kostenbasis, Gewinn und Verlust](kostenbasis-gewinn-verlust.md) — warum DCA und
  Steuerberechnung verschiedene Zahlen liefern
- [Kurse und Währungen](kurse-und-waehrungen.md) — warum der Euro-Wert von damals zählt
