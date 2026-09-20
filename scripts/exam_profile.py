#!/usr/bin/env python3
"""Save, look up, and run remembered exam-format profiles.

A profile stores the *shape* of a paper (course, sitting kind, sections, types,
marks). It must not store real question text. Hermes writes new stems later.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from validate_exam_spec import repair, validate  # noqa: E402

LEAK_KEYS = {
    "stem",
    "stem_after",
    "choices",
    "answer",
    "marking_notes",
    "code",
    "diagram",
}


def default_profiles_dir() -> Path:
    override = os.environ.get("MOCK_EXAM_PROFILES_DIR", "").strip()
    if override:
        return Path(override).expanduser()
    return Path.home() / ".hermes" / "skill-data" / "mock-exam-skill" / "profiles"


def slugify(*parts: str) -> str:
    text = "-".join(p.strip() for p in parts if p and str(p).strip())
    text = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return text or "exam-format"


def normalize_query(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def profile_id(profile: dict[str, Any]) -> str:
    explicit = str(profile.get("id") or "").strip()
    if explicit:
        return slugify(explicit)
    return slugify(str(profile.get("course_code") or ""), str(profile.get("exam_kind") or "exam"))


def _tokens(text: str) -> set[str]:
    return {t for t in normalize_query(text).split() if t}


def profile_matches(profile: dict[str, Any], query: str) -> bool:
    q = normalize_query(query)
    if not q:
        return False
    pid = profile_id(profile)
    if q == normalize_query(pid) or q.replace(" ", "-") == pid:
        return True
    hay = " ".join(
        [
            pid,
            str(profile.get("course_code") or ""),
            str(profile.get("exam_kind") or ""),
            str(profile.get("course_name") or ""),
            " ".join(str(a) for a in (profile.get("aliases") or [])),
        ]
    )
    hay_n = normalize_query(hay)
    if q in hay_n:
        return True
    needed = _tokens(q)
    have = _tokens(hay)
    # "mid-semester exam of COMP2022" → require course code + sitting kind
    course = normalize_query(str(profile.get("course_code") or ""))
    kind = _tokens(str(profile.get("exam_kind") or ""))
    if course and course in needed and kind and kind <= needed:
        return True
    return needed <= have


def _section_from_leaked_questions(section: dict[str, Any]) -> dict[str, Any]:
    questions = section.get("questions")
    if not isinstance(questions, list) or not questions:
        return section
    slots: list[dict[str, Any]] = []
    for item in questions:
        if not isinstance(item, dict):
            continue
        slot: dict[str, Any] = {}
        if item.get("type"):
            slot["type"] = item["type"]
        if item.get("marks") is not None:
            slot["marks"] = item["marks"]
        features: list[str] = []
        if item.get("code"):
            features.append("code")
        if item.get("diagram"):
            features.append("diagram")
        if features:
            slot["features"] = features
        if slot:
            slots.append(slot)
    cleaned = {k: v for k, v in section.items() if k != "questions"}
    if slots:
        cleaned["slots"] = slots
        cleaned["question_count"] = len(slots)
    return cleaned


def sanitize_profile(raw: dict[str, Any]) -> dict[str, Any]:
    """Drop leaked stems/answers; keep only format."""
    profile = json.loads(json.dumps(raw))
    for key in list(profile.keys()):
        if key in LEAK_KEYS:
            profile.pop(key, None)
    sections = []
    for section in profile.get("sections") or []:
        if not isinstance(section, dict):
            continue
        section = _section_from_leaked_questions(section)
        for key in LEAK_KEYS:
            section.pop(key, None)
        sections.append(section)
    profile["sections"] = sections
    profile["id"] = profile_id(profile)
    aliases = profile.get("aliases")
    if not isinstance(aliases, list):
        aliases = []
    course = str(profile.get("course_code") or "").strip()
    kind = str(profile.get("exam_kind") or "").strip()
    auto = []
    if course and kind:
        auto.append(f"{kind} exam of {course}")
        auto.append(f"{course} {kind}")
        auto.append(f"{kind} of {course}")
        kind_l = kind.lower()
        if "mid" in kind_l:
            auto.extend([f"{course} midsem", f"{course} midterm", "midsem", "midterm"])
        if "final" in kind_l:
            auto.extend([f"{course} final", "final exam"])
    merged: list[str] = []
    for alias in [*aliases, *auto]:
        text = str(alias).strip()
        if text and text not in merged:
            merged.append(text)
    profile["aliases"] = merged
    return profile


def validate_profile(profile: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(profile, dict):
        return ["profile must be a JSON object"]
    if not str(profile.get("course_code") or "").strip():
        errors.append("course_code is required")
    if not str(profile.get("exam_kind") or "").strip():
        errors.append("exam_kind is required (e.g. mid-semester, final)")
    sections = profile.get("sections")
    if not isinstance(sections, list) or not sections:
        errors.append("sections must be a non-empty list")
        return errors
    for i, section in enumerate(sections):
        loc = f"sections[{i}]"
        if not isinstance(section, dict):
            errors.append(f"{loc} must be an object")
            continue
        slots = section.get("slots")
        count = section.get("question_count")
        if isinstance(slots, list) and slots:
            if count is not None and count != len(slots):
                errors.append(f"{loc} question_count must equal len(slots)")
        elif not isinstance(count, int) or count < 1:
            errors.append(f"{loc} needs question_count >= 1 or a slots list")
        if "questions" in section:
            errors.append(f"{loc} must not store questions; use slots / question_count")
    return errors


def spec_matches_profile(spec: dict[str, Any], profile: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    meta = spec.get("meta") if isinstance(spec.get("meta"), dict) else {}
    want_course = str(profile.get("course_code") or "").strip().upper()
    got_course = str(meta.get("course_code") or "").strip().upper()
    if want_course and got_course != want_course:
        errors.append(f"course_code must be {want_course} (got {got_course or 'missing'})")
    meta_p = profile.get("meta") if isinstance(profile.get("meta"), dict) else {}
    want_marks = meta_p.get("total_marks")
    if isinstance(want_marks, (int, float)) and meta.get("total_marks") != want_marks:
        errors.append(f"total_marks must be {want_marks:g} to match the saved format")
    spec_sections = spec.get("sections") if isinstance(spec.get("sections"), list) else []
    prof_sections = profile.get("sections") if isinstance(profile.get("sections"), list) else []
    if len(spec_sections) != len(prof_sections):
        errors.append(
            f"section count must be {len(prof_sections)} (got {len(spec_sections)})"
        )
        return errors
    for i, (got, want) in enumerate(zip(spec_sections, prof_sections)):
        loc = f"sections[{i}]"
        questions = got.get("questions") if isinstance(got, dict) else None
        if not isinstance(questions, list):
            errors.append(f"{loc} needs questions")
            continue
        slots = want.get("slots") if isinstance(want, dict) else None
        if isinstance(slots, list) and slots:
            if len(questions) != len(slots):
                errors.append(f"{loc} must have {len(slots)} questions")
                continue
            for j, (q, slot) in enumerate(zip(questions, slots)):
                want_type = str((slot or {}).get("type") or "").strip()
                got_type = str((q or {}).get("type") or "").strip()
                if want_type and got_type != want_type:
                    errors.append(f"{loc}.questions[{j}] type must be {want_type}")
                features = (slot or {}).get("features") or []
                if "code" in features and not (q or {}).get("code"):
                    errors.append(f"{loc}.questions[{j}] needs a code listing")
                if "diagram" in features and not (q or {}).get("diagram"):
                    errors.append(f"{loc}.questions[{j}] needs a diagram")
            continue
        count = want.get("question_count") if isinstance(want, dict) else None
        if isinstance(count, int) and len(questions) != count:
            errors.append(f"{loc} must have {count} questions")
        types = want.get("types") if isinstance(want, dict) else None
        if isinstance(types, list) and len(types) == 1:
            only = str(types[0])
            for j, q in enumerate(questions):
                if str((q or {}).get("type") or "") != only:
                    errors.append(f"{loc}.questions[{j}] type must be {only}")
    return errors


def default_prompts_path() -> Path:
    override = os.environ.get("PROMPTS_PATH", "").strip() or os.environ.get(
        "MOCK_EXAM_PROMPTS_PATH", ""
    ).strip()
    if override:
        return Path(override).expanduser()
    return Path.home() / ".hermes" / "skill-data" / "mock-exam-skill" / "prompts.json"


def _plain(text: str, max_len: int = 80) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9 ._-]+", " ", text or "")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:max_len]


def sitting_label(profile: dict[str, Any]) -> str:
    course = _plain(str(profile.get("course_code") or ""), 24).upper()
    kind = _plain(str(profile.get("exam_kind") or ""), 40).lower()
    return " ".join(part for part in (kind, course) if part)


def website_prompt(profile: dict[str, Any], extras: str = "") -> dict[str, Any]:
    """Same shape as Sydney Uni Hermes sidebar prompts."""
    course = _plain(str(profile.get("course_code") or ""), 24).upper()
    kind = _plain(str(profile.get("exam_kind") or ""), 40).lower()
    label = sitting_label(profile) or "mock exam"
    name = f"{course} {kind}".strip() or "Mock exam"
    text = f"Give me a mock exam of {label}."
    extra = extras.strip()
    if extra:
        text += f" Requirements: {extra}"
    return {
        "id": profile_id(profile),
        "name": name[:80],
        "note": "From a remembered exam format",
        "text": text[:4000],
    }


def upsert_website_prompt(item: dict[str, Any], path: Path | None = None) -> dict[str, Any]:
    path = path or default_prompts_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    items: list[dict[str, Any]] = []
    if path.is_file():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = {}
        if isinstance(payload, list):
            items = [row for row in payload if isinstance(row, dict)]
        elif isinstance(payload, dict):
            items = [row for row in (payload.get("prompts") or []) if isinstance(row, dict)]
    name = str(item.get("name") or "")
    given_id = str(item.get("id") or "")
    match = None
    for row in items:
        if given_id and row.get("id") == given_id:
            match = row
            break
        if name and row.get("name") == name:
            match = row
            break
    if match:
        match.update({k: v for k, v in item.items() if v not in (None, "")})
        match["updated"] = True
        updated = True
    else:
        items.append(dict(item))
        updated = False
    path.write_text(json.dumps({"prompts": items}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"ok": True, "path": str(path.resolve()), "id": item.get("id"), "name": name, "updated": updated, "prompt": item}


def save_profile(
    profile: dict[str, Any],
    directory: Path | None = None,
    prompts_path: Path | None = None,
    write_prompt: bool = True,
) -> dict[str, Any]:
    directory = directory or default_profiles_dir()
    directory.mkdir(parents=True, exist_ok=True)
    clean = sanitize_profile(profile)
    errors = validate_profile(clean)
    if errors:
        return {"ok": False, "errors": errors}
    path = directory / f"{clean['id']}.json"
    path.write_text(json.dumps(clean, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    result: dict[str, Any] = {
        "ok": True,
        "path": str(path.resolve()),
        "id": clean["id"],
        "profile": clean,
        "command": website_prompt(clean)["text"],
    }
    if write_prompt:
        result["website_prompt"] = upsert_website_prompt(website_prompt(clean), prompts_path)
    return result


def list_profiles(directory: Path | None = None) -> list[dict[str, Any]]:
    directory = directory or default_profiles_dir()
    if not directory.is_dir():
        return []
    rows: list[dict[str, Any]] = []
    for path in sorted(directory.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        rows.append(
            {
                "id": profile_id(data),
                "course_code": data.get("course_code"),
                "exam_kind": data.get("exam_kind"),
                "path": str(path),
                "aliases": data.get("aliases") or [],
            }
        )
    return rows


def find_profile(query: str, directory: Path | None = None) -> dict[str, Any] | None:
    directory = directory or default_profiles_dir()
    if not directory.is_dir():
        return None
    hits: list[dict[str, Any]] = []
    for path in sorted(directory.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(data, dict) and profile_matches(data, query):
            data = dict(data)
            data["_path"] = str(path)
            hits.append(data)
    if len(hits) == 1:
        return hits[0]
    if not hits:
        return None
    q = normalize_query(query)
    for hit in hits:
        if profile_id(hit) == slugify(q):
            return hit
    return hits[0]


def render_from_profile(
    spec: dict[str, Any],
    profile: dict[str, Any],
    output_prefix: Path,
) -> dict[str, Any]:
    notes = repair(spec)
    errors = validate(spec)
    errors.extend(spec_matches_profile(spec, profile))
    if errors:
        return {"ok": False, "errors": errors}
    from generate_exam_pdf import render

    paper = output_prefix.with_name(output_prefix.name + "-paper.pdf")
    answers = output_prefix.with_name(output_prefix.name + "-answers.pdf")
    paper_result = render(spec, paper, answers=False)
    answers_result = render(spec, answers, answers=True)
    result = {
        "ok": bool(paper_result.get("ok") and answers_result.get("ok")),
        "paper": paper_result,
        "answers": answers_result,
        "profile_id": profile_id(profile),
    }
    if notes:
        result["repaired"] = notes
    return result


def _load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("JSON root must be an object")
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dir",
        type=Path,
        default=None,
        help="Profiles folder (default: ~/.hermes/skill-data/mock-exam-skill/profiles)",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    save = sub.add_parser("save", help="Remember an exam format")
    save.add_argument("profile", type=Path)
    save.add_argument(
        "--prompts-path",
        type=Path,
        default=None,
        help="Website prompts.json (default: PROMPTS_PATH or ~/.hermes/skill-data/mock-exam-skill/prompts.json)",
    )
    save.add_argument(
        "--no-prompt",
        action="store_true",
        help="Do not upsert a Sydney Uni Hermes sidebar prompt",
    )

    sub.add_parser("list", help="List remembered formats")

    get = sub.add_parser("get", help="Load a format by id or phrase")
    get.add_argument("query")

    render = sub.add_parser("render", help="Validate a spec against a format and write both PDFs")
    render.add_argument("spec", type=Path)
    render.add_argument("query", help="Profile id or phrase, e.g. 'COMP2022 mid-semester'")
    render.add_argument("-o", "--output-prefix", type=Path, required=True)

    args = parser.parse_args()
    directory = args.dir or default_profiles_dir()

    try:
        if args.cmd == "save":
            result = save_profile(
                _load_json(args.profile),
                directory,
                prompts_path=args.prompts_path,
                write_prompt=not args.no_prompt,
            )
        elif args.cmd == "list":
            result = {"ok": True, "profiles": list_profiles(directory), "dir": str(directory)}
        elif args.cmd == "get":
            found = find_profile(args.query, directory)
            result = (
                {"ok": True, "profile": found, "path": found.get("_path")}
                if found
                else {"ok": False, "errors": [f"no saved format matches {args.query!r}"]}
            )
        else:
            found = find_profile(args.query, directory)
            if not found:
                result = {"ok": False, "errors": [f"no saved format matches {args.query!r}"]}
            else:
                result = render_from_profile(_load_json(args.spec), found, args.output_prefix)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        result = {"ok": False, "errors": [str(exc)]}

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
