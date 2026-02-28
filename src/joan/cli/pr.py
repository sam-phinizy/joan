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
from joan.core.git import checkout_branch_args, merge_ff_only_args, push_branch_args, working_branch_for_review
from joan.shell.git_runner import run_git

app = typer.Typer(help="Open Forgejo PRs, inspect review state, finish approved PRs locally, and push upstream separately.")
comment_app = typer.Typer(help="Read or resolve PR comments.")
review_app = typer.Typer(help="Post review verdicts on PRs.")
app.add_typer(comment_app, name="comment")
app.add_typer(review_app, name="review")


@app.command("create", help="Create a PR from the current `joan-review/*` branch to its working branch on the review remote.")
def pr_create(
    title: str | None = typer.Option(default=None, help="PR title. Defaults to the current branch name."),
    body: str | None = typer.Option(default=None, help="Optional PR body/description."),
    base: str | None = typer.Option(
        default=None,
        help="Base branch. Defaults to the branch implied by the current `joan-review/*` branch.",
    ),
    request_human_review: bool = typer.Option(
        True,
        "--request-human-review/--no-request-human-review",
        help="Request review from the configured human reviewer after opening the PR (default: on).",
    ),
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
    human_user = config.forgejo.human_user
    if request_human_review and human_user and human_user != config.forgejo.owner:
        client.request_pr_reviewers(config.forgejo.owner, config.forgejo.repo, pr.number, [human_user])
    typer.echo(f"PR #{pr.number}: {pr.url}")


@app.command("sync", help="Read approval state and unresolved comment count for the open PR on the current branch.")
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


@app.command(
    "comments",
    help=(
        "List unresolved PR-level and inline review comments. "
        "Defaults to the open PR for the current branch; use --pr or --branch to inspect another PR."
    ),
)
def pr_comments(
    all_comments: bool = typer.Option(False, "--all", help="Include resolved comments from the targeted PR"),
    pr_number: int | None = typer.Option(
        None,
        "--pr",
        help="Pull request number to inspect instead of the current branch's open PR",
    ),
    branch: str | None = typer.Option(
        None,
        "--branch",
        help="Branch whose open PR should be inspected (use your latest review branch when not checked out there)",
    ),
) -> None:
    if pr_number is not None and branch is not None:
        typer.echo("Pass either --pr or --branch, not both.", err=True)
        raise typer.Exit(code=2)

    config = load_config_or_exit()
    client = forgejo_client(config)
    pr = current_pr_or_exit(config, pr_number=pr_number, branch=branch.strip() if branch else None)

    comments = parse_comments(client.get_comments(config.forgejo.owner, config.forgejo.repo, pr.number))
    typer.echo(format_comments_json(comments, include_resolved=all_comments))


@comment_app.command("resolve")
def pr_comment_resolve(
    comment_id: int = typer.Argument(..., help="Comment ID to resolve on the current branch's active PR.")
) -> None:
    config = load_config_or_exit()
    client = forgejo_client(config)
    pr = current_pr_or_exit(config)

    client.resolve_comment(config.forgejo.owner, config.forgejo.repo, pr.number, comment_id)
    typer.echo(f"Resolved comment {comment_id}")


@comment_app.command("add")
def pr_comment_add(
    agent: str = typer.Option(..., "--agent", help="Agent name whose Forgejo token should be used."),
    owner: str = typer.Option(..., "--owner", help="Forgejo repo owner for the target PR."),
    repo: str = typer.Option(..., "--repo", help="Forgejo repo name for the target PR."),
    pr: int = typer.Option(..., "--pr", help="Pull request number to comment on."),
    path: str = typer.Option(..., "--path", help="File path within the PR diff."),
    line: int = typer.Option(..., "--line", help="New-side line number for the inline comment."),
    body: str = typer.Option(..., "--body", help="Inline comment text to post."),
) -> None:
    config = load_config_or_exit()
    client = forgejo_client_for_agent_or_exit(config, agent)
    try:
        client.create_inline_pr_comment(owner=owner, repo=repo, index=pr, path=path, line=line, body=body)
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"Failed to post inline comment: {exc}", err=True)
        raise typer.Exit(code=1)
    typer.echo(f"Posted inline comment on PR #{pr}")


@app.command(
    "finish",
    help="Fast-forward the current approved review branch into its original local base branch without pushing upstream.",
)
def pr_finish() -> None:
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
    run_git(checkout_branch_args(pr.base_ref))
    run_git(merge_ff_only_args(branch))
    typer.echo(f"Merged {branch} into local {pr.base_ref}")


@app.command("push", help="Push the current finished local branch to the real upstream remote.")
def pr_push() -> None:
    config = load_config_or_exit()
    branch = current_branch()
    if working_branch_for_review(branch):
        typer.echo(
            "Current branch is a review branch. Run `uv run joan pr finish` first to merge it back into the base branch locally.",
            err=True,
        )
        raise typer.Exit(code=2)

    run_git(push_branch_args(config.remotes.upstream, branch, set_upstream=False))
    typer.echo(f"Pushed {branch} to {config.remotes.upstream}/{branch}")


@review_app.command("create", help="Post a review from JSON to the current branch's active PR.")
def pr_review_create(
    json_input: str = typer.Option(
        ...,
        "--json-input",
        help="Review JSON payload for the current PR: {body, verdict, comments}.",
    ),
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


@review_app.command("approve", help="Approve the current branch's active PR.")
def pr_review_approve(
    body: str = typer.Option("", "--body", help="Optional review summary/body."),
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


@review_app.command("request-changes", help="Request changes on the current branch's active PR.")
def pr_review_request_changes(
    body: str = typer.Option("", "--body", help="Optional review summary/body."),
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


@review_app.command("submit", help="Post a final review verdict on a specific PR using an agent token.")
def pr_review_submit(
    agent: str = typer.Option(..., "--agent", help="Agent name whose Forgejo token should be used."),
    owner: str = typer.Option(..., "--owner", help="Forgejo repo owner for the target PR."),
    repo: str = typer.Option(..., "--repo", help="Forgejo repo name for the target PR."),
    pr: int = typer.Option(..., "--pr", help="Pull request number to review."),
    verdict: str = typer.Option(..., "--verdict", help="Review verdict: `approve`, `request_changes`, or `comment`."),
    body: str = typer.Option("", "--body", help="Optional review summary/body."),
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
