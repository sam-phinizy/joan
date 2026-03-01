# Joan Resolve PR Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add `uv run joan pr reviews` command, fix the `resolve_comment` API fallback, replace `joan-resolve-pr-comments` with a new `joan-resolve-pr` skill that handles the full PR resolution state matrix, and update `joan-review` to route to it.

**Architecture:** Extend the `Review` model with a `body` field and add `format_reviews_json` to expose review submissions via a new CLI command. Fix the existing `resolve_comment` fallback to use the correct Forgejo issues endpoint. The two skills (`joan-resolve-pr` replaces `joan-resolve-pr-comments`) are pure markdown files with no Python backing.

**Tech Stack:** Python 3.13, typer, httpx, pytest (monkeypatch pattern), uv

---

### Task 1: Add `body` to `Review` model

**Files:**
- Modify: `src/joan/core/models.py:64-69`

**Step 1: Read the file**

Open `src/joan/core/models.py` and find the `Review` dataclass (lines 63–69):

```python
@dataclass(slots=True)
class Review:
    id: int
    state: str
    submitted_at: datetime | None
    user: str
```

**Step 2: Add `body` field**

Add `body: str = ""` after `state`:

```python
@dataclass(slots=True)
class Review:
    id: int
    state: str
    body: str
    submitted_at: datetime | None
    user: str
```

Note: `body` has no default so it comes before the optional `submitted_at`. This keeps the dataclass valid (non-default fields must precede default fields — `submitted_at` has no default either, so ordering is fine). Actually both `submitted_at` and `user` have no defaults, so add `body` without a default too.

**Step 3: Run all tests to verify nothing breaks**

```
uv run pytest tests/ -x -q
```

Expected: all tests pass (existing code does not read `body` from `Review` yet, so `parse_reviews` will fail until Task 2).

**Step 4: Commit**

```bash
git add src/joan/core/models.py
git commit -m "feat: add body field to Review model"
```

---

### Task 2: Update `parse_reviews` and add `format_reviews_json`

**Files:**
- Modify: `src/joan/core/forgejo.py:31-40` (parse_reviews)
- Modify: `src/joan/core/forgejo.py` (add format_reviews_json)
- Test: `tests/test_core_forgejo.py`

**Step 1: Write failing tests**

Open `tests/test_core_forgejo.py` and add these two tests at the end of the file. Also add `format_reviews_json` to the import at the top of the file.

Add to the import block (currently lines 8-14):
```python
from joan.core.forgejo import (
    build_create_pr_payload,
    build_create_repo_payload,
    compute_sync_status,
    format_comments_json,
    format_reviews_json,
    parse_comments,
    parse_pr_response,
    parse_reviews,
)
```

Add these tests at the end of the file:

```python
def test_parse_reviews_captures_body() -> None:
    raw = [
        {
            "id": 7,
            "state": "REQUEST_CHANGES",
            "body": "Please fix the auth module",
            "submitted_at": "2026-02-28T14:00:00Z",
            "user": {"login": "reviewer"},
        }
    ]
    reviews = parse_reviews(raw)
    assert len(reviews) == 1
    assert reviews[0].body == "Please fix the auth module"
    assert reviews[0].user == "reviewer"


def test_format_reviews_json_returns_expected_shape() -> None:
    from datetime import datetime, timezone

    from joan.core.models import Review

    reviews = [
        Review(
            id=7,
            state="REQUESTED_CHANGES",
            body="Please fix the auth module",
            submitted_at=datetime(2026, 2, 28, 14, 0, 0, tzinfo=timezone.utc),
            user="reviewer",
        )
    ]
    payload = json.loads(format_reviews_json(reviews))
    assert len(payload) == 1
    assert payload[0]["id"] == 7
    assert payload[0]["state"] == "REQUESTED_CHANGES"
    assert payload[0]["body"] == "Please fix the auth module"
    assert payload[0]["author"] == "reviewer"
    assert payload[0]["submitted_at"] == "2026-02-28T14:00:00Z"


def test_format_reviews_json_handles_empty_body() -> None:
    from joan.core.models import Review

    reviews = [
        Review(id=3, state="APPROVED", body="", submitted_at=None, user="reviewer")
    ]
    payload = json.loads(format_reviews_json(reviews))
    assert payload[0]["body"] == ""
    assert payload[0]["submitted_at"] is None
```

