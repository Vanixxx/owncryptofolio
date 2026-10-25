"""The simple flow diagram of a source of funds drawn into the PDF (ADR 0046): boxes in
columns, height by amount, the flows as see-through bands, losses red. The same columns as
the screen: origins right before the step they feed, losses right after it."""

from __future__ import annotations

import math
from datetime import datetime
from decimal import Decimal

from app.modules.tax.files import BERLIN, _fit

SMALLEST = 0.005
ROOM = 10.0
"""Height every box gets at least, for its two label lines (mm)."""

COLORS = {
    "bank": (42, 191, 191),
    "card": (139, 124, 246),
    "gain": (62, 207, 142),
    "income": (224, 163, 58),
    "futures": (58, 167, 224),
    "unknown": (230, 160, 40),
    "money_unknown": (230, 90, 90),
    "loss": (230, 90, 90),
    "root": (45, 55, 65),
    "stay": (130, 150, 160),
}
LEAF_LABEL = {
    "bank": "Einzahlung vom Bankkonto",
    "card": "Kauf per Karte",
    "gain": "Kursgewinn",
    "income": "Ertrag",
    "futures": "Futures-Ergebnis",
    "unknown": "Zufluss ohne erfassten Kauf",
    "money_unknown": "Euro ohne erfasste Einzahlung",
    "loss": "Kursverlust",
}


def columns(nodes: list[dict], links: list[dict]) -> dict[str, int]:
    """Steps by their longest way from the start; an origin right before the step it feeds,
    a loss right after its step (as on the screen)."""
    leaf = {n["id"] for n in nodes if n["kind"] in LEAF_LABEL}
    ins: dict[str, list[str]] = {}
    outs: dict[str, list[str]] = {}
    for link in links:
        ins.setdefault(link["target"], []).append(link["source"])
        outs.setdefault(link["source"], []).append(link["target"])
    depth: dict[str, int] = {}

    def walk(i: str, seen: frozenset) -> int:
        if i in depth:
            return depth[i]
        if i in seen:
            return 1
        before = [walk(p, seen | {i}) for p in ins.get(i, []) if p not in leaf]
        depth[i] = max(before, default=0) + 1
        return depth[i]

    for n in nodes:
        if n["id"] not in leaf:
            walk(n["id"], frozenset())
    for n in nodes:
        if n["id"] not in leaf:
            continue
        after = [depth.get(p, 1) for p in ins.get(n["id"], [])]
        before = [depth.get(c, 1) for c in outs.get(n["id"], [])]
        depth[n["id"]] = max(after) + 1 if after else max(0, min(before, default=1) - 1)
    low = min(depth.values(), default=0)
    return {k: v - low for k, v in depth.items()}


def _label(n: dict, full: bool = False) -> tuple[str, str]:
    if n["kind"] == "root":
        return "Vorgang", ""
    if full:
        return _full_label(n)
    if n["kind"] in LEAF_LABEL:
        return LEAF_LABEL[n["kind"]], ""
    sub = ""
    if n.get("from"):
        a = datetime.fromisoformat(n["from"]).astimezone(BERLIN)
        b = datetime.fromisoformat(n["to"]).astimezone(BERLIN)
        sub = f"{a:%d.%m.%Y}" + (f" - {b:%d.%m.%Y}" if a.date() != b.date() else "")
        sub += f" · {n.get('count', 0)} Vorgänge"
    return n.get("place") or "außerhalb", sub


def _lines(doc, text: str, width: float, most: int = 2) -> list[str]:
    """Words onto at most `most` lines of `width`; the last one cut if still too long."""
    out: list[str] = []
    for word in text.split(" "):
        if out and doc.get_string_width(f"{out[-1]} {word}") <= width:
            out[-1] = f"{out[-1]} {word}"
        else:
            out.append(word)
    if len(out) > most:
        out = out[: most - 1] + [" ".join(out[most - 1 :])]
    return [_fit(doc, line, width) for line in out]


def _full_label(n: dict) -> tuple[str, str]:
    """A step of the full flow: what it was, then place and day."""
    from app.modules.tax.origin_files import KIND, _cell

    if n.get("detail") == "small":
        return f"kleine Anteile: {LEAF_LABEL.get(n['kind'], n['kind'])}", ""
    if n.get("detail") == "until_transfer":
        return f"{LEAF_LABEL[n['kind']]} bis zum Transfer", ""
    if n.get("detail") == "direct":
        name = "Bezahlt direkt " + ("per Karte" if n["kind"] == "card" else "vom Bankkonto")
    else:
        name = KIND.get(n["kind"], n["kind"])
    if n.get("qty") and n.get("asset") and n["kind"] not in ("gain", "loss"):
        name += f" {_cell(Decimal(n['qty']), 'qty')} {n['asset']}"
        if n.get("into_asset"):
            name += f" > {_cell(Decimal(n['into_qty']), 'qty')} {n['into_asset']}"
    day = ""
    if n.get("at"):
        day = f"{datetime.fromisoformat(n['at']).astimezone(BERLIN):%d.%m.%Y}"
    return name, " · ".join(x for x in (n.get("place") or "", day) if x)


