from __future__ import annotations

import json

import typer

from joan.cli._common import (
    current_branch,
    current_pr_or_exit,
    forgejo_client,
    forgejo_client_for_agent_or_exit,
    load_config_or_exit,
)
from joan.core.forgejo import (
    build_create_pr_payload,
    compute_sync_status,
    format_comments_json,
    parse_comments,
    parse_pr_response,
    parse_reviews,
)
from joan.core.git import push_branch_args, push_refspec_args, working_branch_for_review
from joan.shell.git_runner import run_git

app = typer.Typer(help="Manage pull requests on Forgejo.")
comment_app = typer.Typer(help="Manage PR comments.")
review_app = typer.Typer(help="Post reviews on PRs.")
app.add_typer(comment_app, name="comment")
app.add_typer(review_app, name="review")


@app.command("create")
def pr_create(
    title: str | None = typer.Option(default=None, help="PR title"),
    body: str | None = typer.Option(default=None, help="PR body"),
    base: str | None = typer.Option(default=None, help="Base branch (defaults to the working branch for this review branch)"),
) -> None:
    config = load_config_or_exit()
    client = forgejo_client(config)

    branch = current_branch()
    resolved_base = base or working_branch_for_review(branch)
    if not resolved_base:
        typer.echo(
            "Current branch is not a review branch. Use `joan branch create` first or pass `--base`.",
            err=True,
        )
        raise typer.Exit(code=2)

    run_git(push_branch_args(config.remotes.review, resolved_base, set_upstream=False))
    run_git(push_branch_args(config.remotes.review, branch, set_upstream=True))

    payload = build_create_pr_payload(title=title or branch, head=branch, base=resolved_base, body=body)
    pr_raw = client.create_pr(config.forgejo.owner, config.forgejo.repo, payload)
    pr = parse_pr_response(pr_raw)
    typer.echo(f"PR #{pr.number}: {pr.url}")


@app.command("sync")
def pr_sync() -> None:
    config = load_config_or_exit()
    client = forgejo_client(config)
    pr = current_pr_or_exit(config)

    reviews = parse_reviews(client.get_reviews(config.forgejo.owner, config.forgejo.repo, pr.number))
    comments = parse_comments(client.get_comments(config.forgejo.owner, config.forgejo.repo, pr.number))
    sync = compute_sync_status(reviews, comments)

    typer.echo(
        json.dumps(
            {
                "approved": sync.approved,
                "unresolved_comments": sync.unresolved_comments,
                "latest_review_state": sync.latest_review_state,
            },
            indent=2,
        )
    )


@app.command("comments")
def pr_comments(all_comments: bool = typer.Option(False, "--all", help="Include resolved comments")) -> None:
    config = load_config_or_exit()
    client = forgejo_client(config)
    pr = current_pr_or_exit(config)

    comments = parse_comments(client.get_comments(config.forgejo.owner, config.forgejo.repo, pr.number))
    typer.echo(format_comments_json(comments, include_resolved=all_comments))


@comment_app.command("resolve")
def pr_comment_resolve(comment_id: int) -> None:
    config = load_config_or_exit()
    client = forgejo_client(config)
    pr = current_pr_or_exit(config)

    client.resolve_comment(config.forgejo.owner, config.forgejo.repo, pr.number, comment_id)
    typer.echo(f"Resolved comment {comment_id}")


@comment_app.command("add")
def pr_comment_add(
    agent: str = typer.Option(..., "--agent", help="Agent name whose token should be used"),
    owner: str = typer.Option(..., "--owner", help="Forgejo repo owner"),
    repo: str = typer.Option(..., "--repo", help="Forgejo repo name"),
    pr: int = typer.Option(..., "--pr", help="Pull request number"),
    path: str = typer.Option(..., "--path", help="Path within the pull request diff"),
    line: int = typer.Option(..., "--line", help="New-side line number"),
    body: str = typer.Option(..., "--body", help="Comment body"),
) -> None:
    config = load_config_or_exit()
    client = forgejo_client_for_agent_or_exit(config, agent)
    try:
        client.create_inline_pr_comment(owner=owner, repo=repo, index=pr, path=path, line=line, body=body)
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"Failed to post inline comment: {exc}", err=True)
        raise typer.Exit(code=1)
    typer.echo(f"Posted inline comment on PR #{pr}")


