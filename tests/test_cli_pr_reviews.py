from __future__ import annotations

import json

import joan.cli.pr as pr_mod
from typer.testing import CliRunner


def test_pr_reviews_outputs_json(monkeypatch, sample_config, sample_pr) -> None:
    runner = CliRunner()

    class FakeClient:
        def get_reviews(self, owner, repo, index):
            assert owner == "sam"
            assert repo == "joan"
            assert index == 7  # sample_pr.number
            return [
                {
                    "id": 7,
                    "state": "REQUEST_CHANGES",
                    "body": "Please refactor the auth module",
                    "submitted_at": "2026-02-28T14:00:00Z",
                    "user": {"login": "reviewer"},
                }
            ]

    monkeypatch.setattr(pr_mod, "load_config_or_exit", lambda: sample_config)
    monkeypatch.setattr(pr_mod, "forgejo_client", lambda _cfg: FakeClient())
    monkeypatch.setattr(pr_mod, "current_pr_or_exit", lambda _cfg, **_kw: sample_pr)

    result = runner.invoke(pr_mod.app, ["reviews"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert len(payload) == 1
    assert payload[0]["id"] == 7
    assert payload[0]["body"] == "Please refactor the auth module"
    assert payload[0]["author"] == "reviewer"
    assert payload[0]["state"] == "REQUEST_CHANGES"


def test_pr_reviews_empty_list(monkeypatch, sample_config, sample_pr) -> None:
    runner = CliRunner()

    class FakeClient:
        def get_reviews(self, _owner, _repo, _index):
            return []

    monkeypatch.setattr(pr_mod, "load_config_or_exit", lambda: sample_config)
    monkeypatch.setattr(pr_mod, "forgejo_client", lambda _cfg: FakeClient())
    monkeypatch.setattr(pr_mod, "current_pr_or_exit", lambda _cfg, **_kw: sample_pr)

    result = runner.invoke(pr_mod.app, ["reviews"])
    assert result.exit_code == 0
    assert json.loads(result.output) == []
