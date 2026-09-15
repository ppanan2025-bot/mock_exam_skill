#!/usr/bin/env python3
"""Render a DFA, NFA, or directed graph spec to a one-page PDF."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas as pdfcanvas

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from automata_diagram import draw_automata, normalize_diagram


def render_graph_pdf(spec: dict, output: Path, title: str | None = None) -> dict:
    output.parent.mkdir(parents=True, exist_ok=True)
    data = normalize_diagram(spec)
    width, height = A4
    margin = 36
    canv = pdfcanvas.Canvas(str(output), pagesize=A4)
    canv.setTitle(title or data.get("caption") or "Graph diagram")
    heading = title or data.get("caption") or (data["kind"].upper() + " diagram")
    canv.setFont("Times-Bold", 14)
    canv.drawCentredString(width / 2, height - 40, heading)
    box_w = width - 2 * margin
    box_h = height - 110
    canv.translate(margin, 50)
    canv.setStrokeColorRGB(0.86, 0.86, 0.86)
    canv.roundRect(0, 0, box_w, box_h, 6, stroke=1, fill=0)
    draw_automata(canv, spec, box_w, box_h)
    canv.save()
    return {
        "ok": True,
        "path": str(output.resolve()),
        "kind": data["kind"],
        "states": len(data["states"]),
        "transitions": len(data["transitions"]),
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
