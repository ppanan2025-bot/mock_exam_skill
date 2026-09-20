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

    def test_repair_fixes_total_marks_instead_of_blocking(self) -> None:
        from validate_exam_spec import repair

        spec = json.loads(EXAMPLE.read_text(encoding="utf-8"))
        real_total = spec["meta"]["total_marks"]
        spec["meta"]["total_marks"] = real_total - 8
        notes = repair(spec)
        self.assertTrue(notes)
        self.assertEqual(spec["meta"]["total_marks"], real_total)
        self.assertEqual(validate(spec), [])

    def test_mismatched_total_still_renders_a_paper(self) -> None:
        try:
            import reportlab  # noqa: F401
        except ImportError:
            self.skipTest("reportlab not installed")
        import subprocess

        spec = json.loads(EXAMPLE.read_text(encoding="utf-8"))
        spec["meta"]["total_marks"] = 40
        with tempfile.TemporaryDirectory() as tmp:
            spec_path = Path(tmp) / "spec.json"
            spec_path.write_text(json.dumps(spec), encoding="utf-8")
            out = Path(tmp) / "paper.pdf"
            proc = subprocess.run(
                [sys.executable, str(SCRIPTS / "generate_exam_pdf.py"), str(spec_path), "-o", str(out)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)
            payload = json.loads(proc.stdout)
            self.assertTrue(payload["ok"])
            self.assertIn("repaired", payload)
            self.assertTrue(out.is_file())

    def test_inline_numbered_asks_split_onto_their_own_lines(self) -> None:
        from generate_exam_pdf import split_enumerated

        lead, items = split_enumerated(
            "Consider the language over {a, b}. 1. Give a regular expression "
            "for this language. (4 marks) 2. Explain why your expression is "
            "correct. (4 marks, at most 150 words)"
        )
        self.assertEqual(lead, "Consider the language over {a, b}.")
        self.assertEqual(len(items), 2)
        self.assertTrue(items[0].startswith("Give a regular expression"))
        self.assertTrue(items[1].startswith("Explain why"))

    def test_plain_stem_and_decimals_are_left_alone(self) -> None:
        from generate_exam_pdf import split_enumerated

        plain = "Draw a DFA over {a,b} that accepts strings ending in bab."
        self.assertEqual(split_enumerated(plain), (plain, []))
        decimals = "Show that the ratio is 1.5 and the bound is 2.5 for all inputs."
        self.assertEqual(split_enumerated(decimals), (decimals, []))

    def test_subparts_render_on_separate_lines(self) -> None:
        try:
            from pypdf import PdfReader
            import reportlab  # noqa: F401
        except ImportError:
            self.skipTest("reportlab/pypdf not installed")
        from generate_exam_pdf import render

        spec = {
            "meta": {
                "course_code": "COMP2022",
                "course_name": "Models of Computation",
                "paper_title": "Mock",
                "duration": "1 hour",
                "total_marks": 8,
            },
            "sections": [
                {
                    "id": "B",
                    "title": "Written problems",
                    "questions": [
                        {
                            "id": "B1",
                            "type": "long",
                            "marks": 8,
                            "stem": (
                                "Consider the language over {a, b} of strings containing exactly "
                                "two occurrences of ab. 1. Give a regular expression for this "
                                "language. (4 marks) 2. Explain why your expression is correct. "
                                "(4 marks)"
                            ),
                            "answer": "x",
                        }
                    ],
                }
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "paper.pdf"
            self.assertTrue(render(spec, out, answers=False)["ok"])
            text = "\n".join((p.extract_text() or "") for p in PdfReader(str(out)).pages)
            self.assertIn("(1)", text)
            self.assertIn("(2)", text)
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            first = next(i for i, line in enumerate(lines) if line.startswith("(1)"))
            second = next(i for i, line in enumerate(lines) if line.startswith("(2)"))
            self.assertLess(first, second)

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
            self.assertIn("left % right", text)
            self.assertIn("left // right", text)
            self.assertNotIn("remainder", text.lower())


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
        self.assertLessEqual(height, 72 * mm)
        box = AutomataDiagram(spec, 400)
        self.assertLessEqual(box.height, 80 * mm)
        self.assertGreater(box.height, 28 * mm)
        self.assertIsNone(box._img)

    def test_four_state_path_stays_a_row_not_a_plus(self) -> None:
        from automata_diagram import _is_path_layout, _layout, diagram_size, normalize_diagram

        spec = {
            "kind": "nfa",
            "caption": "NFA over {a,b}",
            "states": ["q0", "q1", "q2", "q3"],
            "start": "q0",
            "accept": ["q3"],
            "transitions": [
                ["q0", "b", "q1"],
                ["q1", "a", "q2"],
                ["q2", "ε", "q3"],
            ],
        }
        data = normalize_diagram(spec)
        self.assertTrue(_is_path_layout(data["transitions"]))
        width, height = diagram_size(spec)
        pos = _layout(data["states"], data["starts"], data["accept"], data["transitions"], width, height)
        xs = [pos["q0"][0], pos["q1"][0], pos["q2"][0], pos["q3"][0]]
        ys = [pos[name][1] for name in ("q0", "q1", "q2", "q3")]
        self.assertEqual(xs, sorted(xs))
        self.assertLess(max(ys) - min(ys), 8)
        self.assertGreater(pos["q3"][0] - pos["q0"][0], 100)
        self.assertLess(width / height, 4.5)

    def test_two_state_dfa_is_side_by_side(self) -> None:
        from automata_diagram import _layout, diagram_size, normalize_diagram

        spec = {
            "kind": "dfa",
            "states": ["q0", "q1"],
            "start": "q0",
            "accept": ["q1"],
            "transitions": [
                ["q0", "0", "q0"],
                ["q0", "1", "q1"],
                ["q1", "0,1,2", "q1"],
            ],
        }
        data = normalize_diagram(spec)
        width, height = diagram_size(spec)
        pos = _layout(data["states"], data["starts"], data["accept"], data["transitions"], width, height)
        self.assertGreater(pos["q1"][0], pos["q0"][0] + 20)
        self.assertLess(abs(pos["q1"][1] - pos["q0"][1]), 6)

    def test_one_way_edges_are_not_treated_as_two_way(self) -> None:
        from automata_diagram import _group_edges, _two_way_pairs

        one_way = _group_edges([("q0", "b", "q1"), ("q1", "a", "q2"), ("q2", "ε", "q3")])
        self.assertEqual(_two_way_pairs(one_way), set())
        both = _group_edges([("q0", "1", "q1"), ("q1", "1", "q0")])
        self.assertEqual(_two_way_pairs(both), {("q0", "q1"), ("q1", "q0")})

    def test_string_dfa_keeps_forward_edges_in_a_row(self) -> None:
        from automata_diagram import _is_row, _layout, diagram_size, normalize_diagram

        spec = {
            "kind": "dfa",
            "states": ["q0", "q1", "q2", "q3"],
            "start": "q0",
            "accept": ["q3"],
            "transitions": [
                ["q0", "a", "q0"],
                ["q0", "b", "q1"],
                ["q1", "a", "q2"],
                ["q1", "b", "q1"],
                ["q2", "a", "q0"],
                ["q2", "b", "q3"],
                ["q3", "a", "q2"],
                ["q3", "b", "q1"],
            ],
        }
        data = normalize_diagram(spec)
        width, height = diagram_size(spec)
        pos = _layout(data["states"], data["starts"], data["accept"], data["transitions"], width, height)
        self.assertTrue(_is_row(pos))
        self.assertLess(pos["q0"][0], pos["q1"][0])
        self.assertLess(pos["q1"][0], pos["q2"][0])
        self.assertLess(pos["q2"][0], pos["q3"][0])

    def test_loop_labels_stay_inside_the_figure_box(self) -> None:
        from reportlab.pdfgen import canvas as pdfcanvas

        import automata_diagram as ad

        spec = {
            "kind": "dfa",
            "states": ["q0", "q1", "q2", "q3"],
            "start": "q0",
            "accept": ["q3"],
            "transitions": [
                {"from": "q0", "symbol": "a", "to": "q0"},
                {"from": "q0", "symbol": "b", "to": "q1"},
                {"from": "q1", "symbol": "a", "to": "q2"},
                {"from": "q1", "symbol": "b", "to": "q1"},
                {"from": "q2", "symbol": "b", "to": "q3"},
                {"from": "q2", "symbol": "a", "to": "q0"},
                {"from": "q3", "symbol": "a", "to": "q2"},
                {"from": "q3", "symbol": "b", "to": "q1"},
            ],
        }
        width, height = ad.diagram_size(spec, ad.MAX_W)
        drawn: list[tuple] = []
        original = ad._label
        ad._label = lambda c, x, y, text, size=11: drawn.append((x, y, text, size))
        try:
            canv = pdfcanvas.Canvas("/dev/null")
            ad.draw_automata(canv, spec, width, height)
        finally:
            ad._label = original

        self.assertTrue(drawn)
        canv = pdfcanvas.Canvas("/dev/null")
        for x, y, text, size in drawn:
            rect = ad._rect_for(canv, x, y, text, size)
            self.assertGreaterEqual(rect[1], 0, f"{text} falls below the figure")
            self.assertLessEqual(rect[3], height, f"{text} spills above the figure")

    def test_edge_labels_do_not_land_on_top_of_each_other(self) -> None:
        from reportlab.pdfgen import canvas as pdfcanvas

        from automata_diagram import _overlaps, _place_labels, _rect_for

        drawn: list[tuple] = []
        canv = pdfcanvas.Canvas("/dev/null")
        original = _place_labels.__globals__["_label"]

        def spy(c, x, y, text, size=11):
            drawn.append((x, y, text, size))

        _place_labels.__globals__["_label"] = spy
        try:
            requests = [
                (100.0, 100.0, "a", 11, (0.0, 1.0)),
                (100.0, 100.0, "b", 11, (0.0, 1.0)),
                (101.0, 102.0, "ε", 11, (0.0, 1.0)),
            ]
            _place_labels(canv, requests, [])
        finally:
            _place_labels.__globals__["_label"] = original

        self.assertEqual(len(drawn), 3)
        rects = [_rect_for(canv, x, y, text, size) for x, y, text, size in drawn]
        for i in range(len(rects)):
            for j in range(i + 1, len(rects)):
                self.assertFalse(_overlaps(rects[i], rects[j]), f"{drawn[i]} overlaps {drawn[j]}")

    def test_labels_are_pushed_off_the_state_circles(self) -> None:
        from reportlab.pdfgen import canvas as pdfcanvas

        from automata_diagram import _overlaps, _place_labels, _rect_for

        drawn: list[tuple] = []
        canv = pdfcanvas.Canvas("/dev/null")
        original = _place_labels.__globals__["_label"]
        _place_labels.__globals__["_label"] = lambda c, x, y, text, size=11: drawn.append((x, y, text, size))
        try:
            circle = (86.0, 86.0, 114.0, 114.0)
            _place_labels(canv, [(100.0, 100.0, "a", 11, (0.0, 1.0))], [circle])
        finally:
            _place_labels.__globals__["_label"] = original

        self.assertEqual(len(drawn), 1)
        self.assertFalse(_overlaps(_rect_for(canv, *drawn[0]), circle))

    def test_arc_endpoints_sit_on_the_state_circles(self) -> None:
        import math

        from automata_diagram import _arc_anchors

        ctrl, start, end = _arc_anchors(0.0, 0.0, 60.0, -50.0, 14.5, 20.0)
        self.assertAlmostEqual(math.hypot(start[0], start[1]), 14.5, places=6)
        self.assertAlmostEqual(math.hypot(end[0] - 60.0, end[1] + 50.0), 14.5, places=6)
        self.assertGreater(math.hypot(ctrl[0] - 30.0, ctrl[1] + 25.0), 15.0)

    def test_bottom_state_leaves_room_for_its_loop(self) -> None:
        from automata_diagram import _layout, diagram_size, normalize_diagram

        spec = {
            "kind": "dfa",
            "states": ["s0", "s1", "s2"],
            "start": "s0",
            "accept": ["s2"],
            "transitions": [
                ["s0", "a", "s0"],
                ["s0", "b", "s1"],
                ["s1", "a", "s0"],
                ["s1", "b", "s2"],
                ["s2", "a", "s0"],
                ["s2", "b", "s2"],
            ],
        }
        data = normalize_diagram(spec)
        width, height = diagram_size(spec)
        pos = _layout(data["states"], data["starts"], data["accept"], data["transitions"], width, height)
        self.assertGreater(pos["s2"][1], 14.5)
        self.assertGreater(pos["s2"][1] - 14.5, 30.0)
        self.assertLess(pos["s2"][1], pos["s0"][1])

    def test_cyclic_dfa_uses_triangle_not_a_line(self) -> None:
        from automata_diagram import _is_path_layout, _layout, diagram_size, normalize_diagram

        spec = {
            "kind": "dfa",
            "states": ["q0", "q1", "q2"],
            "start": "q0",
            "accept": ["q2"],
            "transitions": [
                ["q0", "0", "q0"],
                ["q0", "1", "q1"],
                ["q1", "1", "q0"],
                ["q1", "0", "q2"],
                ["q2", "0", "q2"],
                ["q2", "1", "q0"],
            ],
        }
        data = normalize_diagram(spec)
        self.assertFalse(_is_path_layout(data["transitions"]))
        width, height = diagram_size(spec)
        pos = _layout(data["states"], data["starts"], data["accept"], data["transitions"], width, height)
        self.assertGreater(pos["q1"][0], pos["q0"][0] + 20)
        self.assertGreater(pos["q0"][1], pos["q2"][1] + 12)


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
