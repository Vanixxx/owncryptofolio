---
titel: Kurse und Währungen
aktualisiert: 2026-10-25
---

# Kurse und Währungen

## Warum Kurse gespeichert werden

Um zu wissen, was dein Portfolio **heute** wert ist, genügt der aktuelle Kurs. Um zu
wissen, was ein Kauf **damals** gekostet hat, brauchst du den Kurs von damals — und den
liefert dir keine Börse rückwirkend auf Knopfdruck.

owncryptofolio legt deshalb eine eigene Kurshistorie an:

- **Laufend**: In einem einstellbaren Intervall werden die aktuellen Kurse aller Coins
  gespeichert, die du besitzt.
- **Rückwirkend**: Kommt ein Coin neu dazu, werden die Kurse bis zu deiner ersten
  Transaktion mit diesem Coin nachgeladen.
- **Zum Zeitpunkt jeder Transaktion**: Zu jeder Transaktion wird der damals gültige Kurs
  festgehalten.

Der letzte Punkt ist der entscheidende. Weil der Kurs bei der Transaktion hängt, kannst
du deine Anzeige später umstellen, ohne dass sich historische Bewertungen rückwirkend
verändern.

Trägst du eine Transaktion nach, die weiter zurückliegt als alles bisherige, wird die
Historie automatisch weiter zurück ergänzt.

## Euro oder Dollar

Du kannst die gesamte Anzeige zwischen **Euro und US-Dollar** umschalten — jederzeit,
auch nachträglich. Dafür speichert das Programm nicht nur Coin-Kurse, sondern auch
Wechselkurse (EUR/USD, USDT/EUR und so weiter), ebenfalls mit Historie.

Für die **Steuer** in Deutschland ist der Euro-Wert maßgeblich, unabhängig davon, was du
gerade anzeigen lässt.

## Woher die Kurse kommen

Kostenlose Quellen, keine Anmeldung nötig:

- **Yahoo Finance** für die meisten Coins, mit langer Historie.
- **Bitget** und **Binance** für Coins, die Yahoo nicht kennt.
- **CoinGecko** lässt sich auf der Seite Kurse je Coin als weitere Quelle hinzufügen.

In welcher Reihenfolge neue Coins gesucht werden, stellst du unter *Einstellungen →
Kursabruf* ein (**Standard-Rangfolge der Quellen**, voreingestellt Yahoo, Bitget, Binance).

Gerechnet wird über den Dollarkurs und den Euro-Referenzkurs der EZB. Das klingt
umständlicher als „gleich in Euro holen", ist aber vollständiger: Gegen Dollar führen die
Quellen deutlich mehr Coins als gegen Euro.

## Warum du Kurszuordnungen bestätigen musst

Auf der Seite **Kurse** steht je Coin, woher sein Kurs kommt — und ein Häkchen, mit dem
du es bestätigst. Das ist keine Förmlichkeit.

Ein Kürzel ist keine Identität. Bei den Kursanbietern tragen **Dutzende** Münzen
dasselbe Kürzel: `BTC` trifft auf elf, von denen eine Bitcoin ist und eine `batcat`
heißt. Wird die falsche erwischt, bekommst du keinen fehlenden Kurs — du bekommst einen
**falschen**. Ein fehlender Kurs fällt sofort auf. Ein falscher wandert unbemerkt in
Kostenbasis, Gewinn und Steuerbericht.

owncryptofolio schlägt deshalb vor und prüft dabei, ob die Reihe deinen Zeitraum
wirklich abdeckt. Bestätigen musst du.

**„bis …“** mit einem Datum neben einer Reihe heißt: Sie endet an diesem Tag. Das kann richtig
sein — MATIC und FTM wurden umgestellt und werden nicht mehr gehandelt. Es kann aber
auch ein Fehltreffer sein. Das kann nur ein Mensch unterscheiden.

## Was passiert, wenn es keinen Kurs gibt

