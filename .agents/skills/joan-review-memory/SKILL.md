---
name: joan-review-memory
description: >-
  Persist and reuse recurring reviewer feedback so Joan can run a preflight
  checklist before re-review. Use when the user asks to learn from prior PR
  comments or apply known reviewer preferences.
---

# Joan Review Memory

Use `.joan/review-memory/rules.json` as the local memory store for reusable feedback.

## When to use

- User asks to remember recurring review comments.
- User asks for preflight checks before pushing for re-review.
- User asks to apply reviewer preferences consistently.

## Workflow

1. Ingest reviewer feedback from the active PR (or explicit PR):

```bash
joan review-memory ingest
# or
joan review-memory ingest --pr 42
```

2. Inspect stored rules:

```bash
joan review-memory list
joan review-memory list --path src/joan/cli/pr.py
```

3. Generate preflight suggestions for changed files:

```bash
joan review-memory suggest --paths-from-git --format checklist
```

## Rules

1. Treat suggestions as non-blocking by default.
2. Apply only concrete, generalizable feedback patterns.
3. Keep one-off product-direction comments out of memory rules.
