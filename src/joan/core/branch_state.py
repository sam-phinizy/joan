from __future__ import annotations

import json
from pathlib import Path

_STATE_FILE = ".joan/branch-state.json"


def _state_path() -> Path:
    return Path(_STATE_FILE)


def load_branch_state(branch: str) -> str | None:
    path = _state_path()
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return data.get("branches", {}).get(branch, {}).get("base_sha")


def save_branch_state(branch: str, sha: str) -> None:
    path = _state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, FileNotFoundError):
        data = {}
    branches = data.setdefault("branches", {})
    branches[branch] = {"base_sha": sha}
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
