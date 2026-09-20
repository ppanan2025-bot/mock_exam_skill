#!/usr/bin/env python3
"""Compact textbook DFA/NFA figures (reportlab). Graphviz is not used: `dot` spreads states."""

from __future__ import annotations

import math
import re
import shutil
import subprocess
from collections import defaultdict, deque
from typing import Any

from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import Flowable

INK = colors.HexColor("#111111")
STATE_R = 14.5
START_LEN = 16.0
H_GAP = 66.0
V_GAP = 60.0
# a self-loop plus its label stands this far above the state it belongs to
LOOP_ROOM = 36.0
MAX_W = 120 * mm
MAX_H = 72 * mm

_TRANS = re.compile(
    r"\b([A-Za-z][A-Za-z0-9]*)\s*-{1,2}\s*"
    r"(eps(?:ilon)?|ε|ϵ|[A-Za-z0-9])\s*"
    r"(?:→|->|-->|>)\s*"
    r"([A-Za-z][A-Za-z0-9]*)",
    re.I,
)
_EPS = {"eps", "epsilon", "ε", "ϵ"}


def _norm_symbol(label: str) -> str:
    raw = label.strip()
    if raw.lower() in _EPS:
        return "ε"
    return raw


def infer_diagram_from_text(*texts: str) -> dict[str, Any] | None:
    """Build a diagram spec from `q0 -eps→ q1` / `s0 --a--> s1` sentences."""
    blob = " ".join(str(part or "") for part in texts)
    hits = _TRANS.findall(blob)
    if len(hits) < 2:
        return None
    transitions = []
    seen: set[tuple[str, str, str]] = set()
    states: list[str] = []
    for src, lab, dst in hits:
        symbol = _norm_symbol(lab)
        key = (src, symbol, dst)
        if key in seen:
            continue
        seen.add(key)
        transitions.append({"from": src, "symbol": symbol, "to": dst})
        for name in (src, dst):
            if name not in states:
                states.append(name)
    if len(transitions) < 2:
        return None
    lower = blob.lower()
    kind = "nfa" if any(t["symbol"] == "ε" for t in transitions) or "nfa" in lower else "dfa"
    return {
        "kind": kind,
        "states": states,
        "start": states[0],
        "accept": [],
        "transitions": transitions,
    }


def normalize_diagram(raw: dict[str, Any]) -> dict[str, Any]:
    kind = str(raw.get("kind") or raw.get("type") or "dfa").strip().lower()
    if kind in {"finite-automaton", "fa"}:
        kind = "dfa"
    states = [str(s) for s in (raw.get("states") or [])]
    transitions: list[tuple[str, str, str]] = []
    for item in raw.get("transitions") or []:
        if isinstance(item, dict):
            src = str(item.get("from") or item.get("src") or "")
            dst = str(item.get("to") or item.get("dst") or "")
            lab = str(item.get("symbol") or item.get("label") or item.get("on") or "ε")
            if src and dst:
                transitions.append((src, lab, dst))
        elif isinstance(item, (list, tuple)) and len(item) >= 3:
            transitions.append((str(item[0]), str(item[1]), str(item[2])))
    for src, _lab, dst in transitions:
        if src not in states:
            states.append(src)
        if dst not in states:
            states.append(dst)
    start = raw.get("start")
    starts = raw.get("starts")
    if starts is None:
        starts = [start] if start else ([states[0]] if states else [])
    starts = [str(s) for s in starts if s]
    accept = [str(s) for s in (raw.get("accept") or raw.get("final") or [])]
    caption = str(raw.get("caption") or "").strip()
    return {
        "kind": kind,
        "states": states,
        "starts": starts,
        "accept": accept,
        "transitions": transitions,
        "caption": caption,
    }


