"""Every user setting with its default and allowed values. The UI renders from this."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from zoneinfo import available_timezones


def _hhmm(v: Any) -> bool:
    if not isinstance(v, str) or len(v) != 5 or v[2] != ":":
        return False
    hh, mm = v[:2], v[3:]
    return hh.isdigit() and mm.isdigit() and int(hh) < 24 and int(mm) < 60


def _int_between(lo: int, hi: int) -> Callable[[Any], bool]:
    return lambda v: isinstance(v, int) and not isinstance(v, bool) and lo <= v <= hi


ACCENTS = ("default", "petrol", "blue", "purple", "amber", "green", "rose", "red")
ICONS = (
    "A1",
    "A2",
    "A3",
    "B1",
    "B2",
    "B3",
    "B4",
    "C",
    "C1",
    "D",
    "E1",
    "E2",
    "E3",
    "E4",
    "E5",
    "E6",
)


def _accents(v: Any) -> bool:
    return (
        isinstance(v, dict)
        and len(v) <= 20
        and all(isinstance(k, str) and len(k) <= 20 and a in ACCENTS for k, a in v.items())
    )


def _source_order(v: Any) -> bool:
    known = {"yahoo", "bitget", "binance"}
    return isinstance(v, list) and 0 < len(v) == len(set(v)) and all(x in known for x in v)


@dataclass(frozen=True)
class SettingDef:
    default: Any
    choices: tuple[Any, ...] | None = None
    check: Callable[[Any], bool] | None = None

    def valid(self, value: Any) -> bool:
        if self.choices is not None:
            return value in self.choices
        return self.check(value) if self.check else True


SETTINGS: dict[str, SettingDef] = {
    "appearance.style": SettingDef(
        "night",
        ("night", "neon", "terminal", "graphite", "rose", "contrast", "amethyst", "sand", "ios"),
    ),
    "appearance.theme": SettingDef("system", ("system", "light", "dark")),
    # a colour of one's own per style (Vanixxx, 2026-10-21): {style: accent}; missing = the
    # style's own colour
    "appearance.accents": SettingDef({}, check=_accents),
    # the home screen icon (Vanixxx, 2026-10-21)
    "appearance.icon": SettingDef("E5", ICONS),
    "general.language": SettingDef("de", ("de", "en")),
    "general.currency": SettingDef("EUR", ("EUR", "USD")),
    "general.timezone": SettingDef(
        "Europe/Berlin", check=lambda v: isinstance(v, str) and v in available_timezones()
    ),
    "backup.enabled": SettingDef(True, check=lambda v: isinstance(v, bool)),
    "fetch.enabled": SettingDef(True, check=lambda v: isinstance(v, bool)),
    "fetch.time": SettingDef("04:00", check=_hhmm),
    "backup.time": SettingDef("03:00", check=_hhmm),
    # Prices (ADR 0019): history once a day after the fetch, current prices in an interval.
    "prices.enabled": SettingDef(True, check=lambda v: isinstance(v, bool)),
    "prices.time": SettingDef("04:30", check=_hhmm),
    "prices.latest_minutes": SettingDef(5, check=_int_between(0, 1440)),  # 0 = off
    # Default order for NEW suggestions (ADR 0019/0038); existing mappings stay as they are.
    "prices.source_order": SettingDef(["yahoo", "bitget", "binance"], check=_source_order),
    "backup.keep_daily": SettingDef(14, check=_int_between(1, 365)),
    "backup.keep_monthly": SettingDef(12, check=_int_between(0, 120)),
    # Tax (ADR 0042): FIFO as the BMF reads it, LIFO to compare; airdrops untaxed by default.
    "tax.method": SettingDef("fifo", ("fifo", "lifo")),
    "tax.airdrop_taxable": SettingDef(False, check=lambda v: isinstance(v, bool)),
    # Head of the reports (ADR 0046): name and address on the source of funds and the tax
    # report, the tax number only on the tax report (Vanixxx, 2026-10-24); empty leaves it out.
    "report.name": SettingDef("", check=lambda v: isinstance(v, str) and len(v) <= 120),
    "report.address": SettingDef("", check=lambda v: isinstance(v, str) and len(v) <= 300),
    "report.tax_number": SettingDef("", check=lambda v: isinstance(v, str) and len(v) <= 40),
    # How much the log says (ADR 0047): set on the system page, applies at once.
    "system.log_level": SettingDef("INFO", ("DEBUG", "INFO", "WARNING", "ERROR")),
    # Claude through MCP (ADR 0049): on or off for all; read or edit is set per token.
    "mcp.enabled": SettingDef(False, check=lambda v: isinstance(v, bool)),
    # the read-only JSON API with the same tokens (ADR 0050): off until switched on
    "api.enabled": SettingDef(False, check=lambda v: isinstance(v, bool)),
}
