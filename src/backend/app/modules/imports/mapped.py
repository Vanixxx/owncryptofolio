"""A file of any exchange, read through a column mapping the user sets (ADR 0048, M13 B).

Two forms: one row per movement (date, type, coin, amount; a trade as two rows with the same
id, one plus and one minus) or one row per trade (date, pair, side, amount, price or total).
Delimiter, decimal mark, header row and date format are recognised and can be changed. A row
that cannot be read is named with its row number and reason, never guessed (as in the
manual template, ADR 0036). Nothing here knows an exchange.
"""

from __future__ import annotations

import csv
import io
import re
from collections import Counter
from datetime import UTC, date, datetime, time
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field

from app.modules.plugins import archive
from app.modules.plugins.contract import IncomeKind, Kind, Movement

SAMPLE = 20
SCAN = 500  # rows looked at to recognise formats and list the values of a column
FIAT = {"EUR", "USD", "CHF", "GBP", "PLN", "CZK", "SEK", "NOK", "DKK", "HUF", "TRY", "AUD", "CAD"}
QUOTES = [
    "FDUSD",
    "USDT",
    "USDC",
    "BUSD",
    "TUSD",
    "DAI",
    "EUR",
    "USD",
    "GBP",
    "CHF",
    "TRY",
    "BTC",
    "ETH",
    "BNB",
]
DELIMITERS = [";", ",", "\t", "|"]

ROLES: dict[str, list[str]] = {
    "movement": [
        "date",
        "time",
        "type",
        "asset",
        "amount",
        "counter_asset",
        "counter_amount",
        "fee_amount",
        "fee_asset",
        "id",
        "comment",
    ],
    "trade": [
        "date",
        "time",
        "pair",
        "base",
        "quote",
        "side",
        "amount",
        "price",
        "total",
        "fee_amount",
        "fee_asset",
        "id",
        "comment",
    ],
}
# buy/sell: a whole trade in one row with its counter value (Coinbase); trade: one side of
# a trade whose other side is a second row with the same id (Kraken's ledger)
# convert: a swap whose other side is written in the note ("Converted 0.1 ETH to 0.003 BTC");
# internal: between one's own accounts at the exchange (staking pot, futures), sign = direction
KINDS = [
    "buy",
    "sell",
    "convert",
    "trade",
    "deposit",
    "withdrawal",
    "income",
    "internal",
    "fee",
    "ignore",
]
NOTE_TRADE = re.compile(
    r"(?:bought|sold|gekauft|verkauft|kauf|verkauf)\s+([\d.,]+)\s+([A-Za-z0-9]+)\s+"
    r"(?:for|für|gegen)\s+([\d.,]+)\s+([A-Za-z0-9]+)",
    re.I,
)
CONVERT = re.compile(
    r"([\d.,]+)\s+([A-Za-z0-9]+)\s+(?:to|in|into|zu|nach|→|->)\s+([\d.,]+)\s+([A-Za-z0-9]+)", re.I
)
SIDES = ["buy", "sell", "ignore"]