def _group_edges(transitions: list[tuple[str, str, str]]) -> dict[tuple[str, str], str]:
    grouped: dict[tuple[str, str], list[str]] = {}
    for src, lab, dst in transitions:
        grouped.setdefault((src, dst), [])
        if lab not in grouped[(src, dst)]:
            grouped[(src, dst)].append(lab)
    return {k: ", ".join(v) for k, v in grouped.items()}


def _dot_id(name: str) -> str:
    escaped = name.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _dot_label(name: str) -> str:
    match = re.fullmatch(r"([A-Za-z]+)[_-]?(\d+)", name)
    if match:
        base, digits = match.group(1), match.group(2)
        return f"<<I>{base}</I><SUB>{digits}</SUB>>"
    return f"<<I>{name}</I>>"


def _two_way_pairs(edges: dict[tuple[str, str], str]) -> set[tuple[str, str]]:
    pairs = {key for key in edges if key[0] != key[1]}
    return {key for key in pairs if (key[1], key[0]) in pairs}


def _pair_set(transitions: list[tuple[str, str, str]]) -> set[tuple[str, str]]:
    return {(src, dst) for src, _lab, dst in transitions if src != dst}


def _is_path_layout(transitions: list[tuple[str, str, str]]) -> bool:
    """True only for a real chain (picture-2 style). Cycles and two-way arcs are 2D."""
    pairs = _pair_set(transitions)
    if any((dst, src) in pairs for src, dst in pairs):
        return False
    und: dict[str, set[str]] = defaultdict(set)
    for src, dst in pairs:
        und[src].add(dst)
        und[dst].add(src)
    if len(und) <= 2:
        return True
    if any(len(neigh) > 2 for neigh in und.values()):
        return False
    ends = sum(1 for neigh in und.values() if len(neigh) == 1)
    return ends == 2


def to_dot(spec: dict[str, Any]) -> str:
    """DOT is kept for debugging; exam PDFs draw with reportlab, not Graphviz."""
    data = normalize_diagram(spec)
    edges = _group_edges(data["transitions"])
    lines = [
        "digraph G {",
        "  rankdir=LR;",
        "  splines=true;",
        '  bgcolor="transparent";',
        "  pad=0.12;",
        "  nodesep=0.35;",
        "  ranksep=0.45;",
        '  node [shape=circle, fontname="Times-Italic", fontsize=14,',
        "        width=0.52, height=0.52, fixedsize=true, penwidth=1.35];",
        '  edge [fontname="Times-Italic", fontsize=12, arrowsize=0.72, penwidth=1.2];',
    ]
    for name in data["states"]:
        shape = "doublecircle" if name in data["accept"] else "circle"
        lines.append(f"  {_dot_id(name)} [shape={shape}, label={_dot_label(name)}];")
    if data["starts"]:
        lines.append('  _start [shape=none, label="", width=0.01, height=0.01];')
        lines.append(f"  _start -> {_dot_id(data['starts'][0])} [arrowsize=0.85];")
        for extra in data["starts"][1:]:
            lines.append(f"  _start -> {_dot_id(extra)} [arrowsize=0.85];")
    for (src, dst), label in edges.items():
        lab = label.replace("\\", "\\\\").replace('"', '\\"')
        extra = ', tailport="n", headport="n"' if src == dst else ""
        lines.append(f'  {_dot_id(src)} -> {_dot_id(dst)} [label="{lab}"{extra}];')
    lines.append("}")
    return "\n".join(lines) + "\n"