**Step 2: Run tests to verify they fail**

```
uv run pytest tests/test_core_forgejo.py -x -q -k "parse_reviews_captures_body or format_reviews_json"
```

Expected: FAIL — `format_reviews_json` not imported, `parse_reviews` doesn't capture body.

**Step 3: Update `parse_reviews` in `src/joan/core/forgejo.py`**

Current (lines 31-40):
```python
def parse_reviews(raw_reviews: list[dict]) -> list[Review]:
    return [
        Review(
            id=int(item["id"]),
            state=str(item.get("state", "")),
            submitted_at=_parse_dt(item.get("submitted_at")),
            user=str(item.get("user", {}).get("login", "")),
        )
        for item in raw_reviews
    ]
```

Updated:
```python
def parse_reviews(raw_reviews: list[dict]) -> list[Review]:
    return [
        Review(
            id=int(item["id"]),
            state=str(item.get("state", "")),
            body=str(item.get("body", "")),
            submitted_at=_parse_dt(item.get("submitted_at")),
            user=str(item.get("user", {}).get("login", "")),
        )
        for item in raw_reviews
    ]
```

**Step 4: Add `format_reviews_json` to `src/joan/core/forgejo.py`**

Add after `format_comments_json` (after line 85):

```python
def format_reviews_json(reviews: list[Review]) -> str:
    payload = [
        {
            "id": r.id,
            "state": r.state,
            "body": r.body,
            "author": r.user,
            "submitted_at": r.submitted_at.isoformat().replace("+00:00", "Z") if r.submitted_at else None,
        }
        for r in reviews
    ]
    return json.dumps(payload, indent=2)
```

**Step 5: Run tests**

```
uv run pytest tests/test_core_forgejo.py -x -q
```

Expected: all pass.

**Step 6: Run full suite**

```
uv run pytest tests/ -x -q
```

Expected: all pass.

**Step 7: Commit**

```bash
git add src/joan/core/forgejo.py src/joan/core/models.py tests/test_core_forgejo.py
git commit -m "feat: capture review body in parse_reviews and add format_reviews_json"
```

---

### Task 3: Fix `resolve_comment` fallback in `forgejo_client.py`

**Files:**
- Modify: `src/joan/shell/forgejo_client.py:206-218`
- Modify: `tests/test_shell_forgejo_client.py` (update existing fallback test)

**Step 1: Find the existing fallback test**

Search `tests/test_shell_forgejo_client.py` for `resolve_comment`. You will find a test (around line 270-295) that verifies the fallback PATCH call. It currently asserts:

```python
assert fallback_calls[0][1].endswith("/pulls/comments/9")
assert fallback_calls[0][2]["json"] == {"resolved": True}
```

**Step 2: Update the fallback test**

Change those two assertions to:

```python
assert fallback_calls[0][1].endswith("/issues/comments/9")
assert fallback_calls[0][2]["json"] == {"state": "closed"}
```

**Step 3: Run the test to verify it fails**

```
uv run pytest tests/test_shell_forgejo_client.py -x -q -k "resolve_comment"
```

Expected: FAIL — current implementation uses wrong endpoint and body.

**Step 4: Fix `resolve_comment` in `src/joan/shell/forgejo_client.py`**

Current (lines 206-218):
```python
def resolve_comment(self, owner: str, repo: str, index: int, comment_id: int) -> None:
    # Forgejo installations vary on thread resolution endpoints.
    primary = f"/api/v1/repos/{owner}/{repo}/pulls/{index}/comments/{comment_id}/resolve"
    fallback = f"/api/v1/repos/{owner}/{repo}/pulls/comments/{comment_id}"

    try:
        self._request_json("POST", primary)
        return
    except ForgejoError:
        pass

    response = self._request_raw("PATCH", fallback, json={"resolved": True})
    self._raise_for_status(response)
```

