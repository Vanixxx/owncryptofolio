"""Source of funds (ADR 0046): for a sale, a transfer (also between own wallets) or a
withdrawal, where its money came from — the split by kind of origin and the chain of steps
back to the deposits, as a tree for the PDF and as a flat list of every step for Excel.

The order follows the tax setting (FIFO/LIFO): the same lots as in the tax report."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.modules.merged import service as merged
from app.modules.portfolio.service import _cached
from app.modules.prices.service import Valuer
from app.modules.raw.models import RawTransaction
from app.modules.tax.engine import Engine, Result
from app.modules.tax.lots import ZERO
from app.modules.tax.report import _eur, _n, _t, params, place_names
from app.modules.tax.trace import LEAVES, Node, Trace

TARGETS = ("sale", "swap", "payment", "transfer", "withdrawal")
VIRTUAL = ("holding", "holdings", "planned")
"""Steps made up for one answer: a coin's holding today, all of them, a planned step."""
SMALL = Decimal("0.01")
"""Branches below 1 % of the amount are summed up in the tree (Vanixxx, 2026-10-17); the
Excel list keeps every step."""
MAX_LINES = 400


def traced(session: Session, method: str | None = None) -> Result:
    p = params(session, method)
    p.trace = True

    def make():
        return Engine(merged.build(session), Valuer(session), p).run()

    return _cached(session, f"origin-{p.method}-{p.airdrop_taxable}", make)


def candidates(session: Session, method: str | None = None) -> list[dict]:
    """Every step one can ask about, newest first."""
    tr = traced(session, method).trace
    names = place_names(session)
    valuer = Valuer(session)
    seen, out = set(), []
    for nid in tr.by_row.values():
        n = tr.nodes[nid]
        if n.kind not in TARGETS or nid in seen:
            continue
        seen.add(nid)
        step = _step(n, names) | {"row": n.row}
        if n.kind == "transfer":  # coins moved count with their value that day, as in explain
            price = valuer.eur(n.asset, n.at.date())
            if price is not None:
                step["value"] = _eur(price * n.qty)
        out.append(step)
    return sorted(out, key=lambda x: x["at"], reverse=True)


def _step(n: Node, names: dict[int, str]) -> dict:
    return {
        "kind": n.kind,
        "at": _t(n.at),
        "place": names.get(n.source),
        "to": None if n.to_source is None else names.get(n.to_source),
        "asset": n.asset,
        "qty": _n(n.qty),
        "value": _eur(n.value),
    } | ({"into_asset": n.into[0], "into_qty": _n(n.into[1])} if n.into else {})


def _ancestors(tr: Trace, root: int) -> list[int]:
    """Every node the root's money passed through, oldest first (parents are always older:
    the walk is in time)."""
    seen, todo = {root}, [root]
    while todo:
        for p, _ in tr.nodes[todo.pop()].parents:
            if p not in seen:
                seen.add(p)
                todo.append(p)
    return sorted(seen)


def _flow(tr: Trace, order: list[int], root: int, amount: Decimal) -> dict[int, Decimal]:
    """How much of `amount` passed through each node: handed down by weight, newest first."""
    got = {root: amount}
    for nid in reversed(order):
        v = got.get(nid)
        node = tr.nodes[nid]
        total = sum((w for _, w in node.parents), ZERO)
        if not v or total <= 0:
            continue
        for p, w in node.parents:
            got[p] = got.get(p, ZERO) + v * w / total
    return got


def explain(session: Session, row: int, method: str | None = None) -> dict:
    res = traced(session, method)
    tr = res.trace
    nid = tr.by_row.get(row)
    if nid is None or tr.nodes[nid].kind not in TARGETS:
        raise AppError("origin.not_found", 404)
    root = tr.nodes[nid]
    names = place_names(session)
    base, extra_gain = root.value, ZERO
    if root.kind == "transfer":
        # coins moved are worth their market value then: the difference to their cost is a
        # price gain or loss (negative), the origins keep their full amounts
        price = Valuer(session).eur(root.asset, root.at.date())
        if price is not None:
            extra_gain = price * root.qty - root.value
    target = _step(root, names) | {"row": root.row, "amount": _eur(base + extra_gain)}
    out = _result(session, res, tr, nid, base, extra_gain, target, names, method)
    out.pop("vectors")
    return out


