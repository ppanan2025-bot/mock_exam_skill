#!/usr/bin/env python3
"""Render a mock-exam JSON spec to an A4 PDF question paper (or answer key)."""

from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path
from typing import Any

try:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_RIGHT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        Flowable,
        HRFlowable,
        KeepTogether,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )
except ImportError as exc:
    raise SystemExit(
        "reportlab is required. Install with: python -m pip install reportlab"
    ) from exc


PAGE_W, PAGE_H = A4
LEFT = 18 * mm
RIGHT = 18 * mm
TOP = 16 * mm
BOTTOM = 16 * mm
CONTENT_W = PAGE_W - LEFT - RIGHT

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))


def _p(text: str, style: ParagraphStyle) -> Paragraph:
    cleaned = html.escape(text).replace("\n", "<br/>")
    return Paragraph(cleaned, style)


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "institution": ParagraphStyle(
            "institution",
            parent=base["Normal"],
            fontName="Times-Bold",
            fontSize=11,
            leading=14,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#222222"),
        ),
        "title": ParagraphStyle(
            "title",
            parent=base["Normal"],
            fontName="Times-Bold",
            fontSize=16,
            leading=20,
            alignment=TA_CENTER,
            spaceAfter=4,
        ),
        "subtitle": ParagraphStyle(
            "subtitle",
            parent=base["Normal"],
            fontName="Times-Roman",
            fontSize=11,
            leading=14,
            alignment=TA_CENTER,
            spaceAfter=8,
        ),
        "meta": ParagraphStyle(
            "meta",
            parent=base["Normal"],
            fontName="Times-Roman",
            fontSize=10,
            leading=13,
        ),
        "h_section": ParagraphStyle(
            "h_section",
            parent=base["Normal"],
            fontName="Times-Bold",
            fontSize=13,
            leading=16,
            spaceBefore=10,
            spaceAfter=4,
        ),
        "body": ParagraphStyle(
            "body",
            parent=base["Normal"],
            fontName="Times-Roman",
            fontSize=11,
            leading=15,
            alignment=TA_JUSTIFY,
        ),
        "stem": ParagraphStyle(
            "stem",
            parent=base["Normal"],
            fontName="Times-Roman",
            fontSize=11,
            leading=15,
        ),
        "marks": ParagraphStyle(
            "marks",
            parent=base["Normal"],
            fontName="Times-Bold",
            fontSize=10,
            leading=13,
            alignment=TA_RIGHT,
        ),
        "choice": ParagraphStyle(
            "choice",
            parent=base["Normal"],
            fontName="Times-Roman",
            fontSize=11,
            leading=14,
        ),
        "small": ParagraphStyle(
            "small",
            parent=base["Normal"],
            fontName="Times-Italic",
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#333333"),
        ),
        "footer": ParagraphStyle(
            "footer",
            parent=base["Normal"],
            fontName="Times-Roman",
            fontSize=8,
            leading=10,
            alignment=TA_CENTER,
        ),
        "answer": ParagraphStyle(
            "answer",
            parent=base["Normal"],
            fontName="Times-Roman",
            fontSize=10,
            leading=13,
        ),
    }


class AnswerLines(Flowable):
    def __init__(self, count: int = 4, width: float = CONTENT_W, gap: float = 16):
        super().__init__()
        self.count = max(1, count)
        self.width = width
        self.gap = gap
        self.height = self.count * gap + 4

    def draw(self) -> None:
        self.canv.setStrokeColor(colors.HexColor("#555555"))
        self.canv.setLineWidth(0.4)
        y = self.height - self.gap
        for _ in range(self.count):
            self.canv.line(0, y, self.width, y)
            y -= self.gap


def _header_footer(canvas, doc, meta: dict[str, Any], answers: bool) -> None:
    canvas.saveState()
    canvas.setFont("Times-Roman", 8)
    label = "ANSWER KEY — do not distribute with the question paper" if answers else "Mock examination paper"
    course = str(meta.get("course_code") or "")
    canvas.drawString(LEFT, PAGE_H - 12 * mm, f"{course}  {label}".strip())
    canvas.drawRightString(PAGE_W - RIGHT, PAGE_H - 12 * mm, str(meta.get("sitting") or ""))
    canvas.setStrokeColor(colors.HexColor("#222222"))
    canvas.setLineWidth(0.6)
    canvas.line(LEFT, PAGE_H - 13.5 * mm, PAGE_W - RIGHT, PAGE_H - 13.5 * mm)
    canvas.line(LEFT, 12 * mm, PAGE_W - RIGHT, 12 * mm)
    page = f"Page {doc.page}"
    canvas.drawCentredString(PAGE_W / 2, 8 * mm, page)
    canvas.restoreState()


