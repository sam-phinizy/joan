from __future__ import annotations

from collections import deque
from typing import Any

import typer

from joan.cli._common import forgejo_client, load_config_or_exit, print_json

app = typer.Typer(help="Create, comment, read comments, link, read, close, and graph Forgejo issues.")


def _issue_number(issue: dict[str, Any]) -> int | None:
    raw = issue.get("number", issue.get("index"))
    if isinstance(raw, int):
        return raw
    if isinstance(raw, str) and raw.isdigit():
        return int(raw)
    return None


def _normalize_issue(issue: dict[str, Any]) -> dict[str, Any]:
    return {
        "number": _issue_number(issue),
        "title": str(issue.get("title", "")),
        "body": str(issue.get("body", "")),
        "state": str(issue.get("state", "")),
        "url": str(issue.get("html_url") or issue.get("url") or ""),
        "is_pull_request": bool(issue.get("pull_request")),
    }


def _normalize_issues(issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [_normalize_issue(issue) for issue in issues]


def _normalize_comment(comment: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": comment.get("id"),
        "body": str(comment.get("body", "")),
        "author": str(comment.get("user", {}).get("login", "")),
        "url": str(comment.get("html_url") or comment.get("url") or ""),
        "created_at": str(comment.get("created_at", "")),
        "updated_at": str(comment.get("updated_at", "")),
    }


def _normalize_comments(comments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [_normalize_comment(comment) for comment in comments]


def _sort_by_number(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(items, key=lambda item: (item.get("number") is None, item.get("number", 0)))


def _valid_issue_state(state: str) -> str:
    normalized = state.strip().lower()
    if normalized not in {"open", "closed", "all"}:
        raise typer.BadParameter("state must be one of: open, closed, all")
    return normalized


@app.command("create", help="Create a new issue in the configured repo.")
def issue_create(
    title: str = typer.Argument(..., help="Issue title."),
    body: str | None = typer.Option(None, "--body", help="Optional issue body."),
) -> None:
    config = load_config_or_exit()
    client = forgejo_client(config)
    issue = client.create_issue(config.forgejo.owner, config.forgejo.repo, title=title, body=body)
    number = _issue_number(issue)
    url = str(issue.get("html_url") or issue.get("url") or "")
    if number is None:
        typer.echo(f"Created issue: {url}")
        return
    typer.echo(f"Created issue #{number}: {url}")


@app.command("link", help="Mark ISSUE as blocked by BLOCKED_BY issue.")
def issue_link(
    issue: int = typer.Argument(..., help="Issue number that is blocked."),
    blocked_by: int = typer.Argument(..., help="Issue number that blocks ISSUE."),
) -> None:
    if issue == blocked_by:
        typer.echo("An issue cannot be blocked by itself.", err=True)
        raise typer.Exit(code=2)
    config = load_config_or_exit()
    client = forgejo_client(config)
    client.add_issue_dependency(config.forgejo.owner, config.forgejo.repo, issue, blocked_by)
    typer.echo(f"Linked issue #{issue} as blocked by #{blocked_by}")


@app.command("close", help="Close an issue by number.")
def issue_close(
    issue: int = typer.Argument(..., help="Issue number to close."),
) -> None:
    config = load_config_or_exit()
    client = forgejo_client(config)
    client.close_issue(config.forgejo.owner, config.forgejo.repo, issue)
    typer.echo(f"Closed issue #{issue}")


@app.command("comment", help="Post a comment on an issue by number.")
def issue_comment(
    issue: int = typer.Argument(..., help="Issue number to comment on."),
    body: str = typer.Option(..., "--body", help="Comment text to post."),
) -> None:
    config = load_config_or_exit()
    client = forgejo_client(config)
    client.create_issue_comment(config.forgejo.owner, config.forgejo.repo, issue, body)
    typer.echo(f"Posted comment on issue #{issue}")


@app.command("comments", help="Read all comments for an issue by number as JSON.")
def issue_comments(
    issue: int = typer.Argument(..., help="Issue number to read comments for."),
) -> None:
    config = load_config_or_exit()
    client = forgejo_client(config)
    comments = client.list_issue_comments(config.forgejo.owner, config.forgejo.repo, issue)
    print_json(_normalize_comments(comments))


@app.command("read", help="Read one issue or list issues.")
def issue_read(
    issue: int | None = typer.Option(None, "--issue", help="Issue number to read. If omitted, list issues."),
    state: str = typer.Option("open", "--state", callback=_valid_issue_state, help="Issue state filter when listing: open, closed, all."),
    limit: int = typer.Option(50, "--limit", min=1, max=500, help="Maximum issues to return when listing."),
) -> None:
    config = load_config_or_exit()
    client = forgejo_client(config)
    if issue is not None:
        raw = client.get_issue(config.forgejo.owner, config.forgejo.repo, issue)
        print_json(_normalize_issue(raw))
        return
    issues = client.list_issues(config.forgejo.owner, config.forgejo.repo, state=state, limit=limit)
    print_json(_normalize_issues(issues))


@app.command("blocked-by", help="List the issues that block ISSUE.")
def issue_blocked_by(
    issue: int = typer.Argument(..., help="Issue number to inspect."),
) -> None:
    config = load_config_or_exit()
    client = forgejo_client(config)
    issues = client.list_issue_blocked_by(config.forgejo.owner, config.forgejo.repo, issue)
    print_json(_normalize_issues(issues))


@app.command("blocks", help="List the issues blocked by ISSUE.")
def issue_blocks(
    issue: int = typer.Argument(..., help="Issue number to inspect."),
) -> None:
    config = load_config_or_exit()
    client = forgejo_client(config)
    issues = client.list_issue_blocks(config.forgejo.owner, config.forgejo.repo, issue)
    print_json(_normalize_issues(issues))


@app.command("graph", help="Print issue dependency graph JSON around ISSUE.")
def issue_graph(
    issue: int = typer.Argument(..., help="Root issue number."),
    depth: int = typer.Option(1, "--depth", min=0, max=5, help="How many hops from the root issue to include."),
) -> None:
    config = load_config_or_exit()
    client = forgejo_client(config)

    nodes: dict[int, dict[str, Any]] = {}
    edges: set[tuple[int, int]] = set()
    seen: dict[int, int] = {}
    queue: deque[tuple[int, int]] = deque([(issue, depth)])

    while queue:
        current, remaining = queue.popleft()
        if current in seen and seen[current] >= remaining:
            continue
        seen[current] = remaining

        current_issue = nodes.get(current)
        if current_issue is None:
            current_issue = client.get_issue(config.forgejo.owner, config.forgejo.repo, current)
            nodes[current] = current_issue

        if remaining == 0:
            continue

        blockers = client.list_issue_blocked_by(config.forgejo.owner, config.forgejo.repo, current)
        for blocker in blockers:
            blocker_num = _issue_number(blocker)
            if blocker_num is None:
                continue
            nodes.setdefault(blocker_num, blocker)
            edges.add((blocker_num, current))
            queue.append((blocker_num, remaining - 1))

        blocked = client.list_issue_blocks(config.forgejo.owner, config.forgejo.repo, current)
        for blocked_issue in blocked:
            blocked_num = _issue_number(blocked_issue)
            if blocked_num is None:
                continue
            nodes.setdefault(blocked_num, blocked_issue)
            edges.add((current, blocked_num))
            queue.append((blocked_num, remaining - 1))

    print_json(
        {
            "root_issue": issue,
            "depth": depth,
            "nodes": [_normalize_issue(nodes[number]) for number in sorted(nodes)],
            "edges": [{"from": src, "to": dst} for src, dst in sorted(edges)],
        }
    )


@app.command("get-work", help="Return open issues grouped into ready vs blocked work as JSON.")
def issue_get_work(
    limit: int = typer.Option(200, "--limit", min=1, max=500, help="Maximum open issues to scan."),
    ready_limit: int = typer.Option(25, "--ready-limit", min=1, max=500, help="Maximum ready issues to return."),
) -> None:
    config = load_config_or_exit()
    client = forgejo_client(config)

    issues = client.list_issues(config.forgejo.owner, config.forgejo.repo, state="open", limit=limit)
    issues = [issue for issue in issues if not issue.get("pull_request")]

    ready: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []

    for issue in issues:
        issue_number = _issue_number(issue)
        if issue_number is None:
            continue

        blockers = client.list_issue_blocked_by(config.forgejo.owner, config.forgejo.repo, issue_number)
        open_blockers = [
            _normalize_issue(blocker)
            for blocker in blockers
            if str(blocker.get("state", "")).lower() != "closed"
        ]
        open_blockers = _sort_by_number(open_blockers)

        item = {
            "issue": _normalize_issue(issue),
            "open_blockers": open_blockers,
            "open_blocker_count": len(open_blockers),
        }
        if open_blockers:
            blocked.append(item)
        else:
            ready.append(item)

    ready_sorted = sorted(
        ready,
        key=lambda item: (item["issue"].get("number") is None, item["issue"].get("number", 0)),
    )
    blocked_sorted = sorted(
        blocked,
        key=lambda item: (item["issue"].get("number") is None, item["issue"].get("number", 0)),
    )

    print_json(
        {
            "summary": {
                "open_issue_count": len(issues),
                "ready_count": len(ready_sorted),
                "blocked_count": len(blocked_sorted),
            },
            "ready": ready_sorted[:ready_limit],
            "blocked": blocked_sorted,
        }
    )