def _result(session, res: Result, tr, nid: int, base, extra_gain, target, names, method) -> dict:
    """Split, chain and steps of what passed through node `nid` (worth base + extra_gain)."""
    root = tr.nodes[nid]
    amount = base + extra_gain
    order = _ancestors(tr, nid)
    through = _flow(tr, order, nid, base)
    mix: dict[str, Decimal] = {k: ZERO for k in LEAVES}
    for k_id, v in through.items():
        n = tr.nodes[k_id]
        if n.kind in LEAVES:
            mix[n.kind] += v
    mix["gain" if extra_gain > 0 else "loss"] += extra_gain
    # a step whose parents carry no weight (nothing known before it) counts as unknown
    known = sum(mix.values(), ZERO)
    if amount - known > Decimal("0.005"):
        mix["unknown"] += amount - known
    tx, channel = _tx_ids(
        session, {tr.nodes[i].row for i in order} | {tr.nodes[i].row_in for i in order} - {None}
    )
    vecs = _vectors(tr, order)
    used = [
        i for i in order if through.get(i) and tr.nodes[i].kind not in ("gain", "loss", *VIRTUAL)
    ]
    steps = [
        _step(tr.nodes[i], names)
        | {
            "row": tr.nodes[i].row,
            "share": _eur(through[i]),
            "tx": tx.get(tr.nodes[i].row),
            "channel": channel.get(tr.nodes[i].row),
        }
        | ({"detail": tr.nodes[i].detail} if tr.nodes[i].detail else {})
        for i in used
    ]
    lost = [x for x in res.losses if x.at <= root.at]
    return {
        "target": target,
        "method": params(session, method).method.value,
        "mix": [
            {"kind": k, "value": _eur(v), "share": _eur(v / amount * 100 if amount else ZERO)}
            for k, v in sorted(mix.items(), key=lambda kv: -kv[1])
            if abs(v) > Decimal("0.005")
        ],
        "tree": _tree(tr, nid, base, extra_gain, names, tx, vecs),
        "vectors": vecs,
        "steps": steps,
        "diagram": _diagrams(tr, order, through, nid, names, vecs, extra_gain),
        "overview": _overview(session, tr, used, channel, names),
        "deposits": [s for s in steps if s["kind"] in ("bank", "card")],
        "lost": {"count": len(lost), "assets": sorted({x.asset for x in lost})},
    }


def _tx_ids(session: Session, rows: set[int]) -> tuple[dict[int, str], dict[int, str]]:
    """Per row its id at the source and how it came in: api · chain · file · manual."""
    ids, channel = {}, {}
    for rid, ext, ch in session.execute(
        select(RawTransaction.id, RawTransaction.external_id, RawTransaction.channel).where(
            RawTransaction.id.in_(rows)
        )
    ):
        if ext and not ext.startswith("form:"):
            ids[rid] = ext
        channel[rid] = ch
    return ids, channel


def _overview(session: Session, tr, used: list[int], channel, names) -> dict:
    """What a bank looks at first (as Blockpit shows it): the time span, how many
    transactions, which exchanges and wallets, and how their data came in."""
    from app.modules.sources.models import Source

    nodes = [tr.nodes[i] for i in used if tr.nodes[i].row]
    rows = {n.row for n in nodes}
    per: dict[int, dict] = {}
    for n in nodes:
        # a transfer counts at both ends, each with its own row and channel
        ends = [(n.source, n.row)]
        if n.to_source is not None:
            ends.append((n.to_source, n.row_in or n.row))
        for src, row in ends:
            e = per.setdefault(src, {"rows": set(), "channels": {}})
            if row not in e["rows"]:
                e["rows"].add(row)
                ch = channel.get(row) or "manual"
                e["channels"][ch] = e["channels"].get(ch, 0) + 1
    meta = {s.id: s for s in session.scalars(select(Source).where(Source.id.in_(per)))}
    sources = [
        {
            "place": names.get(src),
            "kind": meta[src].kind if src in meta else "outside",
            "address": meta[src].address if src in meta else None,
            "count": len(e["rows"]),
            "channels": e["channels"],
        }
        for src, e in sorted(per.items(), key=lambda kv: -len(kv[1]["rows"]))
    ]
    kinds: dict[str, int] = {}
    for r in rows:
        ch = channel.get(r) or "manual"
        kinds[ch] = kinds.get(ch, 0) + 1
    ats = [n.at for n in nodes]
    return {
        "from": _t(min(ats)) if ats else None,
        "to": _t(max(ats)) if ats else None,
        "transactions": len(rows),
        "sources": sources,
        "channels": kinds,
    }


