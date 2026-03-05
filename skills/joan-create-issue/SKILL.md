---
name: joan-create-issue
description: >-
  Manage Forgejo issues in a Joan repo. Use when the user wants to create an
  issue, comment on an issue, read one or many issues and comments, link
  dependencies between issues, close an issue, list what blocks an issue, list
  what an issue blocks, or fetch a JSON dependency graph for agent-driven
  planning.
---

# Joan Create Issue

Use this skill for issue lifecycle and dependency management.

## Preconditions

1. Confirm `.joan/config.toml` exists.
2. Run commands from the target repository root.

## Core Commands

```bash
joan issue create "Issue title" --body "Optional details"
joan issue comment <issue> --body "Comment text"
joan issue comments <issue>
joan issue link <issue> <blocked-by-issue>
joan issue close <issue>
joan issue read --issue <issue>
joan issue read --state all --limit 50
joan issue blocked-by <issue>
joan issue blocks <issue>
joan issue graph <issue> --depth 1
```

## Semantics

- `link <issue> <blocked-by-issue>` means:
  - issue `<issue>` depends on `<blocked-by-issue>`
  - `<blocked-by-issue>` blocks `<issue>`
- `blocked-by` returns upstream blockers.
- `blocks` returns downstream issues waiting on this issue.
- `comment` posts a new issue comment.
- `comments` returns issue comments as JSON.
- `graph` returns JSON:
  - `nodes`: normalized issue objects
  - `edges`: `{from, to}` where `from` blocks `to`

## Execution Rules

1. Read first when context is missing:
   - `joan issue read --state all --limit 100`
2. Reuse existing issues before creating duplicates.
3. After creating or linking, echo issue numbers and relation direction clearly.
4. Prefer machine-readable output (`read`, `blocked-by`, `blocks`, `graph`) when another agent will consume results.
