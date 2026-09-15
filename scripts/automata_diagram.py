#!/usr/bin/env python3
"""Layout and draw DFA / NFA / directed graphs with reportlab."""

from __future__ import annotations

import math
from typing import Any

from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import Flowable

INK = colors.HexColor("#1a1a1a")
ACCENT = colors.HexColor("#111111")
STATE_R = 16.0
LOOP_R = 12.0
START_LEN = 26.0
PAD = 44.0


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


def diagram_height(spec: dict[str, Any], width: float | None = None) -> float:
    n = max(1, len(normalize_diagram(spec)["states"]))
    caption = 16 if normalize_diagram(spec)["caption"] else 0
    return max(78 * mm, 58 * mm + n * 16 * mm) + caption


def _layout(states: list[str], starts: list[str], width: float, height: float) -> tuple[dict[str, tuple[float, float]], tuple[float, float]]:
    n = len(states)
    cx, cy = width / 2.0, height / 2.0
    inner_w = max(80.0, width - 2 * PAD)
    inner_h = max(80.0, height - 2 * PAD)
    if n == 0:
        return {}, (cx, cy)
    if n == 1:
        return {states[0]: (cx, cy)}, (cx, cy)
    if n == 2:
        gap = min(inner_w * 0.32, 90)
        return {states[0]: (cx - gap, cy), states[1]: (cx + gap, cy)}, (cx, cy)
    radius = min(inner_w, inner_h) * 0.42
    start_name = starts[0] if starts and starts[0] in states else states[0]
    start_idx = states.index(start_name)
    pos = {}
    for i, name in enumerate(states):
        # Start state on the left; remaining states go clockwise.
        angle = math.pi + 2 * math.pi * ((i - start_idx) % n) / n
        pos[name] = (cx + radius * math.cos(angle), cy + radius * math.sin(angle))
    return pos, (cx, cy)


def _group_edges(transitions: list[tuple[str, str, str]]) -> dict[tuple[str, str], str]:
    grouped: dict[tuple[str, str], list[str]] = {}
    for src, lab, dst in transitions:
        grouped.setdefault((src, dst), [])
        if lab not in grouped[(src, dst)]:
            grouped[(src, dst)].append(lab)
    return {k: ", ".join(v) for k, v in grouped.items()}


def _unit(dx: float, dy: float) -> tuple[float, float]:
    dist = math.hypot(dx, dy) or 1.0
    return dx / dist, dy / dist


def _outward(cx: float, cy: float, x: float, y: float) -> tuple[float, float]:
    return _unit(x - cx, y - cy)


def _draw_arrow_head(canv, x1: float, y1: float, x2: float, y2: float, size: float = 8) -> None:
    angle = math.atan2(y2 - y1, x2 - x1)
    left = (x2 - size * math.cos(angle - 0.38), y2 - size * math.sin(angle - 0.38))
    right = (x2 - size * math.cos(angle + 0.38), y2 - size * math.sin(angle + 0.38))
    p = canv.beginPath()
    p.moveTo(x2, y2)
    p.lineTo(*left)
    p.lineTo(*right)
    p.close()
    canv.setFillColor(INK)
    canv.drawPath(p, fill=1, stroke=0)


def _label(canv, x: float, y: float, text: str) -> None:
    canv.setFont("Times-Italic", 10)
    w = canv.stringWidth(text, "Times-Italic", 10)
    canv.setFillColor(colors.white)
    canv.setStrokeColor(colors.white)
    canv.rect(x - w / 2 - 2.5, y - 2.5, w + 5, 11, fill=1, stroke=0)
    canv.setFillColor(INK)
    canv.drawCentredString(x, y, text)