FULL_MOST = 150
"""More boxes than this do not fit one page: the PDF points to the chain and the Excel."""


def draw(doc, flow: dict, money, total: float | None = None, full: bool = False) -> None:
    """On a new landscape page: the flow, scaled to fit."""
    nodes, links = flow["nodes"], flow["links"]
    if not nodes or not links:
        return
    # on paper the smallest boxes only crowd the rest: below 0.5 % of the largest they go
    big: dict[str, float] = {}
    for link in links:
        v = float(Decimal(link["value"]))
        for end in (link["source"], link["target"]):
            big[end] = big.get(end, 0) + v
    least = max(big.values(), default=0) / 2 * SMALLEST
    keep = {n["id"] for n in nodes if n["kind"] == "root" or big.get(n["id"], 0) / 2 >= least}
    nodes = [n for n in nodes if n["id"] in keep]
    links = [li for li in links if li["source"] in keep and li["target"] in keep]
    col = columns(nodes, links)
    value: dict[str, float] = {}
    inflow: dict[str, float] = {}
    outflow: dict[str, float] = {}
    for link in links:
        v = float(Decimal(link["value"]))
        outflow[link["source"]] = outflow.get(link["source"], 0) + v
        inflow[link["target"]] = inflow.get(link["target"], 0) + v
    for n in nodes:
        value[n["id"]] = max(inflow.get(n["id"], 0), outflow.get(n["id"], 0))
    ncol = max(col.values()) + 1
    # a column of many steps gets a larger sheet (A3 landscape), else they would not fit
    fullest = max(sum(1 for n in nodes if col[n["id"]] == c) for c in set(col.values()))
    doc.add_page(orientation="L", format="A3" if fullest > 10 else "A4")
    doc.set_auto_page_break(False)  # a box near the bottom must not start a new page
    try:
        _draw_page(doc, nodes, links, value, inflow, outflow, col, ncol, money, total, full)
    finally:
        doc.set_auto_page_break(True, margin=14)