def _meta_table(meta: dict[str, Any], styles: dict[str, ParagraphStyle]) -> Table:
    rows = [
        [_p("Course", styles["meta"]), _p(f"{meta.get('course_code', '')}  {meta.get('course_name', '')}".strip(), styles["meta"])],
        [_p("Duration", styles["meta"]), _p(str(meta.get("duration") or ""), styles["meta"])],
        [_p("Total marks", styles["meta"]), _p(str(meta.get("total_marks") or ""), styles["meta"])],
        [
            _p("Materials", styles["meta"]),
            _p(str(meta.get("permitted_materials") or "Closed book unless stated otherwise."), styles["meta"]),
        ],
    ]
    table = Table(rows, colWidths=[32 * mm, CONTENT_W - 32 * mm])
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("FONTNAME", (0, 0), (0, -1), "Times-Bold"),
            ]
        )
    )
    return table


def _candidate_box(styles: dict[str, ParagraphStyle]) -> Table:
    lines = [
        [_p("Candidate name", styles["meta"]), _p("________________________________", styles["meta"])],
        [_p("Student ID", styles["meta"]), _p("________________________________", styles["meta"])],
        [_p("Seat / venue", styles["meta"]), _p("________________________________", styles["meta"])],
    ]
    table = Table(lines, colWidths=[38 * mm, CONTENT_W - 38 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#222222")),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return table


def _question_heading(qid: str, marks: Any, styles: dict[str, ParagraphStyle]) -> Table:
    left = _p(f"Question {qid}", styles["stem"])
    right = _p(f"[{marks:g} marks]" if isinstance(marks, (int, float)) else "", styles["marks"])
    table = Table([[left, right]], colWidths=[CONTENT_W - 32 * mm, 32 * mm])
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("FONTNAME", (0, 0), (0, 0), "Times-Bold"),
            ]
        )
    )
    return table


def _choices(choices: list[dict[str, Any]], styles: dict[str, ParagraphStyle]) -> list[Any]:
    """Render MCQ options as (A) text — never ListFlowable (Times has no bullet glyph)."""
    lines: list[Any] = [Spacer(1, 1.5 * mm)]
    for choice in choices:
        label = str(choice.get("label") or "").strip()
        text = str(choice.get("text") or "").strip()
        body = f"({label})  {text}" if label else text
        lines.append(_p(body, styles["choice"]))
        lines.append(Spacer(1, 0.8 * mm))
    return lines


def _answer_space(question: dict[str, Any], styles: dict[str, ParagraphStyle]) -> Flowable | None:
    qtype = str(question.get("type") or "")
    if qtype == "mcq":
        return _p("Circle one:  (A)    (B)    (C)    (D)", styles["small"])
    if qtype == "true_false":
        return _p("Circle one:  True    /    False", styles["small"])
    n = question.get("answer_lines")
    if not isinstance(n, int):
        n = 8 if qtype == "long" else 3 if qtype == "short" else 6 if qtype == "calculation" else 2
    return AnswerLines(n)


def _question_flowables(
    question: dict[str, Any],
    styles: dict[str, ParagraphStyle],
    answers: bool,
) -> list[Any]:
    bits: list[Any] = [_question_heading(str(question.get("id") or ""), question.get("marks"), styles)]
    stem = str(question.get("stem") or "").strip()
    if stem:
        bits.append(Spacer(1, 2 * mm))
        bits.append(_p(stem, styles["stem"]))
    qtype = str(question.get("type") or "")
    diagram = question.get("diagram")
    if isinstance(diagram, dict) and (diagram.get("states") or diagram.get("transitions")):
        from automata_diagram import AutomataDiagram

        bits.append(Spacer(1, 5 * mm))
        bits.append(AutomataDiagram(diagram, CONTENT_W))
        bits.append(Spacer(1, 5 * mm))
    if qtype == "mcq" and question.get("choices"):
        bits.extend(_choices(question["choices"], styles))
    elif qtype == "true_false":
        bits.append(_p("Circle one:  True    /    False", styles["choice"]))
    for part in question.get("parts") or []:
        pid = str(part.get("id") or "")
        pmarks = part.get("marks")
        label = f"({pid}) " if pid else ""
        mark_bit = f"  [{pmarks:g} marks]" if isinstance(pmarks, (int, float)) else ""
        bits.append(Spacer(1, 1.5 * mm))
        bits.append(_p(f"{label}{part.get('stem', '')}{mark_bit}", styles["stem"]))
        if not answers:
            n = part.get("answer_lines")
            bits.append(Spacer(1, 1 * mm))
            bits.append(AnswerLines(n if isinstance(n, int) else 3))
        else:
            ans = str(part.get("answer") or "").strip()
            notes = str(part.get("marking_notes") or "").strip()
            if ans:
                bits.append(_p(f"Answer: {ans}", styles["answer"]))
            if notes:
                bits.append(_p(f"Marking: {notes}", styles["small"]))
    if answers:
        ans = str(question.get("answer") or "").strip()
        notes = str(question.get("marking_notes") or "").strip()
        if ans:
            bits.append(Spacer(1, 1 * mm))
            bits.append(_p(f"Answer: {ans}", styles["answer"]))
        if notes:
            bits.append(_p(f"Marking: {notes}", styles["small"]))
    else:
        if not question.get("parts"):
            bits.append(Spacer(1, 2 * mm))
            space = _answer_space(question, styles)
            if space is not None:
                bits.append(space)
    bits.append(Spacer(1, 3 * mm))
    has_diagram = isinstance(question.get("diagram"), dict)
    if qtype in {"mcq", "true_false", "short", "fill_blank"} and not has_diagram:
        return [KeepTogether(bits)]
    return bits


