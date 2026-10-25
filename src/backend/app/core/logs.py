"""The recent log lines in memory, for the live view on the system page (ADR 0047).

Backend and browser lines land in one ring: the browser sends its errors to the backend,
which logs them under "frontend". Addresses, keys and tokens are masked before a line is
kept: the view must never show what the logs should not hold. The ring starts empty on
every start; the full log stays on stdout (docker logs)."""

from __future__ import annotations

import logging
import re
import threading
from collections import deque
from datetime import UTC, datetime

LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR")
SIZE = 2000
# chatty helpers stay quiet even at DEBUG: they would bury the app's own lines
QUIET = ("httpcore", "hpack", "multipart", "asyncio", "watchfiles", "python_multipart")
# the reloader and the server itself; their access lines are left out (one per request)
SERVER = ("uvicorn", "uvicorn.error")

_SECRET = re.compile(
    r"(?i)\b(api[_-]?key|apikey|secret|token|password|passphrase|signature|sign|key)"
    r"(\s*[=:]\s*|\"\s*:\s*\")([^\s&\"',;]+)"
)
_BEARER = re.compile(r"(?i)\b(bearer)\s+[A-Za-z0-9._~+/=-]+")
_ADDRESS = re.compile(
    r"\b(0x[0-9a-fA-F]{40,}"  # EVM addresses and hashes
    r"|(?:bc1|tb1|ltc1)[0-9a-z]{20,}"  # bech32
    r"|[xyz]pub[1-9A-HJ-NP-Za-km-z]{100,}"  # extended public keys
    r"|[1-9A-HJ-NP-Za-km-z]{25,})\b"  # base58: legacy addresses, Solana, Tron
)


def mask(text: str) -> str:
    """Secrets out, addresses shortened to their first and last characters."""
    text = _SECRET.sub(lambda m: f"{m[1]}{m[2]}***", text)
    text = _BEARER.sub(lambda m: f"{m[1]} ***", text)
    return _ADDRESS.sub(lambda m: f"{m[1][:6]}…{m[1][-4:]}", text)


class Ring(logging.Handler):
    def __init__(self, size: int = SIZE) -> None:
        super().__init__(logging.DEBUG)
        self.lines: deque[dict] = deque(maxlen=size)
        self.seq = 0
        self._guard = threading.Lock()

    def emit(self, record: logging.LogRecord) -> None:
        try:
            text = record.getMessage()
            if record.exc_info:
                text += "\n" + logging.Formatter().formatException(record.exc_info)
            line = {
                "at": datetime.fromtimestamp(record.created, UTC).isoformat(),
                "level": record.levelname,
                "logger": record.name,
                "origin": "frontend" if record.name.startswith("frontend") else "backend",
                "message": mask(text),
            }
        except Exception:  # a broken log call must not break the app
            self.handleError(record)
            return
        with self._guard:
            self.seq += 1
            self.lines.append({"seq": self.seq, **line})

    def since(self, after: int = 0, limit: int = 500) -> list[dict]:
        with self._guard:
            new = [x for x in self.lines if x["seq"] > after]
        return new[-limit:]


ring = Ring()


def install() -> None:
    """Hang the ring onto the root logger and the server's own loggers (once)."""
    root = logging.getLogger()
    if ring not in root.handlers:
        root.addHandler(ring)
    for name in SERVER:
        lg = logging.getLogger(name)
        # uvicorn's own logger does not pass its lines (and uvicorn.error's) on to root
        if not lg.propagate and ring not in lg.handlers:
            lg.addHandler(ring)


def level() -> str:
    return logging.getLevelName(logging.getLogger().level)


def set_level(name: str) -> None:
    """The level for every logger from now on; the setting `system.log_level` keeps it."""
    if name not in LEVELS:
        return
    value = logging.getLevelName(name)
    logging.getLogger().setLevel(value)
    for n in SERVER:
        logging.getLogger(n).setLevel(value)
    for n in QUIET:
        logging.getLogger(n).setLevel(max(value, logging.WARNING))
