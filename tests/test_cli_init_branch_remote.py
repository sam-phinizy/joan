from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

import joan.cli.branch as branch_mod
import joan.core.git as git_mod
import joan.cli.init as init_mod
import joan.cli.remote as remote_mod
from joan.core.branch_state import load_branch_state, save_branch_state
from joan.core.models import Config, ForgejoConfig, RemotesConfig


def make_config() -> Config:
    return Config(
        forgejo=ForgejoConfig(
            url="http://forgejo.local",
            token="tok",
            owner="joan",
            repo="joan",
            human_user="sam",
        ),
        remotes=RemotesConfig(review="joan-review", upstream="origin"),
    )


def test_init_command(monkeypatch) -> None:
    runner = CliRunner()

    # Prompts: url, admin_username, admin_password, repo
    prompts = iter([
        "http://forgejo.local",
        "sam",
        "secret",
        "my-project",
    ])

    monkeypatch.setattr(init_mod.typer, "prompt", lambda *_args, **_kwargs: next(prompts))

    written_global: list = []
    written_repo: list = []

    class FakeForgejoClient:
        def __init__(self, _url):
            pass

        def create_user(self, **_kwargs):
            return {"id": 1, "login": "joan"}

        def create_token(self, **_kwargs):
            return "token-abc"

    monkeypatch.setattr(init_mod, "ForgejoClient", FakeForgejoClient)
    monkeypatch.setattr(init_mod, "read_global_config", lambda: None)
    monkeypatch.setattr(init_mod, "write_global_config", lambda cfg: written_global.append(cfg) or Path.home() / ".joan" / "config.toml")
    monkeypatch.setattr(init_mod, "write_repo_config", lambda cfg, _cwd: written_repo.append(cfg) or Path(".joan/config.toml"))

    result = runner.invoke(init_mod.app, [])

    assert result.exit_code == 0, result.output
    assert "Wrote config" in result.output
    assert "Next step" in result.output
    assert len(written_global) == 1
    assert written_global[0].owner == "joan"
    assert written_global[0].human_user == "sam"
    assert len(written_repo) == 1
    assert written_repo[0].repo == "my-project"


def test_init_command_reuses_existing_joan_user(monkeypatch) -> None:
    runner = CliRunner()

    prompts = iter([
        "http://forgejo.local",
        "sam",
        "secret",
        "my-project",
    ])

    monkeypatch.setattr(init_mod.typer, "prompt", lambda *_args, **_kwargs: next(prompts))

    from joan.shell.forgejo_client import ForgejoError

    class FakeForgejoClient:
        def __init__(self, _url):
            pass

        def create_user(self, **_kwargs):
            raise ForgejoError("user already exists")

        def create_token(self, **_kwargs):
            return "token-abc"

    monkeypatch.setattr(init_mod, "ForgejoClient", FakeForgejoClient)
    monkeypatch.setattr(init_mod, "read_global_config", lambda: None)
    monkeypatch.setattr(init_mod, "write_global_config", lambda _cfg: Path.home() / ".joan" / "config.toml")
    monkeypatch.setattr(init_mod, "write_repo_config", lambda _cfg, _cwd: Path(".joan/config.toml"))

    result = runner.invoke(init_mod.app, [])

    assert result.exit_code == 0, result.output
    assert "Wrote config" in result.output


def test_init_command_skips_global_setup_when_global_config_exists(monkeypatch) -> None:
    """When ~/.joan/config.toml already exists, global setup (Forgejo prompts) is skipped."""
    from joan.core.models import GlobalConfig, RemotesConfig
    runner = CliRunner()

    existing_global = GlobalConfig(
        url="http://forgejo.local",
        token="existing-token",
        owner="joan",
        human_user="sam",
        remotes=RemotesConfig(),
    )

    # Only the repo prompt should be issued
    prompts = iter(["other-project"])
    monkeypatch.setattr(init_mod.typer, "prompt", lambda *_args, **_kwargs: next(prompts))
    monkeypatch.setattr(init_mod, "read_global_config", lambda: existing_global)
    monkeypatch.setattr(init_mod, "write_repo_config", lambda _cfg, _cwd: Path(".joan/config.toml"))

    result = runner.invoke(init_mod.app, [])

    assert result.exit_code == 0, result.output
    assert "Using existing global config" in result.output
    assert "Wrote config" in result.output


def test_branch_create_with_generated_name(monkeypatch, tmp_path) -> None:
    runner = CliRunner()
    calls: list[list[str]] = []

    monkeypatch.setattr(branch_mod, "load_config_or_exit", make_config)
    monkeypatch.setattr(git_mod, "_next_review_number", lambda _base: 1)
    monkeypatch.chdir(tmp_path)

    def fake_run_git(args):
        calls.append(args)
        if args == ["rev-parse", "--abbrev-ref", "HEAD"]:
            return "feature/cache"
        if args == ["rev-parse", "HEAD"]:
            return "abc123"
        if args == ["merge-base", "origin/main", "HEAD"]:
            return "base000"
        return ""

    monkeypatch.setattr(branch_mod, "run_git", fake_run_git)

    result = runner.invoke(branch_mod.app, ["create"])

    assert result.exit_code == 0, result.output
    assert calls[0] == ["rev-parse", "--abbrev-ref", "HEAD"]
    assert calls[1] == ["rev-parse", "HEAD"]
    # merge-base to find where branch diverged from main
    assert calls[2] == ["merge-base", "origin/main", "HEAD"]
    # Push base SHA (not HEAD) as the working branch
    assert calls[3] == ["push", "joan-review", "base000:refs/heads/feature/cache"]
    assert calls[4] == ["checkout", "-b", "joan-review/feature/cache--r1"]
    assert "Created review branch: joan-review/feature/cache--r1 (base: feature/cache)" in result.output

    # Verify branch state was saved
    state = json.loads((tmp_path / ".joan" / "branch-state.json").read_text())
    assert state["branches"]["feature/cache"]["base_sha"] == "abc123"