# headings and values as exchanges write them, German and English; first match wins
ROLE_WORDS: dict[str, list[str]] = {
    "date": [
        "date",
        "datum",
        "time",
        "zeit",
        "timestamp",
        "datetime",
        "zeitpunkt",
        "created",
        "utc time",
        "date utc",
        "time utc",
        "created at",
        "date time",
    ],
    "time": ["uhrzeit"],
    "type": [
        "type",
        "typ",
        "art",
        "transaction type",
        "kind",
        "operation",
        "category",
        "vorgang",
        "transaktionstyp",
    ],
    "asset": [
        "asset",
        "coin",
        "currency",
        "währung",
        "waehrung",
        "symbol",
        "token",
        "ccy",
        "crypto",
        "cryptocurrency",
        "kryptowährung",
    ],
    "counter_asset": [
        "price currency",
        "spot price currency",
        "gegenwährung",
        "counter currency",
        "fiat currency",
        "native currency",
    ],
    "counter_amount": ["subtotal", "gegenwert", "fiat amount", "native amount", "zwischensumme"],
    "amount": [
        "amount",
        "menge",
        "betrag",
        "quantity",
        "qty",
        "anzahl",
        "change",
        "size",
        "executed amount",
        "filled",
        "executed",
    ],
    "fee_amount": ["fee", "gebühr", "gebuehr", "fee amount", "commission", "fees", "trading fee"],
    "fee_asset": [
        "fee currency",
        "fee asset",
        "fee coin",
        "gebühr währung",
        "fee ccy",
        "commission asset",
        "fee unit",
    ],
    "id": [
        # a reference shared by the two rows of a trade first (Kraken's ledger: refid)
        "refid",
        "reference",
        "referenz",
        "order id",
        "trade id",
        "id",
        "txid",
        "transaction id",
        "tx hash",
        "hash",
    ],
    "comment": ["comment", "notiz", "note", "description", "beschreibung", "memo", "notes"],
    "pair": ["pair", "market", "paar", "markt", "instrument", "pairs", "trading pair"],
    "base": ["base", "base currency", "basis", "base asset"],
    "quote": ["quote", "quote currency", "quote asset"],
    "side": ["side", "seite", "direction", "buy sell", "richtung", "order side"],
    "price": [
        "price",
        "preis",
        "kurs",
        "avg price",
        "filled price",
        "execution price",
        "average price",
    ],
    "total": [
        "total",
        "summe",
        "gesamt",
        "cost",
        "value",
        "wert",
        "executed value",
        "quote amount",
        "turnover",
    ],
}
VALUE_WORDS: dict[str, list[str]] = {
    "deposit": [
        "deposit",
        "einzahlung",
        "receive",
        "received",
        "eingang",
        "transfer in",
        "crypto deposit",
        "fiat deposit",
        "incoming",
    ],
    "withdrawal": [
        "withdraw",
        "withdrawal",
        "auszahlung",
        "send",
        "sent",
        "ausgang",
        "transfer out",
        "crypto withdrawal",
        "fiat withdrawal",
        "outgoing",
    ],
    "trade": [
        "trade",
        "buy",
        "sell",
        "kauf",
        "verkauf",
        "swap",
        "exchange",
        "tausch",
        "spend",
        "match",
    ],
    "income": [
        "staking",
        "reward",
        "rewards",
        "interest",
        "airdrop",
        "earn",
        "bonus",
        "zinsen",
        "ertrag",
        "distribution",
        "mining",
        "rebate",
        "cashback",
        "staking reward",
    ],
    "fee": ["fee", "gebühr", "gebuehr", "commission"],
    "convert": ["convert", "converted", "conversion", "umtausch", "umwandlung"],
    "internal": ["internal transfer", "umbuchung", "transfer"],
    "buy": ["buy", "kauf", "b", "bid", "long"],
    "sell": ["sell", "verkauf", "s", "ask", "short"],
}
DATE_FORMATS = [
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d",
    "%Y/%m/%d %H:%M:%S",
    "%Y/%m/%d",
    "%d.%m.%Y %H:%M:%S",
    "%d.%m.%Y %H:%M",
    "%d.%m.%Y",
    "%d.%m.%y %H:%M",
    "%d.%m.%y",
    "%d/%m/%Y %H:%M:%S",
    "%d/%m/%Y %H:%M",
    "%d/%m/%Y",
    "%m/%d/%Y %H:%M:%S",
    "%m/%d/%Y %H:%M",
    "%m/%d/%Y",
    "%m/%d/%Y %I:%M:%S %p",
    "%d-%m-%Y %H:%M:%S",
    "%d-%m-%Y",
]


class Mapping(BaseModel):
    model_config = ConfigDict(extra="forbid")
    form: Literal["movement", "trade"] = "movement"
    sheet: str | None = None
    header_row: int = Field(0, ge=0, le=100)  # 0-based row of the headings
    delimiter: str | None = Field(None, max_length=1)
    decimal: Literal[".", ","] = "."
    date_format: str | None = Field(None, max_length=40)  # strftime; None = recognise
    timezone: str = "Europe/Berlin"
    columns: dict[str, str] = Field(default_factory=dict)  # role -> heading
    values: dict[str, str] = Field(default_factory=dict)  # value of type/side -> kind/side
    income_kind: IncomeKind = IncomeKind.REWARD
    kind: str | None = None  # without a type column: what every row is (a deposit list)


class Problem(ValueError):
    pass


# --- reading the table -------------------------------------------------------------------


