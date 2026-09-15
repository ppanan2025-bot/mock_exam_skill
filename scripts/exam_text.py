#!/usr/bin/env python3
"""Turn exam ASCII math (a^n, >=) into reportlab Paragraph markup."""

from __future__ import annotations

import html
import re

_SYMBOLS = (
    (">=", "≥"),
    ("<=", "≤"),
    ("!=", "≠"),
    ("->", "→"),
    ("\\emptyset", "∅"),
    ("\\varepsilon", "ε"),
    ("\\epsilon", "ε"),
    ("\\Sigma", "Σ"),
    ("\\sigma", "σ"),
    ("\\delta", "δ"),
    ("\\Delta", "Δ"),
    ("\\in", "∈"),
    ("\\cup", "∪"),
    ("\\cap", "∩"),
    ("\\ge", "≥"),
    ("\\le", "≤"),
    ("\\neq", "≠"),
)

_CARET = re.compile(
    r"(?P<base>[A-Za-z0-9])\^(?:\{(?P<braced>[^}]+)\}|(?P<letter>[A-Za-z])|(?P<digits>[0-9]+)|\*)"
)
_CARET_BARE = re.compile(
    r"\^(?:\{(?P<braced>[^}]+)\}|(?P<letter>[A-Za-z])|(?P<digits>[0-9]+)|\*)"
)
_SUB = re.compile(
    r"(?P<base>[A-Za-z])_(?:\{(?P<braced>[^}]+)\}|(?P<one>[A-Za-z0-9]+))"
)
_NEAR_REL = re.compile(r"(?<![A-Za-z])([A-Za-z])(\s*)(≥|≤|=|∈|:)")
_KLEENE = re.compile(r"(?<![A-Za-z])([A-Za-z])\*(?![A-Za-z0-9])")


def _italic_letters(chunk: str) -> str:
    if re.fullmatch(r"[A-Za-z]+", chunk or ""):
        return f"<i>{chunk}</i>"
    return chunk


def _super_from_caret(match: re.Match[str], with_base: bool) -> str:
    inner = match.group("braced") or match.group("letter") or match.group("digits") or "*"
    inner = _italic_letters(html.escape(inner))
    super_bit = f"<super>{inner}</super>"
    if with_base:
        base = html.escape(match.group("base"))
        if re.fullmatch(r"[A-Za-z]+", base):
            base = f"<i>{base}</i>"
        return f"{base}{super_bit}"
    return super_bit


def format_exam_text(text: str) -> str:
    """ASCII/TeX-ish exam math → reportlab XML (superscripts, ≥, italic variables)."""
    if not text:
        return ""
    raw = text.replace("\r\n", "\n").replace("\r", "\n")
    for src, dst in _SYMBOLS:
        raw = raw.replace(src, dst)
    raw = raw.replace(">=", "≥").replace("<=", "≤")

    pieces: list[str] = []
    index = 0
    for match in _CARET.finditer(raw):
        pieces.append(html.escape(raw[index : match.start()]).replace("\n", "<br/>"))
        pieces.append(_super_from_caret(match, with_base=True))
        index = match.end()
    pieces.append(html.escape(raw[index:]).replace("\n", "<br/>"))
    out = "".join(pieces)

    def _bare(match: re.Match[str]) -> str:
        inner = match.group("braced") or match.group("letter") or match.group("digits") or "*"
        return f"<super>{_italic_letters(inner)}</super>"

    out = _CARET_BARE.sub(_bare, out)

    def _sub(match: re.Match[str]) -> str:
        inner = match.group("braced") or match.group("one")
        return f"<i>{html.escape(match.group('base'))}</i><sub>{html.escape(inner)}</sub>"

    # Subscripts on the still-plain remnant are already escaped; operate on original
    # only for remaining `_` in escaped output (`_` is unchanged by escape).
    out = re.sub(
        r"(?<![>])([A-Za-z])_(?:\{([^}]+)\}|([A-Za-z0-9]+))",
        lambda m: f"<i>{m.group(1)}</i><sub>{m.group(2) or m.group(3)}</sub>",
        out,
    )
    out = _NEAR_REL.sub(r"<i>\1</i>\2\3", out)
    out = _KLEENE.sub(r"<i>\1</i><super>*</super>", out)
    out = out.replace("}*", "}<super>*</super>")
    return out
