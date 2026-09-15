#!/usr/bin/env python3
"""Layout and draw DFA / NFA / directed graphs with reportlab (no Graphviz required)."""

from __future__ import annotations

import math
from typing import Any

from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import Flowable

INK = colors.HexColor("#1a1a1a")
ACCENT = colors.HexColor("#111111")


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


def _layout(states: list[str], width: float, height: float) -> dict[str, tuple[float, float]]:
    n = len(states)
    cx, cy = width / 2.0, height / 2.0 + 4
    if n == 0:
        return {}
    if n == 1:
        return {states[0]: (cx, cy)}
    if n == 2:
        gap = min(width * 0.28, 70)
        return {states[0]: (cx - gap, cy), states[1]: (cx + gap, cy)}
    radius = min(width, height) * 0.33
    pos = {}
    for i, name in enumerate(states):
        angle = math.pi / 2 + (2 * math.pi * i / n)
        pos[name] = (cx + radius * math.cos(angle), cy + radius * math.sin(angle))
    return pos


def _group_edges(transitions: list[tuple[str, str, str]]) -> dict[tuple[str, str], str]:
    grouped: dict[tuple[str, str], list[str]] = {}
    for src, lab, dst in transitions:
        grouped.setdefault((src, dst), [])
        if lab not in grouped[(src, dst)]:
            grouped[(src, dst)].append(lab)
    return {k: ", ".join(v) for k, v in grouped.items()}


def _draw_arrow_head(canv, x1: float, y1: float, x2: float, y2: float, size: float = 7) -> None:
    angle = math.atan2(y2 - y1, x2 - x1)
    left = (x2 - size * math.cos(angle - 0.4), y2 - size * math.sin(angle - 0.4))
    right = (x2 - size * math.cos(angle + 0.4), y2 - size * math.sin(angle + 0.4))
    canv.setFillColor(INK)
    canv.drawPath(
        _path(canv, [(x2, y2), left, right]),
        fill=1,
        stroke=0,
    )


def _path(canv, points):
    p = canv.beginPath()
    p.moveTo(*points[0])
    for pt in points[1:]:
        p.lineTo(*pt)
    p.close()
    return p


def draw_automata(canv, spec: dict[str, Any], width: float, height: float, radius: float = 14) -> None:
    data = normalize_diagram(spec)
    states = data["states"]
    pos = _layout(states, width, height)
    edges = _group_edges(data["transitions"])
    reverse = {(b, a) for a, b in edges if a != b}

    canv.setStrokeColor(INK)
    canv.setFillColor(INK)
    canv.setLineWidth(1.1)
    canv.setLineCap(1)
    canv.setLineJoin(1)

    for (src, dst), label in edges.items():
        if src not in pos or dst not in pos:
            continue
        x1, y1 = pos[src]
        x2, y2 = pos[dst]
        if src == dst:
            loop_r = radius * 1.15
            canv.circle(x1, y1 + radius + loop_r * 0.35, loop_r * 0.7, stroke=1, fill=0)
            _draw_arrow_head(canv, x1 + loop_r * 0.5, y1 + radius + 2, x1 + 4, y1 + radius - 1, 6)
            canv.setFont("Times-Italic", 9)
            canv.drawCentredString(x1, y1 + radius + loop_r * 1.15, label)
            continue
        dx, dy = x2 - x1, y2 - y1
        dist = math.hypot(dx, dy) or 1.0
        ux, uy = dx / dist, dy / dist
        start = (x1 + ux * radius, y1 + uy * radius)
        end = (x2 - ux * radius, y2 - uy * radius)
        curved = (dst, src) in reverse or (src, dst) in reverse
        if curved:
            nx, ny = -uy, ux
            bend = 16
            mx = (start[0] + end[0]) / 2 + nx * bend
            my = (start[1] + end[1]) / 2 + ny * bend
            p = canv.beginPath()
            p.moveTo(*start)
            p.curveTo(mx, my, mx, my, *end)
            canv.drawPath(p, stroke=1, fill=0)
            _draw_arrow_head(canv, mx, my, end[0], end[1], 6)
            canv.setFont("Times-Italic", 9)
            canv.drawCentredString(mx + nx * 8, my + ny * 8, label)
        else:
            canv.line(start[0], start[1], end[0], end[1])
            _draw_arrow_head(canv, start[0], start[1], end[0], end[1], 6)
            canv.setFont("Times-Italic", 9)
            canv.drawCentredString((start[0] + end[0]) / 2, (start[1] + end[1]) / 2 + 8, label)

    for name, (x, y) in pos.items():
        canv.setStrokeColor(INK)
        canv.setFillColor(colors.white)
        canv.setLineWidth(1.4)
        canv.circle(x, y, radius, stroke=1, fill=1)
        if name in data["accept"]:
            canv.circle(x, y, radius - 3.2, stroke=1, fill=0)
        canv.setFillColor(ACCENT)
        canv.setFont("Times-Bold", 9)
        canv.drawCentredString(x, y - 3, name)

    for start_name in data["starts"]:
        if start_name not in pos:
            continue
        x, y = pos[start_name]
        canv.setStrokeColor(INK)
        canv.setLineWidth(1.2)
        canv.line(x - radius - 22, y, x - radius, y)
        _draw_arrow_head(canv, x - radius - 22, y, x - radius, y, 7)


class AutomataDiagram(Flowable):
    def __init__(self, spec: dict[str, Any], width: float, height: float | None = None):
        super().__init__()
        self.spec = spec
        self.diagram_width = width
        n = len(normalize_diagram(spec)["states"])
        self.diagram_height = height if height is not None else max(48 * mm, min(90 * mm, 28 * mm + n * 10 * mm))
        self.width = width
        self.height = self.diagram_height

    def wrap(self, availWidth, availHeight):
        self.width = min(self.diagram_width, availWidth)
        return self.width, self.height

    def draw(self) -> None:
        self.canv.saveState()
        self.canv.setStrokeColor(colors.HexColor("#dddddd"))
        self.canv.setLineWidth(0.4)
        self.canv.roundRect(0, 0, self.width, self.diagram_height, 4, stroke=1, fill=0)
        caption = normalize_diagram(self.spec)["caption"]
        graph_h = self.diagram_height - (12 if caption else 0)
        self.canv.saveState()
        self.canv.translate(0, 12 if caption else 0)
        draw_automata(self.canv, self.spec, self.width, graph_h)
        self.canv.restoreState()
        if caption:
            self.canv.setFillColor(INK)
            self.canv.setFont("Times-Italic", 9)
            self.canv.drawCentredString(self.width / 2, 4, caption)
        self.canv.restoreState()
