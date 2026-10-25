---
titel: Transaktionen zusammenführen
aktualisiert: 2026-10-25
---

# Transaktionen zusammenführen

## Warum ein Transfer zweimal auftaucht

Wenn du Coins von einer Exchange auf deine Hardware-Wallet schickst, ist das **ein**
Vorgang — aber **zwei** Quellen berichten davon:

- Bitget meldet: „gesendet, 0,5 ETH"
- Das Ethereum-Netzwerk meldet: „erhalten, 0,4998 ETH"

Unverbunden sieht das aus wie ein Verkauf bei Bitget und ein Zukauf in der Wallet. Dein
Bestand wäre doppelt gezählt, dein Gewinn falsch, und dein Steuerbericht würde eine
Veräußerung ausweisen, die nie stattgefunden hat.

owncryptofolio erkennt solche Paare und macht daraus **eine** Zeile: einen Transfer.

## Wie das Programm die Paare findet

Zuerst über die **Transaktions-ID**, wenn beide Seiten dieselbe melden — das ist der
sichere Fall. Liefert eine Quelle keine brauchbare ID, sucht das Programm nach
**Zeitpunkt, Menge und Coin**: eine Sendung und ein Eingang, die zeitlich zusammenpassen,
dieselbe Menge betreffen und denselben Coin.

Die Mengen stimmen dabei nie exakt überein, weil das Netzwerk eine Gebühr abzieht. Das
Programm rechnet damit.

Kommen später neue Transaktionen dazu, werden vorhandene noch einmal geprüft. Das ist
wichtig, weil die beiden Hälften eines Transfers meist zu verschiedenen Zeitpunkten
importiert werden — erst die Exchange, Wochen später die Blockchain.

## Wo du das siehst

Die Seite **Transaktionen** zeigt standardmäßig die zusammengeführte Sicht. Ein Transfer
steht dort als eine Karte „Quelle → Ziel“ mit der gesendeten Menge, der angekommenen Menge
und der **Netzgebühr** (gesendet minus angekommen). Darunter steht, woran das Programm das
Paar erkannt hat: an der Transaktions-ID, an Menge und Zeit, oder weil du es verbunden hast.

Mit dem Schalter **Rohdaten** siehst du jede Zeile so, wie die Quelle sie geliefert hat.

Oben filterst du nach **Quelle** (eine Börse, eine ganze Wallet oder ein Netzwerk wie
„Hardware-Wallet – Ethereum“), nach **Art** (z. B. nur Transfers, Erträge oder
Futures-Positionen), nach **Coin** und nach **Zeitraum**. Quelle und Coin wählst du aus einer
Liste; tipp ein paar Buchstaben ins Suchfeld, um sie einzugrenzen.

Eine abgeschlossene **Futures-Position** ist eine Zeile: Ergebnis, Funding und Gebühren der
Position zusammen, die Buchungen dahinter aufklappbar. **Filter zurücksetzen** zeigt wieder
alles. Sortieren kannst du nach **Zeit** oder nach **Wert** (Euro zum Tageskurs), jeweils auf-
oder absteigend.

## Die Filter und Hinweise

| Filter / Hinweis | Bedeutung | Was du tun solltest |
|---|---|---|
| **Kein Gegenstück** | Etwas wurde gesendet, aber kein passender Eingang gefunden | Über **Aktionen → Gegenstück suchen** prüfen, oder markieren |
| **Mehrdeutig** | Mehrere Eingänge passen gleich gut, das Programm rät nicht | Gegenstück suchen und das richtige verbinden |
| **An Fremde** | Von dir markiert: ein echter Abgang (bezahlt, verschenkt) | Nichts |
| **Eigene Wallet, nicht erfasst** | Von dir markiert: ging an eine eigene Wallet, die owncryptofolio nicht kennt | Wallet später anlegen, dann verbindet es sich |
| **Staub** | Winziger Zugang, typisch für Spam-Werbung | Als Spam ausblenden, oder stehen lassen |
| **Spam (ausgeblendet)** | Ausgeblendet, zählt nirgends mit | Siehe [Spam ausblenden](spam-ausblenden.md) |
| „geliefert als …“ | Die Quelle nennt den Coin anders (NTGL statt NGL) | Nichts |

**„Kein Gegenstück“ ist keine Fehlermeldung**, sondern ein Hinweis auf deine Datenlage. Der häufigste
Grund ist harmlos: Du hast die Gegenseite noch nicht angebunden.

## Wenn du selbst eingreifen musst

Die Automatik trifft nicht jeden Fall. Unter **Aktionen** kannst du:

- **Gegenstück suchen** und verbinden, wenn das Programm den Zusammenhang nicht erkannt hat.
  Vorgeschlagen werden Eingänge bis 24 Stunden und 5 % Mengenunterschied.
- **Trennen**, wenn eine Verbindung falsch ist. Beide Hälften bleiben danach einzeln: Das
  Programm verbindet sie nicht von sich aus mit etwas anderem, nur du selbst über
  „Gegenstück suchen“. So ändert sich nichts unbemerkt zurück. Ein getrenntes Paar wird beim
  Suchen weiter angeboten, markiert mit „von dir getrennt“, damit du es rückgängig machen kannst.
- **Bearbeiten** und **Verlauf** wie in den Rohdaten.

Deine Entscheidungen bleiben erhalten, auch wenn Daten neu eingelesen werden — siehe
[Wie deine Daten abgelegt werden](daten-in-owncryptofolio.md).

## Was ein einzelner Handel gebracht hat

Klappst du einen Handel auf, steht dort, was **genau dieser** Kauf heute wert ist: bezahlt
(mit Gebühr), Wert heute, Kurs damals und heute, Gewinn oder Verlust. Bei einem Verkauf gegen
Euro oder Dollar steht der Erlös gegen das, was die verkauften Coins heute wert wären. Das
ist unabhängig vom Durchschnittspreis und von der Steuer; es beantwortet nur: Wie gut war
dieser eine Handel?

## Passt der Bestand?

Auf der Seite **Quellen** prüft der **Bestandsabgleich**, ob der Kontostand einer Börse oder
Wallet zu deinen Vorgängen passt. Eine Abweichung heißt: Es fehlen Vorgänge, siehe
[Quellen einrichten](../anleitungen/quellen.md#bestandsabgleich).

## Weiterlesen

- [Integrationen](integrationen.md) — der Bestandsabgleich zeigt dir, ob etwas fehlt
- [Kostenbasis, Gewinn und Verlust](kostenbasis-gewinn-verlust.md) — warum ein nicht
  erkannter Transfer deine Zahlen verfälscht
