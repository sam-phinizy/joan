---
name: joan-adopt-branch
description: >-
  Register the current working branch's starting point so Joan can open the
  first review PR against the correct base. Use when a branch predates Joan's
  tracking, was created outside Joan, or the user wants to choose the parent
  branch explicitly before opening a review PR.
---

# Joan Adopt Branch

Use this when the current working branch already exists and Joan does not yet
know where that branch started.

This is the explicit escape hatch for branches created before Joan tracking or
created outside the normal Joan workflow.

## When to Use It

Use this skill when:

- the user wants to review work on an existing branch
- the branch was created manually with `git switch -c` or in another tool
- Joan would otherwise guess the branch base and the user wants to pick it
- the branch is based on another non-`main` branch and the parent branch needs
  to be chosen explicitly

Do not use this on a `joan-review/...` branch. Switch to the underlying working
branch first.

## Workflow

### 1. Confirm the current branch

```bash
git rev-parse --abbrev-ref HEAD
```

If the branch starts with `joan-review/`, stop and tell the user to switch back
to the working branch before adopting it.

### 2. Ask which branch this work forked from

The user should choose the actual parent ref, for example:

- `origin/main`
- `origin/master`
- `feature/base`

If the user is unsure, ask them to pick the branch they want the first review
PR to be compared against.

### 3. Register the branch start

```bash
uv run joan branch adopt --base-ref <chosen-ref>
```

This stores the branch start commit in `.joan/branch-state.json`.

### 4. Continue with the normal review flow

After adoption, the normal next step is:

```bash
uv run joan branch create
```

Then continue with `/joan:joan-review`.

## Rules

1. Use `uv run joan`, not bare `joan`.
2. This records the branch start for the current working branch; it does not
   open a PR by itself.
3. Prefer the real parent branch over guessing `main` when the branch is stacked
   on top of another feature branch.
