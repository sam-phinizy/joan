---
name: joan-get-work
description: >-
  Pick the next ready issue in a Joan-managed Forgejo repo. Use when the user
  asks what to work on next, wants a queue of unblocked issues, or wants a
  machine-readable readiness check similar to Beads-style dependency-driven
  work selection.
---

# Joan Get Work

Use this skill to select actionable issues quickly.

## Preconditions

1. Confirm `.joan/config.toml` exists.
2. Run commands from the target repo root.

## Primary Command

```bash
uv run joan issue get-work --limit 200 --ready-limit 25
```

Returns JSON:
- `summary`
- `ready`: open issues with no open blockers
- `blocked`: open issues still blocked by open dependencies

## Workflow

1. Run `joan issue get-work`.
2. If `ready` is non-empty, pick the first issue unless the user provides a different prioritization rule.
3. If `ready` is empty:
   - report blocked items and their blockers
   - run `uv run joan issue graph <issue> --depth 1` for the top blocked issue when dependency context helps
4. Before creating a new issue, check existing work:
   - `uv run joan issue read --state open --limit 100`
