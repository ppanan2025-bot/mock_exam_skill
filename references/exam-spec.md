# Exam spec JSON

Write one UTF-8 JSON file, then validate before rendering.

See `templates/exam_spec.schema.json` and `templates/exam_spec.example.json`.

## Root

```json
{
  "meta": { "...": "..." },
  "sections": [ { "id": "A", "title": "...", "questions": [] } ]
}
```

## `meta`

| Field | Required | Notes |
|---|---|---|
| `institution` | no | Header line |
| `course_code` | yes | e.g. `COMP1099` |
| `course_name` | yes | |
| `paper_title` | yes | Usually `Mock Examination Paper` |
| `sitting` | no | e.g. `Semester 1, 2026` |
| `duration` | yes | Human string, e.g. `2 hours` |
| `total_marks` | yes | Must equal the sum of question marks |
| `permitted_materials` | no | Defaults to closed book wording |
| `instructions` | no | List of strings |

## Question types

`mcq` · `true_false` · `short` · `long` · `calculation` · `fill_blank`

- `mcq` needs `choices` with unique `label` + `text` (at least two).
- `true_false` is rendered as True / False; store the key in `answer`.
- `parts` optional. Each part may have `id`, `stem`, `marks`, `answer_lines`, `answer`, `marking_notes`.
- `answer` / `marking_notes` are omitted from the student PDF.
- `answer_lines` controls blank lines on the student paper.

## IDs

Question `id` values must be unique across the whole paper (`A1`, `B2`, …).
