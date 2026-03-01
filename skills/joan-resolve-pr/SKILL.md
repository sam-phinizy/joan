---
name: joan-resolve-pr
description: >-
  Resolve a Joan PR in its current state. Use when the user wants to address
  review feedback, implement reviewer-requested changes from a review body,
  resolve line comments, finish an approved PR locally, or determine next steps
  when the PR has no actionable feedback. Handles the full state matrix: line
  comments, review body instructions, formal approval, and no-feedback states.
---

# Joan Resolve PR

Single entry point for advancing a Joan PR. Always start by syncing PR state,
then act based on what the sync tells you.

## Preconditions

1. Verify `.joan/config.toml` exists. If not, tell the user to run
   `/joan:joan-setup` first.
2. Confirm the repo is in a usable state:
   ```
   git status --short
   ```
   If there are unrelated user changes that make the context unclear, stop
   and ask before proceeding.

## Step 1: Sync PR state

```
uv run joan pr sync
```

JSON output:
```json
{
  "approved": false,
  "unresolved_comments": 0,
  "latest_review_state": "REQUESTED_CHANGES"
}
```

Route to the correct sub-workflow based on what you see:

| State | Action |
|-------|--------|
| `unresolved_comments > 0` | Sub-workflow A: Resolve Line Comments (even if approved — resolve comments first) |
| `latest_review_state = "REQUESTED_CHANGES"`, `unresolved_comments = 0` | Sub-workflow B: Implement from Review Body |
| `approved = true`, `unresolved_comments = 0` | Sub-workflow C: Finish PR |
| `latest_review_state = "COMMENTED"` or `null`, `unresolved_comments = 0` | No actionable feedback — tell the user the PR is awaiting formal review |

---

## Sub-workflow A: Resolve Line Comments

Use when `unresolved_comments > 0`.

### 1. Fetch unresolved comments

```
uv run joan pr comments
```

If the list is empty despite the count being non-zero, re-sync and re-check.

### 2. Summarize the queue

For each comment, capture `id`, `body`, `path`, `line`. Present a short
checklist, then start with the first one.

### 3. Resolve comments one at a time

For each comment:

1. Read the file at `path` around `line`.
2. Explain briefly what change is needed.
3. Make the change.
4. Show a concise summary of what changed.
5. Resolve:
   ```
   uv run joan pr comment resolve <id>
   ```
   **If this fails with an API error (e.g. 405):** the comment is a PR-level
   discussion comment that cannot be resolved via the API. Tell the user which
   IDs need manual resolution and give them the Forgejo PR URL. Continue with
   the next comment.

   Note: resolving a comment in Forgejo is a bookkeeping step. The actual code
   changes only reach the reviewer once you push in step 4.

Stop and ask the user before resolving a comment if:
- the change is ambiguous
- two comments conflict
- the scope is unclear
- fixing it requires a broader product or design decision

Do not mark a comment resolved unless you made a concrete change or the user
explicitly confirmed a no-code resolution.

### 4. Commit and push

After addressing all comments:

```bash
git add <changed-files>
git commit -m "Address review feedback"
uv run joan branch push
```

### 5. Update PR and notify reviewer

Invoke `joan-pr-comment` to:
1. Append a "Changes (Round N)" section to the PR description summarizing
   what was addressed this cycle.
2. Post a general comment:
   ```
   Addressed review feedback — pushed changes for re-review.

   Changes made:
   - <bullet per resolved comment>
   ```

### 6. Re-sync

```
uv run joan pr sync
```

If `unresolved_comments` is still non-zero, repeat from step 1.
If `approved = true` and `unresolved_comments = 0`, continue to Sub-workflow C.
Otherwise, tell the user the PR is ready for re-review.

---

## Sub-workflow B: Implement from Review Body

Use when `latest_review_state = "REQUESTED_CHANGES"` and `unresolved_comments = 0`.
The reviewer used the "Request Changes" action but left no line comments (or all
comments are already resolved). The instructions are in the review body.

### 1. Fetch review submissions

```
uv run joan pr reviews
```

JSON output (array):
```json
[
  {
    "id": 7,
    "state": "REQUESTED_CHANGES",
    "body": "Please refactor the auth module to use the new token pattern",
    "author": "reviewer-username",
    "submitted_at": "2026-02-28T14:00:00Z"
  }
]
```

Take the most recent entry with `state = "REQUESTED_CHANGES"`.

### 2. Check the body

- **If `body` is empty or blank:** Stop. Tell the user: "The reviewer requested
  changes but left no instructions. Ask them to clarify what they want changed."
  Do not proceed.
- **If `body` has text:** Use it as the instruction for what to implement.

### 3. Implement the requested changes

Read the relevant files, understand the context, then make the changes described
in the review body. Do not resolve any comments — there are none. Work directly
from the body text.

Stop and ask the user if:
- the instructions are ambiguous
- the change requires a broader product or design decision

### 4. Commit and push

```bash
git add <changed-files>
git commit -m "Implement reviewer-requested changes"
uv run joan branch push
```

### 5. Update PR and notify reviewer

Invoke `joan-pr-comment` to:
1. Append a "Changes (Round N)" section to the PR description summarizing
   what was implemented.
2. Post a general comment:
   ```
   Implemented requested changes — pushed for re-review.

   Changes made:
   - <bullet per change>
   ```

### 6. Re-sync

```
uv run joan pr sync
```

Tell the user the PR is ready for re-review.

---

## Sub-workflow C: Finish PR

Use when `approved = true` and `unresolved_comments = 0`.

```
uv run joan pr finish
```

On success:
```
Merged joan-review/feature-x into local main
```

The reviewed changes are now on the original local base branch. They are not
pushed upstream.

Only if the user explicitly wants to publish later, remind them to switch to
the finished base branch first (not the `joan-review/...` branch), then run:
```bash
uv run joan pr push
```

---

## Quick Reference

| Command | Purpose | Output |
|---------|---------|--------|
| `uv run joan pr sync` | Check approval and comment state | JSON: `{approved, unresolved_comments, latest_review_state}` |
| `uv run joan pr comments` | List unresolved PR-level and inline comments | JSON array of comment objects |
| `uv run joan pr reviews` | List review submissions with body text | JSON array: `[{id, state, body, author, submitted_at}]` |
| `uv run joan pr comment resolve <id>` | Mark a comment resolved | `Resolved comment <id>` |
| `uv run joan branch push` | Push current branch for re-review | `Pushed branch: {branch}` |
| `uv run joan pr finish` | Merge approved review branch into local base branch | `Merged {review_branch} into local {base_branch}` |
| `uv run joan pr push` | Push finished base branch upstream (run from base branch) | `Pushed {branch} to origin/{branch}` |
| `uv run joan pr comment post --body "..."` | Post a general discussion comment on the PR | `Posted comment on PR #N` |
| `uv run joan pr update --body "..."` | Update the PR description | `Updated PR #N description` |