Dann steht dort **kein Kurs** — und die Position geht nicht in den Portfolio-Wert ein.

Sie mit 0 anzusetzen wäre bequemer und falsch: Eine Null sähe aus wie ein Totalverlust
und ließe sich von einem echten nicht unterscheiden. Lieber eine sichtbare Lücke als
eine unsichtbare Falschaussage.

## Wenn ein Coin umgestellt wurde

Manche Coins gehen in einem anderen auf (AGIX wurde 2024 zu FET, FTM zu S). Die alte Reihe
lebt bei den Kursquellen oft weiter, nur handelt kaum noch jemand — die Kurse springen dann
wild hin und her. Mit **Kurse beenden** legst du den letzten Tag fest: bis dahin gilt die
Reihe, danach holt die App nichts mehr. Das ist etwas anderes als **wertlos**: ein wertloser
Coin zählt ab dem Tag mit 0 (der Verlust wird sichtbar), ein beendeter hat danach einfach
keinen Kurs.

Einen automatischen Filter gegen „unplausible“ Sprünge gibt es bewusst nicht: Bei Krypto
kann sich ein Kurs an einem Tag verdoppeln oder verdreifachen, und ein solcher Filter würde
genau dann echte Werte verwerfen.

## Tageskurse, nicht Minutenkurse

Bewertet wird mit dem **Tagesschlusskurs**. Ein Verkauf um 14:00 Uhr wird also mit dem
Kurs des ganzen Tages bewertet, nicht mit dem um 14:00.

Für die Anzeige ist das belanglos. Für die Steuer ist es eine Vereinfachung, und sie
steht deshalb im Bericht. Minutenkurse über vier Jahre und vierzig Coins wären über
hundert Millionen Datenpunkte für einen Unterschied, den niemand sieht.

Für die **Anzeige** gibt es zusätzlich feine Kurse: alle 5 Minuten für die letzten 31 Tage
und stündlich für 90 Tage. Daraus entstehen die kurzen Zeiträume im Dashboard und die
Kurven auf der Kursseite. In die Steuer gehen sie nicht ein.

## Wochenenden haben keinen amtlichen Eurokurs

Der Euro-Referenzkurs der EZB erscheint an Werktagen. Krypto handelt täglich.

Für einen Verkauf am Sonntag gibt es also keinen amtlichen Tageskurs. owncryptofolio
nimmt den letzten davor und **kennzeichnet** die Zeile als Näherung. Beides andere wäre
schlechter: Die Lücke zu lassen würde einen Vorgang verschweigen, der stattgefunden hat.
Den Freitagskurs stillschweigend als Sonntagskurs auszugeben, würde eine Genauigkeit
vortäuschen, die es nicht gibt.

## Stablecoins sind nicht konstant

USDT ist nicht per Definition genau ein Dollar. Der reale Kurs schwankt leicht. Das
Programm rechnet mit dem tatsächlichen Kurs, nicht mit einer Annahme — für die Steuer
kann dieser Unterschied eine Rolle spielen.

## Was eine Kurslücke bedeutet

Manchmal liefert keine Kursquelle einen Wert: bei sehr kleinen Coins, bei sehr alten
Zeitpunkten oder wenn ein Anbieter gerade nicht erreichbar ist.

Solche Lücken werden **angezeigt, nicht stillschweigend mit null gefüllt**. Ein fehlender
Kurs würde deinen Portfolio-Wert sonst unbemerkt zu niedrig ausweisen.

Findest du eine Kurslücke, wählst du auf der Seite [Kurse](../anleitungen/kurse.md) eine
andere Quelle (**Quelle hinzufügen**), markierst den Coin als wertlos oder beendest seine Kurse.

## Weiterlesen

- [Kostenbasis, Gewinn und Verlust](kostenbasis-gewinn-verlust.md) — was mit den Kursen
  gerechnet wird
- [Haltefrist und Steuer](haltefrist-und-steuer.md) — warum der Euro-Wert zum
  Transaktionszeitpunkt zählt
