from __future__ import annotations

from datetime import UTC, datetime


def create_branch_args(name: str) -> list[str]:
    return ["checkout", "-b", name]


def push_branch_args(remote: str, branch: str, set_upstream: bool = True) -> list[str]:
    args = ["push"]
    if set_upstream:
        args.append("-u")
    args.extend([remote, branch])
    return args


def current_branch_args() -> list[str]:
    return ["rev-parse", "--abbrev-ref", "HEAD"]


def worktree_add_args(path: str, branch: str | None = None) -> list[str]:
    args = ["worktree", "add"]
    if branch:
        args.extend(["-b", branch])
    args.append(path)
    return args


def worktree_remove_args(path: str) -> list[str]:
    return ["worktree", "remove", path]


def remote_add_args(name: str, url: str) -> list[str]:
    return ["remote", "add", name, url]


def remote_set_url_args(name: str, url: str) -> list[str]:
    return ["remote", "set-url", name, url]


def list_remotes_args() -> list[str]:
    return ["remote"]


def infer_branch_name(hint: str | None = None) -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    if hint:
        safe = "-".join(part for part in hint.lower().replace("_", "-").split() if part)
        if safe:
            return f"codex/{safe}-{stamp}"
    return f"codex/work-{stamp}"
