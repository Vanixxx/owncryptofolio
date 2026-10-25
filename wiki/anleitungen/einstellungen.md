---
titel: Einstellungen
aktualisiert: 2026-10-25
---

# Einstellungen

Unter **Einstellungen** (am Handy über **Mehr**) liegen alle Bereiche untereinander; jeder
lässt sich auf- und zuklappen, die App merkt sich, welche offen sind. Änderungen gelten sofort.

## Darstellung

<p>
  <img src="../bilder/details/einst-darstellung.png" alt="Darstellung" width="640">
</p>

Alle Stile im Vergleich: [Bilder](../bilder.md#stile).

- **Stil**: Nacht, Neon, Terminal, Graphit, Rosé, Hoher Kontrast, Amethyst, Sand und iOS
  (Glasflächen). Jede Kachel zeigt eine kleine Vorschau.
- **Farbe**: zu jedem Stil eine eigene Akzentfarbe (Petrol, Blau, Lila, Bernstein, Grün, Rosé,
  Rot) oder **Standard**, die Farbe des Stils.
- **Thema**: hell, dunkel oder wie das Gerät (**System**).

## App-Icon

Das Symbol für den Home-Bildschirm des Handys, zugleich Symbol im Browser-Tab und oben links.
Ein neues gilt beim nächsten Hinzufügen — siehe [Auf dem Handy](handy.md).

## Sprache und Region

- **Sprache**: Deutsch oder Englisch. Steuerbericht und Herkunftsnachweis bleiben deutsch.
- **Anzeigewährung**: Euro oder Dollar. Derselbe Schalter steht oben rechts auf den Seiten;
  die Steuer rechnet immer in Euro ([Kurse und Währungen](../konzepte/kurse-und-waehrungen.md)).
- **Zeitzone**: für Uhrzeiten und für die Frage, an welchem Tag ein Vorgang liegt.

## Sicherheit

Das Passwort ändern: altes eingeben, neues (mindestens 10 Zeichen). Danach
sind alle anderen Anmeldungen (andere Geräte, andere Browser) beendet; dieser Browser bleibt
angemeldet. Vergessen? Siehe
[Hilfe bei Problemen](hilfe.md#passwort-vergessen).

## Automatischer Abruf

<p>
  <img src="../bilder/details/einst-abruf.png" alt="Automatischer Abruf" width="640">
</p>

**Täglich abrufen** (Standard: an, 04:00 Uhr): einmal täglich zur gewählten Uhrzeit werden alle Börsen mit API-Schlüssel und alle
Wallet-Netzwerke abgerufen. Einzelne Quellen schaltest du auf der Seite [Quellen](quellen.md)
ab.

## Kursabruf

- **Kurse täglich abrufen** zur gewählten Uhrzeit (Standard 04:30 Uhr): die Kurshistorie wird
  ergänzt.
- **Aktuelle Kurse**: wie oft die Tageskurse nachgeführt werden (aus, alle 5, 15, 30 oder
  60 Minuten; Standard 5).
- **Standard-Rangfolge der Quellen**: in welcher Reihenfolge neue Coins ihren Kurs suchen.
  Bereits bestätigte Coins bleiben, wie sie sind — einzeln änderst du das auf der Seite
  [Kurse](kurse.md).
- **Unbestätigte neu vorschlagen**: alle noch nicht bestätigten Coins bekommen nach der
  aktuellen Rangfolge einen neuen Vorschlag, die Kurse werden gleich geholt.

## Steuer

<p>
  <img src="../bilder/details/einst-steuer.png" alt="Steuer" width="640">
</p>

- **Verfahren**: FIFO (älteste zuerst, Standard) oder LIFO. Angewendet wird es **je Wallet und Börse**
  ([warum](../konzepte/haltefrist-und-steuer.md#je-wallet-und-börse-gerechnet)).
- **Airdrops bei Zufluss versteuern**: ob ein Airdrop als Einkommen zählt (Standard: aus).
- **Kopf der Berichte (PDF und Excel)**: **Name** und **Anschrift** oben im
  [Steuerbericht](steuerbericht.md) und im Nachweis der [Mittelherkunft](mittelherkunft.md), die
  **Steuernummer** nur im Steuerbericht. Alles freiwillig; leere Felder lässt der Bericht weg.

Mehr dazu: [Haltefrist und Steuer](../konzepte/haltefrist-und-steuer.md).

## Blockchain-Dienste

<p>
  <img src="../bilder/details/einst-dienste.png" alt="Blockchain-Dienste" width="640">
</p>

Manche Netzwerke brauchen einen kostenlosen Schlüssel eines Blockchain-Dienstes (z. B.
Etherscan für Arbitrum, Linea, Mantle, Blast, Sonic; NodeReal für BNB Smart Chain), bei anderen
hebt er nur die Grenzen an (TronGrid für Tron, toncenter für TON). Die Karte zeigt, wofür jeder
gebraucht wird, und führt zur Registrierung.

## Claude (MCP) und API (JSON)

Zwei getrennte Zugänge mit eigenen Tokens: [Claude anbinden](claude-anbinden.md) und
[API](api.md).

## Sicherung

<p>
  <img src="../bilder/details/einst-sicherung.png" alt="Sicherung" width="640">
</p>

Zeitplan, wie viele Tages- und Monatssicherungen bleiben, „Jetzt sichern“, der
Wiederherstellungsschlüssel und das Zurückspielen: [Sicherung](sicherung.md).