def render_dot_png(spec: dict[str, Any], max_in: tuple[float, float] | None = None) -> bytes | None:
    dot = shutil.which("dot")
    if not dot:
        return None
    if max_in is None:
        max_in = (3.6, 1.7)
    w, h = max_in
    try:
        proc = subprocess.run(
            [dot, "-Tpng", f"-Gsize={w},{h}!", "-Gdpi=170"],
            input=to_dot(spec).encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=12,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0 or not proc.stdout:
        return None
    return proc.stdout


def _layers(states: list[str], starts: list[str], transitions: list[tuple[str, str, str]]) -> list[list[str]]:
    fwd: dict[str, list[str]] = defaultdict(list)
    for src, _lab, dst in transitions:
        if dst != src and dst not in fwd[src]:
            fwd[src].append(dst)
    remaining = list(states)
    seeds = [s for s in starts if s in remaining] or ([remaining[0]] if remaining else [])
    layers: list[list[str]] = []
    seen: set[str] = set()
    q = deque()
    for s in seeds:
        if s not in seen:
            seen.add(s)
            q.append(s)
    while q:
        layer = []
        for _ in range(len(q)):
            node = q.popleft()
            layer.append(node)
            for nxt in fwd[node]:
                if nxt not in seen and nxt in remaining:
                    seen.add(nxt)
                    q.append(nxt)
        if layer:
            layers.append(layer)
    leftovers = [s for s in remaining if s not in seen]
    if leftovers:
        layers.append(leftovers)
    return layers or [[]]


def _has_loops(transitions: list[tuple[str, str, str]]) -> bool:
    return any(src == dst for src, _lab, dst in transitions)


def _layer_index(
    states: list[str], starts: list[str], transitions: list[tuple[str, str, str]]
) -> dict[str, int]:
    index: dict[str, int] = {}
    for i, layer in enumerate(_layers(states, starts, transitions)):
        for name in layer:
            index[name] = i
    return index


def _max_rtl_hops(
    states: list[str], starts: list[str], transitions: list[tuple[str, str, str]]
) -> int:
    index = _layer_index(states, starts, transitions)
    hops = 0
    for src, _lab, dst in transitions:
        if src == dst or src not in index or dst not in index:
            continue
        if index[dst] < index[src]:
            hops = max(hops, index[src] - index[dst])
    return hops


def _return_arc_room(
    states: list[str], starts: list[str], transitions: list[tuple[str, str, str]]
) -> float:
    """Return arcs only dip below a single-row figure; stacked layers curve between states."""
    layers = _layers(states, starts, transitions)
    if max((len(layer) for layer in layers), default=1) > 1:
        return 0.0
    hops = _max_rtl_hops(states, starts, transitions)
    return (18.0 + 12.0 * hops) if hops else 0.0


def _place_layers(
    layers: list[list[str]],
    width: float,
    height: float,
    extra_top: float = 0.0,
    extra_bottom: float = 0.0,
) -> dict[str, tuple[float, float]]:
    n_l = max(1, len(layers))
    n_h = max(1, max((len(layer) for layer in layers), default=1))
    content_w = (n_l - 1) * H_GAP
    content_h = (n_h - 1) * V_GAP
    min_x = STATE_R + START_LEN + 6
    origin_x = max(min_x, (width - content_w) / 2.0)
    origin_y = max(STATE_R + 6 + extra_bottom, extra_bottom + (height - extra_top - extra_bottom - content_h) / 2.0)
    pos: dict[str, tuple[float, float]] = {}
    for li, layer in enumerate(layers):
        x = origin_x + li * H_GAP
        k = len(layer)
        col_h = (k - 1) * V_GAP
        top = origin_y + (content_h - col_h) / 2.0 + col_h
        for j, name in enumerate(layer):
            y = origin_y + content_h / 2.0 if k == 1 else top - j * V_GAP
            pos[name] = (x, y)
    return pos


def _layout(
    states: list[str],
    starts: list[str],
    accept: list[str],
    transitions: list[tuple[str, str, str]],
    width: float,
    height: float,
) -> dict[str, tuple[float, float]]:
    extra_top = LOOP_ROOM if _has_loops(transitions) else 0.0
    extra_bottom = _return_arc_room(states, starts, transitions)
    layers = _layers(states, starts, transitions)
    if len(states) <= 1 or _is_path_layout(transitions):
        return _place_layers(layers, width, height, extra_top, extra_bottom)

    start = starts[0] if starts else states[0]
    rest = [s for s in states if s != start]
    if len(states) == 2:
        return _place_layers([[start], rest], width, height, extra_top, extra_bottom)

    if len(states) == 3:
        partner = next((s for s in rest if s not in accept), rest[0])
        bottom = next(s for s in rest if s != partner)
        min_x = STATE_R + START_LEN + 6
        origin_x = max(min_x, (width - H_GAP) / 2.0)
        top_y = height - STATE_R - 8 - extra_top
        bot_y = top_y - V_GAP
        return {
            start: (origin_x, top_y),
            partner: (origin_x + H_GAP, top_y),
            bottom: (origin_x + H_GAP / 2.0, bot_y),
        }

    return _place_layers(layers, width, height, extra_top, extra_bottom)


def diagram_size(spec: dict[str, Any], max_width: float = MAX_W) -> tuple[float, float]:
    data = normalize_diagram(spec)
    n = max(1, len(data["states"]))
    loops = _has_loops(data["transitions"])
    extra_top = LOOP_ROOM if loops else 0.0
    extra_bottom = _return_arc_room(data["states"], data["starts"], data["transitions"])
    if n == 3 and not _is_path_layout(data["transitions"]):
        width = min(max_width, START_LEN + STATE_R + H_GAP + STATE_R + 20)
        # a loop on the bottom state hangs below it, so reserve room under the row
        height = STATE_R * 2 + V_GAP + extra_top + 28 + (24 if loops else 0)
    else:
        layers = _layers(data["states"], data["starts"], data["transitions"])
        n_l = max(1, len(layers))
        n_h = max(1, max((len(layer) for layer in layers), default=1))
        width = min(max_width, START_LEN + STATE_R + (n_l - 1) * H_GAP + STATE_R + 18)
        height = STATE_R * 2 + (n_h - 1) * V_GAP + extra_top + extra_bottom + 24
    if data["caption"]:
        height += 12
    return width, max(32 * mm, min(MAX_H, height))


def diagram_height(spec: dict[str, Any], width: float | None = None) -> float:
    return diagram_size(spec, width or MAX_W)[1]


def _unit(dx: float, dy: float) -> tuple[float, float]:
    dist = math.hypot(dx, dy) or 1.0
    return dx / dist, dy / dist


def _arrow(canv, x1: float, y1: float, x2: float, y2: float, size: float = 6.5) -> None:
    angle = math.atan2(y2 - y1, x2 - x1)
    p = canv.beginPath()
    p.moveTo(x2, y2)
    p.lineTo(x2 - size * math.cos(angle - 0.38), y2 - size * math.sin(angle - 0.38))
    p.lineTo(x2 - size * math.cos(angle + 0.38), y2 - size * math.sin(angle + 0.38))
    p.close()
    canv.setFillColor(INK)
    canv.drawPath(p, fill=1, stroke=0)


def _label(canv, x: float, y: float, text: str, font_size: float = 11) -> None:
    canv.setFont("Times-Italic", font_size)
    w = canv.stringWidth(text, "Times-Italic", font_size)
    canv.setFillColor(colors.white)
    canv.rect(x - w / 2 - 1.2, y - 1.5, w + 2.4, font_size + 0.6, fill=1, stroke=0)
    canv.setFillColor(INK)
    canv.drawCentredString(x, y, text)


def _rect_for(canv, x: float, y: float, text: str, size: float) -> tuple[float, float, float, float]:
    w = canv.stringWidth(text, "Times-Italic", size)
    return (x - w / 2 - 1.2, y - 1.5, x + w / 2 + 1.2, y + size - 0.9)


def _overlaps(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def _place_labels(
    canv,
    requests: list[tuple],
    blocked: list[tuple[float, float, float, float]],
    bounds: tuple[float, float] | None = None,
) -> None:
    """Draw edge labels, nudging each one clear of the states and of labels already down."""
    taken = list(blocked)
    for x, y, text, size, push in requests:
        canv.setFont("Times-Italic", size)
        spot = None
        for step in (0, 1, -1, 2, -2, 3, -3, 4, -4):
            cx, cy = x + push[0] * step * 6.0, y + push[1] * step * 6.0
            rect = _rect_for(canv, cx, cy, text, size)
            if bounds and not (rect[0] >= 0 and rect[1] >= 0 and rect[2] <= bounds[0] and rect[3] <= bounds[1]):
                continue
            if not any(_overlaps(rect, other) for other in taken):
                spot = (cx, cy, rect)
                break
        if spot is None:
            spot = (x, y, _rect_for(canv, x, y, text, size))
        taken.append(spot[2])
        _label(canv, spot[0], spot[1], text, size)


def _draw_state_name(canv, x: float, y: float, name: str) -> None:
    match = re.fullmatch(r"([A-Za-z]+)[_-]?(\d+)", name)
    canv.setFillColor(INK)
    if not match:
        canv.setFont("Times-Italic", 12)
        canv.drawCentredString(x, y - 4, name)
        return
    base, digits = match.group(1), match.group(2)
    canv.setFont("Times-Italic", 12)
    bw = canv.stringWidth(base, "Times-Italic", 12)
    canv.setFont("Times-Italic", 8)
    dw = canv.stringWidth(digits, "Times-Italic", 8)
    left = x - (bw + dw * 0.72) / 2
    canv.setFont("Times-Italic", 12)
    canv.drawString(left, y - 3.2, base)
    canv.setFont("Times-Italic", 8)
    canv.drawString(left + bw - 0.4, y - 6.4, digits)


def _self_loop(canv, x: float, y: float, radius: float, label: str, angle: float = 90.0, sink=None) -> None:
    """Teardrop loop pointing along `angle` (90 = north), matching textbook figures."""
    ang = math.radians(angle)
    ux, uy = math.cos(ang), math.sin(ang)
    px, py = -uy, ux
    spread = math.radians(28)
    left = (x + radius * math.cos(ang + spread), y + radius * math.sin(ang + spread))
    right = (x + radius * math.cos(ang - spread), y + radius * math.sin(ang - spread))
    apex = (x + (radius + 17) * ux, y + (radius + 17) * uy)
    p = canv.beginPath()
    p.moveTo(*left)
    p.curveTo(
        left[0] + 7 * px + 11 * ux,
        left[1] + 7 * py + 11 * uy,
        apex[0] + 9 * px,
        apex[1] + 9 * py,
        *apex,
    )
    p.curveTo(
        apex[0] - 9 * px,
        apex[1] - 9 * py,
        right[0] - 7 * px + 11 * ux,
        right[1] - 7 * py + 11 * uy,
        *right,
    )
    canv.setStrokeColor(INK)
    canv.setLineWidth(1.2)
    canv.drawPath(p, stroke=1, fill=0)
    _arrow(canv, right[0] - 4 * px + 6 * ux, right[1] - 4 * py + 6 * uy, right[0], right[1], 5.2)
    gap = radius + (22 if uy >= 0 else 28)
    _emit(sink, canv, x + gap * ux, y + gap * uy, label, 11, (ux, uy))


def _emit(sink, canv, x: float, y: float, text: str, size: float, push: tuple[float, float]) -> None:
    if sink is None:
        _label(canv, x, y, text, size)
    else:
        sink.append((x, y, text, size, push))


def _is_row(pos: dict[str, tuple[float, float]]) -> bool:
    if len(pos) < 2:
        return True
    ys = [p[1] for p in pos.values()]
    return max(ys) - min(ys) < 12


def _hops_between(x1: float, x2: float) -> int:
    return max(1, int(round(abs(x2 - x1) / H_GAP)))


def _draw_straight_edge(
    canv, x1: float, y1: float, x2: float, y2: float, radius: float, label: str, sink=None
) -> None:
    ux, uy = _unit(x2 - x1, y2 - y1)
    start = (x1 + ux * radius, y1 + uy * radius)
    end = (x2 - ux * radius, y2 - uy * radius)
    mx, my = (start[0] + end[0]) / 2.0, (start[1] + end[1]) / 2.0
    nx, ny = _unit(-(y2 - y1), x2 - x1)
    canv.setStrokeColor(INK)
    canv.setLineWidth(1.2)
    canv.line(start[0], start[1], end[0], end[1])
    _arrow(canv, start[0], start[1], end[0], end[1], 6.2)
    if abs(y1 - y2) < 8:
        _emit(sink, canv, mx, my + 11, label, 11, (0.0, 1.0))
    else:
        _emit(sink, canv, mx + nx * 10, my + ny * 10, label, 11, (nx, ny))


def _arc_anchors(
    x1: float, y1: float, x2: float, y2: float, radius: float, bow: float
) -> tuple[tuple[float, float], tuple[float, float], tuple[float, float]]:
    """Control point plus entry/exit points sitting on each circle, aimed at the curve."""
    nx, ny = _unit(-(y2 - y1), x2 - x1)
    mx, my = (x1 + x2) / 2.0 + nx * bow, (y1 + y2) / 2.0 + ny * bow
    sx, sy = _unit(mx - x1, my - y1)
    ex, ey = _unit(mx - x2, my - y2)
    return (mx, my), (x1 + sx * radius, y1 + sy * radius), (x2 + ex * radius, y2 + ey * radius)


def _draw_arc_edge(
    canv,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    radius: float,
    label: str,
    bow: float,
    sink=None,
) -> None:
    """Curved edge between two states anywhere on the page, not just along a row."""
    ctrl, start, end = _arc_anchors(x1, y1, x2, y2, radius, bow)
    p = canv.beginPath()
    p.moveTo(*start)
    p.curveTo(ctrl[0], ctrl[1], ctrl[0], ctrl[1], *end)
    canv.setStrokeColor(INK)
    canv.setLineWidth(1.2)
    canv.drawPath(p, stroke=1, fill=0)
    _arrow(canv, ctrl[0], ctrl[1], end[0], end[1], 6.2)
    qx = 0.25 * start[0] + 0.5 * ctrl[0] + 0.25 * end[0]
    qy = 0.25 * start[1] + 0.5 * ctrl[1] + 0.25 * end[1]
    ox, oy = _unit(ctrl[0] - (start[0] + end[0]) / 2.0, ctrl[1] - (start[1] + end[1]) / 2.0)
    _emit(sink, canv, qx + ox * 9, qy + oy * 9 - 3.5, label, 11, (ox, oy))


def _draw_bow_edge(
    canv,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    radius: float,
    label: str,
    side: float,
    hops: int,
    sink=None,
) -> None:
    """side +1 = arc above the row, -1 = arc below."""
    start = (x1, y1 + side * radius)
    end = (x2, y2 + side * radius)
    mx, my = (start[0] + end[0]) / 2.0, (start[1] + end[1]) / 2.0
    bow = 16.0 + 11.0 * hops
    ctrl = (mx, my + side * bow)
    p = canv.beginPath()
    p.moveTo(*start)
    p.curveTo(ctrl[0], ctrl[1], ctrl[0], ctrl[1], *end)
    canv.setStrokeColor(INK)
    canv.setLineWidth(1.2)
    canv.drawPath(p, stroke=1, fill=0)
    _arrow(canv, ctrl[0], ctrl[1], end[0], end[1], 6.2)
    _emit(sink, canv, ctrl[0], ctrl[1] + side * 8, label, 11, (0.0, side))


def draw_automata(canv, spec: dict[str, Any], width: float, height: float, radius: float = STATE_R) -> None:
    data = normalize_diagram(spec)
    pos = _layout(data["states"], data["starts"], data["accept"], data["transitions"], width, height)
    edges = _group_edges(data["transitions"])
    two_way = _two_way_pairs(edges)
    row = _is_row(pos)

    canv.setStrokeColor(INK)
    canv.setFillColor(INK)
    canv.setLineWidth(1.2)
    canv.setLineCap(1)
    canv.setLineJoin(1)

    mid_y = (max(p[1] for p in pos.values()) + min(p[1] for p in pos.values())) / 2.0
    pending: list[tuple] = []

    for (src, dst), label in edges.items():
        if src not in pos or dst not in pos:
            continue
        x1, y1 = pos[src]
        x2, y2 = pos[dst]
        if src == dst:
            # point the loop away from the figure so it cannot sit on top of an edge
            angle = 90.0 if row or y1 >= mid_y else 270.0
            _self_loop(canv, x1, y1, radius, label, angle, pending)
            continue
        hops = _hops_between(x1, x2)
        if row:
            if x2 >= x1 + 8:
                if hops == 1:
                    _draw_straight_edge(canv, x1, y1, x2, y2, radius, label, pending)
                else:
                    _draw_bow_edge(canv, x1, y1, x2, y2, radius, label, 1.0, hops, pending)
            else:
                _draw_bow_edge(canv, x1, y1, x2, y2, radius, label, -1.0, hops, pending)
            continue
        if (src, dst) in two_way:
            # each edge bows left of its own direction, so the pair lands on opposite sides
            dist = math.hypot(x2 - x1, y2 - y1) or 1.0
            bow = min(26.0, max(15.0, dist * 0.22))
            _draw_arc_edge(canv, x1, y1, x2, y2, radius, label, bow, pending)
            continue
        _draw_straight_edge(canv, x1, y1, x2, y2, radius, label, pending)

    for name, (x, y) in pos.items():
        canv.setStrokeColor(INK)
        canv.setFillColor(colors.white)
        canv.setLineWidth(1.35)
        canv.circle(x, y, radius, stroke=1, fill=1)
        if name in data["accept"]:
            canv.circle(x, y, radius - 3.2, stroke=1, fill=0)
        _draw_state_name(canv, x, y, name)

    for start_name in data["starts"]:
        if start_name not in pos:
            continue
        x, y = pos[start_name]
        canv.setStrokeColor(INK)
        canv.setLineWidth(1.25)
        canv.line(x - radius - START_LEN, y, x - radius, y)
        _arrow(canv, x - radius - START_LEN, y, x - radius, y, 6.4)

    circles = [(x - radius, y - radius, x + radius, y + radius) for x, y in pos.values()]
    _place_labels(canv, pending, circles, (width, height))


class AutomataDiagram(Flowable):
    """Compact textbook automaton; never draws a frame, never splits mid-figure."""

    def __init__(self, spec: dict[str, Any], width: float, height: float | None = None):
        super().__init__()
        self.spec = spec
        data = normalize_diagram(spec)
        self.caption = data["caption"]
        nat_w, nat_h = diagram_size(spec, width)
        self.width = min(width, nat_w, MAX_W)
        self.height = height if height is not None else nat_h
        self._img = None
        if self.caption:
            self.height += 11
        self.splitAtTop = 0  # keep atomic so platypus cannot crop the figure

    def wrap(self, availWidth, availHeight):
        self.width = min(self.width, availWidth)
        return self.width, self.height

    def draw(self) -> None:
        cap = 11 if self.caption else 0
        graph_h = self.height - cap
        self.canv.saveState()
        draw_automata(self.canv, self.spec, self.width, graph_h)
        if self.caption:
            self.canv.setFillColor(colors.HexColor("#333333"))
            self.canv.setFont("Times-Italic", 9)
            self.canv.drawCentredString(self.width / 2, 1, self.caption)
        self.canv.restoreState()