def test_branch_push_current_branch(monkeypatch) -> None:
    runner = CliRunner()
    calls: list[list[str]] = []

    monkeypatch.setattr(branch_mod, "load_config_or_exit", make_config)
    monkeypatch.setattr(branch_mod, "run_git", lambda args: calls.append(args) or "codex/existing-1" if args == ["rev-parse", "--abbrev-ref", "HEAD"] else calls.append(args) or "")

    result = runner.invoke(branch_mod.app, ["push"])

    assert result.exit_code == 0, result.output
    assert ["rev-parse", "--abbrev-ref", "HEAD"] in calls
    assert ["push", "-u", "joan-review", "codex/existing-1"] in calls
    assert "Pushed branch" in result.output


def test_remote_add_adds_remote_and_pushes(monkeypatch) -> None:
    runner = CliRunner()
    calls: list[list[str]] = []

    monkeypatch.setattr(remote_mod, "load_config_or_exit", make_config)

    class FakeClient:
        def __init__(self):
            self.collaborator_calls: list[tuple[str, str, str, str]] = []

        def create_repo(self, **_kwargs):
            return {"clone_url": "http://forgejo.local/joan/joan.git"}

        def add_repo_collaborator(self, owner, repo, username, permission):
            self.collaborator_calls.append((owner, repo, username, permission))

    import joan.cli._common as common_mod

    client = FakeClient()
    monkeypatch.setattr(common_mod, "forgejo_client", lambda _cfg: client)

    def fake_run_git(args):
        calls.append(args)
        if args == ["remote"]:
            return "origin\n"
        if args == ["rev-parse", "--abbrev-ref", "HEAD"]:
            return "codex/new-1"
        return ""

    monkeypatch.setattr(remote_mod, "run_git", fake_run_git)

    result = runner.invoke(remote_mod.app, [])
    assert result.exit_code == 0
    assert client.collaborator_calls == [("joan", "joan", "sam", "admin")]
    assert ["remote", "add", "joan-review", "http://joan:tok@forgejo.local/joan/joan.git"] in calls
    assert ["push", "-u", "joan-review", "codex/new-1"] in calls


def test_remote_add_updates_existing_remote(monkeypatch) -> None:
    runner = CliRunner()
    calls: list[list[str]] = []

    monkeypatch.setattr(remote_mod, "load_config_or_exit", make_config)

    class FakeClient:
        def __init__(self):
            self.collaborator_calls: list[tuple[str, str, str, str]] = []

        def create_repo(self, **_kwargs):
            return {}

        def add_repo_collaborator(self, owner, repo, username, permission):
            self.collaborator_calls.append((owner, repo, username, permission))

    import joan.cli._common as common_mod

    client = FakeClient()
    monkeypatch.setattr(common_mod, "forgejo_client", lambda _cfg: client)

    def fake_run_git(args):
        calls.append(args)
        if args == ["remote"]:
            return "origin\njoan-review\n"
        if args == ["rev-parse", "--abbrev-ref", "HEAD"]:
            return "feature"
        return ""

    monkeypatch.setattr(remote_mod, "run_git", fake_run_git)

    result = runner.invoke(remote_mod.app, [])
    assert result.exit_code == 0
    assert client.collaborator_calls == [("joan", "joan", "sam", "admin")]
    assert [
        "remote",
        "set-url",
        "joan-review",
        "http://joan:tok@forgejo.local/joan/joan.git",
    ] in calls


def test_branch_state_round_trip(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    assert load_branch_state("feature/foo") is None

    save_branch_state("feature/foo", "abc123")
    assert load_branch_state("feature/foo") == "abc123"

    save_branch_state("feature/foo", "def456")
    assert load_branch_state("feature/foo") == "def456"

    save_branch_state("feature/bar", "ghi789")
    assert load_branch_state("feature/foo") == "def456"
    assert load_branch_state("feature/bar") == "ghi789"


def test_branch_create_uses_stored_base_sha(monkeypatch, tmp_path) -> None:
    """Second review round: stored base SHA is used instead of computing merge-base."""
    runner = CliRunner()
    calls: list[list[str]] = []

    monkeypatch.setattr(branch_mod, "load_config_or_exit", make_config)
    monkeypatch.setattr(git_mod, "_next_review_number", lambda _base: 2)
    monkeypatch.chdir(tmp_path)

    # Pre-populate stored state from a previous review round.
    save_branch_state("feature/cache", "prev_head_sha")

    def fake_run_git(args):
        calls.append(args)
        if args == ["rev-parse", "--abbrev-ref", "HEAD"]:
            return "feature/cache"
        if args == ["rev-parse", "HEAD"]:
            return "new_head_sha"
        return ""

    monkeypatch.setattr(branch_mod, "run_git", fake_run_git)

    result = runner.invoke(branch_mod.app, ["create"])

    assert result.exit_code == 0, result.output
    # Should push the stored base SHA, not HEAD
    assert ["push", "joan-review", "prev_head_sha:refs/heads/feature/cache"] in calls
    # Should NOT call ls-remote or merge-base since we have stored state
    ls_remote_calls = [c for c in calls if c[:2] == ["ls-remote", "joan-review"]]
    assert len(ls_remote_calls) == 0

    # Verify branch state was updated to new HEAD
    state = json.loads((tmp_path / ".joan" / "branch-state.json").read_text())
    assert state["branches"]["feature/cache"]["base_sha"] == "new_head_sha"
