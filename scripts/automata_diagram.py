#!/usr/bin/env python3
"""Textbook left-to-right DFA/NFA diagrams (Graphviz if present, else reportlab)."""

from __future__ import annotations

import math
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
STATE_R = 13.0
START_LEN = 18.0
MAX_W = 150 * mm
MAX_H = 58 * mm


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


def to_dot(spec: dict[str, Any]) -> str:
    data = normalize_diagram(spec)
    edges = _group_edges(data["transitions"])
    lines = [
        "digraph G {",
        "  rankdir=LR;",
        "  splines=true;",
        '  bgcolor="transparent";',
        "  pad=0.12;",
        "  nodesep=0.42;",
        "  ranksep=0.55;",
        '  node [shape=circle, fontname="Times-Italic", fontsize=12,',
        "        width=0.42, height=0.42, fixedsize=true, penwidth=1.25];",
        '  edge [fontname="Times-Italic", fontsize=11, arrowsize=0.7, penwidth=1.15];',
    ]
    for name in data["states"]:
        shape = "doublecircle" if name in data["accept"] else "circle"
        lines.append(f"  {_dot_id(name)} [shape={shape}];")
    if data["starts"]:
        lines.append('  _start [shape=none, label="", width=0.01, height=0.01];')
        lines.append(f"  _start -> {_dot_id(data['starts'][0])} [arrowsize=0.8];")
        for extra in data["starts"][1:]:
            lines.append(f"  _start -> {_dot_id(extra)} [arrowsize=0.8];")
    for (src, dst), label in edges.items():
        lab = label.replace("\\", "\\\\").replace('"', '\\"')
        lines.append(f'  {_dot_id(src)} -> {_dot_id(dst)} [label="{lab}"];')
    lines.append("}")
    return "\n".join(lines) + "\n"


def render_dot_png(spec: dict[str, Any], max_in: tuple[float, float] = (5.1, 2.15)) -> bytes | None:
    dot = shutil.which("dot")
    if not dot:
        return None
    w, h = max_in
    try:
        proc = subprocess.run(
            [dot, "-Tpng", f"-Gsize={w},{h}!", "-Gdpi=160"],
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
    transitions: list[tuple[str, str, str]],
    width: float,
    height: float,
) -> dict[str, tuple[float, float]]:
    layers = _layers(states, starts, transitions)
    n_l = max(1, len(layers))
    n_h = max(1, max(len(layer) for layer in layers) if layers else 1)
    pad_l, pad_r, pad_t, pad_b = 32.0, 22.0, 40.0, 18.0
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


def diagram_size(spec: dict[str, Any], max_width: float = MAX_W) -> tuple[float, float]:
    data = normalize_diagram(spec)
    layers = _layers(data["states"], data["starts"], data["transitions"])
    n_l = max(1, len(layers))
    n_h = max(1, max((len(layer) for layer in layers), default=1))
    width = min(max_width, 28 * mm + n_l * 32 * mm)
    height = min(MAX_H, 28 * mm + n_h * 26 * mm)
    if any(src == dst for src, _lab, dst in data["transitions"]):
        height = min(MAX_H + 8, height + 10)
    if data["caption"]:
        height += 12
    return width, max(38 * mm, height)


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


def _label(canv, x: float, y: float, text: str, font_size: float = 10) -> None:
    canv.setFont("Times-Italic", font_size)
    w = canv.stringWidth(text, "Times-Italic", font_size)
    canv.setFillColor(colors.white)
    canv.rect(x - w / 2 - 1.5, y - 1.8, w + 3, font_size + 1, fill=1, stroke=0)
    canv.setFillColor(INK)
    canv.drawCentredString(x, y, text)


def _self_loop(canv, x: float, y: float, radius: float, label: str) -> None:
    """Small arc sitting on top of the state, as in standard automata figures."""
    left = (x - radius * 0.42, y + radius * 0.72)
    right = (x + radius * 0.42, y + radius * 0.72)
    p = canv.beginPath()
    p.moveTo(*left)
    p.curveTo(x - 11, y + radius + 16, x + 11, y + radius + 16, *right)
    canv.setStrokeColor(INK)
    canv.setLineWidth(1.15)
    canv.drawPath(p, stroke=1, fill=0)
    _arrow(canv, x + 8, y + radius + 10, right[0], right[1], 5.5)
    _label(canv, x, y + radius + 20, label, 10)


def draw_automata(canv, spec: dict[str, Any], width: float, height: float, radius: float = STATE_R) -> None:
    data = normalize_diagram(spec)
    pos = _layout(data["states"], data["starts"], data["transitions"], width, height)
    edges = _group_edges(data["transitions"])
    reverse = {(b, a) for a, b in edges if a != b}
    layer_index = {}
    for li, layer in enumerate(_layers(data["states"], data["starts"], data["transitions"])):
        for name in layer:
            layer_index[name] = li

    canv.setStrokeColor(INK)
    canv.setFillColor(INK)
    canv.setLineWidth(1.15)
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
        li_s, li_d = layer_index.get(src, 0), layer_index.get(dst, 0)
        if (dst, src) in reverse:
            nx, ny = _unit(-(y2 - y1), x2 - x1)
            sign = 1.0 if src < dst else -1.0
            ctrl = (mx + nx * 15 * sign, my + ny * 15 * sign)
        elif li_d < li_s:
            ctrl = (mx, my + 22)
        elif li_d == li_s:
            ctrl = (mx + 12, my + (12 if y1 >= y2 else -12))
        elif abs(y2 - y1) < 5:
            ctrl = (mx, my + 12)
        else:
            ctrl = (mx, my + 6)
        p = canv.beginPath()
        p.moveTo(*start)
        p.curveTo(ctrl[0], ctrl[1], ctrl[0], ctrl[1], *end)
        canv.setStrokeColor(INK)
        canv.setLineWidth(1.15)
        canv.drawPath(p, stroke=1, fill=0)
        _arrow(canv, ctrl[0], ctrl[1], end[0], end[1], 6)
        qx = 0.25 * start[0] + 0.5 * ctrl[0] + 0.25 * end[0]
        qy = 0.25 * start[1] + 0.5 * ctrl[1] + 0.25 * end[1]
        _label(canv, qx, qy + 6, label)

    for name, (x, y) in pos.items():
        canv.setStrokeColor(INK)
        canv.setFillColor(colors.white)
        canv.setLineWidth(1.25)
        canv.circle(x, y, radius, stroke=1, fill=1)
        if name in data["accept"]:
            canv.circle(x, y, radius - 3.0, stroke=1, fill=0)
        canv.setFillColor(INK)
        canv.setFont("Times-Italic", 11)
        canv.drawCentredString(x, y - 3.5, name)

    for start_name in data["starts"]:
        if start_name not in pos:
            continue
        x, y = pos[start_name]
        canv.setStrokeColor(INK)
        canv.setLineWidth(1.2)
        canv.line(x - radius - START_LEN, y, x - radius, y)
        _arrow(canv, x - radius - START_LEN, y, x - radius, y, 6.5)


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
            self.width = min(width, MAX_W, 140 * mm)
            self.height = min(MAX_H, self.width * aspect)
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
