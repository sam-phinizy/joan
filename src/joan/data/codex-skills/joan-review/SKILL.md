---
name: joan-review
description: >-
  Run the Joan code review cycle through the local Forgejo instance. This skill
  should be used when the user wants to submit code for review, open a pull
  request on Forgejo, check PR status or review feedback, address or resolve
  reviewer comments, finish an approved PR into the task stage branch, or ship
  reviewed work upstream.
---

# Joan Review Workflow

Joan reviews a normal working branch against a long-lived stage branch on the
Forgejo review remote.

## Model

- Working branch: `feature/cache`
- Stage branch: `joan-stage/feature/cache`
- Review PR: `feature/cache -> joan-stage/feature/cache`
- Final publish step: `joan ship`

## Workflow

1. Make sure `.joan/config.toml` exists. If not, invoke `/joan:joan-setup`.
2. Confirm the current branch is a normal task branch:
   ```bash
   git rev-parse --abbrev-ref HEAD
   ```
   If the user is on `main`, start or switch to a task with `/joan:joan-task`.
3. Check whether there is already an open PR:
   ```bash
   joan pr sync
   ```
   - If there is no PR, open one:
     ```bash
     joan pr create --title "Short description of changes"
     ```
   - If a PR exists, invoke `/joan:joan-resolve-pr`.
4. Once the PR is approved and comments are resolved:
   ```bash
   joan pr finish
   ```
   This merges the PR into `joan-stage/<working-branch>`.
5. When the staged work is ready for the final GitHub PR:
   ```bash
   joan ship
   ```

## Rules

1. Always use `joan`.
2. Do not push to the upstream remote directly; use `joan ship`.
3. Resolve comments one at a time and re-push with `joan task push`.
4. `joan-resolve-pr` owns the detailed “what to do with this PR state?” logic.

## Quick Reference

| Command | Purpose | Output |
|---------|---------|--------|
| `joan pr create --title "..." --body "..."` | Open a Forgejo PR from the task branch to its stage branch | `PR #N: {url}` |
| `joan pr sync` | Check approval and comment state | JSON: `{approved, unresolved_comments, latest_review_state}` |
| `joan pr comments` | List unresolved PR comments | JSON array of comment objects |
| `joan pr reviews` | List review submissions | JSON array: `[{id, state, body, author, submitted_at}]` |
| `joan task push` | Push the task branch for another review round | `Pushed task branch: {branch}` |
| `joan pr finish` | Merge the approved PR into the stage branch | `Merged PR #N into joan-stage/{branch}` |
| `joan ship` | Create or refresh the upstream publish branch | `Prepared publish branch ...` |
