from __future__ import annotations

import pytest
import typer

import joan.cli._common as common
from joan.core.models import PullRequest


def test_load_config_or_exit_missing(monkeypatch) -> None:
    def raise_missing(_cwd):
        raise FileNotFoundError("no config")

    monkeypatch.setattr(common, "read_config", raise_missing)

    with pytest.raises(typer.Exit) as exc:
        common.load_config_or_exit()
    assert exc.value.exit_code == 2


def test_load_config_or_exit_generic_error(monkeypatch) -> None:
    def raise_generic(_cwd):
        raise RuntimeError("bad")

    monkeypatch.setattr(common, "read_config", raise_generic)

    with pytest.raises(typer.Exit) as exc:
        common.load_config_or_exit()
    assert exc.value.exit_code == 2


def test_current_branch_success_and_failure(monkeypatch) -> None:
    monkeypatch.setattr(common, "run_git", lambda _args: "main")
    assert common.current_branch() == "main"

    def raise_git(_args):
        raise RuntimeError("broken")

    monkeypatch.setattr(common, "run_git", raise_git)
    with pytest.raises(typer.Exit) as exc:
        common.current_branch()
    assert exc.value.exit_code == 2


def test_current_pr_or_exit_no_pull(monkeypatch, sample_config) -> None:
    monkeypatch.setattr(common, "current_branch", lambda: "feature")

    class FakeClient:
        def list_pulls(self, *_args, **_kwargs):
            return []

    monkeypatch.setattr(common, "forgejo_client", lambda _cfg: FakeClient())

    with pytest.raises(typer.Exit) as exc:
        common.current_pr_or_exit(sample_config)
    assert exc.value.exit_code == 1


def test_current_pr_or_exit_returns_pull(monkeypatch, sample_config) -> None:
    monkeypatch.setattr(common, "current_branch", lambda: "feature")

    class FakeClient:
        def list_pulls(self, *_args, **_kwargs):
            return [{"number": 5, "head": {"ref": "feature"}, "base": {"ref": "main"}}]

    monkeypatch.setattr(common, "forgejo_client", lambda _cfg: FakeClient())

    pr = common.current_pr_or_exit(sample_config)
    assert isinstance(pr, PullRequest)
    assert pr.number == 5


def test_print_json(capsys) -> None:
    common.print_json({"x": 1})
    out = capsys.readouterr().out
    assert '"x": 1' in out


def test_forgejo_client_builder(sample_config) -> None:
    client = common.forgejo_client(sample_config)
    assert client.base_url == sample_config.forgejo.url
    assert client.token == sample_config.forgejo.token
