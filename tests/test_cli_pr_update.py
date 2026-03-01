from __future__ import annotations

import joan.cli.pr as pr_mod
from joan.core.models import Config, ForgejoConfig, RemotesConfig
from typer.testing import CliRunner


def make_config() -> Config:
    return Config(
        forgejo=ForgejoConfig(url="http://forgejo.local", token="tok", owner="sam", repo="joan"),
        remotes=RemotesConfig(review="joan-review", upstream="origin"),
    )


def test_pr_update_patches_description(monkeypatch) -> None:
    runner = CliRunner()
    config = make_config()
    patched: list = []

    monkeypatch.setattr(pr_mod, "load_config_or_exit", lambda: config)

    class FakePR:
        number = 3

    monkeypatch.setattr(pr_mod, "current_pr_or_exit", lambda cfg: FakePR())

    class FakeClient:
        def update_pr(self, owner, repo, index, body):
            patched.append({"owner": owner, "repo": repo, "index": index, "body": body})
            return {"number": index}

    monkeypatch.setattr(pr_mod, "forgejo_client", lambda cfg: FakeClient())

    result = runner.invoke(pr_mod.app, ["update", "--body", "New description here."])

    assert result.exit_code == 0, result.output
    assert "Updated PR #3 description" in result.output
    assert patched == [{"owner": "sam", "repo": "joan", "index": 3, "body": "New description here."}]
