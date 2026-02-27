from __future__ import annotations

import json

import typer

from joan.cli._common import current_branch, current_pr_or_exit, forgejo_client, load_config_or_exit
from joan.core.forgejo import (
    build_create_pr_payload,
    compute_sync_status,
    format_comments_json,
    parse_comments,
    parse_pr_response,
    parse_reviews,
)
from joan.core.git import push_branch_args
from joan.shell.git_runner import run_git

app = typer.Typer(help="Manage pull requests on Forgejo.")
comment_app = typer.Typer(help="Manage PR comments.")
app.add_typer(comment_app, name="comment")


@app.command("create")
def pr_create(
    title: str | None = typer.Option(default=None, help="PR title"),
    body: str | None = typer.Option(default=None, help="PR body"),
    base: str = typer.Option(default="main", help="Base branch"),
) -> None:
    config = load_config_or_exit()
    client = forgejo_client(config)

    branch = current_branch()
    run_git(push_branch_args(config.remotes.review, branch, set_upstream=True))

    payload = build_create_pr_payload(title=title or branch, head=branch, base=base, body=body)
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
    run_git(push_branch_args(config.remotes.upstream, branch, set_upstream=False))
    typer.echo(f"Pushed {branch} to {config.remotes.upstream}")
