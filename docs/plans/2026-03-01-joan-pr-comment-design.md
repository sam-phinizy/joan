# Joan PR Comment — Design

**Date:** 2026-03-01

## Problem

When `joan-resolve-pr` finishes a round of work (resolving line comments or implementing
review body instructions), it only tells the local user "PR is ready for re-review." The
Forgejo reviewer sees nothing — no PR description update, no comment — until they manually
refresh and diff the commits.

Additionally, there is no convenient way for the agent or user to post a general (non-inline)
comment on a PR, or to update the PR description.

## Goals

1. After every work cycle in `joan-resolve-pr`, update the PR description and leave a
   reviewer-visible comment.
2. Provide a unified `joan-pr-comment` skill usable by both humans (direct invocation) and
   other skills (resolve-pr, review).
3. Add two missing CLI primitives: `joan pr comment post` and `joan pr update`.

## Non-Goals

- Changing the existing `joan pr comment add` CLI command.
- Auto-posting comments when finishing (approving) a PR — only when doing work.

## Design

### New CLI Commands

#### `joan pr comment post --body "..."`

Posts a plain issue-level comment on the current branch's open PR.

- API: `POST /api/v1/repos/{owner}/{repo}/issues/{index}/comments`
- Token: main user token from config (not agent token)
- PR: auto-detected via `current_pr_or_exit()`
- Output: `Posted comment on PR #N`

#### `joan pr update --body "..."`

Updates the PR description (body) on the current branch's open PR.

- API: `PATCH /api/v1/repos/{owner}/{repo}/pulls/{index}` with `{"body": "..."}`
- PR: auto-detected via `current_pr_or_exit()`
- Output: `Updated PR #N description`

Both commands need a corresponding method on `ForgejoClient`:
- `create_issue_comment(owner, repo, index, body)` → POST issues comment
- `update_pr(owner, repo, index, body)` → PATCH pull

### New Skill: `joan-pr-comment`

Location: `skills/joan-pr-comment/SKILL.md`

A unified interface for all PR comment/update operations. Serves two roles:

**User-invoked:** guides the user through choosing an action (general comment, inline
comment, or description update) and executing it.

**Skill-invoked:** called by `joan-resolve-pr` (and potentially `joan-review`) with
explicit intent to summarize completed work and notify the reviewer.

#### Behavior

1. Read `.joan/config.toml` for owner, repo, agent name.
2. Run `uv run joan pr sync` to confirm an open PR exists and get its number.
3. Based on context/intent, execute one or more of:
   - **General comment:** `uv run joan pr comment post --body "..."`
   - **Inline comment:** `uv run joan pr comment add --agent <agent> --owner <owner> --repo <repo> --pr <N> --path <path> --line <line> --body "..."` — skill fills in owner/repo/PR/agent from config so callers don't pass them manually
   - **Description update:** `uv run joan pr update --body "..."` — new body is built by reading the current PR description and appending a `## Changes (Round N)` section summarizing what was done this cycle

#### Description Update Format

```markdown
<existing description>

## Changes (Round N)

- <bullet summary of changes made this cycle>
- ...

*Updated by agent on YYYY-MM-DD*
```

Round number is inferred by counting existing `## Changes` sections + 1.

### Updates to `joan-resolve-pr`

After the commit+push step in both Sub-workflow A and Sub-workflow B, add:

> **Step N: Update PR and notify reviewer**
>
> Invoke `joan-pr-comment` to:
> 1. Append a "Changes (Round N)" summary to the PR description.
> 2. Post a general comment: "Addressed review feedback — pushed changes for re-review."
>
> The comment and description update make the work visible to the reviewer without them
> needing to diff commits manually.

The current "tell the user the PR is ready for re-review" message is retained as a local
echo, but the PR-visible notification is now the primary mechanism.

## File Changes

| File | Change |
|------|--------|
| `src/joan/shell/forgejo_client.py` | Add `create_issue_comment()` and `update_pr()` methods |
| `src/joan/cli/pr.py` | Add `pr_comment_post` and `pr_update` commands |
| `skills/joan-pr-comment/SKILL.md` | New skill |
| `src/joan/data/codex-skills/joan-pr-comment/SKILL.md` | New skill (codex copy) |
| `skills/joan-resolve-pr/SKILL.md` | Add step after push in Sub-workflows A and B |
| `src/joan/data/codex-skills/joan-resolve-pr/SKILL.md` | Same update (codex copy) |

## Out of Scope

- `joan-review` skill changes beyond what resolve-pr already delegates to it.
- Tests for new CLI commands (follow existing test patterns separately).
