#!/usr/bin/env python3
"""Textbook left-to-right DFA/NFA diagrams (Graphviz if present, else reportlab)."""

from __future__ import annotations

import math
import re
import shutil
import subprocess
from collections import defaultdict, deque
from io import BytesIO
from typing import Any

from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Flowable

INK = colors.HexColor("#111111")
STATE_R = 14.5
START_LEN = 16.0
MAX_W = 130 * mm
MAX_H = 88 * mm

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


def _pair_set(transitions: list[tuple[str, str, str]]) -> set[tuple[str, str]]:
    return {(src, dst) for src, _lab, dst in transitions if src != dst}


def _is_path_layout(transitions: list[tuple[str, str, str]]) -> bool:
    pairs = _pair_set(transitions)
    if any((dst, src) in pairs for src, dst in pairs):
        return False
    und: dict[str, set[str]] = defaultdict(set)
    for src, dst in pairs:
        und[src].add(dst)
        und[dst].add(src)
    return all(len(neigh) <= 2 for neigh in und.values())


def to_dot(spec: dict[str, Any]) -> str:
    data = normalize_diagram(spec)
    edges = _group_edges(data["transitions"])
    linear = _is_path_layout(data["transitions"])
    lines = [
        "digraph G {",
        "  splines=true;",
        '  bgcolor="transparent";',
        "  pad=0.18;",
        "  nodesep=0.7;",
        "  ranksep=0.7;",
        '  node [shape=circle, fontname="Times-Italic", fontsize=14,',
        "        width=0.52, height=0.52, fixedsize=true, penwidth=1.35];",
        '  edge [fontname="Times-Italic", fontsize=12, arrowsize=0.72, penwidth=1.2];',
    ]
    if linear:
        lines.append("  rankdir=LR;")
    for name in data["states"]:
        shape = "doublecircle" if name in data["accept"] else "circle"
        lines.append(f"  {_dot_id(name)} [shape={shape}, label={_dot_label(name)}];")
    if not linear and data["starts"]:
        start = data["starts"][0]
        rest = [s for s in data["states"] if s != start]
        partner = next((s for s in rest if s not in data["accept"]), rest[0] if rest else None)
        if partner:
            lines.append(f"  {{ rank=same; {_dot_id(start)}; {_dot_id(partner)}; }}")
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
    data = normalize_diagram(spec)
    if max_in is None:
        max_in = (4.6, 2.05) if _is_path_layout(data["transitions"]) else (4.4, 3.35)
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


def _layout(
    states: list[str],
    starts: list[str],
    accept: list[str],
    transitions: list[tuple[str, str, str]],
    width: float,
    height: float,
) -> dict[str, tuple[float, float]]:
    if _is_path_layout(transitions) or len(states) <= 1:
        layers = _layers(states, starts, transitions)
        n_l = max(1, len(layers))
        pad_l, pad_r, pad_t, pad_b = 34.0, 22.0, 36.0, 20.0
        inner_w = max(40.0, width - pad_l - pad_r)
        inner_h = max(36.0, height - pad_t - pad_b)
        xs = [pad_l + inner_w / 2] if n_l == 1 else [pad_l + i * inner_w / (n_l - 1) for i in range(n_l)]
        pos: dict[str, tuple[float, float]] = {}
        for li, layer in enumerate(layers):
            k = len(layer)
            for j, name in enumerate(layer):
                if k == 1:
                    y = pad_b + inner_h / 2
                else:
                    y = pad_b + inner_h - j * inner_h / (k - 1)
                pos[name] = (xs[li], y)
        return pos

    start = starts[0] if starts else states[0]
    rest = [s for s in states if s != start]
    pad_l, pad_r, pad_t, pad_b = 38.0, 26.0, 34.0, 26.0
    top_y = height - pad_t
    bot_y = pad_b + 4
    left_x = pad_l
    right_x = width - pad_r
    pos: dict[str, tuple[float, float]] = {start: (left_x, top_y)}
    if len(states) == 2:
        pos[rest[0]] = (right_x, top_y)
        return pos
    if len(states) == 3:
        partner = next((s for s in rest if s not in accept), rest[0])
        bottom = next(s for s in rest if s != partner)
        pos[partner] = (right_x, top_y)
        pos[bottom] = ((left_x + right_x) / 2.0, bot_y)
        return pos
    ordered = [start] + rest
    cx, cy = width / 2.0, height / 2.0
    rx = max(36.0, (width - pad_l - pad_r) / 2.0)
    ry = max(32.0, (height - pad_t - pad_b) / 2.0)
    for i, name in enumerate(ordered):
        ang = math.pi + i * 2.0 * math.pi / len(ordered)
        pos[name] = (cx + rx * math.cos(ang), cy + ry * math.sin(ang))
    return pos


def diagram_size(spec: dict[str, Any], max_width: float = MAX_W) -> tuple[float, float]:
    data = normalize_diagram(spec)
    n = max(1, len(data["states"]))
    if _is_path_layout(data["transitions"]):
        layers = _layers(data["states"], data["starts"], data["transitions"])
        n_l = max(1, len(layers))
        n_h = max(1, max((len(layer) for layer in layers), default=1))
        width = min(max_width, 30 * mm + n_l * 34 * mm)
        height = min(MAX_H, 32 * mm + n_h * 24 * mm)
    else:
        width = min(max_width, 92 * mm if n <= 3 else 118 * mm)
        height = min(MAX_H, 68 * mm if n <= 3 else 82 * mm)
    if any(src == dst for src, _lab, dst in data["transitions"]):
        height = min(MAX_H, height + 8)
    if data["caption"]:
        height += 12
    return width, max(40 * mm, height)


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