def build_story(spec: dict[str, Any], answers: bool) -> list[Any]:
    styles = _styles()
    meta = spec.get("meta") or {}
    story: list[Any] = []
    if meta.get("institution"):
        story.append(_p(str(meta["institution"]), styles["institution"]))
        story.append(Spacer(1, 2 * mm))
    title = str(meta.get("paper_title") or "Mock Examination Paper")
    if answers:
        title = f"{title} — Answer Key"
    story.append(_p(title, styles["title"]))
    subtitle = " ".join(
        part for part in [str(meta.get("course_code") or ""), str(meta.get("course_name") or "")] if part
    )
    if subtitle:
        story.append(_p(subtitle, styles["subtitle"]))
    story.append(_meta_table(meta, styles))
    story.append(Spacer(1, 4 * mm))
    if not answers:
        story.append(_candidate_box(styles))
        story.append(Spacer(1, 4 * mm))
    instructions = meta.get("instructions") or [
        "Answer all questions.",
        "Show working for calculation questions.",
    ]
    story.append(_p("Instructions", styles["h_section"]))
    for i, item in enumerate(instructions, 1):
        story.append(_p(f"{i}.  {item}", styles["body"]))
        story.append(Spacer(1, 0.6 * mm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#222222"), spaceBefore=6, spaceAfter=6))

    for si, section in enumerate(spec.get("sections") or []):
        sid = str(section.get("id") or chr(65 + si))
        title_s = str(section.get("title") or f"Section {sid}")
        story.append(_p(f"Section {sid}: {title_s}", styles["h_section"]))
        if section.get("instructions"):
            story.append(_p(str(section["instructions"]), styles["small"]))
            story.append(Spacer(1, 2 * mm))
        for question in section.get("questions") or []:
            story.extend(_question_flowables(question, styles, answers))
    return story


def render(spec: dict[str, Any], output: Path, answers: bool) -> dict[str, Any]:
    output.parent.mkdir(parents=True, exist_ok=True)
    meta = spec.get("meta") or {}
    doc = SimpleDocTemplate(
        str(output),
        pagesize=A4,
        leftMargin=LEFT,
        rightMargin=RIGHT,
        topMargin=TOP + 4 * mm,
        bottomMargin=BOTTOM,
        title=str(meta.get("paper_title") or "Mock Examination Paper"),
        author="mock-exam-skill",
    )
    doc.build(
        build_story(spec, answers),
        onFirstPage=lambda c, d: _header_footer(c, d, meta, answers),
        onLaterPages=lambda c, d: _header_footer(c, d, meta, answers),
    )
    pages = None
    try:
        from pypdf import PdfReader

        pages = len(PdfReader(str(output)).pages)
    except Exception:
        pages = None
    return {"ok": True, "path": str(output.resolve()), "pages": pages, "answers": answers}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", type=Path, help="Exam spec JSON")
    parser.add_argument("-o", "--output", type=Path, required=True, help="Output PDF path")
    parser.add_argument("--answers", action="store_true", help="Render the answer key instead of the question paper")
    args = parser.parse_args()
    try:
        spec = json.loads(args.spec.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, ensure_ascii=False))
        return 1
    scripts_dir = Path(__file__).resolve().parent
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    from validate_exam_spec import validate

    errors = validate(spec)
    if errors:
        print(json.dumps({"ok": False, "errors": errors}, ensure_ascii=False, indent=2))
        return 1
    result = render(spec, args.output, args.answers)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
