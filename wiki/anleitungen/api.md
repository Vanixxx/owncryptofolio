---
titel: API (JSON)
aktualisiert: 2026-10-25
---

# API (JSON)

owncryptofolio gibt deine Daten auch als **einfache Web-Adressen** heraus, die ein anderes
Programm abfragen kann: ein Widget am Handy, ein Sensor in Home Assistant, eine Excel-Tabelle,
eine Automation (n8n, Node-RED) oder ein eigenes kleines Skript.

Die API **liest nur**. Es gibt keine Adresse, die etwas ändert, anlegt oder löscht. Zum
Ändern gibt es [Claude mit der Stufe „Bearbeiten“](claude-anbinden.md) oder die Oberfläche.

## Auf einen Blick

| | |
|---|---|
| Adresse | `http://<dein-server>:<port>/api/v1/…` (der Port, den du für den Container freigegeben hast, in den Beispielen 8085) |
| Anmeldung | Header `Authorization: Bearer <Token>` |
| Token | eigene **API-Tokens** (beginnen mit `ocf_api_`), angelegt unter Einstellungen → API (JSON) |
| Ein/Aus | Einstellungen → API (JSON) → **API einschalten** (Standard: aus) |
| Methode | nur `GET` |
| Antwort | JSON, UTF-8 |
| Erreichbar | nur im Heimnetz (unterwegs über ein VPN nach Hause) |
| Protokoll | jeder Aufruf steht im [Protokoll](systemzustand.md#protokoll) (Logger `api`) |

## Einrichten

1. **Einstellungen → API (JSON)** aufklappen und **API einschalten**.
2. Einen Namen eingeben, z. B. „Home Assistant“, und **Token anlegen**.
3. Das Token erscheint **nur dieses eine Mal** — gleich kopieren. Gespeichert wird nur ein
   Fingerabdruck; verloren ist verloren, dann ein neues anlegen.
4. **API nutzen** aufklappen: die Beispiele enthalten das neue Token und die richtige Adresse
   schon.

**Für jede Anwendung ein eigenes Token.** Dann siehst du in der Liste, welche zuletzt gefragt
hat, und kannst eine einzeln **widerrufen**, ohne die anderen anzufassen.

### API-Tokens und Claude-Tokens sind getrennt

Ein API-Token öffnet **nur** die API, ein Claude-Token **nur** Claude (MCP). Ein Token, das
du einer Tabelle oder einem Widget gibst, kann also nie etwas über Claude ändern — auch nicht,
wenn jemand es in die Hände bekommt. Schaltest du die API aus, bleibt Claude davon unberührt,
und umgekehrt.

## Ein erster Aufruf

Im Terminal (Linux, macOS, Windows-PowerShell mit `curl.exe`):

```
curl -H "Authorization: Bearer ocf_api_…" http://192.168.1.10:8085/api/v1
```

Die Antwort listet **alle Adressen** mit Beschreibung und Parametern — die API beschreibt sich
selbst. Danach zum Beispiel:

```
curl -H "Authorization: Bearer ocf_api_…" http://192.168.1.10:8085/api/v1/portfolio
curl -H "Authorization: Bearer ocf_api_…" "http://192.168.1.10:8085/api/v1/prices?asset=BTC&days=7"
```

Parameter hängen wie üblich hinter `?`, mehrere mit `&`. Anführungszeichen um die Adresse,
sobald ein `&` darin vorkommt.

## Was in den Antworten steht

- **Beträge sind Text**, z. B. `"5274.48"` — so bleiben alle Nachkommastellen genau. Für eine
  Rechnung in Excel oder Home Assistant in eine Zahl umwandeln.
- **Werte in deiner Anzeigewährung** (EUR oder USD, wie unter Einstellungen bzw. am
  EUR/USD-Schalter). Welche, steht bei Bestand und Kursen im Feld `currency`.
- **Zeiten** im Format ISO 8601 mit Zeitzone, z. B. `2026-10-20T08:15:00+00:00`.
  Datums-Parameter (`date_from`, `date_to`) gelten in deiner eingestellten Zeitzone.
- **Feldnamen sind englisch** (`value`, `qty`, `cost` …) — so wie in der Programmierung üblich.
- **Adressen sind gekürzt** (`0x5290…9EE7`), Schlüssel und Passwörter kommen nie vor. Name,
  Anschrift und Steuernummer aus dem Kopf der Berichte ebenso wenig.
- **Höchstens 200 Zeilen** je Aufruf. Listen sagen mit `total` und `more`, ob es weitere gibt;
  dann mit `offset` weiterblättern oder den Zeitraum eingrenzen.

## Fehler

| Status | `error.code` | Bedeutung |
|---|---|---|
| 401 | `api.token_invalid` | kein Token, falsches Token, widerrufen — oder ein Claude-Token |
| 403 | `api.off` | die API ist ausgeschaltet |
| 400 | `api.invalid_params` | Parameter fehlt oder passt nicht (z. B. `days=abc`); `error.params.reason` sagt welcher |
| 404 | `api.unknown` | diese Adresse gibt es nicht |
| 503 | `db.unavailable` | die Datenbank ist gerade nicht erreichbar |

Ein Fehler kommt immer als `{"error": {"code": "…", "params": {…}}}`.

## Alle Adressen

Die Beispiele zeigen erfundene Werte; Listen sind auf ein, zwei Einträge gekürzt. `…` steht für weggelassene Felder.

### `/api/v1` — Verzeichnis

Alle Adressen mit Beschreibung (englisch) und Parametern — die API beschreibt sich selbst.

Keine Parameter.

**Anfrage**

```
curl -H "Authorization: Bearer ocf_api_…" http://192.168.1.10:8085/api/v1
```

**Antwort** (gekürzt, Beispielwerte)

```json
{
  "endpoints": [
    {
      "path": "/api/v1/prices",
      "description": "Current price and the daily closes of the last `days` days, in the display currency.",
      "params": {
        "asset": {"type": "string", "description": "Coin, e.g. BTC"},
        "days": {"type": "integer", "default": 30}
      }
    }
  ]
}
```

### `/api/v1/portfolio` — Bestand und Gesamtwert

Der heutige Stand, wie Dashboard und Bestände ihn zeigen.

Keine Parameter.

**Anfrage**

```
curl -H "Authorization: Bearer ocf_api_…" http://192.168.1.10:8085/api/v1/portfolio
```

**Antwort** (gekürzt, Beispielwerte)

```json
{
  "summary": {
    "currency": "EUR",
    "value": "5274.48",
    "crypto": "5201.10",
    "cash": "73.38",
    "cost": "14778.79",
    "unrealized": "-9505.17",
    "unrealized_pct": "-64.3",
    "realized": "-296.88",
    "realized_pct": "-1.7",
    "futures": {"pnl": "-120.10", "funding": "-8.40", "fees": "-16.00", "result": "-144.50"},
    "result": "-9946.55",
    "income": "138.60",
    "net_deposited": "15754.26",
    "high": {"day": "2024-12-06", "value": "19954.81", "cost": "15102.00", "deposited": "15200.00"},
    "first": "2021-03-14"
  },
  "coins": [
    {
      "asset": "BTC", "name": "Bitcoin",
      "qty": "0.0213", "price": "92450.10", "value": "1969.19",
      "cost": "1500.00", "avg_price": "70422.53",
      "realized": "0", "unrealized": "469.19", "unrealized_pct": "31.3",
      "income": "0", "since": "2023-02-01", "days_held": 992, "fiat": false,
      "places": [{"source": "Tangem – Bitcoin", "market": "spot", "qty": "0.0213"}]
    }
  ]
}
```

`summary`: `value` Gesamtwert (= `crypto` + `cash`), `cost` Einstand, `unrealized` / `realized`
(+ `_pct` in Prozent), `futures` Futures-Ergebnis aufgeschlüsselt, `result` Ergebnis gesamt,
`income` Erträge, `net_deposited` netto eingezahlt, `high` der Höchststand, `first` der erste
Vorgang. `coins[]`: je Coin Menge, Kurs, Wert, Einstand, Durchschnittspreis, Ergebnis, seit wann
gehalten und wo er liegt (`places`).

### `/api/v1/sources` — Quellen und Hinweise

Alle Börsen und Wallet-Netzwerke, dazu offene Hinweise.

Keine Parameter.

**Anfrage**

```
curl -H "Authorization: Bearer ocf_api_…" http://192.168.1.10:8085/api/v1/sources
```

**Antwort** (gekürzt, Beispielwerte)

```json
{
  "sources": [
    {
      "id": 4, "label": "Bitget", "provider": "bitget", "kind": "exchange",
      "rows": 1943, "last_fetch": "2026-10-20T04:00:12+00:00",
      "last_check": {"at": "2026-10-20T04:00:05+00:00", "ok": true, "message": null},
      "auto_fetch": true, "wallet_id": null, "address": null
    },
    {
      "id": 9, "label": "Ethereum", "provider": "ethereum", "kind": "wallet",
      "rows": 33, "last_fetch": "2026-10-20T04:01:40+00:00", "last_check": null,
      "auto_fetch": true, "wallet_id": 2, "address": "0x5290…9EE7"
    }
  ],
  "alerts": [
    {"source_id": 12, "kind": "fetch_failed", "date": "2026-10-19", "days": 1, "message": "timeout"}
  ]
}
```

`alerts[].kind`: `key_rejected` (API-Schlüssel abgelehnt), `fetch_failed` (Abruf
fehlgeschlagen), `history_at_risk` (die Börse liefert ältere Daten bald nicht mehr). Die `id`
brauchst du für `search_transactions?source_id=…`.

### `/api/v1/balance_check` — Bestandsabgleich je Quelle

Je Quelle: der aus den Transaktionen berechnete Bestand gegen den, den Börse oder Blockchain melden.

Keine Parameter.

**Anfrage**

```
curl -H "Authorization: Bearer ocf_api_…" http://192.168.1.10:8085/api/v1/balance_check
```

**Antwort** (gekürzt, Beispielwerte)

```json
{
  "sources": [
    {"source": "Bitget", "source_id": 4, "status": "ok", "at": "2026-10-20T04:00:20+00:00",
     "differences": 0, "coins": []},
    {"source": "MEXC", "source_id": 6, "status": "differences", "at": "2026-10-20T04:00:31+00:00",
     "differences": 1,
     "coins": [{"asset": "USDT", "market": "spot", "computed": "12.40", "actual": "12.95",
                "diff": "0.55", "ok": false}]}
  ]
}
```

`status`: `ok`, `differences` (mindestens ein Coin weicht ab) oder `none` (die Quelle meldet
keinen Bestand). `coins[]` nennt nur abweichende Coins.

### `/api/v1/holdings_by_source` — was wo liegt

Je Quelle, Coin und Markt die berechnete Menge.

| Parameter | Pflicht | Bedeutung |
|---|---|---|
| `asset` | nein | nur dieser Coin, z. B. `BTC` |

**Anfrage**

```
curl -H "Authorization: Bearer ocf_api_…" "http://192.168.1.10:8085/api/v1/holdings_by_source?asset=ETH"
```

**Antwort** (gekürzt, Beispielwerte)

```json
{
  "holdings": [
    {"source": "Bitget", "asset": "ETH", "market": "spot", "qty": "0.15"},
    {"source": "Tangem – Ethereum", "asset": "ETH", "market": "spot", "qty": "0.042"}
  ]
}
```

### `/api/v1/search_transactions` — Transaktionen suchen

Wie die Seite Transaktionen: eine Zeile je Handel, Ein-/Auszahlung oder verbundenem Transfer, neueste zuerst.

| Parameter | Pflicht | Bedeutung |
|---|---|---|
| `date_from` | nein | erster Tag, `JJJJ-MM-TT`, deine Zeitzone |
| `date_to` | nein | letzter Tag |
| `asset` | nein | Coin(s), mehrere mit Komma: `BTC,ETH` |
| `kind` | nein | Art: `trade`, `send`, `receive`, `transfer`, `income`, `fiat_deposit`, `fiat_withdrawal`, `fee` … |
| `source_id` | nein | Quelle(n), mehrere mit Komma (Ids aus `/sources`) |
| `text` | nein | Wörter in Coin, Transaktions-ID, Kommentar oder Notiz |
| `show` | nein | `normal` (Standard), `open` (ohne Gegenstück), `edited`, `noted`, `spam`, `dust`, `short` (Bestand negativ), `mcp` (über MCP geändert) |
| `limit` | nein | Zeilen, 1–200, Standard 50 |
| `offset` | nein | ab der wievielten Zeile (zum Blättern), Standard 0 |

**Anfrage**

```
curl -H "Authorization: Bearer ocf_api_…" "http://192.168.1.10:8085/api/v1/search_transactions?asset=BTC&date_from=2025-01-01&date_to=2025-12-31&limit=2"
```

**Antwort** (gekürzt, Beispielwerte)

```json
{
  "total": 37, "shown": 2, "more": true,
  "items": [
    {
      "type": "row", "id": 2210, "at": "2025-11-03T09:12:44+00:00",
      "source": "Bitget", "kind": "trade", "market": "spot",
      "incoming": "0.002 BTC", "outgoing": "180.50 USDT", "fee": "0.18 USDT",
      "external_id": "1189…4471",
      "values": {"incoming": "171.30", "outgoing": "171.30", "fee": "0.17"}
    },
    {
      "type": "transfer", "at": "2025-10-28T18:02:10+00:00",
      "send": {"id": 2190, "source": "Bitget", "kind": "send", "outgoing": "0.005 BTC", "fee": "0.0001 BTC", "…": "…"},
      "receive": {"id": 2191, "source": "Tangem – Bitcoin", "kind": "receive", "incoming": "0.005 BTC", "…": "…"},
      "network_fee": null
    }
  ]
}
```

Eine Zeile (`type: row`) hat `id`, Zeit `at`, `source`, `kind`, die Seiten `incoming`,
`outgoing`, `fee` als Text, die Werte zur Zeit des Vorgangs `values` (Anzeigewährung), und je
nach Fall `note`, `comment`, `income_kind`, `counterparty` (gekürzt) sowie Hinweise wie
`open`, `edited`, `spam`, `dust`. Ein Handel kann `result` haben (Gewinn/Verlust). Ein Transfer
(`type: transfer`) hat `send` und `receive`. Mit `more: true` gibt es weitere Treffer: `offset`
um `shown` erhöhen.

### `/api/v1/transaction` — ein Vorgang im Detail

Die gespeicherte Zeile mit ihren Rohdaten (Adressen gekürzt) und ihre Steuerseite.

| Parameter | Pflicht | Bedeutung |
|---|---|---|
| `row_id` | ja | Id der Zeile (aus `search_transactions`) |

**Anfrage**

```
curl -H "Authorization: Bearer ocf_api_…" "http://192.168.1.10:8085/api/v1/transaction?row_id=2190"
```

**Antwort** (gekürzt, Beispielwerte)

```json
{
  "row": {
    "id": 2190, "source": "Bitget", "source_id": 4, "channel": "api",
    "timestamp": "2025-10-28T18:02:10+00:00", "kind": "send", "market": "spot",
    "outgoing_asset": "BTC", "outgoing_amount": "0.005",
    "fee_asset": "BTC", "fee_amount": "0.0001",
    "external_id": "a3f2…9c10", "counterparty": "bc1qar…5mdq",
    "raw": {"coin": "BTC", "size": "0.005", "toAddress": "bc1qar…5mdq", "…": "…"},
    "imported_at": "2025-10-29T04:00:15+00:00"
  },
  "tax": {
    "method": "fifo", "sold": [], "incomes": [],
    "moved": [{"asset": "BTC", "qty": "0.005", "acquired": "2023-02-01T10:00:00+00:00",
               "cost": "120.00", "origin": 1830, "free_from": "2024-02-01"}],
    "later": {"sold": [], "losses": [], "open": []}
  }
}
```

`raw` sind die Originaldaten der Quelle — je Börse oder Blockchain verschieden. `tax`: was
der Steuerbericht aus dieser Zeile macht — `sold` (Veräußerungen mit Gewinn), `incomes`,
`moved` (umgebuchte Lose mit Anschaffungsdatum und ab wann steuerfrei).

### `/api/v1/open_transfers` — Abgänge und Eingänge ohne Gegenstück

Wie `search_transactions?show=open`.

| Parameter | Pflicht | Bedeutung |
|---|---|---|
| `limit` | nein | 1–200, Standard 100 |

**Anfrage**

```
curl -H "Authorization: Bearer ocf_api_…" "http://192.168.1.10:8085/api/v1/open_transfers?limit=1"
```

**Antwort** (gekürzt, Beispielwerte)

```json
{
  "total": 3, "shown": 1, "more": true,
  "items": [
    {"type": "row", "id": 1907, "at": "2025-06-11T14:20:00+00:00", "source": "MEXC",
     "kind": "send", "market": "spot", "outgoing": "250 USDT", "fee": "1 USDT",
     "counterparty": "TLa2f6…YjU7", "open": true}
  ]
}
```

### `/api/v1/prices` — Kurs eines Coins

Aktueller Kurs und Tageskurse der letzten Tage, in der Anzeigewährung.

| Parameter | Pflicht | Bedeutung |
|---|---|---|
| `asset` | ja | Coin, z. B. `BTC` |
| `days` | nein | Tage Verlauf, 7–3650, Standard 30 |

**Anfrage**

```
curl -H "Authorization: Bearer ocf_api_…" "http://192.168.1.10:8085/api/v1/prices?asset=BTC&days=7"
```

**Antwort** (gekürzt, Beispielwerte)

```json
{
  "now": {"asset": "BTC", "price": "92450.10", "currency": "EUR", "day": "2026-10-20", "latest": true},
  "days": [
    {"day": "2026-10-14", "close": "90310.00", "high": "91200.00", "low": "89120.00"},
    {"day": "2026-10-15", "close": "91022.50", "high": "91880.00", "low": "89900.00"}
  ]
}
```

### `/api/v1/tax_year` — Steuerjahr

Wie der Steuerbericht unter Berichte.

| Parameter | Pflicht | Bedeutung |
|---|---|---|
| `year` | ja | z. B. `2025` |
| `method` | nein | `fifo` oder `lifo`; leer = Einstellung |
| `lines` | nein | `true`: auch die einzelnen Verkäufe und Erträge (je höchstens 200) |

**Anfrage**

```
curl -H "Authorization: Bearer ocf_api_…" "http://192.168.1.10:8085/api/v1/tax_year?year=2025&lines=true"
```

**Antwort** (gekürzt, Beispielwerte)

```json
{
  "summary": {
    "year": 2025, "method": "fifo", "airdrop_taxable": false,
    "s23": {"gains": "219.86", "losses": "-79.96", "net": "139.90", "limit": "1000",
            "taxable": false, "share": "14", "tax_free_gain": "-1.27", "count": 187, "count_taxed": 185, "…": "…"},
    "s22": {"total": "0", "limit": "256", "taxable": false, "share": "0", "count": 0, "…": "…"},
    "s20": {"gains": "83.23", "losses": "-141.59", "fees": "-9.09", "net": "-67.45", "…": "…"},
    "lost": {"cost": "0", "count": 0, "unknown_cost": 0},
    "forms": [{"form": "SO", "line": null, "key": "s23_net", "value": "139.90"}],
    "carry": {"year": {"year": 2025, "start": "303.67", "end": "303.67", "…": "…"}, "rows": ["…"], "opening": null},
    "open": {"uncovered": 0, "open_sends": 0, "unvalued_assets": []}
  },
  "counts": {"disposals": 187, "incomes": 0, "futures": 12, "losses": 0, "…": "…"},
  "disposals": [
    {"asset": "SOL", "place": "Bitget", "sold": "2025-03-02T11:00:00+00:00",
     "acquired": "2024-11-20T08:30:00+00:00", "days": 102, "qty": "1.5",
     "proceeds": "210.00", "cost": "180.00", "gain": "30.00", "tax_free": false,
     "estimated": false, "how": "fifo", "row": 1702, "origin": 1550}
  ],
  "incomes": []
}
```

`s23` private Veräußerungen (§ 23 EStG) mit Freigrenze `limit` und Anteil `share` in Prozent,
`s22` sonstige Einkünfte (§ 22 Nr. 3), `s20` Futures (§ 20), `lost` Totalverluste, `forms`
die Werte für die Anlagen, `carry` der Verlustvortrag (wie `/loss_carry`), `open`
Ungeklärtes. `disposals[]` (nur mit `lines=true`): je Verkauf Coin, Ort, Verkaufs- und
Anschaffungsdatum, Haltedauer `days`, Erlös, Einstand, Gewinn, steuerfrei ja/nein.

### `/api/v1/loss_carry` — Verlustvortrag

Je Jahr der Verlustvortrag nach § 23 Abs. 3 EStG.

Keine Parameter.

**Anfrage**

```
curl -H "Authorization: Bearer ocf_api_…" http://192.168.1.10:8085/api/v1/loss_carry
```

**Antwort** (gekürzt, Beispielwerte)

```json
{
  "year": {"year": 2026, "net": "-40.00", "limit": "1000", "taxable": false,
           "start": "303.67", "used": "0", "loss": "40.00", "end": "343.67", "running": true, "…": "…"},
  "rows": [
    {"year": 2024, "net": "-303.67", "limit": "600", "taxable": false, "start": "0",
     "used": "0", "back_in": "0", "back_out": "0", "loss": "303.67", "remaining": "0",
     "end": "303.67", "assessed": null, "note": null, "diff": null, "running": false}
  ],
  "opening": null
}
```

Je Jahr: `net` Ergebnis § 23, `limit` Freigrenze, `start` Vortrag zu Jahresbeginn, `used`
genutzt, `back_out`/`back_in` Rücktrag ins Vorjahr, `loss` neuer Verlust, `end` Vortrag zum
Jahresende, `assessed` der Wert aus dem Bescheid (falls eingetragen) und `diff` die
Abweichung. `running: true` = laufendes Jahr.

### `/api/v1/tax_free_soon` — bald steuerfrei

Welche Mengen in den nächsten Tagen die Haltefrist von einem Jahr überschreiten — und was heute schon steuerfrei ist.

| Parameter | Pflicht | Bedeutung |
|---|---|---|
| `days` | nein | Blick nach vorn, 1–366 Tage, Standard 90 |

**Anfrage**

```
curl -H "Authorization: Bearer ocf_api_…" "http://192.168.1.10:8085/api/v1/tax_free_soon?days=30"
```

**Antwort** (gekürzt, Beispielwerte)

```json
{
  "upcoming": [
    {"asset": "HBAR", "free_on": "2026-10-22", "qty": "595.7736", "value": "43.42", "gain": "-12.10"}
  ],
  "today": {
    "currency": "EUR",
    "coins": [{"asset": "BTC", "free": "0.0150", "taxed": "0.0063", "value_free": "1386.75",
               "value_taxed": "582.44", "gain_free": "420.00", "gain_taxed": "49.19",
               "next_free": "2027-01-15", "next_qty": "0.0063"}],
    "total": {"value_free": "2950.10", "value_taxed": "2251.00", "gain_free": "390.00", "gain_taxed": "-10012.00"}
  },
  "limits": {"year": 2026,
             "s23": {"value": "-40.00", "limit": "1000", "share": "0", "level": "ok"},
             "s22": {"value": "12.30", "limit": "256", "share": "5", "level": "ok"}}
}
```

`limits.*.level`: `ok`, `near` (Freigrenze bald erreicht) oder `over`.

### `/api/v1/origin` — Mittelherkunft

Woher das Geld eines Verkaufs, Transfers oder einer Auszahlung stammt — oder das des heutigen Bestands.

| Parameter | Pflicht | Bedeutung |
|---|---|---|
| `row_id` | nein | Verkauf, Transfer oder Auszahlung (Id aus `/origin_candidates`); leer = heutiger Bestand |
| `asset` | nein | ohne `row_id`: nur dieser Coin |

**Anfrage**

```
curl -H "Authorization: Bearer ocf_api_…" "http://192.168.1.10:8085/api/v1/origin?row_id=2190"
```

**Antwort** (gekürzt, Beispielwerte)

```json
{
  "target": {"kind": "send", "at": "2025-10-28T18:02:10+00:00", "asset": "BTC",
             "qty": "0.005", "amount": "0.005", "value": "450.00", "place": "Bitget", "to": "Tangem – Bitcoin"},
  "method": "fifo",
  "mix": [
    {"kind": "bank", "value": "380.00", "share": "84.4"},
    {"kind": "gain", "value": "70.00", "share": "15.6"}
  ],
  "overview": {"from": "2023-02-01", "to": "2025-10-28", "transactions": 6,
               "sources": [{"place": "Bitget", "kind": "exchange", "address": null, "count": 6,
                            "channels": {"api": 5, "file": 1, "manual": 0}}],
               "channels": {"api": 5, "file": 1, "manual": 0, "chain": 0}},
  "lost": {"count": 0, "assets": []},
  "deposits": [
    {"kind": "bank", "at": "2023-01-30T09:00:00+00:00", "place": "Bitget", "to": null,
     "asset": "EUR", "qty": "380.00", "value": "380.00", "row": 1801, "share": "84.4",
     "tx": "SEPA…", "channel": "api"}
  ]
}
```

`mix[].kind`: `bank` (Einzahlung vom Bankkonto), `card` (Kartenkauf), `gain` (Kursgewinn),
`income` (Erträge), `futures`, `unknown` / `money_unknown` (nicht zuordenbar), `loss`.
`deposits[]` die Einzahlungen, aus denen das Geld stammt, mit Anteil `share` in Prozent.

### `/api/v1/origin_candidates` — Vorgänge für die Mittelherkunft

Verkäufe, Transfers und Auszahlungen, neueste zuerst — ihre `row` ist die `row_id` für `/origin`.

| Parameter | Pflicht | Bedeutung |
|---|---|---|
| `limit` | nein | 1–200, Standard 50 |

**Anfrage**

```
curl -H "Authorization: Bearer ocf_api_…" "http://192.168.1.10:8085/api/v1/origin_candidates?limit=1"
```

**Antwort** (gekürzt, Beispielwerte)

```json
{
  "total": 350,
  "items": [
    {"kind": "send", "at": "2025-10-28T18:02:10+00:00", "place": "Bitget",
     "to": "Tangem – Bitcoin", "asset": "BTC", "qty": "0.005", "value": "450.00", "row": 2190}
  ]
}
```

### `/api/v1/system_status` — Systemzustand

Läuft alles? Gut für eine Überwachung.

Keine Parameter.

**Anfrage**

```
curl -H "Authorization: Bearer ocf_api_…" http://192.168.1.10:8085/api/v1/system_status
```

**Antwort** (gekürzt, Beispielwerte)

```json
{
  "version": "1.6.1.0",
  "uptime_seconds": 86400,
  "operations": {
    "backup": {"enabled": true, "next_at": "2026-10-21T03:00:00+02:00",
               "last_at": "2026-10-20T03:00:41+02:00", "status": "done", "probe_ok": true, "message": null},
    "fetch": {"enabled": true, "next_at": "2026-10-21T04:00:00+02:00",
              "last_at": "2026-10-20T04:02:10+02:00", "status": "done", "failed": 0},
    "prices": {"enabled": true, "live_at": "2026-10-20T21:55:00+02:00", "status": "done", "failed": 0, "…": "…"},
    "fine": {"enabled": true, "last_at": "2026-10-20T21:00:12+02:00", "status": "done", "failed": 0, "…": "…"},
    "tools": {"pg_dump": 18, "server": 18, "ok": true},
    "disk": {"data": {"path": "/data", "free": 1209462790144, "total": 9452620791808, "used": 5242880},
             "backups": {"path": "/backups", "free": 1209462790144, "total": 9452620791808, "used": 41943040},
             "database": 52428800}
  },
  "log_level": "INFO"
}
```

Beispiel für eine Überwachung: `operations.backup.status` ist nicht `done`, oder
`operations.backup.last_at` liegt mehr als zwei Tage zurück → melden. Speicherangaben in Byte.

### `/api/v1/log_excerpt` — Protokoll-Auszug

Die letzten Zeilen des Protokolls (Server und Browser), ab einer Stufe.

| Parameter | Pflicht | Bedeutung |
|---|---|---|
| `level` | nein | ab `DEBUG`, `INFO`, `WARNING` (Standard) oder `ERROR` |
| `limit` | nein | 1–200 Zeilen, Standard 50 |

**Anfrage**

```
curl -H "Authorization: Bearer ocf_api_…" "http://192.168.1.10:8085/api/v1/log_excerpt?level=WARNING&limit=2"
```

**Antwort** (gekürzt, Beispielwerte)

```json
{
  "lines": [
    {"seq": 812, "at": "2026-10-20T04:00:31+00:00", "level": "WARNING",
     "logger": "app.modules.jobs.service", "origin": "backend",
     "message": "fetch 12 failed: timeout"},
    {"seq": 815, "at": "2026-10-20T08:14:02+00:00", "level": "ERROR",
     "logger": "frontend", "origin": "frontend",
     "message": "GET /api/stats: 500 http_500 (/stats)"}
  ]
}
```

## Beispiele

### Home Assistant: Gesamtwert als Sensor

In `configuration.yaml` (die Karte unter **API nutzen** hat das Beispiel mit deinem Token):

```yaml
rest:
  - resource: http://192.168.1.10:8085/api/v1/portfolio
    headers:
      Authorization: Bearer ocf_api_…
    scan_interval: 900
    sensor:
      - name: owncryptofolio Wert
        value_template: "{{ value_json.summary.value }}"
        unit_of_measurement: "EUR"
      - name: owncryptofolio Ergebnis
        value_template: "{{ value_json.summary.result }}"
        unit_of_measurement: "EUR"
```

`scan_interval: 900` fragt alle 15 Minuten — öfter bringt nichts, die Kurse kommen alle
5 Minuten.

### iPhone-Widget mit der App „Scriptable“

Scriptable (kostenlos im App Store) kann kleine Widgets aus Web-Daten bauen:

```javascript
const req = new Request("http://192.168.1.10:8085/api/v1/portfolio")
req.headers = { Authorization: "Bearer ocf_api_…" }
const data = await req.loadJSON()
const w = new ListWidget()
w.addText("Portfolio").font = Font.boldSystemFont(14)
const v = Number(data.summary.value).toLocaleString("de-DE", { style: "currency", currency: data.summary.currency })
w.addText(v).font = Font.boldSystemFont(22)
Script.setWidget(w)
Script.complete()
```

Das Widget aktualisiert sich, wenn das iPhone im Heimnetz oder im VPN ist.

### Excel (Windows): Daten abrufen

**Daten → Aus dem Web → Erweitert**: Adresse `http://192.168.1.10:8085/api/v1/portfolio`,
als Header `Authorization` mit `Bearer ocf_api_…`. Power Query zeigt das JSON als Tabelle;
`coins` aufklappen. **Aktualisieren** holt neue Werte.

Google Tabellen geht **nicht**: es fragt von Googles Servern aus, und die erreichen dein
Heimnetz nicht.

### Python

```python
import requests
H = {"Authorization": "Bearer ocf_api_…"}
B = "http://192.168.1.10:8085/api/v1"
soon = requests.get(f"{B}/tax_free_soon", headers=H, params={"days": 30}).json()
for x in soon["upcoming"]:
    print(x["free_on"], x["asset"], x["qty"], x["value"])
```

### Automation (n8n, Node-RED)

Ein **HTTP-Request**-Knoten mit Methode GET, Adresse wie oben und dem Header
`Authorization: Bearer ocf_api_…`. Zum Beispiel jeden Morgen `/system_status` fragen und
melden, wenn die letzte Sicherung älter als zwei Tage ist.

## Sicherheit

- Die API ist **nur im Heimnetz** erreichbar. Mach owncryptofolio nicht ohne Weiteres aus dem
  Internet erreichbar (Portfreigabe) — unterwegs geht es über das VPN.
- Ein Token ist so gut wie ein Schlüssel zu deinen Zahlen: nicht in öffentliche Foren, Screenshots
  oder geteilte Tabellen kopieren. Im Zweifel **widerrufen** und neu anlegen.
- **Ausschalten** (Einstellungen → API (JSON)) sperrt sofort alle API-Tokens; sie bleiben erhalten und
  gelten wieder, wenn du einschaltest.

## Verwandte Seiten

- [Claude anbinden](claude-anbinden.md) — dieselben Daten für Claude, dort auch Bearbeiten
- [Systemzustand](systemzustand.md) — das Protokoll mit allen API-Aufrufen
