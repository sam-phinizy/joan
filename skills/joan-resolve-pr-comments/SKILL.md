---
name: joan-resolve-pr-comments
description: >-
  Download unresolved Joan PR review comments and walk through resolving them
  one by one. Use this skill when the user wants to address review feedback,
  fix requested changes, work through PR comments in order, or clear unresolved
  comments before pushing upstream.
---

# Joan Resolve PR Comments

Use this skill to run a guided repair loop for Joan review comments. Do not dump
raw JSON and stop. Turn the current unresolved comments into a work queue and
work through them until they are resolved or blocked.

## Preconditions

1. Verify `.joan/config.toml` exists. If not, tell the user to run
   `/joan:joan-setup` first.
2. Confirm the repo is in a usable state before editing:
   ```
   git status --short
   ```
   If there are unrelated user changes that make the comment context unclear,
   stop and ask before proceeding.

## Guided Loop

### 1. Fetch unresolved comments

Run:
```
uv run joan pr comments
```

This includes both PR-level discussion comments and inline review comments.
If the user points you at a different PR, or you are not on the branch whose PR
you need to inspect, use:

```
uv run joan pr comments --pr <number>
uv run joan pr comments --branch <latest-review-branch>
```

Prefer `--branch` when you know the latest review branch you need, but you are
not currently checked out on it.

- If this returns an empty array, tell the user there are no unresolved comments
  and run `uv run joan pr sync` to confirm the PR state.
- If this fails because there is no open PR, tell the user and stop.

### 2. Summarize the queue

For each unresolved comment, capture:
- `id`
- `body`
- `path`
- `line`

Present a short checklist of the unresolved comments, then start with the first
one.

### 3. Resolve comments one at a time

For each comment:

1. Read the file at `path` around `line` when present.
2. Explain briefly what change is needed.
3. Make the code or content change needed to address the comment.
4. Show the user a concise summary of what changed.
5. Resolve the comment:
   ```
   uv run joan pr comment resolve <id>
   ```
   This still resolves against the current branch's active PR. If you inspected
   comments with `--pr` or `--branch`, switch into that PR's branch context
   before resolving comments.

   **If this command fails with an API error (e.g. 405):** the comment is a
   PR-level discussion comment that cannot be resolved via the API — only inline
   review comments (with a `line` value) can be. Tell the user which comment IDs
   need manual resolution and give them the direct Forgejo PR URL from
   `.joan/config.toml` so they can resolve them in the web UI. Do not stop
   working on other comments; continue with the next one.
6. Move to the next unresolved comment.

## Stop And Ask Rules

Stop and ask the user before resolving a comment if:
- the requested change is ambiguous
- two comments conflict
- the comment is PR-level and the intended file or scope is unclear
- fixing it would require a broader product or design decision

Do not mark a comment resolved unless you made a concrete change or the user
explicitly confirmed a no-code resolution.

## Final Check

After handling all current comments, run:
```
uv run joan pr sync
```

Report:
- whether any unresolved comments remain
- whether the PR is approved
- when the PR is approved by the human reviewer and unresolved comments are `0`,
  immediately finish by running `uv run joan pr finish` so the reviewed changes
  land on the original local base branch without being pushed upstream
- otherwise, whether the user can now move on to finishing the PR with
  `/joan:joan-review` or `uv run joan pr finish`
- only if the user explicitly wants to publish later, remind them they can run
  `uv run joan pr push` from the finished base branch as a separate step
