from __future__ import annotations

from pathlib import Path

from joan.shell.config_io import config_path, read_config
import joan.shell.repo_state as repo_state_mod


def test_config_path_prefers_git_common_dir(monkeypatch, tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    common_dir = tmp_path / "common"
    repo_root.mkdir()
    common_dir.mkdir()

    monkeypatch.setattr(
        repo_state_mod,
        "run_git",
        lambda args, cwd=None: str(common_dir) if args == ["rev-parse", "--git-common-dir"] else "",
    )

    assert config_path(repo_root) == common_dir / "joan" / "config.toml"


def test_repo_state_migrates_legacy_tree_to_shared(monkeypatch, tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    common_dir = tmp_path / "common"
    legacy_file = repo_root / ".joan" / "review-memory" / "rules.json"
    legacy_file.parent.mkdir(parents=True)
    legacy_file.write_text('{"version":1,"rules":[]}', encoding="utf-8")
    common_dir.mkdir(parents=True)

    monkeypatch.setattr(
        repo_state_mod,
        "run_git",
        lambda args, cwd=None: str(common_dir) if args == ["rev-parse", "--git-common-dir"] else "",
    )

    shared_dir = repo_state_mod.repo_state_dir(repo_root, for_write=True)

    assert shared_dir == common_dir / "joan"
    assert (shared_dir / "review-memory" / "rules.json").exists()
    assert (shared_dir / ".migrated_from_legacy").exists()


def test_read_config_uses_legacy_fallback_when_shared_empty(monkeypatch, tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    common_dir = tmp_path / "common"
    (repo_root / ".joan").mkdir(parents=True)
    common_dir.mkdir(parents=True)

    (repo_root / ".joan" / "config.toml").write_text(
        """
[forgejo]
url = "http://forgejo.local"
token = "tok"
owner = "sam"
repo = "joan"
""".strip(),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        repo_state_mod,
        "run_git",
        lambda args, cwd=None: str(common_dir) if args == ["rev-parse", "--git-common-dir"] else "",
    )

    loaded = read_config(repo_root)
    assert loaded.forgejo.owner == "sam"
    assert loaded.forgejo.repo == "joan"