def _vectors(tr: Trace, order: list[int]) -> dict[int, dict[str, Decimal]]:
    """Per node the share of each kind of origin in it (oldest first: parents are done)."""
    out: dict[int, dict[str, Decimal]] = {}
    for i in order:
        n = tr.nodes[i]
        if n.kind in LEAVES:
            out[i] = {n.kind: Decimal(1)}
            continue
        total = sum((w for _, w in n.parents), ZERO)
        if total <= 0:  # sold for nothing: no share of anything reaches later steps
            out[i] = {}
            continue
        vec: dict[str, Decimal] = {}
        for p, w in n.parents:
            for k, x in out.get(p, {}).items():
                vec[k] = vec.get(k, ZERO) + x * w / total
        out[i] = vec or {"unknown": Decimal(1)}
    return out


def _tree(tr: Trace, nid: int, base: Decimal, extra_gain, names, tx, vecs) -> dict:
    """The chain as a tree: each step with what of the amount went through it; branches
    below SMALL of the amount summed per step, at most MAX_LINES lines."""
    floor = abs(base + extra_gain) * SMALL
    lines = [0]

    def node(i: int, value: Decimal, depth: int, floor: Decimal) -> dict:
        n = tr.nodes[i]
        if n.kind == "holding":  # each coin of the holdings by its own 1 %
            floor = value * SMALL
        lines[0] += 1
        out = _step(n, names) | {"row": n.row, "share": _eur(value), "tx": tx.get(n.row)}
        if n.kind in VIRTUAL:  # no place, no transaction: a holding of today
            for k in ("place", "to", "row", "tx"):
                out.pop(k, None)
        if n.detail:
            out["detail"] = n.detail
        total = sum((w for _, w in n.parents), ZERO)
        if not n.parents or total <= 0:
            return out
        weights: dict[int, Decimal] = {}
        for p, w in n.parents:  # one lot taken in several pieces: one branch
            weights[p] = weights.get(p, ZERO) + w
        kids: list[dict] = []
        buckets: dict[str, list] = {"small": [ZERO, 0, {}], "more": [ZERO, 0, {}]}
        for p, w in sorted(weights.items(), key=lambda pw: -pw[1]):
            v = value * w / total
            key = (
                "small"
                if abs(v) < floor
                else "more"
                if lines[0] >= MAX_LINES or depth > 40
                else None
            )
            if key is None:
                kids.append(node(p, v, depth + 1, floor))
                continue
            b = buckets[key]
            b[0] += v
            b[1] += 1
            for k, x in vecs.get(p, {"unknown": Decimal(1)}).items():
                b[2][k] = b[2].get(k, ZERO) + v * x
        for kind, (v, count, mix) in buckets.items():
            if v > 0:
                kids.append(
                    {
                        "kind": kind,
                        "share": _eur(v),
                        "count": count,
                        "mix": {k: _eur(x) for k, x in sorted(mix.items(), key=lambda kx: -kx[1])},
                    }
                )
        out["children"] = kids
        return out

    root = node(nid, base, 0, floor)
    if abs(extra_gain) > Decimal("0.005"):
        root["share"] = _eur(base + extra_gain)
        kind = "gain" if extra_gain > 0 else "loss"
        root.setdefault("children", []).append(
            {"kind": kind, "share": _eur(extra_gain), "detail": "until_transfer"}
        )
    return root


class Overlay:
    """The trace plus steps made up for one answer (today's holdings): the trace itself is
    cached for every request and stays untouched."""

    def __init__(self, tr: Trace) -> None:
        self.base, self.extra = tr.nodes, []
        self.nodes = self

    def __getitem__(self, i: int) -> Node:
        return self.base[i] if i < len(self.base) else self.extra[i - len(self.base)]

    def add(self, kind, at, asset, qty, value, parents, detail=None) -> Node:
        node = Node(len(self.base) + len(self.extra), kind, 0, at, 0, asset, qty, value, parents)
        node.detail = detail
        self.extra.append(node)
        return node


