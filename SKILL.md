---
name: mock-exam-skill
description: Generates original mock exam PDFs from course materials.
version: 0.3.0
author: AnPan (ppanan2025-bot), Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [exam, education, pdf, mock-exam, assessment, automata]
    related_skills: [pdf, graph-diagram]
    config:
      - key: mock_exam_skill.materials_dir
        description: Host folder of stored slides, past papers, and tutorials
        default: ""
        prompt: Absolute path to stored course materials (empty = chat uploads + assets/)
---

# Mock Exam Skill

Builds a **new** mock examination paper as a PDF from lecture slides, past mock exams, and/or tutorial questions. Sources may arrive in the chat, or already live on the Hermes host. Questions must be original; the paper is not a photocopy of the materials.

Do not use this skill to grade students, solve a live sit exam, or emit a pixel-perfect replica of an official university template.

## When to Use

- The user asks for a mock exam, practice paper, or exam-style PDF.
- They attach slides, a past paper, or tutorial questions, or those files are stored on the host.
- Don't use for: copying a past paper with light edits, generating only a question list in chat when they asked for a PDF, or non-exam worksheets.

## Prerequisites

- Python 3.10+
- `python -m pip install -r ${HERMES_SKILL_DIR}/requirements.txt` (`reportlab`, `pypdf`)
- Course materials from **one or more** of:
  1. Files the user sends in this session
  2. `mock_exam_skill.materials_dir` from skill config (preferred on a Hetzner Hermes host)
  3. `${HERMES_SKILL_DIR}/assets/` if this skill was cloned as a full directory

Read `references/question-design.md` before writing items. Read `references/exam-spec.md` before writing JSON.

## How to Run

Use the `terminal` tool. `${HERMES_SKILL_DIR}` is the installed skill directory.

```
terminal(command="python ${HERMES_SKILL_DIR}/scripts/extract_materials.py PATH [PATH ...]", timeout=120)
terminal(command="python ${HERMES_SKILL_DIR}/scripts/validate_exam_spec.py exam.json", timeout=30)
terminal(command="python ${HERMES_SKILL_DIR}/scripts/generate_exam_pdf.py exam.json -o /tmp/mock-exam-paper.pdf", timeout=60)
terminal(command="python ${HERMES_SKILL_DIR}/scripts/generate_exam_pdf.py exam.json -o /tmp/mock-exam-answers.pdf --answers", timeout=60)
```

Helpers print JSON to stdout and exit non-zero on failure.

## Quick Reference

| Task | Command |
|---|---|
| Extract slides / papers / tutorials | `extract_materials.py <files-or-dirs>` |
| Check spec | `validate_exam_spec.py exam.json` |
| Student paper PDF | `generate_exam_pdf.py exam.json -o paper.pdf`  **no** `--answers` |
| Marking key PDF | `generate_exam_pdf.py exam.json -o answers.pdf --answers` |
| DFA / NFA figure | question field `diagram` (see `graph-diagram` skill and `templates/dfa.example.json`) |
| Spec shape | `templates/exam_spec.schema.json`, `templates/exam_spec.example.json` |
| Pedagogy | `references/question-design.md` |

## Procedure

1. **Collect sources.** Ask for missing constraints (course code, duration, total marks, closed/open book) only if they were not given. Build a path list from: session attachments, config `mock_exam_skill.materials_dir` if set, then `${HERMES_SKILL_DIR}/assets/`. If none exist, stop and ask the user to send slides, a past mock, or tutorial questions — do not invent a syllabus.
2. **Extract.** `terminal(command="python ${HERMES_SKILL_DIR}/scripts/extract_materials.py …", timeout=120)`. Read the JSON with `read_file` (or stdout). Skip `skipped` / `error` records. If `likely_scanned` is true, rasterise or use `vision_analyze` / the `pdf` skill OCR path; do not treat empty text as "this deck has no content". For images (`.png`/`.jpg`), use `vision_analyze`.
3. **Blueprint.** From the extracts, list taught topics, typical question styles, and a marks × time plan. Follow `references/question-design.md`. Completion: every requested topic is assigned marks, and total marks match the agreed duration.
4. **Author original questions.** Write new stems. Match course notation. Fill `answer` and `marking_notes` for every item. Completion: no stem is a paraphrase of a single source question.
5. **Write spec JSON** with `write_file` using `templates/exam_spec.example.json` as the shape (`references/exam-spec.md`). IDs unique. MCQ has ≥2 choices. Part marks sum to the parent. `meta.total_marks` equals the question sum. If the item is about a DFA/NFA, put a `diagram` object on the question — do not leave the machine as a `s0 --a--> s1` sentence. Load `graph-diagram` if you need a standalone figure first.
6. **Validate.** `terminal(command="python ${HERMES_SKILL_DIR}/scripts/validate_exam_spec.py exam.json", timeout=30)`. Fix every error; do not render until `"ok": true`.
7. **Render two files.** Student paper **without** `--answers` to a name containing `paper`. Answer key **with** `--answers` to a **different** file containing `answers`. Never give the user only the answers PDF as the exam. Never pass `--answers` when writing the student paper. Completion: both JSON results have `"ok": true`.
8. **Deliver.** In the reply, state course, duration, total marks, and both absolute PDF paths. Put `[[as_document]]` on its own last line.

## Pitfalls

- **Copying source items** is a failure even if wording changed slightly. New scenario + new numbers.
- **Hub installs** copy files named from this SKILL.md (`scripts/`, `templates/`, `references/`, `assets/README.md`, `examples/`). Large slide decks belong in `materials_dir` on the host, not in a public GitHub repo.
- **Scanned PDFs / photo slides** need vision/OCR; `extract_materials.py` will report empty text.
- **Math** is Unicode in the PDF, not LaTeX. Avoid `$...$` markup.
- **MCQ layout:** never use reportlab `ListFlowable` / markdown bullets for options. `generate_exam_pdf.py` prints `(A) …`. If you hand-build a PDF, use the same `(A)` form.
- **Answer key** must not be merged into the student paper. `--answers` is only for the second file.
- **Automata:** if the question needs a DFA/NFA, set `diagram` and let the renderer draw it. Do not ask the student to decode a long transition sentence instead of a picture.
- If `reportlab` / `pypdf` are missing, install from `${HERMES_SKILL_DIR}/requirements.txt` and retry — do not hand-write a one-off PDF script.

## Verification

- `validate_exam_spec.py` prints `"ok": true`.
- `generate_exam_pdf.py` prints `"ok": true` and `pages` ≥ 1.
- Open or `read_file` is the wrong check for a binary PDF; confirm the file exists (`terminal` `test -f`) and mention the absolute path in the reply.
- Spot-check the student PDF: marks sum; options look like `(A)` not `bullAt`; no `Answer:` / `Marking:` lines; DFA questions show a state diagram.
- Optional: if the `pdf` skill is loaded, `pdf_read.py paper.pdf --text` should contain the course code and Question A1 (or the first id).
