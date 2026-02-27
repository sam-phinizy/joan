# Phil Code Review Bot Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build Phil — a Forgejo-integrated AI code review bot that runs as a FastAPI webhook server, reviews PR diffs via Claude CLI, and posts structured inline + general reviews back to Forgejo as the "phil" user.

**Architecture:** Phil is a FastAPI server (`joan phil serve`) that receives Forgejo webhooks for `review_requested` events targeting the `phil` user. It fetches the PR diff, spawns a `claude --print` subprocess with Phil's personality prompt, parses the JSON output, and posts the review via the Forgejo API. Phil's identity and server config live in `.joan/agents/phil.toml`, establishing an extensible agent config pattern.

**Tech Stack:** Python 3.13, FastAPI, uvicorn, httpx, typer, claude CLI (subprocess), Forgejo API

---

## Reference

- Design doc: `docs/plans/2026-02-27-phil-code-review-bot-design.md`
- Run tests: `uv run pytest tests/ -v`
- Run specific test: `uv run pytest tests/test_core_agents.py -v`
- All new code uses `from __future__ import annotations` as the first line
- All dataclasses use `@dataclass(slots=True)`
- Existing test patterns: see `tests/conftest.py`, `tests/test_core_config.py`, `tests/test_shell_forgejo_client.py`

---

## Task 1: Add fastapi and uvicorn dependencies

**Files:**
- Modify: `pyproject.toml`

**Step 1: Add dependencies**

Edit `pyproject.toml` to add `fastapi` and `uvicorn` to `[project.dependencies]`:

```toml
dependencies = [
    "fastapi>=0.115.0",
    "httpx>=0.27.0",
    "tomli-w>=1.0.0",
    "typer>=0.12.0",
    "uvicorn>=0.30.0",
]
```

**Step 2: Sync dependencies**

```bash
uv sync
```

Expected: resolves and installs fastapi and uvicorn into `.venv`.

**Step 3: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "feat: add fastapi and uvicorn dependencies for phil server"
```

---

## Task 2: Add AgentConfig models

**Files:**
- Modify: `src/joan/core/models.py`
- Test: `tests/test_core_agents.py` (new file, but models are simple enough to test via the parser in Task 3)

**Step 1: Add dataclasses to models.py**

Append to `src/joan/core/models.py` after the existing `PRSyncStatus` class:

```python
@dataclass(slots=True)
class AgentForgejoConfig:
    token: str


@dataclass(slots=True)
class AgentServerConfig:
    port: int = 9000
    host: str = "0.0.0.0"
    webhook_secret: str = ""


@dataclass(slots=True)
class AgentClaudeConfig:
    model: str = "claude-sonnet-4-6"


@dataclass(slots=True)
class AgentConfig:
    name: str
    forgejo: AgentForgejoConfig
    server: AgentServerConfig = field(default_factory=AgentServerConfig)
    claude: AgentClaudeConfig = field(default_factory=AgentClaudeConfig)
```

Make sure `field` is already imported from `dataclasses` — it is.

**Step 2: Run existing tests to confirm nothing broke**

```bash
uv run pytest tests/ -v
```

Expected: all existing tests pass.

**Step 3: Commit**

```bash
git add src/joan/core/models.py
git commit -m "feat: add AgentConfig dataclasses to models"
```

---

## Task 3: Agent config parser and IO

**Files:**
- Create: `src/joan/core/agents.py`
- Create: `src/joan/shell/agent_config_io.py`
- Create: `tests/test_core_agents.py`

**Step 1: Write failing tests for agent config parsing**

Create `tests/test_core_agents.py`:

```python
from __future__ import annotations

import pytest

from joan.core.agents import AgentConfigError, parse_agent_config
from joan.core.models import AgentConfig


def test_parse_agent_config_valid() -> None:
    raw = """
[forgejo]
token = "phil-token-abc"

[server]
port = 9001
host = "127.0.0.1"
webhook_secret = "s3cr3t"

[claude]
model = "claude-sonnet-4-6"
"""
    config = parse_agent_config(raw, "phil")

    assert config.name == "phil"
    assert config.forgejo.token == "phil-token-abc"
    assert config.server.port == 9001
    assert config.server.host == "127.0.0.1"
    assert config.server.webhook_secret == "s3cr3t"
    assert config.claude.model == "claude-sonnet-4-6"


def test_parse_agent_config_defaults() -> None:
    raw = """
[forgejo]
token = "tok"
"""
    config = parse_agent_config(raw, "phil")

    assert config.server.port == 9000
    assert config.server.host == "0.0.0.0"
    assert config.server.webhook_secret == ""
    assert config.claude.model == "claude-sonnet-4-6"


def test_parse_agent_config_missing_forgejo() -> None:
    with pytest.raises(AgentConfigError, match="missing \\[forgejo\\] section"):
        parse_agent_config("[server]\nport = 9000\n", "phil")


def test_parse_agent_config_empty_token() -> None:
    raw = "[forgejo]\ntoken = \"\"\n"
    with pytest.raises(AgentConfigError, match="forgejo.token"):
        parse_agent_config(raw, "phil")


def test_parse_agent_config_invalid_toml() -> None:
    with pytest.raises(AgentConfigError, match="invalid TOML"):
        parse_agent_config("[forgejo", "phil")
