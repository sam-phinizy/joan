from __future__ import annotations

from typer.testing import CliRunner

import joan
import joan.cli.doctor as doctor_mod
from joan.core.models import Config, ForgejoConfig, RemotesConfig
from joan.shell.forgejo_client import ForgejoError


def make_config() -> Config:
    return Config(
        forgejo=ForgejoConfig(url="http://forgejo.local", token="tok", owner="joan", repo="demo"),
        remotes=RemotesConfig(review="joan-review", upstream="origin"),
    )


def make_config_with_human_user() -> Config:
    return Config(
        forgejo=ForgejoConfig(
            url="http://forgejo.local",
            token="tok",
            owner="joan",
            repo="demo",
            human_user="sam",
        ),
        remotes=RemotesConfig(review="joan-review", upstream="origin"),
    )


def test_doctor_happy_path_with_user_check(monkeypatch) -> None:
    runner = CliRunner()

    monkeypatch.setattr(doctor_mod, "read_config", lambda _cwd: make_config())

    def fake_run_git(args):
        if args == ["rev-parse", "--is-inside-work-tree"]:
            return "true"
        if args == ["remote"]:
            return "origin\njoan-review\n"
        if args == ["remote", "get-url", "joan-review"]:
            return "http://joan:tok@forgejo.local/joan/demo.git"
        raise AssertionError(args)

    monkeypatch.setattr(doctor_mod, "run_git", fake_run_git)

    class FakeForgejoClient:
        def __init__(self, base_url, token):
            assert base_url == "http://forgejo.local"
            assert token == "tok"

        def get_current_user(self):
            return {"login": "joan"}

        def get_repo(self, owner, repo):
            assert (owner, repo) == ("joan", "demo")
            return {"permissions": {"admin": True}}

        def get_repo_collaborator_permission(self, owner, repo, username):
            assert (owner, repo, username) == ("joan", "demo", "sam")
            return {"permission": "admin"}

    monkeypatch.setattr(doctor_mod, "ForgejoClient", FakeForgejoClient)

    result = runner.invoke(doctor_mod.app, ["--user", "sam"])

    assert result.exit_code == 0, result.output
    assert "Forgejo token authenticated as 'joan'" in result.output
    assert "Forgejo user 'sam' has admin access" in result.output
    assert "Summary: 0 failed, 0 warning(s)." in result.output


def test_doctor_fails_without_config(monkeypatch) -> None:
    runner = CliRunner()

    monkeypatch.setattr(doctor_mod, "read_config", lambda _cwd: (_ for _ in ()).throw(FileNotFoundError("no config")))
    monkeypatch.setattr(doctor_mod, "run_git", lambda args: "true" if args == ["rev-parse", "--is-inside-work-tree"] else "")

    result = runner.invoke(doctor_mod.app, [])

    assert result.exit_code == 1
    assert "Missing .joan/config.toml" in result.output


def test_doctor_warns_when_review_remote_missing(monkeypatch) -> None:
    runner = CliRunner()

    monkeypatch.setattr(doctor_mod, "read_config", lambda _cwd: make_config())

    def fake_run_git(args):
        if args == ["rev-parse", "--is-inside-work-tree"]:
            return "true"
        if args == ["remote"]:
            return "origin\n"
        raise AssertionError(args)

    monkeypatch.setattr(doctor_mod, "run_git", fake_run_git)

    class FakeForgejoClient:
        def __init__(self, _base_url, _token):
            pass

        def get_current_user(self):
            return {"login": "joan"}

        def get_repo(self, owner, repo):
            assert (owner, repo) == ("joan", "demo")
            return {"permissions": {"admin": True}}

    monkeypatch.setattr(doctor_mod, "ForgejoClient", FakeForgejoClient)

    result = runner.invoke(doctor_mod.app, [])

    assert result.exit_code == 0, result.output
    assert "Git remote 'joan-review' is missing" in result.output
    assert "Summary: 0 failed, 1 warning(s)." in result.output


