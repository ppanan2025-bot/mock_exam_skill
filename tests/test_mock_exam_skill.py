#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
EXAMPLE = ROOT / "templates" / "exam_spec.example.json"
sys.path.insert(0, str(SCRIPTS))

from validate_exam_spec import validate  # noqa: E402
from exam_text import format_exam_text  # noqa: E402


class ExamTextTests(unittest.TestCase):
    def test_superscripts_and_geq(self) -> None:
        out = format_exam_text("{a^n b^n : n >= 0}")
        self.assertIn("<super>", out)
        self.assertIn("≥", out)
        self.assertNotIn("^n", out)
        self.assertNotIn(">=", out)
        self.assertIn("<i>a</i>", out)

    def test_kleene_star(self) -> None:
        out = format_exam_text("L2 = a*")
        self.assertIn("<super>*</super>", out)


class ValidateExamSpecTests(unittest.TestCase):
    def test_example_is_valid(self) -> None:
        spec = json.loads(EXAMPLE.read_text(encoding="utf-8"))
        self.assertEqual(validate(spec), [])

    def test_marks_mismatch_is_caught(self) -> None:
        spec = json.loads(EXAMPLE.read_text(encoding="utf-8"))
        spec["meta"]["total_marks"] = 1
        errors = validate(spec)
        self.assertTrue(any("total_marks" in e for e in errors))

    def test_duplicate_ids_are_caught(self) -> None:
        spec = json.loads(EXAMPLE.read_text(encoding="utf-8"))
        spec["sections"][0]["questions"][1]["id"] = spec["sections"][0]["questions"][0]["id"]
        errors = validate(spec)
        self.assertTrue(any("duplicate" in e for e in errors))


