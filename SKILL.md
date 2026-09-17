---
name: mock-exam-skill
description: Generates original mock exam PDFs from course materials. On Sydney Uni Hermes, visitors upload a paper and the website saves a prompt such as "Give me a mock exam of mid-semester COMP2022"; extra requirements in the same message are applied. Reply with compact exam-json. Do not create skills or emit prompt-json.
version: 0.5.1
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
      - key: mock_exam_skill.profiles_dir
        description: Folder of remembered exam formats (course + sitting)
        default: ""
        prompt: Absolute path for saved exam formats (empty = ~/.hermes/skill-data/mock-exam-skill/profiles)
      - key: mock_exam_skill.prompts_path
        description: Sydney Uni Hermes prompts.json (sidebar PROMPTS list)
        default: ""
        prompt: Path to prompts.json (empty = PROMPTS_PATH env or ~/.hermes/skill-data/mock-exam-skill/prompts.json)
---

# Mock Exam Skill

Builds a **new** mock examination paper from lecture slides, past papers, or tutorials. Questions must be original.

Sydney Uni Hermes shows **Skills** (this skill, graph-diagram) and **Prompts** (one reusable command per exam type). After a visitor uploads a paper, the **website** saves a prompt like `Give me a mock exam of mid-semester COMP2022`. Visitors click it later and may add extras in the same box (`Requirements: 30 minutes, extra DFA practice`). Do **not** add a new skill for each sitting. Do **not** emit `prompt-json` unless they ask to rename or delete a prompt. Guest chats have no shell.

Do not use this skill to grade a live sit exam, copy a past paper, or create/edit skills.

## When to Use

- Mock exam / practice paper / exam-style PDF.
- A sidebar prompt: **Give me a mock exam of mid-semester COMP2022** (or another sitting) plus optional extras.
- User says an attached paper is what that sitting is like.
- Don't use for: copying a past paper, worksheets that are not exams, or `skill_manage`.

## Website guest path (Sydney Uni Hermes)

If this session cannot use `terminal` / `write_file` (public website):

1. Do **not** call `skills_list`, `skill_view`, `skill_manage`, or `terminal`.
2. If they uploaded a paper, match its style (sections, MCQ vs written, macros, automata). If they clicked a saved prompt, match that sitting (`course_code`, mid-semester vs final) and apply any `Requirements:` plus the rest of the message.
3. Write **8–12** original questions in **1–2** sections. Keep stems and answers short.
4. Set `meta.course_code` (e.g. `COMP2022`) and `meta.paper_title` so the site can label the prompt (`Mid-Semester` / `Final`).
5. Macros go in `code` + `stem_after`, not a one-line stem.
6. **Automata must be a `diagram` object.** Never write `q0 -eps→ q1` / `s0 --a--> s1` as the only picture. Stem can say “the NFA below”; transitions live in `diagram`.
7. Reply with one or two sentences, then a single fence. The website turns it into both PDFs.

```exam-json
{
  "meta": {
    "course_code": "COMP2022",
    "paper_title": "Mid-Semester Examination",
    "duration": "1 hour",
    "total_marks": 4
  },
  "sections": [{
    "id": "A",
    "title": "Automata",
    "questions": [{
      "id": "A1",
      "type": "mcq",
      "marks": 4,
      "stem": "The NFA below has start state q0. Which transition is added by epsilon-removal before unreachable states are deleted?",
      "diagram": {
        "kind": "nfa",
        "states": ["q0", "q1", "q2", "q3"],
        "start": "q0",
        "accept": ["q3"],
        "transitions": [
          {"from": "q0", "symbol": "ε", "to": "q1"},
          {"from": "q1", "symbol": "ε", "to": "q2"},
          {"from": "q2", "symbol": "a", "to": "q3"}
        ]
      },
      "choices": [
        {"label": "A", "text": "q0 -a→ q3"},
        {"label": "B", "text": "q0 -b→ q3"}
      ],
      "answer": "A"
    }]
  }]
}
```

Shape: `templates/exam_spec.example.json`. Math in JSON as `a^n` and `>=`. MCQ options as `choices` with labels A–D.

## Host path (Feishu / owner Hermes with a shell)

Python 3.10+, `pip install -r ${HERMES_SKILL_DIR}/requirements.txt`. Unicode serif for ≥ ≤.

```
terminal(command="python ${HERMES_SKILL_DIR}/scripts/extract_materials.py PATH --max-chars 8000", timeout=120)
terminal(command="python ${HERMES_SKILL_DIR}/scripts/exam_profile.py save profile.json", timeout=30)
terminal(command="python ${HERMES_SKILL_DIR}/scripts/exam_profile.py get 'Give me a mock exam of mid-semester COMP2022'", timeout=30)
terminal(command="python ${HERMES_SKILL_DIR}/scripts/exam_profile.py render exam.json 'COMP2022 mid-semester' -o /tmp/comp2022-midsem", timeout=60)
```

If `mock_exam_skill.prompts_path` or `PROMPTS_PATH` is the website `prompts.json`, `save` upserts a sidebar prompt (`Give me a mock exam of mid-semester COMP2022`). The visitor clicks **Refresh**. Same course+sitting updates in place. Never write a new SKILL.md for that.

### Teach a format

User attaches a paper: “this is what the mid-semester exam of COMP2022 is like.” Extract, infer format only (no stems), `exam_profile.py save`. Confirm the prompt text.

### Generate from a prompt

User clicks or types `Give me a mock exam of mid-semester COMP2022` plus extras. `exam_profile.py get` that phrase. Write **new** questions in the saved shape. Apply extras. `exam_profile.py render` (paper + answers). Do not reread long references.

### Generic mock (no saved sitting)

Extract materials → original spec → `validate_exam_spec.py` → two PDFs (`paper` without `--answers`, `answers` with `--answers`). See `references/question-design.md` and `references/exam-spec.md`.

## Pitfalls

- Do not copy source items. A prompt is format only.
- Guest website: no new skills, no `prompt-json` on upload (the site saves the prompt).
- Automata: always set `diagram`. Never leave the machine as `q0 -eps→ q1` in the stem. Macros: `code` with 4-space indent; `<=` stays ASCII in code.
- Answer key must not appear on the student paper.

## Verification

- Website: reply contains one `exam-json` fence; `meta.course_code` set; no skill tools.
- Host: `exam_profile.py render` / `generate_exam_pdf.py` print `"ok": true`. Student PDF has `(A)` not `bullAt`, no `Answer:` lines.
