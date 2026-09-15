#!/usr/bin/env python3
"""Boxed, indented macro / pseudocode listing for exam PDFs."""

from __future__ import annotations

import re
from typing import Any

from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.platypus import Flowable

from exam_fonts import mono_bold_font, mono_font

_TOKEN = re.compile(r"(\s+|[A-Za-z_]\w*|\d+(?:\.\d+)?|[!=<>]=|[<>]=?|.)")
_KEYWORDS = frozenset(
    {
        "if",
        "else",
        "elif",
        "while",
        "for",
        "def",
        "return",
        "and",
        "or",
        "not",
        "in",
        "True",
        "False",
        "None",
        "break",
        "continue",
        "pass",
        "then",
        "do",
        "end",
        "begin",
        "macro",
        "repeat",
        "until",
        "switch",
        "case",
    }
)
_KW_COLOR = colors.HexColor("#1557c0")
_INK = colors.HexColor("#111111")
_BORDER = colors.HexColor("#4a4a4a")
_FILL = colors.HexColor("#f7f7f7")


def _spans(line: str) -> list[tuple[str, bool]]:
    """Group tokens so identifiers stay one string; keywords stay their own span."""
    out: list[tuple[str, bool]] = []
    buf = ""
    kw = False

    def flush() -> None:
        nonlocal buf
        if buf:
            out.append((buf, kw))
            buf = ""

    for token in _TOKEN.findall(line):
        is_kw = token in _KEYWORDS
        if token.isspace():
            buf += token
            continue
        if buf and is_kw != kw:
            flush()
        kw = is_kw
        buf += token
    flush()
    return out


def normalize_code(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, dict):
        if isinstance(raw.get("lines"), list):
            raw = raw["lines"]
        else:
            raw = raw.get("text") or raw.get("source") or ""
    if isinstance(raw, list):
        text = "\n".join("" if item is None else str(item) for item in raw)
    else:
        text = str(raw)
    text = text.replace("\t", "    ").replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    while lines and lines[-1] == "":
        lines.pop()
    while lines and lines[0] == "":
        lines.pop(0)
    return lines


def looks_like_code_blob(raw: Any) -> bool:
    """True if the value is a non-empty listing Hermes should box."""
    return bool(normalize_code(raw))


class CodeBlock(Flowable):
    """Monospace listing in a thin rectangle, keywords in blue, indent preserved."""

    def __init__(self, source: Any, width: float) -> None:
        super().__init__()
        self.lines = normalize_code(source) or [""]
        self.box_width = width
        self.pad_x = 3.2 * mm
        self.pad_y = 2.6 * mm
        self.font_size = 10
        self.leading = 13.5

    def wrap(self, avail_width: float, avail_height: float) -> tuple[float, float]:
        font = mono_font()
        longest = max(pdfmetrics.stringWidth(line, font, self.font_size) for line in self.lines)
        needed = longest + 2 * self.pad_x + 4 * mm
        self.width = min(avail_width, max(needed, 95 * mm), self.box_width)
        self.height = 2 * self.pad_y + len(self.lines) * self.leading
        return self.width, self.height

    def draw(self) -> None:
        canvas = self.canv
        regular = mono_font()
        bold = mono_bold_font()
        canvas.setStrokeColor(_BORDER)
        canvas.setFillColor(_FILL)
        canvas.setLineWidth(0.85)
        canvas.rect(0, 0, self.width, self.height, stroke=1, fill=1)
        y = self.height - self.pad_y - self.font_size * 0.85
        for line in self.lines:
            x = self.pad_x
            for text, is_kw in _spans(line):
                font = bold if is_kw else regular
                canvas.setFillColor(_KW_COLOR if is_kw else _INK)
                canvas.setFont(font, self.font_size)
                canvas.drawString(x, y, text)
                x += pdfmetrics.stringWidth(text, font, self.font_size)
            y -= self.leading