class GenerateExamPdfTests(unittest.TestCase):
    def test_renders_example_paper(self) -> None:
        try:
            import reportlab  # noqa: F401
        except ImportError:
            self.skipTest("reportlab not installed")
        sys.path.insert(0, str(SCRIPTS))
        from generate_exam_pdf import render

        spec = json.loads(EXAMPLE.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "paper.pdf"
            result = render(spec, out, answers=False)
            self.assertTrue(result["ok"])
            self.assertTrue(out.is_file())
            self.assertGreater(out.stat().st_size, 1000)
            key = Path(tmp) / "answers.pdf"
            key_result = render(spec, key, answers=True)
            self.assertTrue(key_result["ok"])
            self.assertTrue(key.is_file())


class McqLayoutTests(unittest.TestCase):
    def test_student_paper_has_lettered_choices_not_bullet_glyphs(self) -> None:
        try:
            from pypdf import PdfReader
            import reportlab  # noqa: F401
        except ImportError:
            self.skipTest("reportlab/pypdf not installed")
        from generate_exam_pdf import render

        spec = json.loads(EXAMPLE.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as tmp:
            paper = Path(tmp) / "paper.pdf"
            answers = Path(tmp) / "answers.pdf"
            render(spec, paper, answers=False)
            render(spec, answers, answers=True)
            paper_text = "\n".join((p.extract_text() or "") for p in PdfReader(str(paper)).pages)
            answers_text = "\n".join((p.extract_text() or "") for p in PdfReader(str(answers)).pages)
            self.assertIn("(A)", paper_text)
            self.assertIn("(B)", paper_text)
            self.assertNotIn("bullAt", paper_text)
            self.assertNotIn("bullet", paper_text.lower())
            self.assertNotIn("Marking:", paper_text)
            self.assertNotIn("Answer: B", paper_text)
            self.assertIn("Answer:", answers_text)
            self.assertIn("s0", paper_text)


class InferredDiagramTests(unittest.TestCase):
    def test_parses_eps_arrow_sentence(self) -> None:
        from automata_diagram import infer_diagram_from_text

        spec = infer_diagram_from_text(
            "An NFA has q0 -eps→ q1, q1 -eps→ q2, q2 -a→ q3, and no other transitions."
        )
        assert spec is not None
        self.assertEqual(spec["kind"], "nfa")
        self.assertEqual(spec["start"], "q0")
        symbols = {(t["from"], t["symbol"], t["to"]) for t in spec["transitions"]}
        self.assertIn(("q0", "ε", "q1"), symbols)
        self.assertIn(("q2", "a", "q3"), symbols)

    def test_text_only_nfa_still_draws(self) -> None:
        try:
            import reportlab  # noqa: F401
        except ImportError:
            self.skipTest("reportlab not installed")
        from generate_exam_pdf import render

        spec = {
            "meta": {
                "course_code": "COMP2022",
                "course_name": "Models of Computation",
                "paper_title": "Mock",
                "duration": "1 hour",
                "total_marks": 1,
            },
            "sections": [
                {
                    "id": "A",
                    "title": "Automata",
                    "questions": [
                        {
                            "id": "A10",
                            "type": "mcq",
                            "marks": 1,
                            "stem": (
                                "An NFA has q0 -eps→ q1, q1 -eps→ q2, q2 -a→ q3, "
                                "and no other transitions. Which transition is added?"
                            ),
                            "choices": [
                                {"label": "A", "text": "q0 -a→ q3"},
                                {"label": "B", "text": "q0 -b→ q3"},
                            ],
                            "answer": "A",
                        }
                    ],
                }
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "paper.pdf"
            result = render(spec, out, answers=False)
            self.assertTrue(result["ok"])
            self.assertGreater(out.stat().st_size, 2000)


class CodeListingTests(unittest.TestCase):
    def test_normalize_preserves_indent(self) -> None:
        from code_block import normalize_code

        lines = normalize_code(
            "target = left\nif right:\n    while right <= target:\n        target = target - right"
        )
        self.assertEqual(lines[0], "target = left")
        self.assertEqual(lines[1], "if right:")
        self.assertTrue(lines[2].startswith("    while"))
        self.assertTrue(lines[3].startswith("        target"))

    def test_macro_example_is_boxed_not_one_sentence(self) -> None:
        try:
            from pypdf import PdfReader
            import reportlab  # noqa: F401
        except ImportError:
            self.skipTest("reportlab/pypdf not installed")
        from generate_exam_pdf import render
        from validate_exam_spec import validate

        spec = json.loads((ROOT / "templates" / "macro.example.json").read_text(encoding="utf-8"))
        self.assertEqual(validate(spec), [])
        with tempfile.TemporaryDirectory() as tmp:
            paper = Path(tmp) / "paper.pdf"
            render(spec, paper, answers=False)
            text = "\n".join((p.extract_text() or "") for p in PdfReader(str(paper)).pages)
            self.assertIn("target = left", text)
            self.assertIn("right <= target", text)
            self.assertIn("target = target - right", text)
            self.assertRegex(text, r"\bif\b")
            self.assertRegex(text, r"\bwhile\b")
            self.assertNotIn("rem = left; while", text)
            self.assertIn("Which macro statement", text)


class GraphRenderTests(unittest.TestCase):
    def test_renders_example_dfa(self) -> None:
        try:
            import reportlab  # noqa: F401
        except ImportError:
            self.skipTest("reportlab not installed")
        from render_graph import render_graph_pdf

        spec = json.loads((ROOT / "templates" / "dfa.example.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "dfa.pdf"
            result = render_graph_pdf(spec, out)
            self.assertTrue(result["ok"])
            self.assertTrue(out.is_file())
            self.assertGreater(out.stat().st_size, 500)

    def test_nfa_with_loops_stays_compact(self) -> None:
        from automata_diagram import AutomataDiagram, diagram_height
        from reportlab.lib.units import mm

        spec = {
            "kind": "nfa",
            "caption": "NFA for Question D1",
            "states": ["q0", "q1", "q2", "q3"],
            "start": "q0",
            "accept": ["q3"],
            "transitions": [
                ["q0", "a", "q1"],
                ["q0", "b", "q2"],
                ["q1", "a", "q1"],
                ["q1", "b", "q1"],
                ["q1", "b", "q3"],
                ["q2", "a", "q3"],
                ["q2", "b", "q2"],
            ],
        }
        height = diagram_height(spec)
        self.assertLessEqual(height, 75 * mm)
        box = AutomataDiagram(spec, 400)
        self.assertLessEqual(box.height, 80 * mm)
        self.assertGreater(box.height, 28 * mm)


class ExtractMaterialsTests(unittest.TestCase):
    def test_markdown_file(self) -> None:
        from extract_materials import extract_one

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tutorial.md"
            path.write_text("# Tutorial\nExplain 3NF with a new example.\n", encoding="utf-8")
            rec = extract_one(path)
            assert rec is not None
            self.assertFalse(rec["empty"])
            self.assertIn("3NF", rec["text"])


class ExamProfileTests(unittest.TestCase):
    def test_example_profile_saves_and_matches_phrase(self) -> None:
        from exam_profile import find_profile, save_profile, sanitize_profile, validate_profile

        raw = json.loads((ROOT / "templates" / "exam_profile.example.json").read_text(encoding="utf-8"))
        self.assertEqual(validate_profile(raw), [])
        with tempfile.TemporaryDirectory() as tmp:
            result = save_profile(raw, Path(tmp), write_prompt=False)
            self.assertTrue(result["ok"], result)
            found = find_profile("please give me the mid-semester exam of COMP2022", Path(tmp))
            self.assertIsNotNone(found)
            assert found is not None
            self.assertEqual(found["course_code"], "COMP2022")
            self.assertEqual(found["exam_kind"], "mid-semester")

    def test_sanitize_drops_question_text(self) -> None:
        from exam_profile import sanitize_profile, validate_profile

        leaked = {
            "course_code": "COMP2022",
            "exam_kind": "mid-semester",
            "sections": [
                {
                    "id": "A",
                    "questions": [
                        {
                            "type": "mcq",
                            "marks": 2,
                            "stem": "COPY THIS QUESTION",
                            "answer": "B",
                        }
                    ],
                }
            ],
        }
        clean = sanitize_profile(leaked)
        self.assertNotIn("questions", clean["sections"][0])
        self.assertEqual(clean["sections"][0]["slots"][0]["type"], "mcq")
        blob = json.dumps(clean)
        self.assertNotIn("COPY THIS QUESTION", blob)
        self.assertEqual(validate_profile(clean), [])

    def test_spec_must_follow_saved_section_shape(self) -> None:
        from exam_profile import spec_matches_profile

        profile = json.loads((ROOT / "templates" / "exam_profile.example.json").read_text(encoding="utf-8"))
        spec = {
            "meta": {"course_code": "COMP2022", "total_marks": 40},
            "sections": [{"id": "A", "questions": [{"type": "mcq"}]}],
        }
        errors = spec_matches_profile(spec, profile)
        self.assertTrue(any("section count" in e for e in errors))

    def test_save_upserts_website_prompt(self) -> None:
        from exam_profile import save_profile, website_prompt

        raw = json.loads((ROOT / "templates" / "exam_profile.example.json").read_text(encoding="utf-8"))
        prompt = website_prompt(raw)
        self.assertEqual(prompt["text"], "Give me a mock exam of mid-semester COMP2022.")
        self.assertEqual(prompt["name"], "COMP2022 mid-semester")
        extra = website_prompt(raw, "30 minutes, extra DFA practice")
        self.assertIn("Requirements: 30 minutes, extra DFA practice", extra["text"])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = save_profile(
                raw,
                root / "profiles",
                prompts_path=root / "prompts.json",
            )
            self.assertTrue(result["ok"], result)
            payload = json.loads((root / "prompts.json").read_text(encoding="utf-8"))
            texts = [item["text"] for item in payload["prompts"]]
            self.assertIn("Give me a mock exam of mid-semester COMP2022.", texts)
            self.assertEqual(result["website_prompt"]["ok"], True)


if __name__ == "__main__":
    unittest.main()
