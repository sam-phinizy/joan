---
name: joan-pr-narrative
description: >-
  Generate concise PR descriptions from issue context, commits, changed files, and
  test results. Use when the user asks to draft or refresh a Joan PR body from
  branch facts instead of writing prose manually.
---

# Joan PR Narrative

Build a deterministic PR body for the current branch.

## When to use

- User asks to write/update PR description from code changes.
- User asks for a reviewer-friendly summary with tests.
- You need a repeatable PR body format before `joan pr create` or `joan pr update`.

## Workflow

1. Generate narrative markdown:

```bash
joan pr narrative build \
  --from origin/main \
  --to HEAD \
  --tests-json .joan/tests/latest.json \
  --write .joan/pr/body.md
```

2. If an issue should be referenced, include `--issue <number>`.
3. Open or update PR with the generated body:

```bash
joan pr create --title "<title>" --body-file .joan/pr/body.md
# or
joan pr update --body-file .joan/pr/body.md
```

## Output contract

Narrative output includes exactly these sections:

- `## What`
- `## Why`
- `## How`
- `## Tests`
- `## Risks / Follow-ups`

## Rules

1. Keep bullets concrete and branch-specific.
2. Only claim passing tests when exit status indicates success.
3. Prefer file-level implementation bullets over vague summaries.
