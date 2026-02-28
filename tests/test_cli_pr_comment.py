from __future__ import annotations

import joan.cli.pr as pr_mod
from joan.core.models import Config, ForgejoConfig, RemotesConfig
from typer.testing import CliRunner


def make_config() -> Config:
    return Config(
        forgejo=ForgejoConfig(url="http://forgejo.local", token="tok", owner="sam", repo="joan"),
        remotes=RemotesConfig(review="joan-review", upstream="origin"),
    )


def test_pr_comment_add_uses_agent_client(monkeypatch) -> None:
    runner = CliRunner()
    config = make_config()
    posted: list = []

    monkeypatch.setattr(pr_mod, "load_config_or_exit", lambda: config)

    class FakeClient:
        def create_inline_pr_comment(self, owner, repo, index, path, line, body):
            posted.append(
                {
                    "owner": owner,
                    "repo": repo,
                    "index": index,
                    "path": path,
                    "line": line,
                    "body": body,
                }
            )
            return {"id": 8}

    monkeypatch.setattr(pr_mod, "forgejo_client_for_agent_or_exit", lambda _cfg, _agent: FakeClient())

    result = runner.invoke(
        pr_mod.app,
        [
            "comment",
            "add",
            "--agent",
            "phil",
            "--owner",
            "sam",
            "--repo",
            "joan",
            "--pr",
            "7",
            "--path",
            "src/foo.py",
            "--line",
            "42",
            "--body",
            "This breaks.",
        ],
    )

    assert result.exit_code == 0, result.output
    assert posted == [
        {
            "owner": "sam",
            "repo": "joan",
            "index": 7,
            "path": "src/foo.py",
            "line": 42,
            "body": "This breaks.",
        }
    ]
