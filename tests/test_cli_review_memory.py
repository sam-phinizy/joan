from __future__ import annotations

import json
from pathlib import Path

import joan.cli.review_memory as review_memory_mod
from joan.core.models import PullRequest
from typer.testing import CliRunner


def test_review_memory_ingest_writes_rules(monkeypatch, sample_config, tmp_path: Path) -> None:
    runner = CliRunner()

    monkeypatch.chdir(tmp_path)
    (tmp_path / ".joan").mkdir()

    monkeypatch.setattr(review_memory_mod, "load_config_or_exit", lambda: sample_config)
    monkeypatch.setattr(
        review_memory_mod,
        "current_pr_or_exit",
        lambda _cfg, pr_number=None: PullRequest(
            number=pr_number or 7,
            title="Demo",
            url="http://forgejo.local/sam/joan/pulls/7",
            state="open",
            head_ref="feature/x",
            base_ref="main",
        ),
    )

    class FakeClient:
        def get_reviews(self, *_args, **_kwargs):
            return [{"id": 1, "state": "REQUESTED_CHANGES", "body": "Please add a regression test", "user": {"login": "r"}}]

        def get_comments(self, *_args, **_kwargs):
            return [
                {
                    "id": 9,
                    "body": "Please improve typing here",
                    "path": "src/joan/cli/pr.py",
                    "line": 10,
                    "resolved": False,
                    "user": {"login": "r"},
                }
            ]

    monkeypatch.setattr(review_memory_mod, "forgejo_client", lambda _cfg: FakeClient())

    result = runner.invoke(review_memory_mod.app, ["ingest"])
    assert result.exit_code == 0, result.output

    rules_path = tmp_path / ".joan" / "review-memory" / "rules.json"
    assert rules_path.exists()
    payload = json.loads(rules_path.read_text(encoding="utf-8"))
    ids = {rule["id"] for rule in payload["rules"]}
    assert "add-regression-test" in ids
    assert "improve-types" in ids


def test_review_memory_list_and_suggest(monkeypatch, tmp_path: Path) -> None:
    runner = CliRunner()

    monkeypatch.chdir(tmp_path)
    store_dir = tmp_path / ".joan" / "review-memory"
    store_dir.mkdir(parents=True)
    (store_dir / "rules.json").write_text(
        json.dumps(
            {
                "version": 1,
                "rules": [
                    {
                        "id": "add-regression-test",
                        "pattern": "Please add a regression test",
                        "scope": {"paths": ["src/joan/cli/pr.py"]},
                        "action": "suggest_test_case",
                        "count": 3,
                        "last_seen_at": "2026-03-12T00:00:00Z",
                        "confidence": 0.8,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    list_result = runner.invoke(review_memory_mod.app, ["list", "--path", "src/joan/cli/pr.py"])
    assert list_result.exit_code == 0, list_result.output
    listed = json.loads(list_result.output)
    assert len(listed["rules"]) == 1

    monkeypatch.setattr(review_memory_mod, "run_git", lambda _args: "src/joan/cli/pr.py\n")
    suggest_result = runner.invoke(review_memory_mod.app, ["suggest", "--paths-from-git", "--format", "checklist"])
    assert suggest_result.exit_code == 0, suggest_result.output
    assert "Review preflight checklist:" in suggest_result.output
    assert "Please add a regression test" in suggest_result.output