def draw_automata(canv, spec: dict[str, Any], width: float, height: float, radius: float = STATE_R) -> None:
    data = normalize_diagram(spec)
    states = data["states"]
    pos, (cx, cy) = _layout(states, data["starts"], width, height)
    edges = _group_edges(data["transitions"])
    reverse = {(b, a) for a, b in edges if a != b}

    canv.saveState()
    clip = canv.beginPath()
    clip.rect(1, 1, width - 2, height - 2)
    canv.clipPath(clip, stroke=0)

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
            ux, uy = _outward(cx, cy, x1, y1)
            # Park the loop off the radial so it does not sit on the start arrow.
            ang = 0.95
            rx = ux * math.cos(ang) - uy * math.sin(ang)
            ry = ux * math.sin(ang) + uy * math.cos(ang)
            offset = radius + LOOP_R + 8
            lx = x1 + rx * offset
            ly = y1 + ry * offset
            canv.setStrokeColor(INK)
            canv.setLineWidth(1.15)
            canv.circle(lx, ly, LOOP_R, stroke=1, fill=0)
            tip_x = x1 + rx * radius
            tip_y = y1 + ry * radius
            _draw_arrow_head(canv, lx - rx * 2, ly - ry * 2, tip_x, tip_y, 6)
            _label(canv, lx + rx * (LOOP_R + 10), ly + ry * (LOOP_R + 10), label)
            continue

        ux, uy = _unit(x2 - x1, y2 - y1)
        start = (x1 + ux * radius, y1 + uy * radius)
        end = (x2 - ux * radius, y2 - uy * radius)
        mx = (start[0] + end[0]) / 2
        my = (start[1] + end[1]) / 2
        paired = (dst, src) in reverse
        if paired:
            nx, ny = -uy, ux
            bend = 34
        else:
            nx, ny = _outward(cx, cy, mx, my)
            bend = 30
        ctrl = (mx + nx * bend, my + ny * bend)
        p = canv.beginPath()
        p.moveTo(*start)
        p.curveTo(ctrl[0], ctrl[1], ctrl[0], ctrl[1], *end)
        canv.setStrokeColor(INK)
        canv.setLineWidth(1.15)
        canv.drawPath(p, stroke=1, fill=0)
        _draw_arrow_head(canv, ctrl[0], ctrl[1], end[0], end[1], 7)
        qx = 0.25 * start[0] + 0.5 * ctrl[0] + 0.25 * end[0]
        qy = 0.25 * start[1] + 0.5 * ctrl[1] + 0.25 * end[1]
        _label(canv, qx + nx * 8, qy + ny * 8, label)

    for name, (x, y) in pos.items():
        canv.setStrokeColor(INK)
        canv.setFillColor(colors.white)
        canv.setLineWidth(1.5)
        canv.circle(x, y, radius, stroke=1, fill=1)
        if name in data["accept"]:
            canv.circle(x, y, radius - 3.4, stroke=1, fill=0)
        canv.setFillColor(ACCENT)
        canv.setFont("Times-Bold", 10)
        canv.drawCentredString(x, y - 3.5, name)

    for start_name in data["starts"]:
        if start_name not in pos:
            continue
        x, y = pos[start_name]
        canv.setStrokeColor(INK)
        canv.setLineWidth(1.3)
        canv.line(x - radius - START_LEN, y, x - radius, y)
        _draw_arrow_head(canv, x - radius - START_LEN, y, x - radius, y, 8)

    canv.restoreState()


class AutomataDiagram(Flowable):
    def __init__(self, spec: dict[str, Any], width: float, height: float | None = None):
        super().__init__()
        self.spec = spec
        self.diagram_width = width
        self.diagram_height = height if height is not None else diagram_height(spec, width)
        self.width = width
        self.height = self.diagram_height

    def wrap(self, availWidth, availHeight):
        self.width = min(self.diagram_width, availWidth)
        return self.width, self.height

    def draw(self) -> None:
        caption = normalize_diagram(self.spec)["caption"]
        cap_h = 14 if caption else 0
        graph_h = self.diagram_height - cap_h
        self.canv.saveState()
        self.canv.setStrokeColor(colors.HexColor("#c8c8c8"))
        self.canv.setLineWidth(0.5)
        self.canv.setFillColor(colors.white)
        self.canv.roundRect(0, 0, self.width, self.diagram_height, 5, stroke=1, fill=1)
        self.canv.saveState()
        self.canv.translate(0, cap_h)
        draw_automata(self.canv, self.spec, self.width, graph_h)
        self.canv.restoreState()
        if caption:
            self.canv.setFillColor(colors.HexColor("#333333"))
            self.canv.setFont("Times-Italic", 9)
            self.canv.drawCentredString(self.width / 2, 4, caption)
        self.canv.restoreState()