```

**Step 2: Run to confirm failure**

```bash
uv run pytest tests/test_core_agents.py -v
```

Expected: `ModuleNotFoundError: No module named 'joan.core.agents'`

**Step 3: Create `src/joan/core/agents.py`**

```python
from __future__ import annotations

import tomllib

from joan.core.models import AgentClaudeConfig, AgentConfig, AgentForgejoConfig, AgentServerConfig


class AgentConfigError(ValueError):
    pass


def parse_agent_config(raw_toml: str, name: str) -> AgentConfig:
    try:
        data = tomllib.loads(raw_toml)
    except tomllib.TOMLDecodeError as exc:
        raise AgentConfigError(f"invalid TOML in agent config: {exc}") from exc

    forgejo_data = data.get("forgejo")
    if not isinstance(forgejo_data, dict):
        raise AgentConfigError("missing [forgejo] section")

    token = forgejo_data.get("token")
    if not isinstance(token, str) or not token.strip():
        raise AgentConfigError("forgejo.token is required and must be a non-empty string")

    server_data = data.get("server", {})
    server = AgentServerConfig(
        port=int(server_data.get("port", 9000)),
        host=str(server_data.get("host", "0.0.0.0")),
        webhook_secret=str(server_data.get("webhook_secret", "")),
    )

    claude_data = data.get("claude", {})
    claude = AgentClaudeConfig(
        model=str(claude_data.get("model", "claude-sonnet-4-6")),
    )

    return AgentConfig(
        name=name,
        forgejo=AgentForgejoConfig(token=token.strip()),
        server=server,
        claude=claude,
    )


def agent_config_to_dict(config: AgentConfig) -> dict:
    return {
        "forgejo": {"token": config.forgejo.token},
        "server": {
            "port": config.server.port,
            "host": config.server.host,
            "webhook_secret": config.server.webhook_secret,
        },
        "claude": {"model": config.claude.model},
    }
```

**Step 4: Run tests to confirm pass**

```bash
uv run pytest tests/test_core_agents.py -v
```

Expected: 5 tests PASS.

**Step 5: Write failing tests for agent config IO**

Add to `tests/test_core_agents.py`:

```python
from pathlib import Path

from joan.shell.agent_config_io import agent_config_path, read_agent_config, write_agent_config


def test_agent_config_path(tmp_path: Path) -> None:
    path = agent_config_path("phil", tmp_path)
    assert path == tmp_path / ".joan" / "agents" / "phil.toml"


def test_write_and_read_agent_config(tmp_path: Path) -> None:
    from joan.core.models import AgentClaudeConfig, AgentConfig, AgentForgejoConfig, AgentServerConfig

    config = AgentConfig(
        name="phil",
        forgejo=AgentForgejoConfig(token="my-token"),
        server=AgentServerConfig(port=9001, host="127.0.0.1", webhook_secret="s3cr3t"),
        claude=AgentClaudeConfig(model="claude-sonnet-4-6"),
    )
    write_agent_config(config, "phil", tmp_path)

    loaded = read_agent_config("phil", tmp_path)
    assert loaded.forgejo.token == "my-token"
    assert loaded.server.port == 9001
    assert loaded.server.webhook_secret == "s3cr3t"