def _unrealized(g: Overlay, parents: list, at, asset: str, qty, value: Decimal) -> None:
    """Today's value against what the origins weigh: above a price gain not yet sold, below
    a price loss not yet sold (negative)."""
    delta = value - sum((w for _, w in parents), ZERO)
    if abs(delta) > Decimal("0.005"):
        kind = "gain" if delta > 0 else "loss"
        leaf = g.add(kind, at, asset, qty, abs(delta), [], "unrealized")
        parents.append((leaf.id, delta))


def holdings(session: Session, method: str | None = None, asset: str | None = None) -> dict:
    """Where today's holdings came from (Vanixxx, 2026-10-17): every open lot and the euro on
    the exchanges with their origin, valued today; above the cost an unrealized price gain.
    `asset` narrows it to one coin (with its chain), else all with a split per coin."""
    from datetime import UTC, datetime

    from app.modules.tax.lots import local_day

    res = traced(session, method)
    tr = res.trace
    g = Overlay(tr)
    names = place_names(session)
    valuer = Valuer(session)
    now = datetime.now(UTC)
    today = local_day(now)
    groups: dict[str, dict] = {}
    for _, lot in res.lots.open():
        e = groups.setdefault(lot.asset, {"qty": ZERO, "cost": ZERO, "parents": []})
        e["qty"] += lot.qty
        e["cost"] += lot.cost
        w = lot.cost
        if w <= 0:  # an untaxed airdrop: weighed by its value, else it would vanish
            price = valuer.latest_eur(lot.asset, today)
            w = price * lot.qty if price else ZERO
        e["parents"] += Trace.spread(lot.parts, w)
    for (_, currency), slices in tr.pots.items():
        e = groups.setdefault(currency, {"qty": ZERO, "cost": ZERO, "parents": []})
        for sl in slices:
            e["qty"] += sl.amount
            e["cost"] += sl.amount
            e["parents"] += Trace.spread(sl.parts, sl.amount)
    coins = []
    for a, e in groups.items():
        if e["qty"] <= 0 or not e["parents"]:
            continue
        price = Decimal(1) if a == "EUR" else valuer.latest_eur(a, today)
        value = price * e["qty"] if price is not None else None
        parents = list(e["parents"])
        if value is not None:
            _unrealized(g, parents, now, a, e["qty"], value)
        node = g.add(
            "holding", now, a, e["qty"], value if value is not None else e["cost"], parents
        )
        coins.append({"asset": a, "node": node, "priced": value is not None, "cost": e["cost"]})
    coins.sort(key=lambda c: -c["node"].value)
    if asset is not None:
        pick = next((c for c in coins if c["asset"] == asset), None)
        if pick is None:
            raise AppError("origin.not_found", 404)
        root = pick["node"]
    else:
        root = g.add(
            "holdings",
            now,
            "",
            ZERO,
            sum((c["node"].value for c in coins), ZERO),
            [(c["node"].id, c["node"].value) for c in coins],
        )
    target = {
        "kind": root.kind,
        "at": _t(now),
        "asset": root.asset,
        "qty": _n(root.qty),
        "amount": _eur(root.value),
        "value": _eur(root.value),
        "place": None,
        "to": None,
    }
    out = _result(session, res, g, root.id, root.value, ZERO, target, names, method)
    vecs = out.pop("vectors")
    out["coins"] = [
        {
            "asset": c["asset"],
            "qty": _n(c["node"].qty),
            "value": _eur(c["node"].value),
            "cost": _eur(c["cost"]),
            "priced": c["priced"],
            "mix": {
                k: _eur(x * c["node"].value)
                for k, x in sorted(vecs.get(c["node"].id, {}).items(), key=lambda kx: -kx[1])
                if abs(x * c["node"].value) > Decimal("0.005")
            },
        }
        for c in coins
        if (asset is None or c["asset"] == asset) and c["node"].value >= Decimal("0.01")
    ]
    return out


