from __future__ import annotations

from pathlib import Path

import joan.cli.pr as pr_mod
from typer.testing import CliRunner


def test_pr_narrative_build_writes_markdown(monkeypatch, tmp_path: Path) -> None:
    runner = CliRunner()

    calls: list[list[str]] = []

    def fake_run_git(args):
        calls.append(args)
        if args[:2] == ["log", "--format=%H%x1f%s%x1f%b%x1e"]:
            return "abc123\x1fRefactor PR command parsing\x1f\x1e"
        if args[:2] == ["diff", "--numstat"]:
            return "12\t4\tsrc/joan/cli/pr.py"
        raise AssertionError(args)

    monkeypatch.setattr(pr_mod, "run_git", fake_run_git)

    tests_file = tmp_path / "tests.json"
    tests_file.write_text(
        '[{"cmd":"uv run pytest -q","exit_code":0,"summary":"12 passed"}]',
        encoding="utf-8",
    )
    output_file = tmp_path / "body.md"

    result = runner.invoke(
        pr_mod.app,
        [
            "narrative",
            "build",
            "--from",
            "origin/main",
            "--to",
            "HEAD",
            "--tests-json",
            str(tests_file),
            "--write",
            str(output_file),
            "--no-stdout",
        ],
    )

    assert result.exit_code == 0, result.output
    assert output_file.exists()
    body = output_file.read_text(encoding="utf-8")
    assert "## What" in body
    assert "## Why" in body
    assert "## How" in body
    assert "## Tests" in body
    assert "## Risks / Follow-ups" in body
    assert "PASS `uv run pytest -q`: 12 passed" in body
    assert ["log", "--format=%H%x1f%s%x1f%b%x1e", "origin/main..HEAD"] in calls
    assert ["diff", "--numstat", "origin/main..HEAD"] in calls


def test_pr_narrative_build_with_issue(monkeypatch, sample_config) -> None:
    runner = CliRunner()

    monkeypatch.setattr(pr_mod, "load_config_or_exit", lambda: sample_config)

    class FakeClient:
        def get_issue(self, owner, repo, index):
            assert owner == "sam"
            assert repo == "joan"
            assert index == 11
            return {"number": 11, "title": "Tighten PR narrative", "body": "..."}

    monkeypatch.setattr(pr_mod, "forgejo_client", lambda _cfg: FakeClient())

    def fake_run_git(args):
        if args[:2] == ["log", "--format=%H%x1f%s%x1f%b%x1e"]:
            return ""
        if args[:2] == ["diff", "--numstat"]:
            return ""
        raise AssertionError(args)

    monkeypatch.setattr(pr_mod, "run_git", fake_run_git)

    result = runner.invoke(pr_mod.app, ["narrative", "build", "--issue", "11"])

    assert result.exit_code == 0, result.output
    assert "Addresses issue #11: Tighten PR narrative" in result.output
