from __future__ import annotations

from datetime import UTC, datetime

import joan.core.git as git_mod


def test_git_arg_builders() -> None:
    assert git_mod.create_branch_args("feat") == ["checkout", "-b", "feat"]
    assert git_mod.push_branch_args("origin", "feat", set_upstream=True) == ["push", "-u", "origin", "feat"]
    assert git_mod.push_branch_args("origin", "feat", set_upstream=False) == ["push", "origin", "feat"]
    assert git_mod.push_refspec_args("joan-review", "refs/heads/feat", "refs/heads/joan/feat") == [
        "push",
        "joan-review",
        "refs/heads/feat:refs/heads/joan/feat",
    ]
    assert git_mod.current_branch_args() == ["rev-parse", "--abbrev-ref", "HEAD"]
    assert git_mod.worktree_add_args("/tmp/wt", branch="feat") == ["worktree", "add", "-b", "feat", "/tmp/wt"]
    assert git_mod.worktree_add_args("/tmp/wt") == ["worktree", "add", "/tmp/wt"]
    assert git_mod.worktree_remove_args("/tmp/wt") == ["worktree", "remove", "/tmp/wt"]
    assert git_mod.remote_add_args("r", "u") == ["remote", "add", "r", "u"]
    assert git_mod.remote_set_url_args("r", "u") == ["remote", "set-url", "r", "u"]
    assert git_mod.list_remotes_args() == ["remote"]


def test_infer_branch_name_with_hint(monkeypatch) -> None:
    class FakeDatetime:
        @classmethod
        def now(cls, _tz):
            return datetime(2026, 2, 27, 1, 2, 3, tzinfo=UTC)

    monkeypatch.setattr(git_mod, "datetime", FakeDatetime)

    assert git_mod.infer_branch_name("Feature Name_here") == "codex/feature-name-here-20260227-010203"


def test_infer_branch_name_without_hint(monkeypatch) -> None:
    class FakeDatetime:
        @classmethod
        def now(cls, _tz):
            return datetime(2026, 2, 27, 1, 2, 3, tzinfo=UTC)

    monkeypatch.setattr(git_mod, "datetime", FakeDatetime)

    assert git_mod.infer_branch_name(None) == "codex/work-20260227-010203"
