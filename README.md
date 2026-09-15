# mock_exam_skill

Hermes Agent skill that writes an **original** mock exam paper as a PDF from:

- lecture slides
- past mock exams
- tutorial questions

You can **send** those files in a Hermes chat, or **store** them on the Hermes host (typical if Hermes runs on a Hetzner cloud VM).

## Install on Hermes

```bash
hermes skills install ppanan2025-bot/mock_exam_skill
```

From a URL:

```bash
hermes skills install https://github.com/ppanan2025-bot/mock_exam_skill
```

Then, in a session that has the skills toolset:

> Generate a same format mock exam from my lecture slides.

## Stored materials (Hetzner / host disk)

Preferred for recurring use. Put PDFs, `.pptx`, `.docx`, `.txt`, or `.md` in a folder the Hermes process can read, then:

```bash
hermes config set skills.config.mock_exam_skill.materials_dir /home/YOU/course-materials
```

Chat uploads still work for one-off papers.

Do not push copyrighted slides to a public GitHub copy of this repo. If you clone the skill onto the host, you may also drop files in `assets/` (see `assets/README.md`).

## What Hermes does

1. Reads the materials (or uses the stored folder).
2. Builds a marks/time blueprint for the course.
3. Writes **new** questions (same topics and style, not copies).
4. Renders an A4 PDF question paper, and optionally a separate answer key.

Helpers:

| Script | Role |
|---|---|
| `scripts/extract_materials.py` | Text from PDF / PPTX / DOCX / markdown |
| `scripts/validate_exam_spec.py` | JSON spec checks |
| `scripts/generate_exam_pdf.py` | Student paper or `--answers` key |
| `scripts/render_graph.py` | Standalone DFA/NFA/graph PDF |

```bash
python -m pip install -r requirements.txt
python scripts/generate_exam_pdf.py templates/exam_spec.example.json -o /tmp/mock-exam-paper.pdf
python scripts/generate_exam_pdf.py templates/macro.example.json -o /tmp/macro-paper.pdf
python scripts/render_graph.py templates/dfa.example.json -o /tmp/dfa.pdf
```

## Graph diagrams (second Hermes skill)

This repo also contains `graph-diagram/`, a separate Hermes skill that draws DFA/NFA figures. Copy it onto the host:

```bash
scp -r graph-diagram root@YOUR_SERVER:~/.hermes/skills/diagrams/graph-diagram
```

Then start a **new** Hermes session. For automata exam questions, Hermes should set a `diagram` object so the picture is embedded in the mock-exam PDF. For macro / pseudocode items, Hermes should set `code` (boxed listing) and `stem_after` instead of inlining the program in `stem`.

## Layout

```
SKILL.md                 # mock-exam Hermes instructions
graph-diagram/           # DFA/NFA drawing skill
scripts/                 # extract, validate, render, graphs
templates/               # exam JSON schema + examples
references/
assets/
examples/
```