Updated:
```python
def resolve_comment(self, owner: str, repo: str, index: int, comment_id: int) -> None:
    # Forgejo installations vary on thread resolution endpoints.
    primary = f"/api/v1/repos/{owner}/{repo}/pulls/{index}/comments/{comment_id}/resolve"
    fallback = f"/api/v1/repos/{owner}/{repo}/issues/comments/{comment_id}"

    try:
        self._request_json("POST", primary)
        return
    except ForgejoError:
        pass

    response = self._request_raw("PATCH", fallback, json={"state": "closed"})
    self._raise_for_status(response)
```

**Step 5: Run tests**

```
uv run pytest tests/test_shell_forgejo_client.py -x -q -k "resolve_comment"
```

Expected: pass.

**Step 6: Run full suite**

```
uv run pytest tests/ -x -q
```

Expected: all pass.

**Step 7: Commit**

```bash
git add src/joan/shell/forgejo_client.py tests/test_shell_forgejo_client.py
git commit -m "fix: use correct Forgejo issues endpoint for resolve_comment fallback"
```

---

### Task 4: Add `pr reviews` CLI command

**Files:**
- Modify: `src/joan/cli/pr.py`
- Create: `tests/test_cli_pr_reviews.py`

**Step 1: Write failing test**

Create `tests/test_cli_pr_reviews.py`:

```python
from __future__ import annotations

import json

import joan.cli.pr as pr_mod
from typer.testing import CliRunner


def test_pr_reviews_outputs_json(monkeypatch, sample_config, sample_pr) -> None:
    runner = CliRunner()

    class FakeClient:
        def get_reviews(self, _owner, _repo, _index):
            return [
                {
                    "id": 7,
                    "state": "REQUEST_CHANGES",
                    "body": "Please refactor the auth module",
                    "submitted_at": "2026-02-28T14:00:00Z",
                    "user": {"login": "reviewer"},
                }
            ]

    monkeypatch.setattr(pr_mod, "load_config_or_exit", lambda: sample_config)
    monkeypatch.setattr(pr_mod, "forgejo_client", lambda _cfg: FakeClient())
    monkeypatch.setattr(pr_mod, "current_pr_or_exit", lambda _cfg, **_kw: sample_pr)

    result = runner.invoke(pr_mod.app, ["reviews"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert len(payload) == 1
    assert payload[0]["id"] == 7
    assert payload[0]["body"] == "Please refactor the auth module"
    assert payload[0]["author"] == "reviewer"
    assert payload[0]["state"] == "REQUEST_CHANGES"
```

Check what `sample_config` and `sample_pr` fixtures look like — they are in `tests/conftest.py`. If that file does not exist, check `test_cli_pr_worktree_and_entrypoint.py` for a `@pytest.fixture` definition. Use the same fixture pattern already in the test suite.

**Step 2: Run test to verify it fails**

```
uv run pytest tests/test_cli_pr_reviews.py -x -q
```

Expected: FAIL — `reviews` command does not exist.

**Step 3: Add `pr reviews` command to `src/joan/cli/pr.py`**

Add the import for `format_reviews_json` at the top (in the existing import from `joan.core.forgejo`):

```python
from joan.core.forgejo import (
    build_create_pr_payload,
    compute_sync_status,
    format_comments_json,
    format_reviews_json,
    parse_comments,
    parse_pr_response,
    parse_reviews,
)
```

Add the command after `pr_comments` (after line 164):

```python
@app.command("reviews", help="List review submissions (with body text) for the open PR on the current branch.")
def pr_reviews() -> None:
    config = load_config_or_exit()
    client = forgejo_client(config)
    pr = current_pr_or_exit(config)

    reviews = parse_reviews(client.get_reviews(config.forgejo.owner, config.forgejo.repo, pr.number))
    typer.echo(format_reviews_json(reviews))
```

**Step 4: Run tests**

```
uv run pytest tests/test_cli_pr_reviews.py -x -q
```

Expected: pass.

**Step 5: Run full suite**

```
uv run pytest tests/ -x -q
```

Expected: all pass.

**Step 6: Commit**

```bash
git add src/joan/cli/pr.py tests/test_cli_pr_reviews.py
git commit -m "feat: add pr reviews command to expose review submission bodies"
```

---

### Task 5: Create `joan-resolve-pr` skill and delete `joan-resolve-pr-comments`