def test_doctor_fails_when_user_lacks_admin_access(monkeypatch) -> None:
    runner = CliRunner()

    monkeypatch.setattr(doctor_mod, "read_config", lambda _cwd: make_config())

    def fake_run_git(args):
        if args == ["rev-parse", "--is-inside-work-tree"]:
            return "true"
        if args == ["remote"]:
            return "joan-review\n"
        if args == ["remote", "get-url", "joan-review"]:
            return "http://joan:tok@forgejo.local/joan/demo.git"
        raise AssertionError(args)

    monkeypatch.setattr(doctor_mod, "run_git", fake_run_git)

    class FakeForgejoClient:
        def __init__(self, _base_url, _token):
            pass

        def get_current_user(self):
            return {"login": "joan"}

        def get_repo(self, _owner, _repo):
            return {"permissions": {"admin": True}}

        def get_repo_collaborator_permission(self, _owner, _repo, _username):
            return {"permission": "write"}

    monkeypatch.setattr(doctor_mod, "ForgejoClient", FakeForgejoClient)

    result = runner.invoke(doctor_mod.app, ["--user", "sam"])

    assert result.exit_code == 1, result.output
    assert "has 'write' access, not admin" in result.output


def test_doctor_reports_missing_collaborator(monkeypatch) -> None:
    runner = CliRunner()

    monkeypatch.setattr(doctor_mod, "read_config", lambda _cwd: make_config())

    def fake_run_git(args):
        if args == ["rev-parse", "--is-inside-work-tree"]:
            return "true"
        if args == ["remote"]:
            return "joan-review\n"
        if args == ["remote", "get-url", "joan-review"]:
            return "http://joan:tok@forgejo.local/joan/demo.git"
        raise AssertionError(args)

    monkeypatch.setattr(doctor_mod, "run_git", fake_run_git)

    class FakeForgejoClient:
        def __init__(self, _base_url, _token):
            pass

        def get_current_user(self):
            return {"login": "joan"}

        def get_repo(self, _owner, _repo):
            return {"permissions": {"admin": True}}

        def get_repo_collaborator_permission(self, _owner, _repo, _username):
            raise ForgejoError("Forgejo API 404: not found")

    monkeypatch.setattr(doctor_mod, "ForgejoClient", FakeForgejoClient)

    result = runner.invoke(doctor_mod.app, ["--user", "sam"])

    assert result.exit_code == 1, result.output
    assert "is not a collaborator" in result.output


def test_doctor_uses_configured_human_user_by_default(monkeypatch) -> None:
    runner = CliRunner()

    monkeypatch.setattr(doctor_mod, "read_config", lambda _cwd: make_config_with_human_user())

    def fake_run_git(args):
        if args == ["rev-parse", "--is-inside-work-tree"]:
            return "true"
        if args == ["remote"]:
            return "joan-review\n"
        if args == ["remote", "get-url", "joan-review"]:
            return "http://joan:tok@forgejo.local/joan/demo.git"
        raise AssertionError(args)

    monkeypatch.setattr(doctor_mod, "run_git", fake_run_git)

    class FakeForgejoClient:
        def __init__(self, _base_url, _token):
            pass

        def get_current_user(self):
            return {"login": "joan"}

        def get_repo(self, _owner, _repo):
            return {"permissions": {"admin": True}}

        def get_repo_collaborator_permission(self, owner, repo, username):
            assert (owner, repo, username) == ("joan", "demo", "sam")
            return {"permission": "admin"}

    monkeypatch.setattr(doctor_mod, "ForgejoClient", FakeForgejoClient)

    result = runner.invoke(doctor_mod.app, [])

    assert result.exit_code == 0, result.output
    assert "Forgejo user 'sam' has admin access" in result.output


def test_root_cli_has_doctor_command() -> None:
    runner = CliRunner()
    result = runner.invoke(joan.app, ["--help"])
    assert result.exit_code == 0
    assert "doctor" in result.output
