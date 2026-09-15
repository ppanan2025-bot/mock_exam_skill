# Diagram JSON

```json
{
  "kind": "dfa",
  "caption": "DFA over {a, b}",
  "states": ["s0", "s1", "s2"],
  "start": "s0",
  "accept": ["s2"],
  "transitions": [
    {"from": "s0", "symbol": "a", "to": "s0"},
    {"from": "s0", "symbol": "b", "to": "s1"},
    {"from": "s1", "symbol": "a", "to": "s0"},
    {"from": "s1", "symbol": "b", "to": "s2"},
    {"from": "s2", "symbol": "a", "to": "s2"},
    {"from": "s2", "symbol": "b", "to": "s2"}
  ]
}
```

| Field | Meaning |
|---|---|
| `kind` | `dfa`, `nfa`, or `graph` |
| `states` | Node names (inferred from transitions if omitted) |
| `start` or `starts` | Start state(s); start arrow is drawn on the left |
| `accept` | Double-circle states |
| `transitions` | `{from, symbol, to}` or `[from, symbol, to]` |
| `caption` | Optional label under the figure |

Use `ε` for epsilon. Parallel arrows between the same pair are merged into one labelled `a, b`.

In a mock-exam question, put this object on the question as `"diagram": { ... }`.
