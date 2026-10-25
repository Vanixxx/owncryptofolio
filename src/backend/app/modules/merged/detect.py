"""Which two halves belong together — pure computation, no database (ADR 0005).

The tolerances are measured, not guessed: on 46 real pairs of Vanixxx's data (2026-08-28)
the largest amount difference was 0.63 % (ETH, network fee), the largest time offset
3 minutes. Hence ±1 % and ±1 hour.

**More than one candidate → no pair.** A guessed pair falsifies the cost basis and never
shows, because the result looks plausible; an open case stands visibly in the UI.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

WINDOW = timedelta(hours=1)
TOLERANCE = Decimal("0.01")
WIDE_WINDOW = timedelta(hours=24)
WIDE_TOLERANCE = Decimal("0.05")
"""For SUGGESTIONS only, never for linking: shown, linked on a click. A counterpart with
3 % network fee lies beyond detection and is still obviously the one."""


@dataclass(frozen=True)
class Half:
    fp: str
    at: datetime
    asset: str
    amount: Decimal
    tx: str | None = None
    source_id: int = 0


@dataclass(frozen=True)
class Pair:
    send: str
    receive: str
    reason: str  # tx | match | manual


def _fits(send: Half, recv: Half) -> bool:
    return (
        send.asset == recv.asset
        and send.amount > 0
        and abs(recv.at - send.at) <= WINDOW
        and abs(recv.amount - send.amount) <= send.amount * TOLERANCE
        and send.source_id != recv.source_id
    )


def _tx(tx: str) -> str:
    """One spelling of a transaction id: Coinbase writes an Ethereum hash without the
    "0x" the chain gives it (2026-10-11), and case does not matter."""
    tx = tx.strip().lower()
    return tx[2:] if tx.startswith("0x") else tx


def find_pairs(
    sends: list[Half],
    receives: list[Half],
    forbidden: set[tuple[str, str]] = frozenset(),
    taken: set[str] = frozenset(),
) -> tuple[list[Pair], list[str]]:
    """Pairs and the ambiguous sends. 1. same transaction id (chains give hashes; where an
    exchange names the same one, nothing is left to weigh), 2. asset, time, amount."""
    pairs: list[Pair] = []
    ambiguous: list[str] = []
    used = set(taken)
    by_tx: dict[str, list[Half]] = {}
    for r in receives:
        if r.tx:
            by_tx.setdefault(_tx(r.tx), []).append(r)
    for s in sends:
        if s.fp in used or not s.tx:
            continue
        hits = [
            r
            for r in by_tx.get(_tx(s.tx), [])
            if r.fp not in used
            and (s.fp, r.fp) not in forbidden
            and r.asset == s.asset
            and r.source_id != s.source_id
        ]
        if len(hits) == 1:
            pairs.append(Pair(s.fp, hits[0].fp, "tx"))
            used |= {s.fp, hits[0].fp}
    # Certain is what holds in EVERY way to pair as many as possible. Sends and receives that
    # could belong together form small groups; in each, all maximum pairings are tried and
    # only the pairs common to all of them are made. One send with two fitting receives, or
    # two sends for one receive: no common pair, both stay open as before. A coin moved
    # twice within the hour (Bitget → Ronin → bridge → Ethereum, 2026-10-04): only
    # Bitget→Ronin + Ronin→Ethereum pairs both sends, so that is made — still no guess.
    open_sends = [s for s in sends if s.fp not in used]
    fits = {
        s.fp: [
            r.fp
            for r in receives
            if r.fp not in used and (s.fp, r.fp) not in forbidden and _fits(s, r)
        ]
        for s in open_sends
    }
    for group in _groups(fits):
        for send_fp, recv_fp in _certain(group, fits):
            pairs.append(Pair(send_fp, recv_fp, "match"))
            used |= {send_fp, recv_fp}
    for s in open_sends:
        if s.fp not in used and any(r not in used for r in fits[s.fp]):
            ambiguous.append(s.fp)  # undecidable — guessing costs more than waiting
    return pairs, ambiguous


MAX_GROUP = 10
"""Sends in one group up to which all pairings are tried; beyond (never seen in real
data) only a send with a single, uncontested receive is paired."""


def _groups(fits: dict[str, list[str]]) -> list[list[str]]:
    """Sends connected through shared fitting receives."""
    by_recv: dict[str, list[str]] = {}
    for s, rs in fits.items():
        for r in rs:
            by_recv.setdefault(r, []).append(s)
    seen: set[str] = set()
    out = []
    for start, rs in fits.items():
        if start in seen or not rs:
            continue
        group, todo = [], [start]
        while todo:
            s = todo.pop()
            if s in seen:
                continue
            seen.add(s)
            group.append(s)
            todo += [o for r in fits[s] for o in by_recv[r] if o not in seen]
        out.append(group)
    return out


def _certain(group: list[str], fits: dict[str, list[str]]) -> list[tuple[str, str]]:
    if len(group) > MAX_GROUP:
        claims: dict[str, int] = {}
        for s in group:
            for r in fits[s]:
                claims[r] = claims.get(r, 0) + 1
        return [(s, fits[s][0]) for s in group if len(fits[s]) == 1 and claims[fits[s][0]] == 1]
    best: list[frozenset] = []
    size = 0

    def walk(i: int, taken: frozenset, chosen: frozenset) -> None:
        nonlocal best, size
        if i == len(group):
            if len(chosen) > size:
                best, size = [chosen], len(chosen)
            elif len(chosen) == size:
                best.append(chosen)
            return
        s = group[i]
        for r in fits[s]:
            if r not in taken:
                walk(i + 1, taken | {r}, chosen | {(s, r)})
        walk(i + 1, taken, chosen)

    walk(0, frozenset(), frozenset())
    if not size:
        return []
    common = frozenset.intersection(*best)
    return sorted(common)


@dataclass(frozen=True)
class Candidate:
    receive: str
    minutes: int
    diff_pct: Decimal
    sharp: bool  # fits the measured tolerance: left only because of a second candidate


def candidates(
    send: Half, receives: list[Half], forbidden: set[tuple[str, str]], taken: set[str]
) -> list[Candidate]:
    """Possible partners for ONE open send, best first (both deviations normalised to
    their limit: sorting by amount alone put a match from three days ago first)."""
    if send.amount <= 0:
        return []
    out = []
    for r in receives:
        if (
            r.asset != send.asset
            or r.fp in taken
            or (send.fp, r.fp) in forbidden
            or r.source_id == send.source_id
        ):
            continue
        gap = abs(r.at - send.at)
        diff = abs(r.amount - send.amount)
        if gap > WIDE_WINDOW or diff > send.amount * WIDE_TOLERANCE:
            continue
        out.append(
            Candidate(
                r.fp, int(gap.total_seconds() // 60), diff / send.amount * 100, _fits(send, r)
            )
        )
    limit_pct, limit_min = WIDE_TOLERANCE * 100, Decimal(int(WIDE_WINDOW.total_seconds() // 60))
    return sorted(out, key=lambda c: c.diff_pct / limit_pct + Decimal(c.minutes) / limit_min)
