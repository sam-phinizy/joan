from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

import joan.cli.init as init_mod
import joan.cli.remote as remote_mod
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
    assert len(written_global) == 1
    assert len(written_repo) == 1
    assert written_repo[0].repo == "my-project"


def test_init_command_skips_global_setup_when_global_config_exists(monkeypatch) -> None:
    from joan.core.models import GlobalConfig

    runner = CliRunner()
    existing_global = GlobalConfig(
        url="http://forgejo.local",
        token="existing-token",
        owner="joan",
        human_user="sam",
        remotes=RemotesConfig(),
    )

    prompts = iter(["other-project"])
    monkeypatch.setattr(init_mod.typer, "prompt", lambda *_args, **_kwargs: next(prompts))
    monkeypatch.setattr(init_mod, "read_global_config", lambda: existing_global)
    monkeypatch.setattr(init_mod, "write_repo_config", lambda _cfg, _cwd: Path(".joan/config.toml"))

    result = runner.invoke(init_mod.app, [])

    assert result.exit_code == 0, result.output
    assert "Using existing global config" in result.output


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
        def create_repo(self, **_kwargs):
            return {}

        def add_repo_collaborator(self, *_args, **_kwargs):
            return None

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
        "http://joan:tok@forgejo.local/joan/joan.git",
    ] in calls
