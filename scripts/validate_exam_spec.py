#!/usr/bin/env python3
"""Validate a mock-exam JSON spec. Prints JSON to stdout; exits 1 on errors."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ALLOWED_TYPES = {
    "mcq",
    "true_false",
    "short",
    "long",
    "calculation",
    "fill_blank",
}


def _err(errors: list[str], msg: str) -> None:
    errors.append(msg)


def _is_num(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def validate(spec: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(spec, dict):
        return ["root must be a JSON object"]

    meta = spec.get("meta")
    if not isinstance(meta, dict):
        _err(errors, "meta must be an object")
        meta = {}

    for key in ("course_code", "course_name", "paper_title", "duration"):
        if not str(meta.get(key) or "").strip():
            _err(errors, f"meta.{key} is required")

    declared_total = meta.get("total_marks")
    if declared_total is not None and not _is_num(declared_total):
        _err(errors, "meta.total_marks must be a number")

    instructions = meta.get("instructions", [])
    if instructions is not None and not isinstance(instructions, list):
        _err(errors, "meta.instructions must be a list of strings")

    sections = spec.get("sections")
    if not isinstance(sections, list) or not sections:
        _err(errors, "sections must be a non-empty list")
        return errors

    seen_ids: set[str] = set()
    mark_sum = 0.0

    for si, section in enumerate(sections):
        loc = f"sections[{si}]"
        if not isinstance(section, dict):
            _err(errors, f"{loc} must be an object")
            continue
        sid = str(section.get("id") or "").strip() or f"S{si + 1}"
        questions = section.get("questions")
        if not isinstance(questions, list) or not questions:
            _err(errors, f"{loc} ({sid}) needs a non-empty questions list")
            continue
        for qi, q in enumerate(questions):
            qloc = f"{loc}.questions[{qi}]"
            if not isinstance(q, dict):
                _err(errors, f"{qloc} must be an object")
                continue
            qid = str(q.get("id") or "").strip()
            if not qid:
                _err(errors, f"{qloc} is missing id")
            elif qid in seen_ids:
                _err(errors, f"duplicate question id {qid!r}")
            else:
                seen_ids.add(qid)
            qtype = str(q.get("type") or "").strip()
            if qtype not in ALLOWED_TYPES:
                _err(errors, f"{qloc} type must be one of {sorted(ALLOWED_TYPES)}")
            if not str(q.get("stem") or "").strip() and not q.get("parts"):
                _err(errors, f"{qloc} needs a stem or parts")
            marks = q.get("marks")
            if not _is_num(marks) or marks <= 0:
                _err(errors, f"{qloc} marks must be a positive number")
            else:
                mark_sum += float(marks)
            if qtype == "mcq":
                choices = q.get("choices")
                if not isinstance(choices, list) or len(choices) < 2:
                    _err(errors, f"{qloc} mcq needs at least two choices")
                else:
                    labels = []
                    for ci, choice in enumerate(choices):
                        if not isinstance(choice, dict) or not str(choice.get("text") or "").strip():
                            _err(errors, f"{qloc}.choices[{ci}] needs text")
                            continue
                        labels.append(str(choice.get("label") or "").strip())
                    if labels and len(set(labels)) != len(labels):
                        _err(errors, f"{qloc} choice labels must be unique")
            if qtype == "true_false" and q.get("choices") not in (None, []):
                pass
            parts = q.get("parts")
            if parts is not None:
                if not isinstance(parts, list):
                    _err(errors, f"{qloc}.parts must be a list")
                else:
                    part_marks = 0.0
                    for pi, part in enumerate(parts):
                        ploc = f"{qloc}.parts[{pi}]"
                        if not isinstance(part, dict) or not str(part.get("stem") or "").strip():
                            _err(errors, f"{ploc} needs a stem")
                            continue
                        pm = part.get("marks")
                        if pm is not None:
                            if not _is_num(pm) or pm < 0:
                                _err(errors, f"{ploc} marks must be a non-negative number")
                            else:
                                part_marks += float(pm)
                    if (
                        _is_num(marks)
                        and part_marks
                        and abs(part_marks - float(marks)) > 0.01
                    ):
                        _err(
                            errors,
                            f"{qloc} part marks ({part_marks:g}) must sum to question marks ({marks:g})",
                        )

    if _is_num(declared_total) and abs(float(declared_total) - mark_sum) > 0.01:
        _err(
            errors,
            f"meta.total_marks ({declared_total:g}) does not match question mark sum ({mark_sum:g})",
        )

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", type=Path, help="Path to exam spec JSON")
    args = parser.parse_args()
    try:
        spec = json.loads(args.spec.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, ensure_ascii=False))
        return 1
    errors = validate(spec)
    print(json.dumps({"ok": not errors, "errors": errors}, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