def planned_options(session: Session, method: str | None = None) -> list[dict]:
    """What a planned step can take: per source and coin the quantity held now (spot and
    futures together, euro in the pots)."""
    res = traced(session, method)
    names = place_names(session)
    held: dict[tuple[int, str], Decimal] = {}
    for (source, _, asset), lot in res.lots.open():
        held[(source, asset)] = held.get((source, asset), ZERO) + lot.qty
    for (source, currency), slices in res.trace.pots.items():
        amount = sum((s.amount for s in slices), ZERO)
        if amount > Decimal("0.005"):
            held[(source, currency)] = held.get((source, currency), ZERO) + amount
    return sorted(
        (
            {"source": s, "place": names.get(s), "asset": a, "qty": _n(q)}
            for (s, a), q in held.items()
            if q > 0
        ),
        key=lambda x: (x["place"] or "", x["asset"]),
    )


def planned(
    session: Session, source: int, asset: str, qty: Decimal, day, method: str | None = None
) -> dict:
    """A step not done yet (Vanixxx, 2026-10-17, as Blockpit offers it): `qty` of `asset`
    leaving `source` now — which lots it would take in the tax order and where their money
    came from, valued today. Nothing is booked."""
    from datetime import UTC, datetime

    from app.modules.tax.lots import Method, local_day

    if qty <= 0:
        raise AppError("origin.planned_qty", 400)
    res = traced(session, method)
    tr = res.trace
    g = Overlay(tr)
    names = place_names(session)
    now = datetime.now(UTC)
    today = local_day(now)
    valuer = Valuer(session)
    lifo = params(session, method).method is Method.LIFO
    parents: list[tuple[int, Decimal]] = []
    left, cost = qty, ZERO
    if asset == "EUR":
        for sl in tr.pots.get((source, "EUR"), []):
            if left <= 0:
                break
            used = min(left, sl.amount)
            parents += Trace.spread(sl.parts, used)
            cost += used
            left -= used
    else:
        lots = [lot for (s, _, a), lot in res.lots.open() if s == source and a == asset]
        # spot and futures of the source in one line, in the order the tax takes them
        for lot in sorted(lots, key=lambda x: (x.acquired, x.seq), reverse=lifo):
            if left <= 0:
                break
            used = min(left, lot.qty)
            part = lot.cost * used / lot.qty
            w = part
            if w <= 0:
                price = valuer.latest_eur(asset, today)
                w = price * used if price else ZERO
            parents += Trace.spread(lot.parts, w)
            cost += part
            left -= used
    if left > Decimal("0.00000001"):
        raise AppError("origin.planned_too_much", 400, held=_n(qty - left))
    price = Decimal(1) if asset == "EUR" else valuer.latest_eur(asset, today)
    value = price * qty if price is not None else cost
    _unrealized(g, parents, now, asset, qty, value)
    root = g.add("planned", now, asset, qty, value, parents)
    root.source = source
    target = {
        "kind": "planned",
        "at": day.isoformat() if day else _t(now),
        "asset": asset,
        "qty": _n(qty),
        "amount": _eur(value),
        "value": _eur(value),
        "place": names.get(source),
        "to": None,
    }
    out = _result(session, res, g, root.id, value, ZERO, target, names, method)
    out.pop("vectors")
    return out


