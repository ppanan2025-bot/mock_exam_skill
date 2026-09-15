---
name: graph-diagram
description: Draws DFA, NFA, and labelled directed graphs.
version: 0.1.0
author: AnPan (ppanan2025-bot), Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [dfa, nfa, automata, graph, diagram, pdf]
    related_skills: [mock-exam-skill, pdf]
---

# Graph Diagram Skill

Draws a **DFA, NFA, or labelled directed graph** as a PDF figure from a JSON spec. Use this whenever a question or explanation needs an automaton picture instead of a transition list in prose.

Do not describe a DFA only as `s0 --a--> s1` in exam text when a diagram can be drawn.

## When to Use

- The user asks to draw a DFA, NFA, ε-NFA, or directed graph.
- A mock-exam item is about the language of an automaton, conversion NFA→DFA, or pumping / regex ↔ automaton.
- Don't use for: pixel-perfect Graphviz house style, or charts/plots (use matplotlib via `execute_code`).

## Prerequisites

- Python 3.10+ with `reportlab` (same install as mock-exam-skill):
  `python -m pip install reportlab`
- Scripts live in this skill directory, or next to mock-exam-skill at `${HERMES_SKILL_DIR}/../scripts` if the whole repo was copied.

Prefer, in order:

1. `${HERMES_SKILL_DIR}/scripts/render_graph.py` when this folder is the skill root
2. `${HERMES_SKILL_DIR}/../scripts/render_graph.py` when installed as part of `mock_exam_skill`

## How to Run

```
terminal(command="python ${HERMES_SKILL_DIR}/scripts/render_graph.py diagram.json -o /tmp/dfa.pdf --title 'DFA over {a,b}'", timeout=30)
```

If that path 404s, retry with the repo `scripts/` directory shown above. The command prints JSON with `path`.

## Quick Reference

| Task | Command |
|---|---|
| Draw figure | `render_graph.py spec.json -o /tmp/graph.pdf` |
| Example spec | `templates/dfa.example.json` |
| Spec fields | `references/diagram-spec.md` |

## Procedure

1. **Collect the machine.** From the user or from an exam question, obtain states, alphabet, start, accept, and transitions. Completion: every mentioned state appears in `states` or will be inferred from transitions.
2. **Write JSON** with `write_file` in the shape of `templates/dfa.example.json`. Use `kind`: `dfa`, `nfa`, or `graph`. Epsilon labels: `ε`. Multiple symbols on one arrow: either several transition objects or the renderer will join labels `a, b` on the same pair of states.
3. **Never dump a long `s0 --a--> s1` sentence as the only figure.** Put that information in `transitions` and draw it.
4. **Render.** `terminal(command="python …/render_graph.py spec.json -o /tmp/dfa.pdf", timeout=30)` until `"ok": true`.
5. **Deliver** the absolute PDF path. End with `[[as_document]]`. If this figure belongs inside a mock exam, copy the same object into the question's `diagram` field and let `generate_exam_pdf.py` embed it — do not paste a screenshot description.

## Pitfalls

- Times/list bullets are unrelated to this skill; still never encode the graph only as markdown bullets.
- Large machines (>12 states) get crowded on one page — split or ask to focus on a subset.
- `graph` kind is the same drawer without requiring accept/start, but start arrows are skipped when `starts` is empty.

## Verification

- JSON result has `"ok": true` and `states` ≥ 1.
- File exists (`test -f`).
- Spot-check: start state has a left-pointing arrow; accept states are double circles.