def _text(data: bytes) -> str:
    for enc in ("utf-8-sig", "cp1252"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("latin-1")


def _sniff(text: str) -> str:
    lines = [x for x in text.splitlines()[:20] if x.strip()]
    best = max(
        DELIMITERS,
        key=lambda d: (min((x.count(d) for x in lines), default=0), sum(x.count(d) for x in lines)),
    )
    return best if any(best in x for x in lines) else ","


def table(path: Path, sheet: str | None = None, delimiter: str | None = None) -> dict:
    """All rows of the file as cell lists, with what was chosen to read it."""
    suffix = path.suffix.lower()
    if suffix in (".xlsx", ".xlsm"):
        from openpyxl import load_workbook

        archive.check(path)
        wb = load_workbook(path, read_only=True, data_only=True)
        names = wb.sheetnames
        ws = wb[sheet] if sheet in names else wb[names[0]]
        rows = [list(r) for r in ws.iter_rows(values_only=True)]
        wb.close()
        return {"rows": rows, "sheets": names, "sheet": ws.title, "delimiter": None}
    if suffix not in (".csv", ".txt", ".tsv"):
        raise Problem("unsupported_type")
    text = _text(path.read_bytes())
    delimiter = delimiter or ("\t" if suffix == ".tsv" else _sniff(text))
    rows = [r for r in csv.reader(io.StringIO(text), delimiter=delimiter)]
    return {"rows": rows, "sheets": [], "sheet": None, "delimiter": delimiter}


def _filled(row: list) -> int:
    return sum(1 for c in row if c not in (None, ""))


def guess_header(rows: list[list]) -> int:
    """The first row as wide as the table whose cells are all words (a title line above
    the headings, as some exchanges write, is skipped)."""
    head = rows[:20]
    width = max((_filled(r) for r in head), default=0)
    for i, r in enumerate(head):
        cells = [c for c in r if c not in (None, "")]
        words = all(isinstance(c, str) for c in cells) and not all(map(_number_like, cells))
        if width and len(cells) >= max(2, width * 0.8) and words:
            return i
    return 0


def _number_like(v: Any) -> bool:
    return bool(re.fullmatch(r"-?[\d.,'\s]+", str(v).strip()))


def headings(row: list) -> list[str]:
    out: list[str] = []
    for i, c in enumerate(row):
        name = str(c).strip() if c not in (None, "") else f"#{i + 1}"
        while name in out:
            name += "'"
        out.append(name)
    return out


def _records(t: dict, header_row: int) -> tuple[list[str], list[tuple[int, dict]]]:
    rows = t["rows"]
    if header_row >= len(rows):
        raise Problem("no_rows")
    names = headings(rows[header_row])
    out = []
    for n, r in enumerate(rows[header_row + 1 :], start=header_row + 2):  # 1-based like a sheet
        if not _filled(r):
            continue
        out.append((n, {names[i]: (r[i] if i < len(r) else None) for i in range(len(names))}))
    return names, out


def _cell(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, datetime):
        return v.isoformat(sep=" ")
    return str(v)


# --- recognising -------------------------------------------------------------------------


def _norm(s: str) -> str:
    s = re.sub(r"\(.*?\)", " ", s.lower())
    return re.sub(r"[^a-z0-9äöüß]+", " ", s).strip()


def _fits(heading: str, word: str, exact: bool) -> bool:
    return heading == word if exact else word in heading.split() or heading.startswith(word)


def _guess_columns(names: list[str], form: str) -> dict[str, str]:
    free = {_norm(n): n for n in names}
    out: dict[str, str] = {}
    for exact in (True, False):
        for role in ROLES[form]:
            if role in out:
                continue
            for word in ROLE_WORDS[role]:
                hit = next(
                    (
                        k
                        for k in free
                        if (k == word if exact else word in k.split() or k.startswith(word))
                    ),
                    None,
                )
                if hit:
                    out[role] = free.pop(hit)
                    break
    return out


def guess_value(value: str, choices: list[str]) -> str | None:
    v = _norm(value)
    for c in choices:
        if v in VALUE_WORDS.get(c, []):
            return c
    # a move between one's own accounts is no income nor trade ("Retail Staking Transfer"):
    # left for the user to decide
    # a move between one's own accounts ("Retail Staking Transfer") is neither income nor trade
    if "transfer" in v.split() or "umbuchung" in v:
        return "internal" if "internal" in choices else None
    for c in choices:
        if c in VALUE_WORDS and (
            v in VALUE_WORDS[c] or any(w in v.split() for w in VALUE_WORDS[c] if len(w) > 2)
        ):
            return c
    return None


def guess_decimal(records: list[tuple[int, dict]]) -> str:
    comma = dot = 0
    for _, r in records[:SCAN]:
        for v in r.values():
            if isinstance(v, str):
                s = v.strip()
                if re.fullmatch(r"-?\d{1,3}(\.\d{3})*,\d+|-?\d+,\d+", s):
                    comma += 1
                elif re.fullmatch(r"-?\d{1,3}(,\d{3})*\.\d+|-?\d+\.\d+", s):
                    dot += 1
    return "," if comma > dot else "."


def distinct(records: list[tuple[int, dict]], limit: int = 40) -> dict[str, list[str]]:
    """Per column its words, if there are few: the values one maps to a kind or side."""
    seen: dict[str, Counter] = {}
    for _, r in records[:SCAN]:
        for k, v in r.items():
            if isinstance(v, str) and v.strip() and not _number_like(v):
                seen.setdefault(k, Counter())[v.strip()] += 1
    return {k: sorted(c) for k, c in seen.items() if len(c) <= limit}


def _paired(records, cols: dict, key: str, values: dict, decimal: str) -> dict[str, str]:
    """Words whose rows share their id with a row of the other sign are halves of trades
    (Kraken: "spend" and "receive" of an instant buy, refid in common)."""
    if "id" not in cols or "amount" not in cols:
        return {}
    signs: dict[str, set] = {}
    rows: list[tuple[str, str]] = []
    for _, r in records[:SCAN]:
        ref, word = _cell(r.get(cols["id"])).strip(), _cell(r.get(key)).strip()
        try:
            amount = number(r.get(cols["amount"]), decimal)[0]
        except Problem:
            continue
        if ref and word and amount:
            signs.setdefault(ref, set()).add(amount > 0)
            rows.append((word, ref))
    out: dict[str, str] = {}
    for word in {w for w, _ in rows}:
        if values.get(word) in ("buy", "sell", "internal", "ignore"):
            continue
        refs = [ref for w, ref in rows if w == word]
        if sum(len(signs[ref]) == 2 for ref in refs) >= 0.8 * len(refs):
            out[word] = "trade"
    return out


def inspect(
    path: Path,
    sheet: str | None = None,
    header_row: int | None = None,
    delimiter: str | None = None,
    saved: dict | None = None,
    timezone: str = "Europe/Berlin",
) -> dict:
    """What the file holds and a mapping to start from: the saved one, else a guess."""
    if saved:
        m = Mapping.model_validate(saved)
        sheet = sheet or m.sheet
        delimiter = delimiter or m.delimiter
        header_row = m.header_row if header_row is None else header_row
    t = table(path, sheet, delimiter)
    if header_row is None:
        header_row = guess_header(t["rows"])
    names, records = _records(t, header_row)
    words = distinct(records)
    if saved and set(Mapping.model_validate(saved).columns.values()) <= set(names):
        mapping = Mapping.model_validate(saved)
    else:
        trade_cols = _guess_columns(names, "trade")
        form = (
            "trade"
            if "side" in trade_cols and ("pair" in trade_cols or "base" in trade_cols)
            else "movement"
        )
        cols = trade_cols if form == "trade" else _guess_columns(names, "movement")
        key = cols.get("side" if form == "trade" else "type")
        whole = "counter_asset" in cols and "counter_amount" in cols
        drop = (set() if whole else {"buy", "sell"}) | (set() if "comment" in cols else {"convert"})
        choices = SIDES if form == "trade" else [k for k in KINDS if k not in drop]
        values = {v: g for v in words.get(key, []) if (g := guess_value(v, choices))} if key else {}
        if whole:  # buys and sells stand in one row: a "Convert" there is not half a trade
            values = {v: g for v, g in values.items() if g != "trade"}
        if form == "movement" and key:
            values |= _paired(records, cols, key, values, guess_decimal(records))
        mapping = Mapping(
            form=form,
            columns=cols,
            values=values,
            decimal=guess_decimal(records),
            timezone=timezone,
        )
    mapping.sheet, mapping.delimiter, mapping.header_row = t["sheet"], t["delimiter"], header_row
    head = t["rows"][: header_row + 1 + SAMPLE]
    return {
        "sheets": t["sheets"],
        "columns": names,
        "rows": len(records),
        "top": [[_cell(c) for c in r] for r in head],  # what the file looks like, header included
        "sample": [{k: _cell(v) for k, v in r.items()} for _, r in records[:SAMPLE]],
        "distinct": words,
        "mapping": mapping.model_dump(mode="json"),
        "saved": bool(saved),
    }


# --- converting --------------------------------------------------------------------------


def number(v: Any, decimal: str) -> tuple[Decimal | None, str | None]:
    """A number and a unit written next to it ("0.5 BTC")."""
    if v is None or v == "":
        return None, None
    if isinstance(v, bool):
        raise Problem("number")
    if isinstance(v, int | float | Decimal):
        return Decimal(str(v)), None
    s = str(v).strip().replace(" ", "").replace("'", "")
    # "-$13.05" (Coinbase): the sign may stand before the currency sign
    m = re.fullmatch(
        r"([-+]?)([A-Za-z$€£]*)\s*([-+]?[\d.,\s]*\d(?:[eE][-+]?\d+)?)\s*([A-Za-z$€£]*)", s
    )
    if not m:
        raise Problem(f"number:{s[:30]}")
    body = m.group(1) + m.group(3).replace(" ", "")
    body = "-" + body[2:] if body.startswith("--") else body
    body = body.replace(".", "").replace(",", ".") if decimal == "," else body.replace(",", "")
    try:
        value = Decimal(body)
    except InvalidOperation as exc:
        raise Problem(f"number:{s[:30]}") from exc
    unit = m.group(4) or m.group(2) or None
    # "$0.01" is a fee in dollars, not in the row's coin (Coinbase)
    return value, ({"$": "USD", "€": "EUR", "£": "GBP"}.get(unit, unit.upper()) if unit else None)


def _clean_date(s: str) -> tuple[str, bool]:
    s = s.strip()
    utc = bool(re.search(r"(\s*\(?UTC\)?|Z)$", s))
    return re.sub(r"\s*\(?UTC\)?$", "", s), utc


def detect_format(values: list[Any]) -> str | None:
    """The format every sample date reads with; None: ISO, numbers or real dates."""
    texts = [_clean_date(str(v))[0] for v in values if isinstance(v, str) and v.strip()]
    texts = [x for x in texts if not re.fullmatch(r"\d{10,13}(\.\d+)?", x)]
    if not texts:
        return None
    try:
        for x in texts:
            datetime.fromisoformat(x.replace("Z", "+00:00"))
        return None
    except ValueError:
        pass
    for fmt in DATE_FORMATS:
        try:
            for x in texts:
                datetime.strptime(re.sub(r"\.\d+$", "", x), fmt)
            return fmt
        except ValueError:
            continue
    raise Problem("date_format")


def when(v: Any, t: Any, fmt: str | None, tz: str) -> datetime:
    if isinstance(v, datetime):
        d = v
    elif isinstance(v, date):
        d = datetime.combine(v, time())
    elif isinstance(v, int | float) and not isinstance(v, bool):
        d = datetime.fromtimestamp(v / 1000 if v > 1e11 else v, UTC)
    else:
        s, utc = _clean_date(str(v or ""))
        if not s:
            raise Problem("date_missing")
        if re.fullmatch(r"\d{10,13}(\.\d+)?", s):
            x = float(s)
            d = datetime.fromtimestamp(x / 1000 if x > 1e11 else x, UTC)
        else:
            try:
                d = (
                    datetime.strptime(re.sub(r"\.\d+$", "", s), fmt)
                    if fmt
                    else datetime.fromisoformat(s.replace("Z", "+00:00"))
                )
            except ValueError as exc:
                raise Problem(f"date:{s[:30]}") from exc
        if utc and d.tzinfo is None:
            d = d.replace(tzinfo=UTC)
    if t not in (None, ""):
        if isinstance(t, time):
            d = datetime.combine(d.date(), t, d.tzinfo)
        else:
            try:
                parts = [int(x) for x in str(t).strip().split(":")]
            except ValueError as exc:
                raise Problem(f"time:{str(t)[:20]}") from exc
            d = d.replace(
                hour=parts[0],
                minute=parts[1] if len(parts) > 1 else 0,
                second=parts[2] if len(parts) > 2 else 0,
            )
    if d.tzinfo is None:
        d = d.replace(tzinfo=ZoneInfo(tz))
    return d.astimezone(UTC)


def split_pair(s: str) -> tuple[str, str]:
    s = s.strip().upper()
    for sep in ("/", "-", "_", ":"):
        if sep in s:
            a, b = s.split(sep, 1)
            if a and b:
                return a, b.split(":")[0]
    for q in QUOTES:
        if s.endswith(q) and len(s) > len(q):
            return s[: -len(q)], q
    raise Problem(f"pair:{s[:20]}")


def _raw(r: dict) -> dict:
    return {k: _cell(v) for k, v in r.items() if v not in (None, "")}


def _fee(r: dict, m: Mapping, default_asset: str | None) -> tuple[str | None, Decimal | None]:
    c = m.columns
    amount, unit = (
        number(r.get(c["fee_amount"]), m.decimal) if c.get("fee_amount") else (None, None)
    )
    if not amount:
        return None, None
    asset = (str(r.get(c["fee_asset"]) or "").strip() if c.get("fee_asset") else "") or unit
    return (asset or default_asset), abs(amount)


def _text_of(r: dict, m: Mapping, role: str) -> str | None:
    col = m.columns.get(role)
    v = r.get(col) if col else None
    return None if v in (None, "") else _cell(v).strip() or None


def _trade_row(r: dict, m: Mapping, at: datetime) -> Movement | None:
    c = m.columns
    side_value = _text_of(r, m, "side") or ""
    side = m.values.get(side_value)
    if side is None:
        raise Problem(f"unmapped:{side_value[:30]}")
    if side == "ignore":
        return None
    if c.get("pair"):
        base, quote = split_pair(str(r.get(c["pair"]) or ""))
    else:
        base, quote = _text_of(r, m, "base"), _text_of(r, m, "quote")
        if not base or not quote:
            raise Problem("pair_missing")
    qty, unit = number(r.get(c.get("amount", "")), m.decimal)
    if qty is None:
        raise Problem("amount_missing")
    total = number(r.get(c["total"]), m.decimal)[0] if c.get("total") else None
    if total is None and c.get("price"):
        price = number(r.get(c["price"]), m.decimal)[0]
        total = qty * price if price is not None else None
    if total is None:
        raise Problem("total_missing")
    qty, total = abs(qty), abs(total)
    buy = side == "buy"
    fee_asset, fee_amount = _fee(r, m, quote)
    return Movement(
        timestamp=at,
        kind=Kind.TRADE,
        incoming_asset=base if buy else quote,
        incoming_amount=qty if buy else total,
        outgoing_asset=quote if buy else base,
        outgoing_amount=total if buy else qty,
        fee_asset=fee_asset,
        fee_amount=fee_amount,
        external_id=_text_of(r, m, "id"),
        comment=_text_of(r, m, "comment") or f"{base}/{quote} {side}",
        raw=_raw(r),
    )


def _whole_trade(
    r: dict, m: Mapping, at: datetime, kind: str, asset: str, qty: Decimal, type_value: str
) -> Movement:
    """A buy or sell in one row: the coin and its counter value (Coinbase: Subtotal).

    A note that tells the trade ("Bought 316.16 USDC for 304.94 EUR") wins over the counter
    columns: Coinbase fills those in the display currency, the note names what was really
    paid, fee included (the fee column, in the display currency, is then left out)."""
    note = _text_of(r, m, "comment") or ""
    told = NOTE_TRADE.search(note)
    if told and told.group(2).upper() == asset.upper():
        counter, value = told.group(4).upper(), abs(number(told.group(3), m.decimal)[0])
        shown = (_text_of(r, m, "counter_asset") or "").upper()
        fee_asset, fee_amount = (None, None) if shown != counter else _fee(r, m, counter)
    else:
        counter = _text_of(r, m, "counter_asset")
        value, unit = number(r.get(m.columns.get("counter_amount", "")), m.decimal)
        counter = counter or unit
        if not counter or value is None:
            raise Problem("counter_missing")
        value = abs(value)
        fee_asset, fee_amount = _fee(r, m, counter)
    buy = kind == "buy"
    return Movement(
        timestamp=at,
        kind=Kind.TRADE,
        incoming_asset=asset if buy else counter,
        incoming_amount=qty if buy else value,
        outgoing_asset=counter if buy else asset,
        outgoing_amount=value if buy else qty,
        fee_asset=fee_asset,
        fee_amount=fee_amount,
        external_id=_text_of(r, m, "id"),
        comment=_text_of(r, m, "comment") or type_value or kind,
        raw=_raw(r),
    )


def _movement_row(r: dict, m: Mapping, at: datetime) -> tuple[str, dict | Movement | None]:
    """One row of the movement form: a whole movement, or one side of a trade."""
    c = m.columns
    type_value = _text_of(r, m, "type") or ""
    kind = m.values.get(type_value) if c.get("type") else m.kind
    if kind is None:
        raise Problem(f"unmapped:{type_value[:30]}")
    if kind == "ignore":
        return "ignore", None
    asset = _text_of(r, m, "asset")
    amount, unit = number(r.get(c.get("amount", "")), m.decimal)
    asset = asset or unit
    if not asset or amount is None:
        raise Problem("amount_missing")
    if kind in ("buy", "sell"):
        return "one", _whole_trade(r, m, at, kind, asset, abs(amount), type_value)
    fee_asset, fee_amount = _fee(r, m, asset)
    if kind == "trade":
        return "part", {
            "asset": asset,
            "amount": amount,
            "fee": (fee_asset, fee_amount),
            "raw": _raw(r),
        }
    base = {
        "timestamp": at,
        "fee_asset": fee_asset,
        "fee_amount": fee_amount,
        "external_id": _text_of(r, m, "id"),
        "comment": _text_of(r, m, "comment") or type_value,
        "raw": _raw(r),
    }
    if amount == 0 and kind != "fee":
        return "ignore", None
    fiat = asset.upper() in FIAT
    if kind == "deposit":
        mv = Movement(
            kind=Kind.FIAT_DEPOSIT if fiat else Kind.RECEIVE,
            incoming_asset=asset,
            incoming_amount=abs(amount),
            **base,
        )
    elif kind == "withdrawal":
        mv = Movement(
            kind=Kind.FIAT_WITHDRAWAL if fiat else Kind.SEND,
            outgoing_asset=asset,
            outgoing_amount=abs(amount),
            **base,
        )
    elif kind == "income":
        mv = Movement(
            kind=Kind.INCOME,
            income_kind=m.income_kind,
            incoming_asset=asset,
            incoming_amount=abs(amount),
            **base,
        )
    elif kind == "internal":
        side = "incoming" if amount > 0 else "outgoing"
        mv = Movement(
            kind=Kind.INTERNAL_TRANSFER,
            **{f"{side}_asset": asset, f"{side}_amount": abs(amount)},
            **base,
        )
    elif kind == "convert":
        return "convert", _convert(r, m, base)
    elif kind == "fee":
        mv = Movement(
            kind=Kind.FEE, fee_asset=asset, fee_amount=abs(amount) + (fee_amount or 0), **base
        )
    else:
        raise Problem(f"kind:{kind}")
    return "one", mv


def _convert(r: dict, m: Mapping, base: dict) -> Movement:
    """A swap written out in the note: "Converted 292.32 USDT to 292.91 USDC"."""
    note = _text_of(r, m, "comment") or ""
    hit = CONVERT.search(note)
    if not hit:
        raise Problem(f"convert:{note[:40]}")
    out_qty, out_asset, in_qty, in_asset = hit.groups()
    fee_asset, fee_amount = _fee(r, m, out_asset)  # a swap's fee comes off what is given
    return Movement(
        **(base | {"comment": note, "fee_asset": fee_asset, "fee_amount": fee_amount}),
        kind=Kind.TRADE,
        outgoing_asset=out_asset,
        outgoing_amount=abs(number(out_qty, m.decimal)[0]),
        incoming_asset=in_asset,
        incoming_amount=abs(number(in_qty, m.decimal)[0]),
    )


def _join(key: str, at: datetime, parts: list[dict]) -> Movement:
    """The two rows of one trade: the plus side in, the minus side out, fees added up."""
    sides: dict[str, dict[str, Decimal]] = {"in": {}, "out": {}}
    fees: dict[str, Decimal] = {}
    for p in parts:
        side = "in" if p["amount"] > 0 else "out"
        sides[side][p["asset"]] = sides[side].get(p["asset"], Decimal(0)) + abs(p["amount"])
        fa, fv = p["fee"]
        if fa and fv:
            fees[fa] = fees.get(fa, Decimal(0)) + fv
    if len(sides["in"]) != 1 or len(sides["out"]) != 1 or len(fees) > 1:
        raise Problem("trade_sides")
    (ia, iv), (oa, ov) = next(iter(sides["in"].items())), next(iter(sides["out"].items()))
    fa, fv = next(iter(fees.items()), (None, None))
    return Movement(
        timestamp=at,
        kind=Kind.TRADE,
        incoming_asset=ia,
        incoming_amount=iv,
        outgoing_asset=oa,
        outgoing_amount=ov,
        fee_asset=fa,
        fee_amount=fv,
        external_id=key or None,
        comment=f"{oa} → {ia}",
        raw={"rows": [p["raw"] for p in parts]},
    )


def read(path: Path, mapping: Mapping) -> dict:
    """Every row as a movement, or as a problem with its row number. Writes nothing."""
    t = table(path, mapping.sheet, mapping.delimiter)
    names, records = _records(t, mapping.header_row)
    missing = [c for c in mapping.columns.values() if c not in names]
    if missing:
        raise Problem(f"columns:{', '.join(missing)[:100]}")
    need = ["date", "amount"] + (["side"] if mapping.form == "trade" else [])
    if mapping.form == "movement" and not mapping.kind:
        need.append("type")
    if lacking := [r for r in need if r not in mapping.columns]:
        raise Problem(f"roles:{','.join(lacking)}")
    date_col, time_col = mapping.columns["date"], mapping.columns.get("time")
    fmt = mapping.date_format or detect_format([r.get(date_col) for _, r in records[:SCAN]])
    movements: list[tuple[int, Movement]] = []
    problems: list[dict] = []
    skipped = 0
    groups: dict[str, tuple[int, datetime, list[dict]]] = {}
    converted: list[tuple[int, tuple[datetime, str | None]]] = []
    for n, r in records:
        try:
            at = when(r.get(date_col), r.get(time_col) if time_col else None, fmt, mapping.timezone)
            if mapping.form == "trade":
                mv = _trade_row(r, mapping, at)
                if mv is None:
                    skipped += 1
                else:
                    movements.append((n, mv))
                continue
            what, item = _movement_row(r, mapping, at)
            if what == "ignore":
                skipped += 1
            elif what == "one":
                movements.append((n, item))
            elif what == "convert":
                # Coinbase writes a swap twice (out and in, seconds apart) with the same
                # note: once is enough
                twin = next(
                    (
                        i
                        for i, (at0, note) in converted
                        if note == item.comment
                        and abs((at0 - item.timestamp).total_seconds()) < 300
                    ),
                    None,
                )
                if twin is None:
                    converted.append((len(movements), (item.timestamp, item.comment)))
                    movements.append((n, item))
                else:
                    skipped += 1
                    first = movements[twin][1]
                    if item.fee_amount and not first.fee_amount:  # the fee sits on one of them
                        first.fee_asset, first.fee_amount = item.fee_asset, item.fee_amount
            else:  # one side of a trade: rows with the same id (or time) belong together
                key = _text_of(r, mapping, "id") or ""
                g = groups.setdefault(key or at.isoformat(), (n, at, []))
                g[2].append(item)
        except (Problem, ValueError) as exc:
            problems.append({"row": n, "message": str(exc)[:200]})
    for key, (n, at, parts) in groups.items():
        try:
            movements.append((n, _join(key if mapping.columns.get("id") else "", at, parts)))
        except (Problem, ValueError) as exc:
            problems.append({"row": n, "message": str(exc)[:200]})
    movements.sort(key=lambda x: x[0])
    problems.sort(key=lambda x: x["row"])
    return {"movements": movements, "problems": problems, "skipped": skipped, "date_format": fmt}
