from __future__ import annotations

import subprocess
from types import SimpleNamespace

import pytest

from joan.shell.git_runner import GitError, run_git


def test_run_git_success(monkeypatch) -> None:
    def fake_run(*_args, **_kwargs):
        return SimpleNamespace(returncode=0, stdout="main\n", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    assert run_git(["status"]) == "main"


def test_run_git_failure_uses_stderr(monkeypatch) -> None:
    def fake_run(*_args, **_kwargs):
        return SimpleNamespace(returncode=1, stdout="", stderr="boom")

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(GitError, match="boom"):
        run_git(["status"])


def test_run_git_failure_uses_stdout_then_unknown(monkeypatch) -> None:
    def fake_run_stdout(*_args, **_kwargs):
        return SimpleNamespace(returncode=1, stdout="oops", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run_stdout)
    with pytest.raises(GitError, match="oops"):
        run_git(["status"])

    def fake_run_unknown(*_args, **_kwargs):
        return SimpleNamespace(returncode=1, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run_unknown)
    with pytest.raises(GitError, match="unknown git error"):
        run_git(["status"])
