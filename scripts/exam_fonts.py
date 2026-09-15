#!/usr/bin/env python3
"""Register a Unicode serif so ≥, ≤, superscripts look like exam handwriting/print."""

from __future__ import annotations

from pathlib import Path

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

_FAMILY = "ExamSerif"
_MONO = "ExamMono"
_MONO_BOLD = "ExamMono-Bold"
_REGISTERED = False
_MONO_REGISTERED = False

_MONO_PATHS = (
    (
        Path("/System/Library/Fonts/Supplemental/Courier New.ttf"),
        Path("/System/Library/Fonts/Supplemental/Courier New Bold.ttf"),
    ),
    (
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"),
    ),
    (
        Path("/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf"),
        Path("/usr/share/fonts/truetype/liberation/LiberationMono-Bold.ttf"),
    ),
    (
        Path("/usr/share/fonts/truetype/freefont/FreeMono.ttf"),
        Path("/usr/share/fonts/truetype/freefont/FreeMonoBold.ttf"),
    ),
)

_PAIRS = (
    (
        Path("/System/Library/Fonts/Supplemental/Times New Roman.ttf"),
        Path("/System/Library/Fonts/Supplemental/Times New Roman Italic.ttf"),
    ),
    (
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSerif-Italic.ttf"),
    ),
    (
        Path("/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf"),
        Path("/usr/share/fonts/truetype/liberation/LiberationSerif-Italic.ttf"),
    ),
    (
        Path("/usr/share/fonts/truetype/freefont/FreeSerif.ttf"),
        Path("/usr/share/fonts/truetype/freefont/FreeSerifItalic.ttf"),
    ),
    (
        Path("/System/Library/Fonts/Supplemental/STIXTwoText.ttf"),
        Path("/System/Library/Fonts/Supplemental/STIXTwoText-Italic.ttf"),
    ),
)


def body_font() -> str:
    ensure_exam_font()
    names = set(pdfmetrics.getRegisteredFontNames())
    return _FAMILY if _FAMILY in names else "Times-Roman"


def italic_font() -> str:
    ensure_exam_font()
    names = set(pdfmetrics.getRegisteredFontNames())
    italic = f"{_FAMILY}-Italic"
    return italic if italic in names else "Times-Italic"


def ensure_exam_font() -> str:
    global _REGISTERED
    if _REGISTERED:
        names = set(pdfmetrics.getRegisteredFontNames())
        return _FAMILY if _FAMILY in names else "Times-Roman"
    _REGISTERED = True
    for regular, italic in _PAIRS:
        if not regular.is_file():
            continue
        try:
            pdfmetrics.registerFont(TTFont(_FAMILY, str(regular)))
            if italic.is_file():
                pdfmetrics.registerFont(TTFont(f"{_FAMILY}-Italic", str(italic)))
                pdfmetrics.registerFontFamily(
                    _FAMILY,
                    normal=_FAMILY,
                    italic=f"{_FAMILY}-Italic",
                    bold=_FAMILY,
                    boldItalic=f"{_FAMILY}-Italic",
                )
            else:
                pdfmetrics.registerFontFamily(
                    _FAMILY,
                    normal=_FAMILY,
                    italic=_FAMILY,
                    bold=_FAMILY,
                    boldItalic=_FAMILY,
                )
            return _FAMILY
        except Exception:
            continue
    return "Times-Roman"


def mono_font() -> str:
    ensure_mono_font()
    names = set(pdfmetrics.getRegisteredFontNames())
    return _MONO if _MONO in names else "Courier"


def mono_bold_font() -> str:
    ensure_mono_font()
    names = set(pdfmetrics.getRegisteredFontNames())
    if _MONO_BOLD in names:
        return _MONO_BOLD
    return "Courier-Bold"


def ensure_mono_font() -> str:
    global _MONO_REGISTERED
    if _MONO_REGISTERED:
        names = set(pdfmetrics.getRegisteredFontNames())
        return _MONO if _MONO in names else "Courier"
    _MONO_REGISTERED = True
    for regular, bold in _MONO_PATHS:
        if not regular.is_file():
            continue
        try:
            pdfmetrics.registerFont(TTFont(_MONO, str(regular)))
            if bold.is_file():
                pdfmetrics.registerFont(TTFont(_MONO_BOLD, str(bold)))
            return _MONO
        except Exception:
            continue
    return "Courier"
