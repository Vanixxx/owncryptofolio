---
titel: Kostenbasis, Gewinn und Verlust
aktualisiert: 2026-10-25
---

# Kostenbasis, Gewinn und Verlust

## Kostenbasis

Die **Kostenbasis** ist das, was du tatsächlich eingesetzt hast — der Kaufpreis
einschließlich aller Gebühren.

Beispiel: Du kaufst für 1.000 € Bitcoin und zahlst 2 € Gebühr. Deine Kostenbasis beträgt
1.002 €, nicht 1.000 €.

## Warum Gebühren zählen

Gebühren erhöhen deinen Einstandswert und mindern deinen Erlös. Lässt man sie weg, sieht
jeder Gewinn besser aus, als er ist — bei vielen kleinen Käufen summiert sich das
erheblich.

owncryptofolio rechnet Gebühren immer mit ein, auch wenn sie in einem Coin statt in Euro
abgerechnet wurden. In dem Fall wird die Gebühr mit dem Kurs zum Zeitpunkt der
Transaktion umgerechnet.

## Unrealisiert und realisiert

| Begriff | Bedeutung |
|---|---|
| **Unrealisierter Gewinn/Verlust** | Was deine **noch gehaltenen** Positionen aktuell wert sind, verglichen mit ihrer Kostenbasis. Ein Buchwert — er ändert sich mit jedem Kursausschlag. |
| **Realisierter Gewinn/Verlust** | Das Ergebnis der Positionen, die du **verkauft** hast. Steht fest und ändert sich nicht mehr. |

Beide werden in Euro oder Dollar **und in Prozent** angezeigt.

Für die Steuer zählt in aller Regel nur der **realisierte** Teil — solange du hältst, ist
nichts zu versteuern.

## DCA — dein Durchschnittspreis

**DCA** steht für *Dollar Cost Averaging*. Der DCA-Wert ist der durchschnittliche Preis,
den du für einen Coin bezahlt hast, über alle deine Käufe hinweg gewichtet.

Er beantwortet die Frage: **Ab welchem Kurs bin ich im Plus?**

Beispiel: Du kaufst 1 ETH für 2.000 € und später 1 ETH für 3.000 €. Dein DCA liegt bei
2.500 € — ab diesem Kurs ist deine Position insgesamt im Gewinn.

## Warum DCA und Steuerberechnung verschiedene Zahlen liefern

Das ist der Punkt, der am ehesten für Verwirrung sorgt — und es ist **kein Fehler**.

Der DCA fasst alle deine Käufe zu einem Durchschnitt zusammen. Die Steuerberechnung tut
das ausdrücklich **nicht**: sie verfolgt jeden einzelnen Kauf getrennt weiter und ordnet
einem Verkauf ganz bestimmte Käufe zu, je nach Verfahren.

Verkaufst du im Beispiel oben 1 ETH für 3.500 €, dann

- sagt der DCA: 1.000 € Gewinn (3.500 − 2.500),
- sagt die Steuerberechnung nach FIFO: 1.500 € Gewinn (der erste, günstigere Kauf zählt),
- sagt die Steuerberechnung nach LIFO: 500 € Gewinn (der letzte Kauf zählt).

Der DCA ist eine **Orientierungsgröße für dich**. Für die Steuer gilt die Losverfolgung —
siehe [Haltefrist und Steuer](haltefrist-und-steuer.md).

**Beide Werte können deutlich auseinanderliegen.** Das ist kein Fehler, aber die meisten
glauben zuerst den falschen Grund: **Oft kommt der größere Teil nicht von den zwei
Rechenwegen**, sondern davon, dass ein Teil deiner Münzen auf Wallets
liegt, die das Programm noch nicht lesen kann — der Steuerbericht führt sie deshalb
weiter, das Portfolio zeigt sie schon als verschwunden. Erst ein kleinerer, echter Rest
bleibt übrig, weil DCA und Losverfolgung unterschiedlich rechnen — und der schlägt mal in
die eine, mal in die andere Richtung aus, macht also keine der beiden Zahlen durchgängig
höher oder niedriger.

Portfolio und Steuerbericht bleiben deshalb bewusst getrennte Zahlen, statt sie künstlich
anzugleichen. Jeder erzeugte Steuerbericht (Excel) nennt auf dem Blatt „Zusammenfassung"
ausdrücklich, nach welchem Verfahren er rechnet, damit die beiden Zahlen nie verwechselt
werden.

## Wenn Vorgänge fehlen

Gibst du laut den Daten mehr ab, als du hattest, fehlt ein Zugang: ein Kauf vor dem ersten
Export, eine Einzahlung, ein Ertrag. owncryptofolio bucht dafür **keinen Gewinn**, denn
etwas zu verkaufen, das scheinbar nichts gekostet hat, sähe aus wie ein reiner Gewinn. Der
Teil steht stattdessen ohne Kostenbasis im Steuerbericht unter **Offene Punkte**. Wo und ab
wann er fehlt, zeigt die Seite Bestände unter **Lücken**, siehe
[Dashboard und Bestände](../anleitungen/portfolio.md).

## Staking-Erträge zählen nicht als reiner Gewinn

Bekommst du Coins als Staking-Ertrag, hast du dafür nichts bezahlt. Trotzdem setzt das
Programm sie **nicht mit null** an, sondern mit ihrem Marktwert zum Zeitpunkt des
Zuflusses.

Der Grund: Dieser Zufluss gilt bereits als Einkommen und wird als solches erfasst. Würde
er mit null in der Kostenbasis stehen, erschiene sein ganzer Wert später noch einmal als
Gewinn — ein Gewinn, den du nie gemacht hast.

## Portfolio-Höchststand

Der höchste Wert, den dein Portfolio je erreicht hat. Nützlich als Bezugspunkt: er zeigt
dir, wie weit du vom Höchststand entfernt bist.

## Was deine Zahlen verfälschen kann

**Ein nicht erkannter Transfer** ist die häufigste Ursache für falsche Zahlen. Er sieht
aus wie ein Verkauf plus ein Zukauf und erzeugt einen Gewinn, den es nie gab. Prüfe
deshalb Zeilen mit dem Hinweis **Kein Gegenstück** — siehe
[Transaktionen zusammenführen](transaktionen-zusammenfuehren.md).

**Eine Kurslücke** führt dazu, dass eine Position mit unbekanntem Wert in die Rechnung
eingeht. Auch das wird angezeigt.

## Weiterlesen

- [Kurse und Währungen](kurse-und-waehrungen.md) — woher die Werte kommen
- [Haltefrist und Steuer](haltefrist-und-steuer.md) — wie derselbe Verkauf steuerlich
  gerechnet wird
