from __future__ import annotations

import argparse
import filecmp
import shutil
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPO_ROOT / "skills"
TARGET_ROOTS = (
    REPO_ROOT / ".agents" / "skills",
    REPO_ROOT / "src" / "joan" / "data" / "codex-skills",
)


def _skill_dirs(base: Path) -> dict[str, Path]:
    if not base.exists():
        return {}
    return {path.name: path for path in sorted(base.iterdir()) if path.is_dir()}


def _compare_dirs(source: Path, target: Path) -> bool:
    if not target.exists() or not target.is_dir():
        return False

    comparison = filecmp.dircmp(source, target)
    if comparison.left_only or comparison.right_only or comparison.funny_files:
        return False

    _, mismatches, errors = filecmp.cmpfiles(
        source,
        target,
        comparison.common_files,
        shallow=False,
    )
    if mismatches or errors:
        return False

    return all(
        _compare_dirs(source / common_dir, target / common_dir)
        for common_dir in comparison.common_dirs
    )


def sync_skills(
    source_root: Path = SOURCE_ROOT,
    target_roots: tuple[Path, ...] = TARGET_ROOTS,
    *,
    check: bool = False,
) -> list[str]:
    issues: list[str] = []
    source_skills = _skill_dirs(source_root)

    if not source_skills:
        return [f"No skills found in {source_root}."]

    expected_names = set(source_skills)

    for target_root in target_roots:
        target_skills = _skill_dirs(target_root)
        target_names = set(target_skills)

        stale_names = sorted(target_names - expected_names)
        missing_names = sorted(expected_names - target_names)

        if check:
            for stale_name in stale_names:
                issues.append(f"{target_root}: unexpected skill directory {stale_name}")
            for missing_name in missing_names:
                issues.append(f"{target_root}: missing skill directory {missing_name}")
        else:
            target_root.mkdir(parents=True, exist_ok=True)
            for stale_name in stale_names:
                shutil.rmtree(target_root / stale_name)

        for skill_name, source_dir in source_skills.items():
            target_dir = target_root / skill_name
            if check:
                if not _compare_dirs(source_dir, target_dir):
                    issues.append(f"{target_dir} is out of sync with {source_dir}")
                continue

            if target_dir.exists():
                shutil.rmtree(target_dir)
            shutil.copytree(source_dir, target_dir)

    return issues


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Mirror canonical Joan skills into Codex skill locations.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify mirror trees are up to date without changing files.",
    )
    args = parser.parse_args()

    issues = sync_skills(check=args.check)
    if issues:
        label = "out of sync" if args.check else "failed"
        print(f"Skill sync {label}:", file=sys.stderr)
        for issue in issues:
            print(f"- {issue}", file=sys.stderr)
        return 1

    if args.check:
        print("Skill mirrors are in sync.")
    else:
        print("Synced skills into repo-local and packaged Codex mirrors.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
