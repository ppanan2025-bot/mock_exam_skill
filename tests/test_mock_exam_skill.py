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


if __name__ == "__main__":
    unittest.main()
