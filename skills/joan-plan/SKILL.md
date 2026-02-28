---
name: joan-plan
description: >-
  Put an already-formed plan into Joan's review workflow. This skill should be
  used when the user already has a plan, outline, or agreed direction and wants
  to scaffold a plan document, create a plan review branch, open a plan PR on
  Forgejo, check plan PR status, or land an approved plan. This skill is for
  review logistics, not brainstorming or writing the plan from scratch.
---

# Joan Plan Review

## Use This Skill For

Use this skill when the user already knows what they want to build and wants to:

- create a plan document in the repo
- put that plan on a Joan review branch
- open a PR so humans can comment on the plan
- check or finish a plan PR after review

Do not use this skill to run product discovery, brainstorm options, or generate a planning methodology. If the user is still figuring out the plan, help them with that separately first.

## Workflow

### 1. Confirm the plan is already formed

This skill starts when the user already has a plan idea, outline, or agreed direction. If they are still exploring what to do, stop and work through that first instead of forcing it into Joan.

### 2. Create the plan PR

Use:

```bash
uv run joan plan create <slug> [--title "Readable title"]
```

Behavior:

- creates a Markdown plan file in `docs/plans/`
- creates a review branch like `joan-review/<base>--plan-<slug>`
- opens a PR on Forgejo by default
- requests the configured human reviewer by default

Use `--no-open-pr` only if the user explicitly wants to stage the plan doc without opening review yet.

### 3. Share the review link

When `uv run joan plan create` prints a PR URL, surface it to the user so they can review the plan in Forgejo's UI.

### 4. Check plan review state

Plan PRs use the normal Joan PR commands:

```bash
uv run joan pr sync
uv run joan pr comments
```

Use `uv run joan pr comments` to inspect unresolved feedback on the plan document. Treat plan discussion comments as user-facing feedback, not code changes to auto-resolve unless you made the requested plan edit.

### 5. Land the approved plan

Once the plan PR is approved and has no unresolved comments:

```bash
uv run joan pr finish
```

This lands the approved plan back onto the base branch locally.

## Rules

1. Use `uv run joan`, not bare `joan`.
2. Treat this as a review workflow only. Do not replace the user's planning process.
3. Do not start implementation automatically after the plan lands. Wait for explicit user direction.
4. Use the standard PR commands for status, comments, and finishing. Plan PRs do not have a separate merge path.
