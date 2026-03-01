from __future__ import annotations

import importlib.util
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CLAUDE_SKILLS = REPO_ROOT / "skills"
REPO_CODEX_SKILLS = REPO_ROOT / ".agents" / "skills"
PACKAGED_CODEX_SKILLS = REPO_ROOT / "src" / "joan" / "data" / "codex-skills"
SYNC_SCRIPT = REPO_ROOT / "scripts" / "sync_skills.py"


def _load_sync_module():
    spec = importlib.util.spec_from_file_location("sync_skills", SYNC_SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _skill_map(base: Path) -> dict[str, Path]:
    return {path.name: path / "SKILL.md" for path in base.iterdir() if path.is_dir()}


def test_skill_trees_are_in_sync() -> None:
    claude_skills = _skill_map(CLAUDE_SKILLS)
    repo_codex_skills = _skill_map(REPO_CODEX_SKILLS)
    packaged_codex_skills = _skill_map(PACKAGED_CODEX_SKILLS)

    assert claude_skills.keys() == repo_codex_skills.keys() == packaged_codex_skills.keys()

    for skill_name in sorted(claude_skills):
        claude_body = claude_skills[skill_name].read_text()
        repo_codex_body = repo_codex_skills[skill_name].read_text()
        packaged_codex_body = packaged_codex_skills[skill_name].read_text()

        assert claude_body == repo_codex_body
        assert claude_body == packaged_codex_body


def test_sync_script_check_passes_for_repo() -> None:
    sync_mod = _load_sync_module()

    assert sync_mod.sync_skills(check=True) == []


def test_sync_script_populates_targets(tmp_path: Path) -> None:
    sync_mod = _load_sync_module()

    source = tmp_path / "skills"
    repo_codex = tmp_path / ".agents" / "skills"
    packaged_codex = tmp_path / "src" / "joan" / "data" / "codex-skills"

    skill_dir = source / "demo-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nname: demo\ndescription: test\n---\n")
    (skill_dir / "notes.txt").write_text("copied")

    stale = repo_codex / "stale-skill"
    stale.mkdir(parents=True)
    (stale / "SKILL.md").write_text("old")

    issues = sync_mod.sync_skills(
        source_root=source,
        target_roots=(repo_codex, packaged_codex),
    )

    assert issues == []
    assert not stale.exists()
    assert (repo_codex / "demo-skill" / "SKILL.md").exists()
    assert (repo_codex / "demo-skill" / "notes.txt").read_text() == "copied"
    assert (packaged_codex / "demo-skill" / "SKILL.md").exists()
