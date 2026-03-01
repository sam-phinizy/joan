# Joan PR Comment Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add `joan pr comment post` and `joan pr update` CLI commands, a `joan-pr-comment` skill, and update `joan-resolve-pr` to notify reviewers after each work cycle.

**Architecture:** Two new `ForgejoClient` methods power two new CLI commands (`joan pr comment post`, `joan pr update`). A new `joan-pr-comment` skill wraps these commands as a unified interface for both users and other skills. `joan-resolve-pr` gets a new step after each push that calls the skill to update the description and leave a reviewer-visible comment.

**Tech Stack:** Python, Typer CLI, httpx, pytest/monkeypatch, Forgejo REST API

---

### Task 1: Add `create_issue_comment()` to `ForgejoClient`

**Files:**
- Modify: `src/joan/shell/forgejo_client.py`
- Test: `tests/test_shell_forgejo_client.py`

**Step 1: Write the failing test**

Add to `tests/test_shell_forgejo_client.py`:

```python
def test_create_issue_comment_posts_to_issues_endpoint(monkeypatch) -> None:
    captured: dict = {}

    def fake_request_json(self, method, path, **kwargs):
        captured["method"] = method
        captured["path"] = path
        captured["payload"] = kwargs.get("json", {})
        return {"id": 42}

    monkeypatch.setattr(ForgejoClient, "_request_json", fake_request_json)
    client = ForgejoClient("http://forgejo.local", "tok")
    result = client.create_issue_comment("sam", "joan", 7, "Great work!")

    assert captured["method"] == "POST"
    assert captured["path"] == "/api/v1/repos/sam/joan/issues/7/comments"
    assert captured["payload"] == {"body": "Great work!"}
    assert result == {"id": 42}
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_shell_forgejo_client.py::test_create_issue_comment_posts_to_issues_endpoint -v
```

Expected: `FAILED` with `AttributeError: 'ForgejoClient' object has no attribute 'create_issue_comment'`

**Step 3: Implement**

Add to `src/joan/shell/forgejo_client.py` after `create_inline_pr_comment()`:

```python
def create_issue_comment(self, owner: str, repo: str, index: int, body: str) -> dict[str, Any]:
    payload = {"body": body}
    return self._request_json("POST", f"/api/v1/repos/{owner}/{repo}/issues/{index}/comments", json=payload)
```

**Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_shell_forgejo_client.py::test_create_issue_comment_posts_to_issues_endpoint -v
```

Expected: `PASSED`

**Step 5: Commit**

```bash
git add src/joan/shell/forgejo_client.py tests/test_shell_forgejo_client.py
git commit -m "feat: add create_issue_comment to ForgejoClient"
```

---

### Task 2: Add `update_pr()` to `ForgejoClient`

**Files:**
- Modify: `src/joan/shell/forgejo_client.py`
- Test: `tests/test_shell_forgejo_client.py`

**Step 1: Write the failing test**

Add to `tests/test_shell_forgejo_client.py`:

```python
def test_update_pr_patches_pull_body(monkeypatch) -> None:
    captured: dict = {}

    def fake_request_json(self, method, path, **kwargs):
        captured["method"] = method
        captured["path"] = path
        captured["payload"] = kwargs.get("json", {})
        return {"number": 7, "body": "updated body"}

    monkeypatch.setattr(ForgejoClient, "_request_json", fake_request_json)
    client = ForgejoClient("http://forgejo.local", "tok")
    result = client.update_pr("sam", "joan", 7, "updated body")

    assert captured["method"] == "PATCH"
    assert captured["path"] == "/api/v1/repos/sam/joan/pulls/7"
    assert captured["payload"] == {"body": "updated body"}
    assert result["number"] == 7
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_shell_forgejo_client.py::test_update_pr_patches_pull_body -v
```

Expected: `FAILED` with `AttributeError: 'ForgejoClient' object has no attribute 'update_pr'`

**Step 3: Implement**

Add to `src/joan/shell/forgejo_client.py` after `create_issue_comment()`:

```python
def update_pr(self, owner: str, repo: str, index: int, body: str) -> dict[str, Any]:
    payload = {"body": body}
    return self._request_json("PATCH", f"/api/v1/repos/{owner}/{repo}/pulls/{index}", json=payload)
```

**Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_shell_forgejo_client.py::test_update_pr_patches_pull_body -v
```

Expected: `PASSED`

**Step 5: Commit**

```bash
git add src/joan/shell/forgejo_client.py tests/test_shell_forgejo_client.py
git commit -m "feat: add update_pr to ForgejoClient"
```

---

