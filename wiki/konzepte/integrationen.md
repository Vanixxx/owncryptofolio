---
titel: Integrationen
aktualisiert: 2026-10-25
---

# Integrationen

Eine **Integration** ist eine Verbindung zu einer Quelle, aus der deine Transaktionen
kommen. Jede Quelle ist eine eigene Integration:

- **Exchanges** — Bitget, Coinbase, MEXC. Verbindung über einen API-Schlüssel, den du
  bei der Exchange erstellst. Kraken, KuCoin und gut 50 weitere Börsen laufen über eine
  gemeinsame Schnittstelle (ccxt); was noch niemand mit einem echten Konto geprüft hat, ist als
  **Beta** markiert ([Liste](../anleitungen/quellen.md)).
- **Blockchain-Netzwerke** — für deine Hardware-Wallet. Du gibst deine öffentliche
  Adresse an, das Programm liest die Bewegungen aus dem Netzwerk.
- **Datei-Import** — Excel- oder CSV-Dateien. Unterstützt werden die Ausfuhren von
  Bitget, Coinbase, MEXC, **Kraken** und **KuCoin**; bei Kraken die Ledger-Datei,
  bei KuCoin die BillingHistory-ZIP (die musst du nicht entpacken). Für jede andere Börse
  gibt es **Eigene Datei (CSV/Excel)**: Du ordnest die Spalten selbst zu.
- **Manuelle Eingabe** — Transaktionen, die du selbst einträgst, auch für eine Börse ohne
  API oder ein Netzwerk ohne Anbindung.

Auch Datei-Import und manuelle Eingabe sind Integrationen. Damit trägt **jede**
Transaktion die Information, woher sie stammt.

## Dieselbe Quelle mehrfach

Du kannst eine Integration mehrmals anlegen — zum Beispiel zwei Bitget-Konten oder
mehrere Wallet-Adressen im selben Netzwerk. Jede bekommt einen eigenen Namen und wird
getrennt geführt.

## API-Schlüssel: nur lesen

Wenn du einen API-Schlüssel bei einer Exchange erstellst, gib ihm **nur Leserechte**.
owncryptofolio handelt nicht und braucht keine Handelsrechte. Ein Schlüssel ohne
Handelsrechte kann selbst dann keinen Schaden anrichten, wenn er in falsche Hände gerät.

Deine Schlüssel werden verschlüsselt gespeichert.

## Der Bestandsabgleich

Das ist die nützlichste Funktion dieser Seite. Das Programm rechnet aus deinen
Transaktionen aus, wie viel von jedem Coin bei einer Quelle liegen müsste — und
vergleicht das mit dem, was die Quelle tatsächlich meldet.

**Stimmen beide überein, sind deine Transaktionen wahrscheinlich vollständig.**
Das ist der beste Selbsttest, den du hast.

Weicht der Bestand ab, meldet das Programm es dir. Häufige Ursachen:

| Ursache | Woran du es erkennst |
|---|---|
| Eine Transaktion fehlt | Die Abweichung entspricht ungefähr einer dir bekannten Bewegung |
| Ein Transfer wurde nicht erkannt | Bei zwei Quellen ist eine im Plus, die andere im Minus |
| Ein Bereich ist bewusst ausgelassen | Zum Beispiel Futures — die Abweichung wird dann **beziffert und benannt**, nicht verschwiegen |
| Gebühren fehlen | Kleine Abweichung, immer in dieselbe Richtung |
| Spam-Token | Abweichung bei einem Coin, den du nie gekauft hast |

Kleine Abweichungen sind normal — Börsen runden ihre Bestände. Als stimmig gilt deshalb ein
Unterschied bis **0,1 %** des gemeldeten Bestands, bei Euro, Dollar und Stablecoins zudem
bis **5 Cent**.

## Weiterlesen

- [Transaktionen zusammenführen](transaktionen-zusammenfuehren.md) — was passiert, wenn
  du zwischen zwei Integrationen überweist
- [Spam ausblenden](spam-ausblenden.md) — bei Blockchain-Integrationen der Normalfall
- [Wie deine Daten abgelegt werden](daten-in-owncryptofolio.md) — wohin das Eingelesene fließt
