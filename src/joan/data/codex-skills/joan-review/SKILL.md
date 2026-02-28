---
name: joan-review
description: >-
  Run the Joan code review cycle through the local Forgejo instance. This skill
  should be used when the user wants to submit code for review, open a pull
  request on Forgejo, check PR status or review feedback, address or resolve
  reviewer comments, create a review branch, finish an approved PR locally, or
  push finished changes upstream. Covers the full lifecycle: branch creation,
  PR creation, comment resolution, gated local finish, and separate upstream
  push.
---

# Joan Review Workflow

## Overview

Joan gates all code through local Forgejo review before it reaches upstream (GitHub, GitLab, etc.). The cycle is:

1. Create a review branch
2. Open a PR on Forgejo
3. Human reviews and leaves comments
4. Agent addresses feedback and resolves comments
5. Once approved by the human reviewer with no unresolved comments, immediately finish the review locally by merging the review branch back into the original base branch with `uv run joan pr finish`
6. Only push to GitHub later, as a separate explicit step, with `uv run joan pr push`

All Joan data commands (`pr sync`, `pr comments`) output structured JSON to stdout.

## Determine Current State

Before doing anything, figure out where you are in the review cycle:

1. **Check config**: Verify `.joan/config.toml` exists. If not, tell the user to run setup first (invoke `$joan-setup`).

2. **Check current branch**:
   ```
   git rev-parse --abbrev-ref HEAD
   ```
   If on `main`, stop and create a real working branch first. Joan review branches should be created from an existing non-`main` working branch.

3. **Check for existing PR**:
   ```
   uv run joan pr sync
   ```
   - If this succeeds with JSON output → there's an active PR. Check its state to decide between Sub-workflow B or C.
   - If this fails with "No open PR found" → no PR exists yet. Go to Sub-workflow A.

**Routing summary:**
| State | Action |
|-------|--------|
| On `main`, no PR | Create a working branch first, then continue with Sub-workflow A |
| On branch, no PR | Start Sub-workflow A at step 1: create a Joan review branch, then create the PR |
| PR exists, has unresolved comments or not approved | Sub-workflow B: Check & Address Feedback |
| PR exists, approved by the human reviewer, no unresolved comments | Sub-workflow C: Finish PR Locally |

---

## Sub-workflow A: Submit New Work

Use this when starting fresh work that needs review.

### 1. Create a review branch

Always do this before `uv run joan pr create` unless you intentionally plan to pass `--base` from a non-review branch. The normal Joan flow is to open PRs from a `joan-review/...` branch.

```
uv run joan branch create [name]
```

If `[name]` is omitted, Joan creates `joan-review/<current-branch>` and checks it out.
Joan also pushes the untouched current branch to Forgejo first so it can be used as the PR base.

Output:
```
Created review branch: joan-review/feature/add-in-cacheing (base: feature/add-in-cacheing)
```

### 2. Stage and commit changes

Stage and commit your work on this branch as usual with `git add` and `git commit`. If the work is already committed, skip this step.

### 3. Create a PR

```
uv run joan pr create --title "Short description of changes" --body "Detailed explanation"
```

- `--title` defaults to the branch name if omitted
- `--body` is optional
- `--base` defaults to the base branch implied by `joan-review/<base-branch>`
- By default, Joan requests review from the configured human user in `.joan/config.toml`
- Pass `--no-request-human-review` to skip the automatic reviewer request
- If you're not on a `joan-review/...` branch, pass `--base` explicitly

Output:
```
PR #4: http://localhost:3000/owner/repo/pulls/4
```

Tell the user the Forgejo URL so they can review the PR in the web UI.

---

## Sub-workflow B: Check & Address Feedback

Use this when a PR exists and you need to check for or address review comments.

### 1. Sync PR status

```
uv run joan pr sync
```

JSON output:
```json
{
  "approved": false,
  "unresolved_comments": 3,
  "latest_review_state": "REQUESTED_CHANGES"
}
```

Fields:
- `approved`: `true` if any review granted approval
- `unresolved_comments`: count of unresolved review comments
- `latest_review_state`: `"APPROVED"`, `"REQUESTED_CHANGES"`, `"COMMENTED"`, or `null`

If `approved` is `true` and `unresolved_comments` is `0`, skip to Sub-workflow C and complete the local review flow with `uv run joan pr finish` instead of stopping at status reporting.

### 2. Fetch unresolved comments

```
uv run joan pr comments
```

This includes both PR-level discussion comments and inline review comments.
If you need to inspect a different PR than the one implied by the current branch, use one of:

```
uv run joan pr comments --pr <number>
uv run joan pr comments --branch <latest-review-branch>
```

Prefer `--branch` when you know the latest review branch you want, but you are not currently checked out on it.

