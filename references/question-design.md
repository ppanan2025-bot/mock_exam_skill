# Question design

Use sources to learn the course, not to copy it.

## What to extract from materials

- Topics and learning outcomes actually taught
- Notation, definitions, and diagrams the cohort already uses
- Difficulty and length of existing questions
- Mix of types (MCQ, short, calculation, long) if past papers exist
- Mark allocations and time pressure (roughly 1 mark per minute unless the course does otherwise)

## Originality rules

- Never paste a source question, even with names swapped.
- Change the scenario, numbers, schema, or passage so a student who memorised the tutorial cannot recognise it.
- Keep the same *concept* (for example 3NF, not the tutorial's specific `Hotel` table).
- If a worked example is the only treatment of a method, write a new instance of that method.
- Do not leak answers, marking notes, or tutorial solutions onto the question paper.

## Coverage

- Build a short blueprint before writing items: topic × marks × type.
- Prefer breadth across lectures over many items on the last slide deck.
- Include at least one question that needs combining two ideas from different weeks when the materials support it.
- Match the course's language (variable names, theorem titles). Write exponents as `a^n` or `a^{n}` and inequalities as `>=` / `<=` (the PDF renderer turns these into superscripts and ≥ ≤). Do not leave a visible caret in the intended print form.
- Macro / program / pseudocode definitions belong in `code`, not in the stem. English prompt in `stem`, indented listing in `code`, follow-up sentence in `stem_after`. Never flatten a loop into `rem = left; while rem >= right: { rem = rem - right }`.

## Marks and time

- `meta.total_marks` must equal the sum of question `marks`.
- If a question has `parts`, part marks must sum to the question marks.
- State permitted materials honestly (closed book, formula sheet, calculator).
- Default duration: about 1 minute per mark, rounded to a clean sitting length.

## Answer key

Fill `answer` and `marking_notes` on every item. They appear only when
`generate_exam_pdf.py` is run with `--answers`. The student paper must still
be solvable from the stem alone.
