---
name: joan-pr-comment
description: >-
  Post a comment or update the description on a Joan PR. Use when the user
  wants to leave a general comment on the current PR, post an inline line
  comment, or update the PR description. Also invoked by joan-resolve-pr
  after each work cycle to notify the reviewer.
---

# Joan PR Comment

Unified interface for all PR comment and description update operations.

## Preconditions

1. Verify `.joan/config.toml` exists. If not, tell the user to run
   `/joan:joan-setup` first.
2. Confirm an open PR exists for the current branch:
   ```
   uv run joan pr sync
   ```
   If this fails with "No open PR found", stop and tell the user.

## Determining Intent

**When invoked by another skill** (e.g. joan-resolve-pr after a work cycle),
the intent is passed in context. Proceed directly to the appropriate action.

**When invoked directly by the user**, ask what they want to do:
- Post a general comment (discussion, status update, question)
- Post an inline line comment (feedback on a specific file+line)
- Update the PR description

---

## Action: Post a General Comment

```bash
uv run joan pr comment post --body "<comment text>"
```

Use this when the intent is to leave a discussion comment visible to the
reviewer. After completing a work cycle in joan-resolve-pr, the body should
summarize what was done:

```
Addressed review feedback — pushed changes for re-review.

Changes made:
- <bullet 1>
- <bullet 2>
```

---

## Action: Post an Inline Comment

Read `.joan/config.toml` to get `owner`, `repo`, and the agent name. Get
the PR number from `uv run joan pr sync`. Then:

```bash
uv run joan pr comment add \
  --agent <agent-name> \
  --owner <owner> \
  --repo <repo> \
  --pr <N> \
  --path <file-path> \
  --line <line-number> \
  --body "<comment text>"
```

The agent name is the `name` field from `.joan/agents/<name>.toml`. If
multiple agents exist, use the first one or ask the user.

---

## Action: Update PR Description

There is no joan CLI command to read the current PR body. When updating the
description:

- **When called from joan-resolve-pr:** Build the new body from context only.
  Use the PR title as the opening line (available from the context of the work
  just completed), then append the Changes section. Do not attempt to fetch the
  existing description.
- **When invoked directly by the user:** Ask the user to paste the current PR
  description, or tell them to check the Forgejo UI. Build the new body from
  what they provide.

Count existing `## Changes (Round N)` patterns in what you know of the body to
determine the next round number. If unsure, start at Round 1.

Build the new body:

```
<existing description or title if unknown>

## Changes (Round N)

- <bullet summary of what was done this cycle>
- ...

*Updated by agent on YYYY-MM-DD*
```

Replace `YYYY-MM-DD` with today's date. Replace "agent" with the agent name
from `.joan/config.toml` if available, otherwise leave as "agent".

Then apply:

```bash
uv run joan pr update --body "<full new body>"
```

---

## When Called from joan-resolve-pr

After each commit+push in Sub-workflow A or B, call both actions in sequence:

1. Update the PR description (append Changes round)
2. Post a general comment summarizing this round's work

The comment body should be concise — 2-5 bullets of what changed — so the
reviewer can quickly understand the response without diffing commits.
