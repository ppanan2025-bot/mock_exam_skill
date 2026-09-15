# Sample

`templates/exam_spec.example.json` is a 40-mark databases paper used to test
PDF output. It is not tied to a real cohort.

After install, Hermes should be able to render it with:

```
python ${HERMES_SKILL_DIR}/scripts/generate_exam_pdf.py \
  ${HERMES_SKILL_DIR}/templates/exam_spec.example.json \
  -o /tmp/mock-exam-sample.pdf
```

The printed JSON includes `path` and `pages`. Mention that absolute path in
the reply so the gateway can attach the PDF.