def _self_loop(canv, x: float, y: float, radius: float, label: str) -> None:
    """Teardrop loop on the north of the state, matching textbook figures."""
    left = (x + radius * math.cos(math.radians(118)), y + radius * math.sin(math.radians(118)))
    right = (x + radius * math.cos(math.radians(62)), y + radius * math.sin(math.radians(62)))
    apex = (x, y + radius + 17)
    p = canv.beginPath()
    p.moveTo(*left)
    p.curveTo(left[0] - 7, left[1] + 11, apex[0] - 9, apex[1], *apex)
    p.curveTo(apex[0] + 9, apex[1], right[0] + 7, right[1] + 11, *right)
    canv.setStrokeColor(INK)
    canv.setLineWidth(1.2)
    canv.drawPath(p, stroke=1, fill=0)
    _arrow(canv, right[0] + 4, right[1] + 6, right[0], right[1], 5.2)
    _label(canv, x, y + radius + 22, label, 11)


def draw_automata(canv, spec: dict[str, Any], width: float, height: float, radius: float = STATE_R) -> None:
    data = normalize_diagram(spec)
    pos = _layout(data["states"], data["starts"], data["accept"], data["transitions"], width, height)
    edges = _group_edges(data["transitions"])
    reverse = {(b, a) for a, b in edges if a != b}

    canv.setStrokeColor(INK)
    canv.setFillColor(INK)
    canv.setLineWidth(1.2)
    canv.setLineCap(1)
    canv.setLineJoin(1)

    for (src, dst), label in edges.items():
        if src not in pos or dst not in pos:
            continue
        x1, y1 = pos[src]
        x2, y2 = pos[dst]
        if src == dst:
            _self_loop(canv, x1, y1, radius, label)
            continue
        ux, uy = _unit(x2 - x1, y2 - y1)
        start = (x1 + ux * radius, y1 + uy * radius)
        end = (x2 - ux * radius, y2 - uy * radius)
        mx, my = (start[0] + end[0]) / 2.0, (start[1] + end[1]) / 2.0
        dist = math.hypot(x2 - x1, y2 - y1) or 1.0
        nx, ny = _unit(-(y2 - y1), x2 - x1)
        if (dst, src) in reverse:
            sign = 1.0 if src < dst else -1.0
            bow = min(34.0, max(20.0, dist * 0.28))
            ctrl = (mx + nx * bow * sign, my + ny * bow * sign)
        else:
            # bulge slightly outward from the figure centre
            cx = sum(p[0] for p in pos.values()) / len(pos)
            cy = sum(p[1] for p in pos.values()) / len(pos)
            away = (mx - cx, my - cy)
            if abs(away[0]) + abs(away[1]) < 4:
                away = (0, 14)
            bx, by = _unit(*away)
            bow = min(22.0, max(10.0, dist * 0.12))
            ctrl = (mx + bx * bow, my + by * bow)
        p = canv.beginPath()
        p.moveTo(*start)
        p.curveTo(ctrl[0], ctrl[1], ctrl[0], ctrl[1], *end)
        canv.setStrokeColor(INK)
        canv.setLineWidth(1.2)
        canv.drawPath(p, stroke=1, fill=0)
        _arrow(canv, ctrl[0], ctrl[1], end[0], end[1], 6.2)
        qx = 0.25 * start[0] + 0.5 * ctrl[0] + 0.25 * end[0]
        qy = 0.25 * start[1] + 0.5 * ctrl[1] + 0.25 * end[1]
        ox, oy = _unit(ctrl[0] - mx, ctrl[1] - my)
        _label(canv, qx + ox * 10, qy + oy * 10, label)

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


class AutomataDiagram(Flowable):
    """Compact textbook automaton; never draws a frame, never splits mid-figure."""

    def __init__(self, spec: dict[str, Any], width: float, height: float | None = None):
        super().__init__()
        self.spec = spec
        data = normalize_diagram(spec)
        self.caption = data["caption"]
        self._png = render_dot_png(spec)
        nat_w, nat_h = diagram_size(spec, width)
        if self._png is not None:
            img = ImageReader(BytesIO(self._png))
            iw, ih = img.getSize()
            aspect = ih / float(iw or 1)
            self.width = min(width, MAX_W, 125 * mm)
            self.height = min(MAX_H, max(42 * mm, self.width * aspect))
            if height is not None:
                self.height = min(self.height, height)
            self._img = img
        else:
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
        if self._img is not None:
            self.canv.drawImage(
                self._img,
                0,
                cap,
                width=self.width,
                height=graph_h,
                preserveAspectRatio=True,
                mask="auto",
                anchor="c",
            )
        else:
            draw_automata(self.canv, self.spec, self.width, graph_h)
        if self.caption:
            self.canv.setFillColor(colors.HexColor("#333333"))
            self.canv.setFont("Times-Italic", 9)
            self.canv.drawCentredString(self.width / 2, 1, self.caption)
        self.canv.restoreState()
