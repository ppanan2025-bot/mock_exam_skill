# Bundled course materials

Drop lecture slides, past mock exams, or tutorial sheets here only if this
skill is cloned onto the Hermes host as a full directory.

Hermes GitHub installs copy files that `SKILL.md` names, not every binary
you add later. On a Hetzner (or other) Hermes host, prefer a local folder
and set:

```
hermes config set skills.config.mock_exam_skill.materials_dir /path/to/course-materials
```

You can also attach PDFs, slides, or tutorial questions in the chat for a
one-off paper. Do not commit copyrighted course files to a public repo.
