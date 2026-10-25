---
titel: Eigene Integration bauen
aktualisiert: 2026-10-25
---

# Eigene Integration bauen

Eine neue Börse oder ein neues Netzwerk ist **ein Ordner** — ohne Eingriff ins übrige
Programm. owncryptofolio findet beim Start jeden Ordner unter `src/backend/integrations/`, der
eine `plugin.toml` enthält. Fehlt etwas oder wirft der Code einen Fehler, wird nur diese
Integration nicht geladen; den Grund nennt das
[Protokoll im Systemzustand](systemzustand.md#protokoll).

Die mitgelieferten Integrationen sind die besten Beispiele: `chain_stellar` (einfaches
Netzwerk), `chain_xrp` (eigenes JSON-RPC), `chain_dogecoin` (UTXO), `bitget_api` (Börse mit
Schlüssel), `bitget_file` (Datei-Import).

## Aufbau eines Ordners

```
src/backend/integrations/chain_beispiel/
├── __init__.py      # leer
├── plugin.toml      # was die Integration ist und kann
└── reader.py        # liest und wandelt um
```

Den Namen des Ordners wählst du frei (Konvention: `chain_<netz>`, `<börse>_api`,
`<börse>_file`). API und Datei derselben Börse sind **zwei** Ordner mit demselben `provider`.

## plugin.toml

```toml
[plugin]
name = "Beispiel"
author = "dein-name"
version = "1.0.0"
description = "Liest XYZ-Überweisungen einer Adresse über explorer.example (kostenlos)."
status = "beta"              # "tested" erst, wenn an einem echten Konto geprüft

[source]
provider = "beispiel"        # Schlüssel der Quelle, klein, ohne Leerzeichen
provider_name = "Beispiel"   # so steht sie in der Oberfläche
kind = "wallet"              # "wallet" (Netzwerk) oder "exchange"
channel = "chain"            # "chain", "api", "file" oder "manual"
provides_balance = true      # es gibt eine balance()-Funktion für den Bestandsabgleich
provides_id = true           # Zeilen tragen eine Transaktions-ID
not_read = ["NFTs"]          # was bewusst nicht gelesen wird — steht in der Oberfläche

[chain]                      # nur für channel = "chain"
native_asset = "XYZ"
decimals = 8
address_pattern = "^xyz1[0-9a-z]{38}$"   # regulärer Ausdruck für gültige Adressen
explorer = "https://explorer.example/api"
# service = "etherscan"      # braucht einen Dienst-Schlüssel (Einstellungen → Blockchain-Dienste)
# service_optional = true    # … der nur die Grenzen anhebt
```

Eine Börse mit API-Schlüssel beschreibt die Eingabefelder:

```toml
[credentials]
fields = ["api_key", "api_secret"]
secret = ["api_secret"]      # verdeckt angezeigt, verschlüsselt gespeichert
```

Bei `channel = "file"` nennen `expected_files = [...]` die Dateien, die der Nutzer hochlädt.

## reader.py

Je nach Kanal stellt die Datei diese Funktionen bereit:

| Kanal | Funktion | Bedeutung |
|---|---|---|
| `chain` | `fetch(address, since, progress=None, key=None)` | liefert Bewegungen ab `since` (oder alle) |
| `chain` | `balance(address, key=None, tokens=None)` | aktueller Bestand: Liste von `("spot", coin, menge)` |
| `api` | `fetch(credentials, since, progress=None)` | wie oben, mit den Feldern aus `[credentials]` |
| `api` | `balance(credentials)` | wie oben |
| `file` | `read(path, options=None)` | liest eine hochgeladene Datei |

`progress({"step": "…", "done": 1, "total": 3, "rows": 120})` zeigt den Fortschritt im
Live-Protokoll. Ein Netzwerkfehler wird als `chain.ChainUnavailable` gemeldet — der Abruf
schlägt dann fehl und läuft beim nächsten Mal erneut, statt still Daten auszulassen. Das gilt
auch für eine Historie, die mitten im Blättern abbricht, oder für eine Seitengrenze, die nicht
alles liefert: lieber ein Fehler als eine Lücke. Gespeichert wird erst, wenn `fetch` ganz
durchgelaufen ist. Lehnt ein Dienst den Schlüssel ab, melde `ChainUnavailable("HTTP 401")`
bzw. `"HTTP 403"` (macht `http_json` von selbst) — die App nennt das dann als abgelehnten
Schlüssel mit Verweis auf Einstellungen → Blockchain-Dienste.

## Das Datenformat: `Movement`

Jede Zeile ist eine `Movement` aus `app.modules.plugins.contract`:

| Feld | Inhalt |
|---|---|
| `timestamp` | Zeitpunkt (mit Zeitzone) |
| `kind` | `trade`, `send`, `receive`, `fiat_deposit`, `fiat_withdrawal`, `income`, `internal_transfer`, `migration`, `fee`, `realized_pnl`, `funding`, `futures_position`, `other` |
| `income_kind` | bei `income`: `staking`, `reward`, `interest` oder `airdrop` |
| `market` | `spot` (Standard) oder `futures` |
| `incoming_asset`, `incoming_amount` | was hereinkam |
| `outgoing_asset`, `outgoing_amount` | was hinausging |
| `fee_asset`, `fee_amount` | die Gebühr |
| `external_id` | Transaktions-ID — wichtig für Wiedererkennung und Transfers |
| `counterparty` | Adresse der Gegenseite |
| `comment`, `instrument`, `raw` | Notiz, Futures-Kontrakt, das Original als Dictionary |

Regeln, die owncryptofolio durchsetzt:

- **Beträge sind `Decimal`, niemals `float`.** Aus kleinsten Einheiten wird exakt umgerechnet
  (`chain.units(wert, stellen)`).
- Asset und Menge kommen immer **zusammen**; ein Handel hat beide Seiten.
- Nichts wird weggelassen: was die Integration nicht versteht, wird `other` — es erscheint in
  der Oberfläche und lässt sich von Hand einordnen.
- Dieselbe Zeile zweimal geliefert wird erkannt und nur einmal gespeichert (Fingerabdruck aus
  Zeit, Art, Beträgen und ID).

Hilfen in `app.modules.plugins.chain`: `transfer(...)` entscheidet aus Absender und Empfänger
selbst, ob `send`, `receive` oder `internal_transfer`; `since_only(...)` filtert nach
Zeitpunkt; `http_json(url, body=None, headers=None)` fragt eine Schnittstelle ab, mit
Wiederholung bei Überlastung. Für UTXO-Netzwerke verrechnet `mempool.netted(...)` Eingänge,
Wechselgeld und Gebühr.

## Testen

1. **Ohne Netz:** ein Test mit ausgedachten Antworten in der Form der Schnittstelle (Beispiele
   in `src/backend/tests/test_chains_nonevm.py`) — er prüft Umwandlung, Gebühren und
   Sonderfälle.
2. **Gegen eine öffentliche Adresse:** abrufen und die Summe aller Bewegungen mit dem
   Kontostand vergleichen, den `balance()` meldet. Stimmt sie auf die letzte Stelle, ist das
   Modell richtig.
3. **In der App:** eine Wallet anlegen, das Netzwerk hinzufügen, abrufen — der
   [Bestandsabgleich](quellen.md#bestandsabgleich) muss „stimmt“ zeigen.
4. Erst wenn das an einem **eigenen** Konto stimmt, `status = "tested"`.

Danach die neue Quelle in die Tabelle unter [Quellen](quellen.md#alle-quellen-auf-einen-blick)
eintragen — ein Test erinnert daran, wenn sie fehlt.

## Vollständiges Beispiel

Ein ausgedachtes Netzwerk „Beispiel“ (Coin `XYZ`, 8 Stellen), dessen Explorer
`GET /address/<adresse>/txs?page=N` mit `{"txs": [{"hash", "time", "from", "to", "value",
"fee", "ok"}]}` und `GET /address/<adresse>` mit `{"balance": "…"}` antwortet (Beträge in
kleinsten Einheiten als Text, Zeit in Unix-Sekunden):

```python
"""Beispiel through explorer.example (written from its docs, 2026-10-23)."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import datetime

from app.modules.plugins import chain
from app.modules.plugins.contract import Kind, Movement

API = "https://explorer.example/api"
NATIVE, DECIMALS = "XYZ", 8


def transactions(address: str) -> list[dict]:
    rows: list[dict] = []
    page = 1
    while True:
        body = chain.http_json(f"{API}/address/{address}/txs?page={page}")
        txs = (body or {}).get("txs")
        if not isinstance(txs, list):
            raise chain.ChainUnavailable("invalid answer")  # never guess on a broken answer
        rows += txs
        if not txs:
            return rows
        page += 1


def convert(address: str, txs: list[dict]) -> list[Movement]:
    out: list[Movement] = []
    for t in txs:
        sent = t["from"] == address
        fee = chain.units(t.get("fee") or 0, DECIMALS) if sent else None
        base = {"timestamp": chain.seconds(t["time"]), "external_id": t["hash"], "raw": t}
        if not t.get("ok"):
            if fee:  # failed: only the fee left the address
                out.append(Movement(kind=Kind.FEE, fee_asset=NATIVE, fee_amount=fee, **base))
            continue
        out.append(
            chain.transfer(
                sent=sent,
                received=t["to"] == address,
                asset=NATIVE,
                amount=chain.units(t["value"], DECIMALS),
                sender=t["from"],
                receiver=t["to"],
                fee=fee,
                fee_asset=NATIVE,
                **base,
            )
        )
    return out


def fetch(
    address: str,
    since: datetime | None,
    progress: Callable[[dict], None] | None = None,
    key: str | None = None,
) -> Iterator[Movement]:
    txs = transactions(address)
    if progress:
        progress({"step": "transactions", "done": 1, "total": 1, "rows": len(txs)})
    yield from chain.since_only(convert(address, txs), since)


def balance(address: str, key: str | None = None, tokens: dict | None = None) -> list:
    body = chain.http_json(f"{API}/address/{address}")
    return [("spot", NATIVE, chain.units(body.get("balance") or 0, DECIMALS))]
```

Und der Test dazu, ohne Netz (`src/backend/tests/test_beispiel.py`):

```python
from decimal import Decimal

from app.modules.plugins.contract import Kind


def test_beispiel_send_with_fee_receive_and_failed():
    from integrations.chain_beispiel import reader

    txs = [
        {"hash": "a", "time": 1, "from": "X", "to": "ME", "value": "150000000", "fee": "1000", "ok": True},
        {"hash": "b", "time": 2, "from": "ME", "to": "Y", "value": "50000000", "fee": "1000", "ok": True},
        {"hash": "c", "time": 3, "from": "ME", "to": "Y", "value": "1", "fee": "1000", "ok": False},
    ]
    got = reader.convert("ME", txs)
    assert [m.kind for m in got] == [Kind.RECEIVE, Kind.SEND, Kind.FEE]
    assert got[0].incoming_amount == Decimal("1.5")
    assert (got[1].outgoing_amount, got[1].fee_amount) == (Decimal("0.5"), Decimal("0.00001"))
```

Tests laufen in `src/backend` mit `uv run pytest -q tests/test_beispiel.py`, Formatierung und
Prüfung mit `uv run ruff format` und `uv run ruff check`.

## Checkliste (auch für eine KI, die eine Integration schreiben soll)

Gib einer KI diese Seite und die Dokumentation der Schnittstelle. Eine Integration ist fertig,
wenn:

1. der Ordner `src/backend/integrations/<name>/` mit `__init__.py`, `plugin.toml` und
   `reader.py` existiert und **nichts außerhalb** dieses Ordners geändert wurde (außer dem
   neuen Test und der Zeile in der Quellen-Tabelle);
2. `plugin.toml` alle Pflichtfelder hat (`[plugin]` name, author, version, description,
   status; `[source]` provider, provider_name, kind, channel; bei Netzwerken `[chain]`
   native_asset, decimals, address_pattern, explorer) — unbekannte Felder sind verboten;
3. `reader.py` die Funktionen des Kanals mit **genau diesen Namen und Parametern** hat
   (Tabelle oben) und für jede Zeile eine `Movement` liefert;
4. alle Beträge `Decimal` sind (`chain.units` aus kleinsten Einheiten, `Decimal(text)` aus
   Dezimaltext), nie `float`;
5. Gebühren nur der Absender trägt, eine fehlgeschlagene Transaktion nur ihre Gebühr ist,
   Unverstandenes `Kind.OTHER` wird und nichts verloren geht;
6. jede Zeile eine stabile `external_id` hat (Hash, bei mehreren Zeilen je Transaktion mit
   Zusatz: die erste behält den Hash, weitere bekommen `hash:2`, `hash:3` …, damit zwei gleiche
   Bewegungen in einer Transaktion zwei Zeilen bleiben);
7. eine kaputte oder fehlende Antwort `chain.ChainUnavailable` auslöst statt Daten
   auszulassen;
8. ein Test ohne Netz die Umwandlung prüft und `uv run pytest`, `uv run ruff check` und
   `uv run ruff format --check` ohne Fehler durchlaufen;
9. an einer öffentlichen Adresse **Summe aller Bewegungen = `balance()`** gilt — erst dann ist
   das Modell richtig;
10. `status = "beta"` bleibt, bis jemand es an einem eigenen Konto geprüft hat.

Was eine Integration ist und wie sie sich im Programm verhält: [Integrationen](../konzepte/integrationen.md).