JSON output (array of unresolved comments):
```json
[
  {
    "id": 42,
    "body": "This function should handle the error case",
    "path": "src/handler.py",
    "line": 15,
    "resolved": false,
    "author": "reviewer-username",
    "created_at": "2026-02-27T10:00:00Z"
  }
]
```

Use `--all` to include already-resolved comments if you need full context.

Fields:
- `id`: comment ID (used to resolve it later)
- `body`: the reviewer's feedback
- `path`: file path the comment refers to
- `line`: line number (can be `null` for PR-level comments)
- `resolved`: always `false` in default output
- `author`: who wrote the comment
- `created_at`: ISO 8601 timestamp

### 3. Address each comment

For each unresolved comment:

1. **Read** the file at `path` around `line` to understand the context
2. **Make the requested change** — edit the code to address the feedback
3. **Resolve the comment**:
   ```
   uv run joan pr comment resolve <id>
   ```
   Output: `Resolved comment <id>`

`uv run joan pr comment resolve` still applies to the current branch's active PR. If you inspected comments with `--pr` or `--branch`, switch to that PR's working branch before resolving comments.

Work through comments one at a time. This ensures each resolution is deliberate and traceable.

**Important:** If a comment is a discussion or question (not an actionable code change), surface it to the user rather than auto-resolving it. Only resolve comments where you've made a concrete change.

### 4. Commit and push

After addressing all comments, commit the changes and push:
```
git add <changed-files>
git commit -m "Address review feedback"
uv run joan branch push
```

### 5. Re-check status

```
uv run joan pr sync
```

Verify `unresolved_comments` is `0`. If there are still unresolved comments, repeat from step 2. If the reviewer hasn't re-approved yet, tell the user the PR is ready for another look.

---

## Sub-workflow C: Finish PR Locally

Use this when the PR is approved by the human reviewer and all comments are resolved. Do not stop after confirming approval; finish the review workflow by running `uv run joan pr finish`. This merges the approved review branch back into the original base branch locally only. It does not push to GitHub.

### 1. Verify readiness

Run `uv run joan pr sync` and confirm:
- `"approved": true`
- `"unresolved_comments": 0`

### 2. Finish

```
uv run joan pr finish
```

This command enforces approval gates internally. If the PR is not approved or has unresolved comments, it exits with code 1 and an error message:
- `PR is not approved on Forgejo.`
- `PR has N unresolved comments.`

On success:
```
Merged joan-review/feature-x into local main
```

The reviewed changes are now applied back to the original local base branch. They are not pushed upstream yet.

### 3. Optional later push

Only when the user explicitly wants to publish the finished local branch upstream, run:
```
uv run joan pr push
```

Run this from the finished base branch (for example `main`), not from the `joan-review/...` branch.

---

## Rules

1. **Never push to `origin` directly.** When the user wants to publish upstream, use `uv run joan pr push` instead.
2. **Always use `uv run joan`**, not bare `joan`. Joan is managed by `uv` and may not be on PATH.
3. **Resolve comments one at a time** as you address each one, not in bulk at the end.
4. **Discussion comments go to the user.** If a comment is a question or discussion point (not an actionable change request), surface it to the user and let them decide how to handle it. Do not auto-resolve.
5. **Check state before acting.** Always run `uv run joan pr sync` to understand where you are before starting work.
6. **Approval is not the stopping point.** When the PR is approved by the human reviewer and there are no unresolved comments, immediately run `uv run joan pr finish` so the reviewed changes land on the original local base branch.
7. **Upstream push is separate.** Do not push to GitHub as part of finishing a PR. Only run `uv run joan pr push` later if the user explicitly wants the finished branch published upstream.

---

## Quick Reference

| Command | Purpose | Output |
|---------|---------|--------|
| `uv run joan branch create [name]` | Create review branch | `Created review branch: {review_branch} (base: {working_branch})` |
| `uv run joan pr create --title "..." --body "..."` | Open PR on Forgejo and request the configured human reviewer by default | `PR #N: {url}` |
| `uv run joan pr sync` | Check approval & comment status | JSON: `{approved, unresolved_comments, latest_review_state}` |
| `uv run joan pr comments` | List unresolved PR-level and inline review comments for the current PR | JSON array of comment objects |
| `uv run joan pr comments --pr N` | List unresolved comments for a specific PR | JSON array of comment objects |
| `uv run joan pr comments --branch <name>` | List unresolved comments for the open PR on a specific branch | JSON array of comment objects |
| `uv run joan pr comments --all` | List all comments (incl. resolved) | JSON array of comment objects |
| `uv run joan pr comment resolve <id>` | Mark comment as resolved | `Resolved comment <id>` |
| `uv run joan pr finish` | Merge an approved review branch back into its original local base branch | `Merged {review_branch} into local {working_branch}` |
| `uv run joan pr push` | Push the current finished local branch upstream | `Pushed {branch} to origin/{branch}` |
| `uv run joan branch push` | Push current branch for re-review | `Pushed branch: {branch}` |
