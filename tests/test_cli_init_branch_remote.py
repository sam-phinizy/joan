from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

import joan.cli.branch as branch_mod
import joan.cli.init as init_mod
import joan.cli.remote as remote_mod
from joan.core.models import Config, ForgejoConfig, RemotesConfig


def make_config() -> Config:
    return Config(
        forgejo=ForgejoConfig(url="http://forgejo.local", token="tok", owner="sam", repo="joan"),
        remotes=RemotesConfig(review="joan-review", upstream="origin"),
    )


def test_init_command(monkeypatch) -> None:
    runner = CliRunner()

    prompts = iter([
        "http://forgejo.local",
        "sam",
        "secret",
        "sam",
        "joan",
    ])

    monkeypatch.setattr(init_mod.typer, "prompt", lambda *_args, **_kwargs: next(prompts))

    class FakeForgejoClient:
        def __init__(self, _url):
            pass

        def create_token(self, **_kwargs):
            return "token-abc"

    monkeypatch.setattr(init_mod, "ForgejoClient", FakeForgejoClient)
    monkeypatch.setattr(init_mod, "write_config", lambda _cfg, _cwd: Path(".joan/config.toml"))

    result = runner.invoke(init_mod.app, [])

    assert result.exit_code == 0
    assert "Wrote config" in result.output
    assert "Next step" in result.output


def test_branch_create_with_generated_name(monkeypatch) -> None:
    runner = CliRunner()
    calls: list[list[str]] = []

    monkeypatch.setattr(branch_mod, "load_config_or_exit", make_config)
    monkeypatch.setattr(branch_mod, "infer_branch_name", lambda: "codex/new-1")
    monkeypatch.setattr(branch_mod, "run_git", lambda args: calls.append(args) or "")

    result = runner.invoke(branch_mod.app, [])

    assert result.exit_code == 0
    assert calls[0] == ["checkout", "-b", "codex/new-1"]
    assert calls[1] == ["push", "-u", "joan-review", "codex/new-1"]


def test_remote_add_adds_remote_and_pushes(monkeypatch) -> None:
    runner = CliRunner()
    calls: list[list[str]] = []

    monkeypatch.setattr(remote_mod, "load_config_or_exit", make_config)

    class FakeClient:
        def create_repo(self, **_kwargs):
            return {"clone_url": "http://forgejo.local/sam/joan.git"}

    import joan.cli._common as common_mod

    monkeypatch.setattr(common_mod, "forgejo_client", lambda _cfg: FakeClient())

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
    assert ["remote", "add", "joan-review", "http://forgejo.local/sam/joan.git"] in calls
    assert ["push", "-u", "joan-review", "codex/new-1"] in calls


def test_remote_add_updates_existing_remote(monkeypatch) -> None:
    runner = CliRunner()
    calls: list[list[str]] = []

    monkeypatch.setattr(remote_mod, "load_config_or_exit", make_config)

    class FakeClient:
        def create_repo(self, **_kwargs):
            return {}

    import joan.cli._common as common_mod

    monkeypatch.setattr(common_mod, "forgejo_client", lambda _cfg: FakeClient())

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
    assert [
        "remote",
        "set-url",
        "joan-review",
        "http://forgejo.local/sam/joan.git",
    ] in calls
