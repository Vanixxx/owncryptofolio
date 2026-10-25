---
titel: Hilfe bei Problemen
aktualisiert: 2026-10-25
---

# Hilfe bei Problemen

Erste Anlaufstelle ist der [Systemzustand](systemzustand.md): Er zeigt Datenbank, Abrufe,
Sicherungen und das Protokoll. Die häufigsten Fälle:

## Die Seite ist nicht erreichbar

- Läuft der Container? `docker ps` bzw. der Docker-Reiter deines Systems.
- Stimmen Adresse und Port (`http://<rechner>:<port>`)?
- Nach einem Update braucht der Start etwa eine Minute.

## „Keine Verbindung zur Datenbank“

owncryptofolio läuft, erreicht aber PostgreSQL nicht. Den Datenbank-Server bzw. -Container
starten; die Seite versucht es selbst weiter und öffnet sich dann. Bleibt es dabei: Host, Port,
Benutzer und Passwort der Datenbank in der Container-Einstellung prüfen.

## Passwort vergessen

Im Terminal des Servers:

```
docker exec -it owncryptofolio python -m app.modules.auth reset-password
```

Das neue Passwort zweimal eingeben (mindestens 10 Zeichen), dann damit anmelden. Alle
bestehenden Anmeldungen enden dabei, auf jedem Gerät meldest du dich neu an. Wer Befehle im
Container ausführen darf, hat den Server ohnehin in der Hand — die Weboberfläche selbst bietet
bewusst keinen Weg am Passwort vorbei.

## Einrichtungscode gesucht

Nur nötig, wenn im Datenordner schon Schlüssel liegen. Er steht im Protokoll:
`docker logs owncryptofolio`. Jeder Neustart erzeugt einen neuen — den jüngsten nehmen
([Erster Start](erster-start.md)). Nach einem falschen Code dauert die Antwort absichtlich
etwas, nach zehn Fehlversuchen länger.

## Ein Abruf schlägt fehl

- **Schlüssel abgelehnt**: Börsen lassen API-Schlüssel ohne IP-Bindung oft nach 90 Tagen
  ablaufen. Neuen Schlüssel anlegen und unter [Quellen](quellen.md) eintragen.
- **Zeitüberschreitung**: Manche kostenlosen Explorer sind zeitweise langsam; der nächste Lauf
  holt es nach.
- Oben auf der Seite Quellen steht, welche Quelle betroffen ist und seit wann.

## Der Bestand weicht ab

Der [Bestandsabgleich](quellen.md#bestandsabgleich) vergleicht, was owncryptofolio rechnet,
mit dem, was Börse oder Netzwerk melden. Häufige Ursachen: ein fehlender Zeitraum (Datei
nachladen), ein nicht gelesener Vorgang (z. B. DEX-Handel, Staking — steht beim Netzwerk unter
„Nicht gelesen“), bei Cosmos-Netzwerken eine Geschichte, die älter ist als die Knoten
speichern. Fehlendes trägst du [von Hand](quellen.md#von-hand-erfassen) nach.

## Ein Coin hat keinen Kurs

In der [Statistik](statistik.md) unter **Coins ohne Kurs** antippen: Der Coin öffnet sich auf
der Seite [Kurse](kurse.md). Dort eine andere Quelle wählen, ihn als wertlos markieren oder die
Kurse beenden (bei einem umgestellten Coin).

## Eine Börse hat eine Buchung geändert

Steht oben auf der Seite Quellen als **Von der Quelle geändert** — du entscheidest, ob die neuen
Werte gelten ([Quellen](quellen.md#wenn-die-quelle-eine-buchung-ändert)).

## Noch etwas unklar?

Das Protokoll im [Systemzustand](systemzustand.md#protokoll) zeigt, was zuletzt geschah —
Adressen und Schlüssel darin sind gekürzt.
