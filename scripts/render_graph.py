#!/usr/bin/env python3
"""Render a DFA, NFA, or directed graph spec to a compact PDF figure."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas as pdfcanvas

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from automata_diagram import AutomataDiagram, normalize_diagram
from reportlab.platypus import SimpleDocTemplate, Spacer, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm


def render_graph_pdf(spec: dict, output: Path, title: str | None = None) -> dict:
    output.parent.mkdir(parents=True, exist_ok=True)
    data = normalize_diagram(spec)
    heading = title or data.get("caption") or (data["kind"].upper() + " diagram")
    page_w, page_h = A4
    fig = AutomataDiagram(spec, page_w - 40 * mm)
    doc = SimpleDocTemplate(
        str(output),
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=heading,
        author="graph-diagram",
    )
    styles = getSampleStyleSheet()
    story = [Paragraph(heading, styles["Title"]), Spacer(1, 6 * mm), fig]
    doc.build(story)
    return {
        "ok": True,
        "path": str(output.resolve()),
        "kind": data["kind"],
        "states": len(data["states"]),
        "transitions": len(data["transitions"]),
        "size": [round(fig.width, 1), round(fig.height, 1)],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", type=Path, help="JSON diagram spec")
    parser.add_argument("-o", "--output", type=Path, required=True, help="Output PDF")
    parser.add_argument("--title", default="", help="Optional figure title")
    args = parser.parse_args()
    try:
        spec = json.loads(args.spec.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, ensure_ascii=False))
        return 1
    if "diagram" in spec and isinstance(spec["diagram"], dict):
        spec = spec["diagram"]
    result = render_graph_pdf(spec, args.output, args.title or None)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