@app.command("push")
def pr_push() -> None:
    config = load_config_or_exit()
    client = forgejo_client(config)
    pr = current_pr_or_exit(config)

    reviews = parse_reviews(client.get_reviews(config.forgejo.owner, config.forgejo.repo, pr.number))
    comments = parse_comments(client.get_comments(config.forgejo.owner, config.forgejo.repo, pr.number))
    sync = compute_sync_status(reviews, comments)
    if not sync.approved:
        typer.echo("PR is not approved on Forgejo.", err=True)
        raise typer.Exit(code=1)
    if sync.unresolved_comments > 0:
        typer.echo(f"PR has {sync.unresolved_comments} unresolved comments.", err=True)
        raise typer.Exit(code=1)

    branch = current_branch()
    run_git(push_refspec_args(config.remotes.upstream, branch, f"refs/heads/{pr.base_ref}"))
    typer.echo(f"Pushed {branch} to {config.remotes.upstream}/{pr.base_ref}")


@review_app.command("create")
def pr_review_create(
    json_input: str = typer.Option(..., "--json-input", help="Review JSON: {body, verdict, comments}"),
) -> None:
    try:
        data = json.loads(json_input)
    except json.JSONDecodeError as exc:
        typer.echo(f"Invalid JSON: {exc}", err=True)
        raise typer.Exit(code=2)

    config = load_config_or_exit()
    client = forgejo_client(config)
    pr = current_pr_or_exit(config)

    body = str(data.get("body", ""))
    verdict = str(data.get("verdict", "comment"))
    comments = list(data.get("comments", []))

    client.create_review(
        config.forgejo.owner,
        config.forgejo.repo,
        pr.number,
        body=body,
        verdict=verdict,
        comments=comments,
    )
    typer.echo(f"Posted review ({verdict}) on PR #{pr.number}")


@review_app.command("approve")
def pr_review_approve(
    body: str = typer.Option("", "--body", help="Review body"),
) -> None:
    config = load_config_or_exit()
    client = forgejo_client(config)
    pr = current_pr_or_exit(config)
    client.create_review(
        config.forgejo.owner,
        config.forgejo.repo,
        pr.number,
        body=body,
        verdict="approve",
        comments=[],
    )
    typer.echo(f"Approved PR #{pr.number}")


@review_app.command("request-changes")
def pr_review_request_changes(
    body: str = typer.Option("", "--body", help="Review body"),
) -> None:
    config = load_config_or_exit()
    client = forgejo_client(config)
    pr = current_pr_or_exit(config)
    client.create_review(
        config.forgejo.owner,
        config.forgejo.repo,
        pr.number,
        body=body,
        verdict="request_changes",
        comments=[],
    )
    typer.echo(f"Requested changes on PR #{pr.number}")


@review_app.command("submit")
def pr_review_submit(
    agent: str = typer.Option(..., "--agent", help="Agent name whose token should be used"),
    owner: str = typer.Option(..., "--owner", help="Forgejo repo owner"),
    repo: str = typer.Option(..., "--repo", help="Forgejo repo name"),
    pr: int = typer.Option(..., "--pr", help="Pull request number"),
    verdict: str = typer.Option(..., "--verdict", help="approve, request_changes, or comment"),
    body: str = typer.Option("", "--body", help="Review body"),
) -> None:
    config = load_config_or_exit()
    client = forgejo_client_for_agent_or_exit(config, agent)
    try:
        client.create_review(
            owner=owner,
            repo=repo,
            index=pr,
            body=body,
            verdict=verdict,
            comments=[],
        )
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"Failed to post review: {exc}", err=True)
        raise typer.Exit(code=1)
    typer.echo(f"Posted review ({verdict}) on PR #{pr}")
