# Joan Resolve PR Design

Date: 2026-03-01

## Problem

When a Forgejo reviewer submits a "Request Changes" review with no line-level comments (or all line comments have already been resolved), the existing skill workflow has no actionable path. The agent reports a confusing dead-end state instead of attempting to implement the requested changes.

Additionally, the existing `resolve_comment` implementation uses an incorrect PATCH endpoint and request body for the Forgejo API.

## Solution

1. Add a new `uv run joan pr reviews` CLI command that returns review submissions (not line comments).
2. Replace `joan-resolve-pr-comments` with a new `joan-resolve-pr` skill that handles the full PR resolution state matrix, including the approved case.
3. Update `joan-review` to route to `joan-resolve-pr` for all existing-PR work.
4. Fix the `resolve_comment` fallback in `forgejo_client.py` to use the correct Forgejo API endpoint and body.

---

## New CLI Command: `uv run joan pr reviews`

Returns all review submissions for the current PR.

**JSON output:**
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

Fields:
- `id`: review submission ID
- `state`: `APPROVED`, `REQUESTED_CHANGES`, or `COMMENTED`
- `body`: top-level review body text (can be empty string)
- `author`: reviewer username
- `submitted_at`: ISO 8601 timestamp

---

## Backend Fix: `resolve_comment` in `forgejo_client.py`

The current fallback uses the wrong endpoint and body. Replace with the correct Forgejo API:

- **Endpoint**: `PATCH /api/v1/repos/{owner}/{repo}/issues/comments/{comment_id}`
- **Body**: `{"state": "closed"}`

The primary POST endpoint (`/pulls/{index}/comments/{comment_id}/resolve`) can remain as the first attempt since some Forgejo versions support it.

---

## New Skill: `joan-resolve-pr` (replaces `joan-resolve-pr-comments`)

Single entry point for resolving a PR in its current state. Handles the full state matrix:

| `pr sync` state | Action |
|----------------|--------|
| `unresolved_comments > 0` | Walk through line comments one by one; resolve each after implementing the fix |
| `REQUESTED_CHANGES`, `unresolved_comments = 0`, body present | Fetch review body via `pr reviews`; implement from most recent `REQUESTED_CHANGES` body; commit and push |
| `REQUESTED_CHANGES`, `unresolved_comments = 0`, body empty | Surface to user — cannot proceed without instructions |
| `approved`, `unresolved_comments = 0` | Run `uv run joan pr finish` |

After addressing comments or implementing from body: commit changes, run `uv run joan branch push`, re-sync to confirm state.

---

## Updated Skill: `joan-review`

Sub-workflow B (Check & Address Feedback) is simplified: after syncing an existing PR, invoke `joan-resolve-pr` to handle resolution. The inline comment-walking steps move out of `joan-review` entirely.

---

## Affected Files

| File | Change |
|------|--------|
| `skills/joan-resolve-pr/SKILL.md` | New skill (replaces `joan-resolve-pr-comments`) |
| `src/joan/data/codex-skills/joan-resolve-pr/SKILL.md` | Same |
| `skills/joan-resolve-pr-comments/` | Delete |
| `src/joan/data/codex-skills/joan-resolve-pr-comments/` | Delete |
| `skills/joan-review/SKILL.md` | Update Sub-workflow B routing |
| `src/joan/data/codex-skills/joan-review/SKILL.md` | Same |
| Plugin manifest (`plugin.json` or equivalent) | Replace `joan-resolve-pr-comments` with `joan-resolve-pr` |
| `src/joan/shell/forgejo_client.py` | Fix `resolve_comment` fallback endpoint and body |
| `src/joan/cli/pr.py` | Add `reviews` subcommand |
| Supporting Forgejo client code | Add `get_reviews()` method |