def _draw_page(doc, nodes, links, value, inflow, outflow, col, ncol, money, total, full) -> None:
    doc.set_font("Helvetica", "B", 13)
    title = "komplett" if full else "vereinfacht"
    doc.cell(0, 8, f"Mittelflussdiagramm ({title})", new_x="LMARGIN", new_y="NEXT")
    doc.set_font("Helvetica", "", 8)
    if full and len(nodes) > FULL_MOST:
        doc.multi_cell(
            0,
            5,
            f"Mit {len(nodes)} Schritten passt das komplette Diagramm nicht auf eine Seite. Jeder "
            "Schritt steht in der Belegkette oben und einzeln in der Excel-Datei.",
            new_x="LMARGIN",
            new_y="NEXT",
        )
        return
    doc.cell(
        0,
        5,
        (
            "Jeder Schritt ab 1 % des Betrags, kleinere als ein Strom je Herkunft; "
            if full
            else "Links die Herkunft, in der Mitte die Börsen und Wallets, rechts der Vorgang; "
        )
        + "rot: Kursverluste. Breite der Ströme nach Betrag.",
        new_x="LMARGIN",
        new_y="NEXT",
    )
    top, bottom = doc.get_y() + 4, doc.h - 16
    left, right = doc.l_margin, doc.w - doc.r_margin - 46  # room for the last labels
    node_w, gap = 3.5, 7.0
    per_col: dict[int, list[dict]] = {}
    for n in nodes:
        per_col.setdefault(col[n["id"]], []).append(n)
    # order in a column by the middle of what feeds it (fewer crossings), two passes
    pos: dict[str, float] = {}
    for _ in range(2):
        for c in range(ncol):
            ns = per_col.get(c, [])

            def key(n: dict) -> float:
                # the middle of what feeds it; an origin by what it feeds
                ys = [
                    pos[li["source"]]
                    for li in links
                    if li["target"] == n["id"] and li["source"] in pos
                ]
                if not ys:
                    ys = [
                        pos[li["target"]]
                        for li in links
                        if li["source"] == n["id"] and li["target"] in pos
                    ]
                return sum(ys) / len(ys) if ys else 0.0

            ns.sort(key=key)
            for i, n in enumerate(ns):
                pos[n["id"]] = i
    usable = bottom - top
    # the fullest column decides how much room a box and its gap get (never past the page)
    most = max(len(ns) for ns in per_col.values())
    gap = min(gap, usable * 0.12 / most)
    room = min(ROOM, usable * 0.5 / most)
    if room < 3.6:  # too many boxes for one page: a picture nobody can read helps nobody
        doc.multi_cell(
            0,
            5,
            f"In einer Spalte stehen {most} Schritte, das passt nicht lesbar auf eine Seite. Jeder "
            "Schritt steht in der Belegkette und einzeln in der Excel-Datei.",
            new_x="LMARGIN",
            new_y="NEXT",
        )
        return
    lines = 2 if room >= 9 else 1
    big_font = min(6.8, room * 0.8)
    small_font = min(6.0, room * 0.7)
    scale = min(
        (usable - (gap + room) * len(ns)) / max(sum(value[n["id"]] for n in ns), 1e-9)
        for ns in per_col.values()
        if ns
    )
    xs = {c: left + (right - left - node_w) * c / max(ncol - 1, 1) for c in range(ncol)}
    colw = (right - left) / max(ncol - 1, 1)
    box: dict[str, tuple[float, float, float]] = {}  # x, y, height
    for c, ns in per_col.items():
        y = top
        for n in ns:
            h = max(value[n["id"]] * scale, 0.6)
            box[n["id"]] = (xs[c], y, h)
            y += max(h, room) + gap
    # flows: bands from the right edge of the source to the left edge of the target
    out_y = {k: v[1] for k, v in box.items()}
    in_y = {k: v[1] for k, v in box.items()}
    for link in sorted(links, key=lambda li: (box[li["source"]][1], box[li["target"]][1])):
        s, t = link["source"], link["target"]
        w = float(Decimal(link["value"])) * scale
        if w <= 0.05:
            continue
        x0, x1 = box[s][0] + node_w, box[t][0]
        y0, y1 = out_y[s], in_y[t]
        out_y[s] += w
        in_y[t] += w
        color = COLORS["loss"] if link["loss"] else COLORS.get(_kind(nodes, s), COLORS["stay"])
        pts_top, pts_bottom = [], []
        for i in range(17):
            f = i / 16
            e = (1 - math.cos(math.pi * f)) / 2
            x = x0 + (x1 - x0) * f
            pts_top.append((x, y0 + (y1 - y0) * e))
            pts_bottom.append((x, y0 + w + (y1 - y0) * e))
        with doc.local_context(fill_opacity=0.35):
            doc.set_fill_color(*color)
            doc.polygon(pts_top + pts_bottom[::-1], style="F")
    for n in nodes:
        x, y, h = box[n["id"]]
        kind = "root" if n.get("goal") else n["kind"]
        doc.set_fill_color(*COLORS.get(kind, COLORS["stay"]))
        doc.rect(x, y, node_w, h, style="F")
        name, sub = _label(n, full)
        if n["kind"] == "root" or n.get("goal"):  # its own amount: in minus losses, all of it
            shown = total if total is not None else inflow.get(n["id"], 0) - outflow.get(n["id"], 0)
        else:
            shown = value[n["id"]]
        # the name on up to two lines, then amount and time, all within the column
        width = 44 if col[n["id"]] == ncol - 1 else colw - node_w - 2
        doc.set_font("Helvetica", "B", big_font)
        names = _lines(doc, name, width, lines)
        doc.set_font("Helvetica", "", small_font)
        rest = _lines(doc, money(shown) + (f" · {sub}" if sub else ""), width, lines)
        lh, sh = big_font * 0.44, small_font * 0.45
        y0 = y + max(h, room) / 2 - (len(names) * lh + len(rest) * sh) / 2
        doc.set_font("Helvetica", "B", big_font)
        for k, line in enumerate(names):
            doc.set_xy(x + node_w + 1.2, y0 + k * lh)
            doc.cell(width, lh, line)
        doc.set_font("Helvetica", "", small_font)
        for k, line in enumerate(rest):
            doc.set_xy(x + node_w + 1.2, y0 + len(names) * lh + k * sh)
            doc.cell(width, sh, line)


def _kind(nodes: list[dict], node_id: str) -> str:
    return next((n["kind"] for n in nodes if n["id"] == node_id), "stay")
