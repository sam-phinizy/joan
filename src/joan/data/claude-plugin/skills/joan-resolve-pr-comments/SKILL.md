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
- whether the user can now move on to pushing upstream with `/joan:joan-review`
  or `uv run joan pr push`