def _diagrams(
    tr, order: list[int], through: dict, root: int, names: dict, vecs: dict, extra=ZERO
) -> dict:
    """The chain as a flow (ADR 0046): "full" with every step, "simple" with one box per stay
    of the money at an exchange or wallet (the same exchange twice when the money came back:
    a flow has no loops), the origins on the left, price losses flowing out to the right."""
    nodes = tr.nodes
    edges: dict[tuple[int, int], Decimal] = {}
    for c in order:
        v = through.get(c)
        n = nodes[c]
        total = sum((w for _, w in n.parents), ZERO)
        if not v or total <= 0:
            continue
        for p, w in n.parents:
            if p in through:
                edges[(p, c)] = edges.get((p, c), ZERO) + v * w / total
    used = [i for i in order if i in through]

    def link(src, dst, amount: Decimal) -> dict:
        # a loss leaves the step it belongs to: drawn from the step to the loss
        if amount < 0:
            return {"source": dst, "target": src, "value": _eur(-amount), "loss": True}
        return {"source": src, "target": dst, "value": _eur(amount), "loss": False}

    def label(n: Node) -> dict:
        return _step(n, names) | ({"detail": n.detail} if n.detail else {})

    # the price change of a transfer up to its day (not a step of the trace)
    if abs(extra) > Decimal("0.005"):
        edges[(-1, root)] = extra
    # full: every step from 1 % of the amount on, the smaller ones as one flow per origin
    floor = abs(through.get(root, ZERO) + extra) * SMALL
    big = {i for i in used if abs(through[i]) >= floor} | {root}
    small: dict[tuple[str, int], Decimal] = {}
    full_links = []
    for (p, c), a in edges.items():
        if c not in big or abs(a) <= Decimal("0.005"):
            continue
        if p == -1:
            full_links.append(link("x", f"n{c}", a))
        elif p in big:
            full_links.append(link(f"n{p}", f"n{c}", a))
        else:
            for k, x in vecs.get(p, {"unknown": Decimal(1)}).items():
                small[(k, c)] = small.get((k, c), ZERO) + a * x
    full_links += [
        link(f"s:{k}", f"n{c}", a) for (k, c), a in small.items() if abs(a) > Decimal("0.005")
    ]
    kinds = {k for k, _ in small}
    full = {
        "nodes": [
            {"id": f"n{i}", "goal": i == root} | label(nodes[i])
            for i in sorted(big)
            if i in through
        ]
        + [{"id": f"s:{k}", "kind": k, "detail": "small"} for k in sorted(kinds)]
        + (
            [{"id": "x", "kind": "gain" if extra > 0 else "loss", "detail": "until_transfer"}]
            if (-1, root) in edges
            else []
        ),
        "links": full_links,
    }
    # simple: in time order each step joins the box of its place, unless that closes a loop
    # (the money came back): then the place gets a new box. Leaves: one box per kind.
    inner = sorted(
        (i for i in used if nodes[i].kind not in (*LEAVES, *VIRTUAL) and i != root),
        key=lambda i: (nodes[i].at, i),
    )
    parents_of: dict[int, list[int]] = {}
    for p, c in edges:
        parents_of.setdefault(c, []).append(p)
    box: dict[int, str] = {}
    last: dict[int, str] = {}
    out: dict[str, set[str]] = {}

    def reaches(start: str, goals: set[str]) -> bool:
        seen, todo = {start}, [start]
        while todo:
            for t in out.get(todo.pop(), ()):
                if t in goals:
                    return True
                if t not in seen:
                    seen.add(t)
                    todo.append(t)
        return False

    for i in inner:
        src = nodes[i].source
        from_boxes = {box[p] for p in parents_of.get(i, []) if p in box}
        g = last.get(src)
        if g is None or reaches(g, from_boxes - {g}):
            g = f"g{i}"
            last[src] = g
        box[i] = g
        for b in from_boxes - {g}:
            out.setdefault(b, set()).add(g)

    def group(i: int) -> str:
        if i == -1:
            return "leaf:gain" if extra > 0 else "leaf:loss"
        if i == root or nodes[i].kind in VIRTUAL:  # today's holdings of a coin: the goal
            return "root"
        if nodes[i].kind in LEAVES:
            return f"leaf:{nodes[i].kind}"
        return box[i]

    links: dict[tuple[str, str], Decimal] = {}
    for (p, c), a in edges.items():
        gp, gc = group(p), group(c)
        if gp != gc:
            links[(gp, gc)] = links.get((gp, gc), ZERO) + a
    members: dict[str, list[Node]] = {}
    for i in used:
        members.setdefault(group(i), []).append(nodes[i])
    simple_nodes = []
    for g, ms in members.items():
        first = ms[0]
        ats = [m.at for m in ms]
        simple_nodes.append(
            {
                "id": g,
                "kind": "root" if g == "root" else first.kind if g.startswith("leaf:") else "stay",
                "place": None if g.startswith("leaf:") else names.get(first.source),
                "from": _t(min(ats)),
                "to": _t(max(ats)),
                "count": len({m.row for m in ms if m.row}),
            }
        )
    if (-1, root) in edges and group(-1) not in members:
        simple_nodes.append({"id": group(-1), "kind": group(-1)[5:], "place": None, "count": 0})
    linked = {e for (s, t), a in links.items() if abs(a) > Decimal("0.005") for e in (s, t)}
    simple = {
        # a box without a flow (an origin of 0.00 €) has nothing to show
        "nodes": [n for n in simple_nodes if n["id"] in linked or n["id"] == "root"],
        "links": [link(s, t, a) for (s, t), a in links.items() if abs(a) > Decimal("0.005")],
    }
    return {"simple": simple, "full": full}
