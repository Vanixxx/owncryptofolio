---
titel: Wie deine Daten abgelegt werden
aktualisiert: 2026-08-22
---

# Wie deine Daten abgelegt werden

owncryptofolio führt deine Transaktionen auf **zwei Ebenen**. Das ist der wichtigste
Punkt, um zu verstehen, was du in der Oberfläche siehst.

## Die Rohdaten

Alles, was hereinkommt, landet zuerst unverändert in den Rohdaten: jede Zeile genau so,
wie die Exchange, die Blockchain oder deine Datei sie geliefert hat. Diese Ebene wird
**nie verändert**. Nichts wird dort korrigiert, zusammengefasst oder gelöscht. Einzige
Ausnahme: Den jeweils letzten Datei-Import einer Quelle kannst du zurücknehmen, solange keine
Zeile daraus korrigiert oder ausgeblendet ist — dann verschwinden seine Zeilen wieder.

Die Rohdaten sind dein Beleg. Wenn du wissen willst, woher eine Zahl kommt, findest du
sie hier — im Originalzustand.

## Die Anzeige-Ebene

Aus den Rohdaten berechnet das Programm die Tabelle, die du tatsächlich benutzt. Hier
werden zusammengehörige Vorgänge verbunden, Spam ausgeblendet und Markierungen gesetzt.
Diese Ebene kannst du **korrigieren** — sie ist zum Arbeiten da.

## Warum die Trennung wichtig für dich ist

**Du kannst nichts kaputt machen.** Wenn du in der Anzeige-Ebene etwas falsch
zusammenführst oder ausblendest, sind deine Originaldaten davon unberührt. Das Programm
kann die Anzeige-Ebene jederzeit komplett neu aus den Rohdaten aufbauen.

**Deine Korrekturen bleiben erhalten.** Ein solcher Neuaufbau wirft deine manuellen
Eingriffe nicht weg — sie werden getrennt gespeichert und danach wieder angewendet.

**Regeln dürfen sich ändern.** Wenn später besser erkannt wird, welche Transaktionen
zusammengehören, musst du nichts neu importieren. Die Rohdaten liegen ja vor; es wird
nur neu gerechnet.

## Was das im Alltag bedeutet

- Du arbeitest fast immer in der **Anzeige-Ebene**.
- Die **Rohdaten** schaust du dir an, wenn eine Zahl dich stutzig macht und du wissen
  willst, was die Quelle wirklich geliefert hat: Schalter **Rohdaten** auf der Seite
  [Transaktionen](../anleitungen/transaktionen.md).
- Beide Ebenen kannst du exportieren.

## Weiterlesen

- [Transaktionen zusammenführen](transaktionen-zusammenfuehren.md) — was in der
  Anzeige-Ebene mit deinen Daten passiert
- [Integrationen](integrationen.md) — woher die Rohdaten kommen