### Task 3: Add `joan pr comment post` CLI command

**Files:**
- Modify: `src/joan/cli/pr.py`
- Test: `tests/test_cli_pr_comment.py`

The existing `comment_app` typer (already registered under `app` as `"comment"`) just needs a new `"post"` subcommand alongside the existing `"add"` and `"resolve"`.

**Step 1: Write the failing test**

Add to `tests/test_cli_pr_comment.py`:

```python
def test_pr_comment_post_calls_create_issue_comment(monkeypatch) -> None:
    runner = CliRunner()
    config = make_config()
    posted: list = []

    monkeypatch.setattr(pr_mod, "load_config_or_exit", lambda: config)

    class FakePR:
        number = 5
        title = "test"
        url = "http://forgejo.local/owner/repo/pulls/5"
        state = "open"
        head_ref = "joan-review/main"
        base_ref = "main"

    monkeypatch.setattr(pr_mod, "current_pr_or_exit", lambda cfg: FakePR())

    class FakeClient:
        def create_issue_comment(self, owner, repo, index, body):
            posted.append({"owner": owner, "repo": repo, "index": index, "body": body})
            return {"id": 10}

    monkeypatch.setattr(pr_mod, "forgejo_client", lambda cfg: FakeClient())

    result = runner.invoke(pr_mod.app, ["comment", "post", "--body", "Hello reviewer!"])

    assert result.exit_code == 0, result.output
    assert "Posted comment on PR #5" in result.output
    assert posted == [{"owner": "sam", "repo": "joan", "index": 5, "body": "Hello reviewer!"}]
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_cli_pr_comment.py::test_pr_comment_post_calls_create_issue_comment -v
```

Expected: `FAILED` — no `post` subcommand exists yet.

**Step 3: Implement**

Add to `src/joan/cli/pr.py` after the existing `pr_comment_resolve` function (before `pr_comment_add`):

```python
@comment_app.command("post")
def pr_comment_post(
    body: str = typer.Option(..., "--body", help="Comment text to post on the current PR."),
) -> None:
    config = load_config_or_exit()
    client = forgejo_client(config)
    pr = current_pr_or_exit(config)
    client.create_issue_comment(config.forgejo.owner, config.forgejo.repo, pr.number, body)
    typer.echo(f"Posted comment on PR #{pr.number}")
```

**Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_cli_pr_comment.py::test_pr_comment_post_calls_create_issue_comment -v
```

Expected: `PASSED`

**Step 5: Commit**

```bash
git add src/joan/cli/pr.py tests/test_cli_pr_comment.py
git commit -m "feat: add joan pr comment post command"
```

---

### Task 4: Add `joan pr update` CLI command

**Files:**
- Modify: `src/joan/cli/pr.py`
- Test: `tests/test_cli_pr_worktree_and_entrypoint.py` (or create `tests/test_cli_pr_update.py`)

**Step 1: Write the failing test**

Create `tests/test_cli_pr_update.py`:

```python
from __future__ import annotations

import joan.cli.pr as pr_mod
from joan.core.models import Config, ForgejoConfig, RemotesConfig
from typer.testing import CliRunner


def make_config() -> Config:
    return Config(
        forgejo=ForgejoConfig(url="http://forgejo.local", token="tok", owner="sam", repo="joan"),
        remotes=RemotesConfig(review="joan-review", upstream="origin"),
    )


def test_pr_update_patches_description(monkeypatch) -> None:
    runner = CliRunner()
    config = make_config()
    patched: list = []

    monkeypatch.setattr(pr_mod, "load_config_or_exit", lambda: config)

    class FakePR:
        number = 3

    monkeypatch.setattr(pr_mod, "current_pr_or_exit", lambda cfg: FakePR())

    class FakeClient:
        def update_pr(self, owner, repo, index, body):
            patched.append({"owner": owner, "repo": repo, "index": index, "body": body})
            return {"number": index}

    monkeypatch.setattr(pr_mod, "forgejo_client", lambda cfg: FakeClient())

    result = runner.invoke(pr_mod.app, ["update", "--body", "New description here."])

    assert result.exit_code == 0, result.output
    assert "Updated PR #3 description" in result.output
    assert patched == [{"owner": "sam", "repo": "joan", "index": 3, "body": "New description here."}]
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_cli_pr_update.py::test_pr_update_patches_description -v
```

Expected: `FAILED` — no `update` command exists yet.

**Step 3: Implement**

Add to `src/joan/cli/pr.py` after `pr_push` (before the `review_app` commands):

```python
@app.command("update", help="Update the description of the current branch's open PR.")
def pr_update(
    body: str = typer.Option(..., "--body", help="New PR description/body text."),
) -> None:
    config = load_config_or_exit()
    client = forgejo_client(config)
    pr = current_pr_or_exit(config)
    client.update_pr(config.forgejo.owner, config.forgejo.repo, pr.number, body)
    typer.echo(f"Updated PR #{pr.number} description")