**Files:**
- Create: `skills/joan-resolve-pr/SKILL.md`
- Create: `src/joan/data/codex-skills/joan-resolve-pr/SKILL.md`
- Delete: `skills/joan-resolve-pr-comments/SKILL.md` (and directory)
- Delete: `src/joan/data/codex-skills/joan-resolve-pr-comments/SKILL.md` (and directory)

**Step 1: Create `skills/joan-resolve-pr/SKILL.md`**

```markdown
---
name: joan-resolve-pr
description: >-
  Resolve a Joan PR in its current state. Use when the user wants to address
  review feedback, implement reviewer-requested changes, resolve line comments,
  finish an approved PR locally, or advance a PR that is stuck after all
  comments were resolved but the reviewer hasn't re-approved. Handles the full
  state matrix: line comments, review body instructions, and final approval.
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
| `unresolved_comments > 0` | Sub-workflow A: Resolve Line Comments |
| `latest_review_state = "REQUESTED_CHANGES"`, `unresolved_comments = 0` | Sub-workflow B: Implement from Review Body |
| `approved = true`, `unresolved_comments = 0` | Sub-workflow C: Finish PR |

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

### 5. Re-sync

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

### 5. Re-sync

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

Only if the user explicitly wants to publish later, remind them they can run
`uv run joan pr push` from the finished base branch as a separate step.
```

**Step 2: Create `src/joan/data/codex-skills/joan-resolve-pr/SKILL.md`**

Copy the identical content from the file you just created. Both files must be identical.

**Step 3: Delete `joan-resolve-pr-comments` files**

```bash
rm -rf skills/joan-resolve-pr-comments
rm -rf src/joan/data/codex-skills/joan-resolve-pr-comments
```

**Step 4: Commit**

```bash
git add skills/joan-resolve-pr/ src/joan/data/codex-skills/joan-resolve-pr/
git rm -r skills/joan-resolve-pr-comments/ src/joan/data/codex-skills/joan-resolve-pr-comments/
git commit -m "feat: replace joan-resolve-pr-comments with joan-resolve-pr skill"
```

---

### Task 6: Update `joan-review` skill routing

**Files:**
- Modify: `skills/joan-review/SKILL.md`
- Modify: `src/joan/data/codex-skills/joan-review/SKILL.md`

**Step 1: Update the routing table in Sub-workflow B**

In both files, find the routing summary table (around line 54):

```
| PR exists, has unresolved comments or not approved | Sub-workflow B: Check & Address Feedback |
```

Replace Sub-workflow B with a reference to `joan-resolve-pr`:

Updated routing table:
```markdown
| State | Action |
|-------|--------|
| On `main`, no PR | Create a working branch first, then continue with Sub-workflow A |
| On branch, no PR | Start Sub-workflow A at step 1: create a Joan review branch, then create the PR |
| PR exists | Invoke `/joan:joan-resolve-pr` to handle all review states |
```

**Step 2: Replace Sub-workflow B body**

Find the existing Sub-workflow B section (lines 105-206 in the skill) and replace it entirely:

```markdown
## Sub-workflow B: Check & Address Feedback

Use this when a PR exists. Invoke the `joan-resolve-pr` skill — it handles the
full state matrix: line comments, reviewer-requested changes with a body,
and PR approval/finish.

```
/joan:joan-resolve-pr
```

Do not replicate the resolution logic here. `joan-resolve-pr` owns it.
```

**Step 3: Update the Quick Reference table**

In the Quick Reference table at the bottom of both files, the row for `uv run joan pr comments` stays. Add a new row:

```markdown
| `uv run joan pr reviews` | List review submissions with body and state | JSON array of review objects |
```

**Step 4: Commit**

```bash
git add skills/joan-review/SKILL.md src/joan/data/codex-skills/joan-review/SKILL.md
git commit -m "feat: update joan-review to route to joan-resolve-pr"
```

---

### Task 7: Final verification

**Step 1: Run the full test suite**

```
uv run pytest tests/ -q
```

Expected: all tests pass, no failures.

**Step 2: Verify new command is accessible**

```
uv run joan pr --help
```

Expected: `reviews` appears in the list of commands.

**Step 3: Commit if anything was missed**

If Step 1 or Step 2 revealed issues, fix them and commit with an appropriate message. Do not skip failing tests.
