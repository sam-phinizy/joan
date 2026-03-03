from __future__ import annotations

from datetime import UTC, datetime


def create_branch_args(name: str, start_point: str | None = None) -> list[str]:
    args = ["checkout", "-b", name]
    if start_point:
        args.append(start_point)
    return args


def checkout_branch_args(name: str) -> list[str]:
    return ["checkout", name]


def merge_ff_only_args(branch: str) -> list[str]:
    return ["merge", "--ff-only", branch]


def reset_branch_args(name: str, start_point: str) -> list[str]:
    return ["branch", "-f", name, start_point]


def push_branch_args(remote: str, branch: str, set_upstream: bool = True) -> list[str]:
    args = ["push"]
    if set_upstream:
        args.append("-u")
    args.extend([remote, branch])
    return args


def push_refspec_args(remote: str, src_ref: str, dst_ref: str) -> list[str]:
    return ["push", remote, f"{src_ref}:{dst_ref}"]


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


def stage_branch_name(working_branch: str) -> str:
    return f"joan-stage/{working_branch}"


def working_branch_for_stage(branch: str) -> str | None:
    prefix = "joan-stage/"
    if not branch.startswith(prefix):
        return None
    working_branch = branch[len(prefix) :]
    return working_branch or None


def is_stage_branch(branch: str) -> bool:
    return working_branch_for_stage(branch) is not None


def default_publish_branch_name(working_branch: str) -> str:
    flattened = working_branch.replace("/", "-")
    return f"publish/{flattened}"


def delete_branch_args(name: str) -> list[str]:
    return ["branch", "-D", name]


def ls_remote_ref_args(remote: str, branch: str) -> list[str]:
    return ["ls-remote", remote, f"refs/heads/{branch}"]


def merge_base_args(ref1: str, ref2: str) -> list[str]:
    return ["merge-base", ref1, ref2]


def rev_parse_args(ref: str) -> list[str]:
    return ["rev-parse", ref]