```

**Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_cli_pr_update.py::test_pr_update_patches_description -v
```

Expected: `PASSED`

**Step 5: Run full test suite to check for regressions**

```bash
uv run pytest tests/ -v --ignore=tests/integration
```

Expected: All existing tests still pass.

**Step 6: Commit**

```bash
git add src/joan/cli/pr.py tests/test_cli_pr_update.py
git commit -m "feat: add joan pr update command"
```

---

### Task 5: Create `joan-pr-comment` skill

**Files:**
- Create: `skills/joan-pr-comment/SKILL.md`
- Create: `src/joan/data/codex-skills/joan-pr-comment/SKILL.md`

There are no unit tests for skill markdown files — correctness is validated by the skill working in practice.

**Step 1: Create the skill**

Create `skills/joan-pr-comment/SKILL.md`:

```markdown
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

Read the current PR description first (from `uv run joan pr sync` output or
by reading the PR via `uv run joan pr reviews`). Count existing
`## Changes (Round N)` sections to determine the next round number.

Build the new body:

```
<existing description>

## Changes (Round N)

- <bullet summary of what was done this cycle>
- ...

*Updated by agent on YYYY-MM-DD*
```

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
```

**Step 2: Copy to codex directory**

```bash
mkdir -p src/joan/data/codex-skills/joan-pr-comment
cp skills/joan-pr-comment/SKILL.md src/joan/data/codex-skills/joan-pr-comment/SKILL.md
```

**Step 3: Commit**

```bash
git add skills/joan-pr-comment/ src/joan/data/codex-skills/joan-pr-comment/
git commit -m "feat: add joan-pr-comment skill"
```

---

### Task 6: Update `joan-resolve-pr` skill

**Files:**
- Modify: `skills/joan-resolve-pr/SKILL.md`
- Modify: `src/joan/data/codex-skills/joan-resolve-pr/SKILL.md`

**Step 1: Update Sub-workflow A**

In `skills/joan-resolve-pr/SKILL.md`, find Sub-workflow A's commit+push step (currently step 4) and add a new step 5 after it, replacing the existing step 5 (Re-sync):

Current step 4 in Sub-workflow A:
```markdown
### 4. Commit and push

After addressing all comments:

```bash
git add <changed-files>
git commit -m "Address review feedback"
uv run joan branch push
```

### 5. Re-sync
```

Change to:
```markdown
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

Then renumber "Re-sync" from step 5 to step 6, and update its body:

```markdown
### 6. Re-sync

```
uv run joan pr sync
```

If `unresolved_comments` is still non-zero, repeat from step 1.
If `approved = true` and `unresolved_comments = 0`, continue to Sub-workflow C.
Otherwise, tell the user the PR is ready for re-review.
```

**Step 2: Update Sub-workflow B**

Find Sub-workflow B's commit+push step (currently step 4) and add a new step 5, replacing the current step 5 (Re-sync):

Current:
```markdown
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
```

Change to:
```markdown
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
```

**Step 3: Also update the Quick Reference table** to add the two new commands:

```markdown
| `uv run joan pr comment post --body "..."` | Post a general discussion comment on the PR | `Posted comment on PR #N` |
| `uv run joan pr update --body "..."` | Update the PR description | `Updated PR #N description` |
```

**Step 4: Copy updated skill to codex directory**

```bash
cp skills/joan-resolve-pr/SKILL.md src/joan/data/codex-skills/joan-resolve-pr/SKILL.md
```

**Step 5: Commit**

```bash
git add skills/joan-resolve-pr/SKILL.md src/joan/data/codex-skills/joan-resolve-pr/SKILL.md
git commit -m "feat: update joan-resolve-pr to notify reviewer after each work cycle"
```

---

### Task 7: Final verification

**Step 1: Run full test suite**

```bash
uv run pytest tests/ -v --ignore=tests/integration
```

Expected: All tests pass. No new failures.

**Step 2: Verify CLI help reflects new commands**

```bash
uv run joan pr --help
uv run joan pr comment --help
```

Expected output includes `post` under `comment` and `update` at the top level.

**Step 3: Commit if anything was missed**

If any stray files need staging, commit them now. Otherwise the prior task commits are sufficient.
