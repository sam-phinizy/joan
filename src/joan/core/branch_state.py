from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

_STATE_FILE = ".joan/branch-state.json"


@dataclass(frozen=True)
class BranchState:
    branch_start_sha: str | None = None
    review_checkpoint_sha: str | None = None


def _state_path() -> Path:
    return Path(_STATE_FILE)


def load_branch_state(branch: str) -> BranchState:
    path = _state_path()
    if not path.exists():
        return BranchState()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return BranchState()
    branch_data = data.get("branches", {}).get(branch, {})
    legacy_base_sha = branch_data.get("base_sha")
    return BranchState(
        branch_start_sha=branch_data.get("branch_start_sha"),
        review_checkpoint_sha=branch_data.get("review_checkpoint_sha", legacy_base_sha),
    )


def _save_branch_values(
    branch: str,
    *,
    branch_start_sha: str | None = None,
    review_checkpoint_sha: str | None = None,
) -> None:
    path = _state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, FileNotFoundError):
        data = {}
    branches = data.setdefault("branches", {})
    branch_data = branches.setdefault(branch, {})
    if branch_start_sha is not None:
        branch_data["branch_start_sha"] = branch_start_sha
    if review_checkpoint_sha is not None:
        branch_data["review_checkpoint_sha"] = review_checkpoint_sha
    branch_data.pop("base_sha", None)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def save_branch_start(branch: str, sha: str) -> None:
    _save_branch_values(branch, branch_start_sha=sha)


def save_review_checkpoint(branch: str, sha: str) -> None:
    _save_branch_values(branch, review_checkpoint_sha=sha)