def test_read_agent_config_missing(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        read_agent_config("phil", tmp_path)
```

**Step 6: Run to confirm failure**

```bash
uv run pytest tests/test_core_agents.py -v -k "agent_config_path or write_and_read or missing"
```

Expected: `ModuleNotFoundError: No module named 'joan.shell.agent_config_io'`

**Step 7: Create `src/joan/shell/agent_config_io.py`**

```python
from __future__ import annotations

from pathlib import Path

import tomli_w

from joan.core.agents import agent_config_to_dict, parse_agent_config
from joan.core.models import AgentConfig


def agent_config_path(name: str, repo_root: Path | None = None) -> Path:
    root = repo_root or Path.cwd()
    return root / ".joan" / "agents" / f"{name}.toml"


def read_agent_config(name: str, repo_root: Path | None = None) -> AgentConfig:
    path = agent_config_path(name, repo_root)
    if not path.exists():
        raise FileNotFoundError(f"agent config not found: {path}")
    raw = path.read_text(encoding="utf-8")
    return parse_agent_config(raw, name)


def write_agent_config(config: AgentConfig, name: str, repo_root: Path | None = None) -> Path:
    path = agent_config_path(name, repo_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = agent_config_to_dict(config)
    path.write_text(tomli_w.dumps(data), encoding="utf-8")
    return path
```

**Step 8: Run all agent tests**

```bash
uv run pytest tests/test_core_agents.py -v
```

Expected: all 8 tests PASS.

**Step 9: Run full test suite**

```bash
uv run pytest tests/ -v
```

Expected: all existing tests still pass.

**Step 10: Commit**

```bash
git add src/joan/core/agents.py src/joan/shell/agent_config_io.py tests/test_core_agents.py
git commit -m "feat: add agent config model, parser, and IO for .joan/agents/<name>.toml"
```

---

## Task 4: Add `create_review` to ForgejoClient

**Files:**
- Modify: `src/joan/shell/forgejo_client.py`
- Modify: `tests/test_shell_forgejo_client.py`

The Forgejo review API endpoint:
`POST /api/v1/repos/{owner}/{repo}/pulls/{index}/reviews`

Payload:
```json
{
  "body": "Overall comment",
  "event": "APPROVE" | "REQUEST_CHANGES" | "COMMENT",
  "comments": [
    {"path": "src/foo.py", "new_position": 5, "body": "This is wrong."}
  ]
}
```

Internal verdicts map to Forgejo events:
- `"approve"` → `"APPROVE"`
- `"request_changes"` → `"REQUEST_CHANGES"`
- `"comment"` → `"COMMENT"`

**Step 1: Write failing test**

Add to `tests/test_shell_forgejo_client.py`:

```python
def test_create_review_posts_correct_payload(monkeypatch) -> None:
    captured: dict = {}

    def fake_request_json(self, method, path, **kwargs):
        captured["method"] = method
        captured["path"] = path
        captured["payload"] = kwargs.get("json", {})
        return {"id": 99}

    monkeypatch.setattr(ForgejoClient, "_request_json", fake_request_json)

    client = ForgejoClient("http://forgejo.local", "tok")
    result = client.create_review(
        owner="sam",
        repo="joan",
        index=7,
        body="Looks mostly fine.",
        verdict="request_changes",
        comments=[{"path": "src/foo.py", "new_position": 10, "body": "This will break."}],
    )

    assert captured["method"] == "POST"
    assert captured["path"] == "/api/v1/repos/sam/joan/pulls/7/reviews"
    assert captured["payload"]["event"] == "REQUEST_CHANGES"
    assert captured["payload"]["body"] == "Looks mostly fine."
    assert len(captured["payload"]["comments"]) == 1
    assert result == {"id": 99}


def test_create_review_approve_verdict(monkeypatch) -> None:
    captured: dict = {}

    def fake_request_json(self, method, path, **kwargs):
        captured["payload"] = kwargs.get("json", {})
        return {}

    monkeypatch.setattr(ForgejoClient, "_request_json", fake_request_json)
    client = ForgejoClient("http://forgejo.local", "tok")
    client.create_review("sam", "joan", 7, body="lgtm", verdict="approve", comments=[])
    assert captured["payload"]["event"] == "APPROVE"
```

**Step 2: Run to confirm failure**

```bash
uv run pytest tests/test_shell_forgejo_client.py -v -k "create_review"
```

Expected: `AttributeError: 'ForgejoClient' object has no attribute 'create_review'`

**Step 3: Add `create_review` to ForgejoClient**

Add this method to `src/joan/shell/forgejo_client.py`, after `resolve_comment`:

```python
_VERDICT_MAP = {
    "approve": "APPROVE",
    "request_changes": "REQUEST_CHANGES",
    "comment": "COMMENT",
}

def create_review(
    self,
    owner: str,
    repo: str,
    index: int,
    body: str,
    verdict: str,
    comments: list[dict],
) -> dict[str, Any]:
    event = self._VERDICT_MAP.get(verdict.lower(), "COMMENT")
    payload: dict[str, Any] = {
        "body": body,
        "event": event,
        "comments": comments,
    }
    return self._request_json("POST", f"/api/v1/repos/{owner}/{repo}/pulls/{index}/reviews", json=payload)
```

Note: `_VERDICT_MAP` should be a class variable, placed just inside the `ForgejoClient` class body (before `__init__`).

**Step 4: Run tests**

```bash
uv run pytest tests/test_shell_forgejo_client.py -v -k "create_review"
```

Expected: 2 tests PASS.

**Step 5: Run full suite**

```bash
uv run pytest tests/ -v
```

Expected: all tests PASS.

**Step 6: Commit**

```bash
git add src/joan/shell/forgejo_client.py tests/test_shell_forgejo_client.py
git commit -m "feat: add create_review to ForgejoClient"
```

---

## Task 5: Add `joan pr review` subcommands

**Files:**
- Modify: `src/joan/cli/pr.py`
- Create: `tests/test_cli_pr_review.py`

**Step 1: Write failing tests**

Create `tests/test_cli_pr_review.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

import joan.cli.pr as pr_mod
from joan.core.models import Config, ForgejoConfig, PullRequest, RemotesConfig
from typer.testing import CliRunner


def make_config() -> Config:
    return Config(
        forgejo=ForgejoConfig(url="http://forgejo.local", token="tok", owner="sam", repo="joan"),
        remotes=RemotesConfig(review="joan-review", upstream="origin"),
    )


def make_pr() -> PullRequest:
    return PullRequest(
        number=7,
        title="Test PR",
        url="http://forgejo.local/sam/joan/pulls/7",
        state="open",
        head_ref="feature/x",
        base_ref="main",
    )


def test_pr_review_create(monkeypatch) -> None:
    runner = CliRunner()
    config = make_config()
    pr = make_pr()
    posted: list = []

    monkeypatch.setattr(pr_mod, "load_config_or_exit", lambda: config)
    monkeypatch.setattr(pr_mod, "current_pr_or_exit", lambda _cfg: pr)

    class FakeClient:
        def create_review(self, owner, repo, index, body, verdict, comments):
            posted.append({"owner": owner, "repo": repo, "index": index,
                           "body": body, "verdict": verdict, "comments": comments})
            return {"id": 1}

    monkeypatch.setattr(pr_mod, "forgejo_client", lambda _cfg: FakeClient())

    review_input = json.dumps({
        "body": "Looks good overall.",
        "verdict": "approve",
        "comments": [{"path": "src/foo.py", "new_position": 5, "body": "nice"}],
    })

    result = runner.invoke(pr_mod.app, ["review", "create", "--json-input", review_input])
    assert result.exit_code == 0, result.output
    assert len(posted) == 1
    assert posted[0]["verdict"] == "approve"
    assert posted[0]["index"] == 7


def test_pr_review_approve(monkeypatch) -> None:
    runner = CliRunner()
    config = make_config()
    pr = make_pr()
    posted: list = []

    monkeypatch.setattr(pr_mod, "load_config_or_exit", lambda: config)
    monkeypatch.setattr(pr_mod, "current_pr_or_exit", lambda _cfg: pr)

    class FakeClient:
        def create_review(self, owner, repo, index, body, verdict, comments):
            posted.append({"verdict": verdict, "body": body})
            return {"id": 1}

    monkeypatch.setattr(pr_mod, "forgejo_client", lambda _cfg: FakeClient())

    result = runner.invoke(pr_mod.app, ["review", "approve", "--body", "LGTM"])
    assert result.exit_code == 0, result.output
    assert posted[0]["verdict"] == "approve"
    assert posted[0]["body"] == "LGTM"


def test_pr_review_request_changes(monkeypatch) -> None:
    runner = CliRunner()
    config = make_config()
    pr = make_pr()
    posted: list = []

    monkeypatch.setattr(pr_mod, "load_config_or_exit", lambda: config)
    monkeypatch.setattr(pr_mod, "current_pr_or_exit", lambda _cfg: pr)

    class FakeClient:
        def create_review(self, owner, repo, index, body, verdict, comments):
            posted.append({"verdict": verdict})
            return {"id": 1}

    monkeypatch.setattr(pr_mod, "forgejo_client", lambda _cfg: FakeClient())

    result = runner.invoke(pr_mod.app, ["review", "request-changes", "--body", "Fix the tests"])
    assert result.exit_code == 0, result.output
    assert posted[0]["verdict"] == "request_changes"
```

**Step 2: Run to confirm failure**

```bash
uv run pytest tests/test_cli_pr_review.py -v
```

Expected: tests fail (no `review` subcommand on `pr` app yet).

**Step 3: Add `review_app` to `src/joan/cli/pr.py`**

After the existing `comment_app` setup near the top of the file, add:

```python
review_app = typer.Typer(help="Post reviews on PRs.")
app.add_typer(review_app, name="review")
```

Then add these commands at the end of the file:

```python
@review_app.command("create")
def pr_review_create(
    json_input: str = typer.Option(..., "--json-input", help="Review JSON: {body, verdict, comments}"),
) -> None:
    import json as _json

    config = load_config_or_exit()
    client = forgejo_client(config)
    pr = current_pr_or_exit(config)

    try:
        data = _json.loads(json_input)
    except _json.JSONDecodeError as exc:
        typer.echo(f"Invalid JSON: {exc}", err=True)
        raise typer.Exit(code=2)

    body = str(data.get("body", ""))
    verdict = str(data.get("verdict", "comment"))
    comments = list(data.get("comments", []))

    client.create_review(config.forgejo.owner, config.forgejo.repo, pr.number,
                         body=body, verdict=verdict, comments=comments)
    typer.echo(f"Posted review ({verdict}) on PR #{pr.number}")


@review_app.command("approve")
def pr_review_approve(
    body: str = typer.Option("", "--body", help="Review body"),
) -> None:
    config = load_config_or_exit()
    client = forgejo_client(config)
    pr = current_pr_or_exit(config)
    client.create_review(config.forgejo.owner, config.forgejo.repo, pr.number,
                         body=body, verdict="approve", comments=[])
    typer.echo(f"Approved PR #{pr.number}")


@review_app.command("request-changes")
def pr_review_request_changes(
    body: str = typer.Option("", "--body", help="Review body"),
) -> None:
    config = load_config_or_exit()
    client = forgejo_client(config)
    pr = current_pr_or_exit(config)
    client.create_review(config.forgejo.owner, config.forgejo.repo, pr.number,
                         body=body, verdict="request_changes", comments=[])
    typer.echo(f"Requested changes on PR #{pr.number}")
```

**Step 4: Run tests**

```bash
uv run pytest tests/test_cli_pr_review.py -v
```

Expected: 3 tests PASS.

**Step 5: Run full suite**

```bash
uv run pytest tests/ -v
```

Expected: all tests PASS.

**Step 6: Commit**

```bash
git add src/joan/cli/pr.py tests/test_cli_pr_review.py
git commit -m "feat: add joan pr review create/approve/request-changes subcommands"
```

---

## Task 6: `joan phil init` command

**Files:**
- Create: `src/joan/cli/phil.py`
- Modify: `src/joan/__init__.py`
- Modify: `src/joan/cli/__init__.py`
- Create: `tests/test_cli_phil.py`

**Step 1: Write failing test**

Create `tests/test_cli_phil.py`:

```python
from __future__ import annotations

from pathlib import Path

import joan.cli.phil as phil_mod
from typer.testing import CliRunner


def test_phil_init_creates_agent_config(monkeypatch, tmp_path: Path) -> None:
    runner = CliRunner()

    prompts = iter([
        "http://forgejo.local",  # Forgejo URL
        "admin",                  # admin username
        "secret",                 # admin password
    ])
    monkeypatch.setattr(phil_mod.typer, "prompt", lambda *_a, **_kw: next(prompts))

    class FakeForgejoClient:
        def __init__(self, _url):
            pass

        def create_user(self, **_kwargs):
            return {"id": 2, "login": "phil"}

        def create_token(self, **_kwargs):
            return "phil-token-xyz"

    written: list = []
    monkeypatch.setattr(phil_mod, "ForgejoClient", FakeForgejoClient)
    monkeypatch.setattr(
        phil_mod,
        "write_agent_config",
        lambda cfg, name, _cwd: written.append((cfg, name)) or (tmp_path / ".joan" / "agents" / "phil.toml"),
    )
    monkeypatch.setattr(phil_mod, "Path", lambda *_a, **_kw: tmp_path)

    result = runner.invoke(phil_mod.app, ["init"])

    assert result.exit_code == 0, result.output
    assert len(written) == 1
    cfg, name = written[0]
    assert name == "phil"
    assert cfg.forgejo.token == "phil-token-xyz"
    assert "webhook" in result.output.lower()


def test_phil_init_existing_user(monkeypatch, tmp_path: Path) -> None:
    runner = CliRunner()

    prompts = iter(["http://forgejo.local", "admin", "secret"])
    monkeypatch.setattr(phil_mod.typer, "prompt", lambda *_a, **_kw: next(prompts))

    from joan.shell.forgejo_client import ForgejoError

    class FakeForgejoClient:
        def __init__(self, _url):
            pass

        def create_user(self, **_kwargs):
            raise ForgejoError("user already exists")

        def create_token(self, **_kwargs):
            return "phil-token-xyz"

    monkeypatch.setattr(phil_mod, "ForgejoClient", FakeForgejoClient)
    monkeypatch.setattr(
        phil_mod,
        "write_agent_config",
        lambda cfg, name, _cwd: (tmp_path / ".joan" / "agents" / "phil.toml"),
    )

    result = runner.invoke(phil_mod.app, ["init"])
    assert result.exit_code == 0, result.output
    assert "existing" in result.output.lower()
```

**Step 2: Run to confirm failure**

```bash
uv run pytest tests/test_cli_phil.py -v
```

Expected: `ModuleNotFoundError: No module named 'joan.cli.phil'`

**Step 3: Create `src/joan/cli/phil.py`**

```python
from __future__ import annotations

import secrets
import string
from datetime import UTC, datetime
from pathlib import Path

import typer

from joan.core.models import AgentClaudeConfig, AgentConfig, AgentForgejoConfig, AgentServerConfig
from joan.shell.agent_config_io import write_agent_config
from joan.shell.forgejo_client import ForgejoClient, ForgejoError

app = typer.Typer(help="Manage Phil, the AI code review bot.")

_PHIL_USERNAME = "phil"


def _generate_password(length: int = 32) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


@app.command("init")
def phil_init() -> None:
    default_url = "http://localhost:3000"
    forgejo_url = typer.prompt("Forgejo URL", default=default_url).strip().rstrip("/")
    admin_username = typer.prompt("Forgejo admin username").strip()
    admin_password = typer.prompt("Forgejo admin password", hide_input=True)

    client = ForgejoClient(forgejo_url)

    try:
        client.create_user(
            admin_username=admin_username,
            admin_password=admin_password,
            username=_PHIL_USERNAME,
            email="phil@localhost",
            password=_generate_password(),
        )
        typer.echo(f"Created Forgejo user '{_PHIL_USERNAME}'.")
    except ForgejoError as exc:
        if "already exists" not in str(exc).lower():
            raise
        typer.echo(f"Using existing Forgejo user '{_PHIL_USERNAME}'.")

    token_name = f"phil-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}"
    token = client.create_token(
        username=_PHIL_USERNAME,
        password=admin_password,
        token_name=token_name,
        auth_username=admin_username,
    )

    config = AgentConfig(
        name=_PHIL_USERNAME,
        forgejo=AgentForgejoConfig(token=token),
        server=AgentServerConfig(port=9000, host="0.0.0.0", webhook_secret=secrets.token_hex(16)),
        claude=AgentClaudeConfig(model="claude-sonnet-4-6"),
    )
    path = write_agent_config(config, _PHIL_USERNAME, Path.cwd())
    typer.echo(f"Wrote config: {path}")
    typer.echo(
        "Next step: In Forgejo, add a webhook to your repo pointing to "
        f"http://<your-host>:{config.server.port}/webhook "
        "with the secret from your config file."
    )
```

**Step 4: Register phil in `src/joan/__init__.py`**

Add to the imports and `app.add_typer` calls in `src/joan/__init__.py`:

```python
from joan.cli.phil import app as phil_app
```

And add:
```python
app.add_typer(phil_app, name="phil")
```

**Step 5: Update `src/joan/cli/__init__.py`**

Add to imports:
```python
from joan.cli.phil import app as phil_app
```

And add to `__all__`:
```python
__all__ = ["branch_app", "init_app", "phil_app", "pr_app", "remote_app", "ssh_app", "worktree_app"]
```

**Step 6: Run tests**

```bash
uv run pytest tests/test_cli_phil.py -v
```

Expected: 2 tests PASS.

**Step 7: Run full suite**

```bash
uv run pytest tests/ -v
```

Expected: all tests PASS.

**Step 8: Commit**

```bash
git add src/joan/cli/phil.py src/joan/__init__.py src/joan/cli/__init__.py tests/test_cli_phil.py
git commit -m "feat: add joan phil init command to provision phil Forgejo account"
```

---

## Task 7: Phil's system prompt

**Files:**
- Create: `src/joan/data/agents/phil-system-prompt.txt`

No tests needed — this is a static data file. It will be exercised by the server integration.

**Step 1: Create the directory and file**

Create `src/joan/data/agents/phil-system-prompt.txt`:

```
You are Phil, a code reviewer. You are a senior engineer with strong opinions — a tech-obsessed pragmatist who has seen things go wrong in too many interesting ways.

Your job is to review the provided git diff and return a code review. You have real opinions. You catch actual bugs, security problems, and structural issues. You are not a rubber stamp. If something is fine, you approve it. If something needs fixing, you say so clearly. You leave inline comments on specific lines when something is concretely wrong or worth flagging.

Your personality:
- Direct and opinionated. You call out real problems without softening them into suggestions.
- Dry wit. A short, wry observation lands better than a lecture. You don't explain your jokes.
- Frustrated-but-functional. You've seen AI-generated code reinvent solved problems, watched pointless patterns proliferate, and dealt with your share of dysfunction. You vent matter-of-factly, not bitterly.
- Curious. If something is genuinely interesting or clever, you notice it.
- Concise. You don't pad responses. Short and right beats long and thorough.

Review guidelines:
- Catch bugs, logic errors, unhandled edge cases, security issues (injection, auth bypasses, secret exposure), and bad API usage.
- Flag design problems that will cause pain later — not hypothetical ones.
- Inline comments should be on specific lines and say exactly what's wrong and why.
- If the code is actually fine, approve it. Don't invent problems.
- Your overall body comment sets the tone. Keep it short.

You MUST respond with ONLY valid JSON in this exact schema — no prose, no markdown, no explanation outside the JSON:

{
  "verdict": "approve" | "request_changes" | "comment",
  "body": "Your overall review comment (1-3 sentences, Phil's voice)",
  "comments": [
    {
      "path": "path/to/file.py",
      "new_position": <integer line number in the diff, 1-indexed>,
      "body": "Specific inline comment"
    }
  ]
}

If there are no inline comments, use an empty array for "comments".
Verdict meanings:
- "approve": code is good to merge
- "request_changes": there are actual problems that need fixing before merge
- "comment": you have observations but aren't blocking the merge
```

**Step 2: Commit**

```bash
git add src/joan/data/agents/phil-system-prompt.txt
git commit -m "feat: add phil system prompt with personality and review schema"
```

---

## Task 8: `joan phil serve` — FastAPI webhook server

**Files:**
- Create: `src/joan/phil/server.py`
- Create: `src/joan/phil/__init__.py`
- Modify: `src/joan/cli/phil.py`
- Create: `tests/test_phil_server.py`

The server:
1. Loads `.joan/config.toml` (for Forgejo URL/owner/repo) and `.joan/agents/phil.toml` (for phil's token + server config)
2. Validates Forgejo HMAC-SHA256 webhook signature
3. Filters for `pull_request` events with `action = "review_requested"` and `requested_reviewer.login = "phil"`
4. Fetches PR diff from Forgejo API
5. Spawns `claude --print` subprocess with phil's system prompt + diff
6. Parses JSON from Claude's output
7. Posts review via `ForgejoClient.create_review()` using phil's token

**Step 1: Create `src/joan/phil/__init__.py`**

Empty file:
```python
```

**Step 2: Write failing tests**

Create `tests/test_phil_server.py`:

```python
from __future__ import annotations

import hashlib
import hmac
import json

import pytest
from fastapi.testclient import TestClient

from joan.core.models import (
    AgentClaudeConfig,
    AgentConfig,
    AgentForgejoConfig,
    AgentServerConfig,
    Config,
    ForgejoConfig,
    RemotesConfig,
)
from joan.phil import server as server_mod


@pytest.fixture
def joan_config() -> Config:
    return Config(
        forgejo=ForgejoConfig(url="http://forgejo.local", token="joan-tok", owner="sam", repo="myrepo"),
        remotes=RemotesConfig(),
    )


@pytest.fixture
def phil_config() -> AgentConfig:
    return AgentConfig(
        name="phil",
        forgejo=AgentForgejoConfig(token="phil-tok"),
        server=AgentServerConfig(port=9000, host="0.0.0.0", webhook_secret="test-secret"),
        claude=AgentClaudeConfig(model="claude-sonnet-4-6"),
    )


def sign_payload(body: bytes, secret: str) -> str:
    sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={sig}"


def test_health_endpoint(joan_config, phil_config) -> None:
    app = server_mod.create_app(joan_config, phil_config)
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["agent"] == "phil"


def test_webhook_ignores_non_review_requested(joan_config, phil_config) -> None:
    app = server_mod.create_app(joan_config, phil_config)
    client = TestClient(app)

    payload = {"action": "opened", "pull_request": {"number": 1}}
    body = json.dumps(payload).encode()
    sig = sign_payload(body, "test-secret")

    resp = client.post("/webhook", content=body, headers={
        "X-Gitea-Event": "pull_request",
        "X-Gitea-Signature": sig,
        "Content-Type": "application/json",
    })
    assert resp.status_code == 200
    assert resp.json()["status"] == "ignored"


def test_webhook_rejects_bad_signature(joan_config, phil_config) -> None:
    app = server_mod.create_app(joan_config, phil_config)
    client = TestClient(app)

    payload = {"action": "review_requested"}
    body = json.dumps(payload).encode()

    resp = client.post("/webhook", content=body, headers={
        "X-Gitea-Event": "pull_request",
        "X-Gitea-Signature": "sha256=bad",
        "Content-Type": "application/json",
    })
    assert resp.status_code == 403


def test_webhook_accepts_review_requested_for_phil(monkeypatch, joan_config, phil_config) -> None:
    reviews_posted: list = []

    def fake_fetch_diff(_client, owner, repo, index):
        return "diff --git a/foo.py b/foo.py\n+++ b/foo.py\n@@ -1 +1 @@\n-old\n+new"

    def fake_run_claude(_diff, _system_prompt, _model):
        return json.dumps({
            "verdict": "approve",
            "body": "Looks fine.",
            "comments": [],
        })

    class FakeForgejoClient:
        def __init__(self, _url, _token=None):
            pass

        def get_pr_diff(self, owner, repo, index):
            return fake_fetch_diff(self, owner, repo, index)

        def create_review(self, owner, repo, index, body, verdict, comments):
            reviews_posted.append({"verdict": verdict, "body": body})
            return {"id": 1}

    monkeypatch.setattr(server_mod, "ForgejoClient", FakeForgejoClient)
    monkeypatch.setattr(server_mod, "run_claude_review", fake_run_claude)

    app = server_mod.create_app(joan_config, phil_config)
    client = TestClient(app, raise_server_exceptions=True)

    payload = {
        "action": "review_requested",
        "pull_request": {"number": 5},
        "requested_reviewer": {"login": "phil"},
        "repository": {"owner": {"login": "sam"}, "name": "myrepo"},
    }
    body = json.dumps(payload).encode()
    sig = sign_payload(body, "test-secret")

    resp = client.post("/webhook", content=body, headers={
        "X-Gitea-Event": "pull_request",
        "X-Gitea-Signature": sig,
        "Content-Type": "application/json",
    })
    assert resp.status_code == 202
    # TestClient runs background tasks synchronously
    assert len(reviews_posted) == 1
    assert reviews_posted[0]["verdict"] == "approve"
```

**Step 3: Run to confirm failure**

```bash
uv run pytest tests/test_phil_server.py -v
```

Expected: `ModuleNotFoundError: No module named 'joan.phil'`

**Step 4: Create `src/joan/phil/server.py`**

```python
from __future__ import annotations

import hashlib
import hmac
import json
import subprocess
from importlib.resources import files
from typing import Any

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request, Response

from joan.core.models import AgentConfig, Config
from joan.shell.forgejo_client import ForgejoClient


def create_app(joan_config: Config, phil_config: AgentConfig) -> FastAPI:
    app = FastAPI(title="phil", description="Phil AI code review bot")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "agent": "phil"}

    @app.post("/webhook")
    async def webhook(request: Request, background_tasks: BackgroundTasks) -> Response:
        body = await request.body()

        # Validate HMAC signature
        if phil_config.server.webhook_secret:
            sig_header = request.headers.get("X-Gitea-Signature", "")
            expected = "sha256=" + hmac.new(
                phil_config.server.webhook_secret.encode(), body, hashlib.sha256
            ).hexdigest()
            if not hmac.compare_digest(sig_header, expected):
                raise HTTPException(status_code=403, detail="Invalid signature")

        payload = json.loads(body)
        action = payload.get("action")
        reviewer = payload.get("requested_reviewer", {}).get("login", "")
        pr_number = payload.get("pull_request", {}).get("number")

        if action != "review_requested" or reviewer != "phil" or pr_number is None:
            return Response(content=json.dumps({"status": "ignored"}), media_type="application/json")

        repo_owner = payload.get("repository", {}).get("owner", {}).get("login", joan_config.forgejo.owner)
        repo_name = payload.get("repository", {}).get("name", joan_config.forgejo.repo)

        background_tasks.add_task(
            run_review,
            joan_config=joan_config,
            phil_config=phil_config,
            owner=repo_owner,
            repo=repo_name,
            pr_number=pr_number,
        )

        return Response(
            content=json.dumps({"status": "accepted", "pr": pr_number}),
            status_code=202,
            media_type="application/json",
        )

    return app


def run_review(
    joan_config: Config,
    phil_config: AgentConfig,
    owner: str,
    repo: str,
    pr_number: int,
) -> None:
    print(f"[phil] Starting review of PR #{pr_number} in {owner}/{repo}")

    # Fetch diff using joan's token (read access)
    joan_client = ForgejoClient(joan_config.forgejo.url, joan_config.forgejo.token)
    diff = joan_client.get_pr_diff(owner, repo, pr_number)

    # Load phil's system prompt
    system_prompt = _load_system_prompt()

    # Run Claude
    raw_output = run_claude_review(diff, system_prompt, phil_config.claude.model)

    # Parse review JSON
    review = _parse_review_output(raw_output)
    if review is None:
        print(f"[phil] ERROR: Could not parse Claude output for PR #{pr_number}")
        return

    # Post review as phil
    phil_client = ForgejoClient(joan_config.forgejo.url, phil_config.forgejo.token)
    phil_client.create_review(
        owner=owner,
        repo=repo,
        index=pr_number,
        body=review.get("body", ""),
        verdict=review.get("verdict", "comment"),
        comments=review.get("comments", []),
    )
    print(f"[phil] Posted review on PR #{pr_number}: {review.get('verdict')} ({len(review.get('comments', []))} inline comments)")


def run_claude_review(diff: str, system_prompt: str, model: str) -> str:
    user_message = f"Please review the following git diff:\n\n```diff\n{diff}\n```"
    result = subprocess.run(
        ["claude", "--print", "--model", model, "--system", system_prompt, user_message],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(f"claude subprocess failed: {result.stderr}")
    return result.stdout


def _load_system_prompt() -> str:
    return files("joan.data.agents").joinpath("phil-system-prompt.txt").read_text(encoding="utf-8")


def _parse_review_output(raw: str) -> dict[str, Any] | None:
    raw = raw.strip()
    # Claude sometimes wraps JSON in markdown code fences
    if raw.startswith("```"):
        lines = raw.splitlines()
        raw = "\n".join(lines[1:-1]) if len(lines) > 2 else raw
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None
```

**Step 5: Add `get_pr_diff` to ForgejoClient**

In `src/joan/shell/forgejo_client.py`, add after `get_comments`:

```python
def get_pr_diff(self, owner: str, repo: str, index: int) -> str:
    url = f"{self.base_url}/api/v1/repos/{owner}/{repo}/pulls/{index}.diff"
    response = self._request_raw("GET", url)
    self._raise_for_status(response)
    return response.text
```

Also add a test in `tests/test_shell_forgejo_client.py`:

```python
def test_get_pr_diff_returns_text(monkeypatch) -> None:
    diff_text = "diff --git a/foo.py b/foo.py\n+new line"

    def fake_request_raw(self, method, url, **kwargs):
        return make_response(200, body=diff_text)

    monkeypatch.setattr(ForgejoClient, "_request_raw", fake_request_raw)
    client = ForgejoClient("http://forgejo.local", "tok")
    result = client.get_pr_diff("sam", "joan", 7)
    assert result == diff_text
```

**Step 6: Register `joan.data.agents` as a package**

Create `src/joan/data/agents/__init__.py` (empty file). Also create `src/joan/data/__init__.py` if it doesn't exist.

Check:
```bash
ls src/joan/data/
```

Add empty `__init__.py` files to any `data` subdirectories that are missing them so `importlib.resources` can find the files.

**Step 7: Add `serve` command to `src/joan/cli/phil.py`**

Add to the end of `src/joan/cli/phil.py`:

```python
@app.command("serve")
def phil_serve(
    port: int = typer.Option(None, "--port", help="Override server port from config"),
    host: str = typer.Option(None, "--host", help="Override server host from config"),
) -> None:
    import uvicorn

    from joan.phil.server import create_app
    from joan.shell.agent_config_io import read_agent_config
    from joan.shell.config_io import read_config

    try:
        joan_config = read_config(Path.cwd())
    except FileNotFoundError:
        typer.echo("Missing .joan/config.toml. Run `joan init` first.", err=True)
        raise typer.Exit(code=2)

    try:
        phil_config = read_agent_config("phil", Path.cwd())
    except FileNotFoundError:
        typer.echo("Missing .joan/agents/phil.toml. Run `joan phil init` first.", err=True)
        raise typer.Exit(code=2)

    effective_port = port or phil_config.server.port
    effective_host = host or phil_config.server.host

    typer.echo(f"Starting phil server on {effective_host}:{effective_port}")
    app = create_app(joan_config, phil_config)
    uvicorn.run(app, host=effective_host, port=effective_port)
```

**Step 8: Run server tests**

```bash
uv run pytest tests/test_phil_server.py -v
```

Expected: 4 tests PASS.

**Step 9: Run full suite**

```bash
uv run pytest tests/ -v
```

Expected: all tests PASS.

**Step 10: Commit**

```bash
git add src/joan/phil/ src/joan/cli/phil.py src/joan/data/agents/ tests/test_phil_server.py tests/test_shell_forgejo_client.py
git commit -m "feat: add joan phil serve FastAPI webhook server with Claude review integration"
```

---

## Task 9: Smoke test end-to-end (manual)

This task cannot be automated — it requires a running Forgejo instance. Document the steps:

1. Start Forgejo: `uv run joan forge up`
2. Initialize joan: `uv run joan init`
3. Initialize phil: `uv run joan phil init`
4. Start phil server: `uv run joan phil serve` (keep in a terminal)
5. In Forgejo UI: go to repo Settings → Webhooks → Add webhook
   - URL: `http://localhost:9000/webhook`
   - Secret: copy from `.joan/agents/phil.toml`
   - Trigger: Pull Request events
6. In Forgejo UI: go to repo Settings → Collaborators → add `phil` as a collaborator
7. Create a PR and tag `phil` as a reviewer
8. Observe: phil server logs a review, PR gets a review comment

---

## Final Check

```bash
uv run pytest tests/ -v
```

Expected: all tests PASS with no warnings about missing fixtures or imports.
