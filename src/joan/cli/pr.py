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
    exclude_comments_by_author,
    format_comments_json,
    format_reviews_json,
    parse_comments,
    parse_pr_response,
    parse_reviews,
)
from joan.core.git import is_stage_branch, ls_remote_ref_args, push_branch_args, stage_branch_name
from joan.shell.git_runner import run_git

app = typer.Typer(help="Open Forgejo PRs, inspect review state, and merge approved work into Joan stage branches.")
comment_app = typer.Typer(help="Read or resolve PR comments.")
review_app = typer.Typer(help="Post review verdicts on PRs.")
app.add_typer(comment_app, name="comment")
app.add_typer(review_app, name="review")


def _ensure_task_branch(branch: str) -> None:
    if branch in {"main", "master"} or branch.startswith("joan-review/") or is_stage_branch(branch):
        typer.echo("Run this command from a normal Joan task branch.", err=True)
        raise typer.Exit(code=2)


def _ensure_stage_exists(remote: str, branch: str) -> str:
    stage_branch = stage_branch_name(branch)
    if not run_git(ls_remote_ref_args(remote, stage_branch)):
        typer.echo(
            "No Joan stage branch exists for this task. Use `uv run joan task start ...` "
            "or `uv run joan task track --from <ref>` first.",
            err=True,
        )
        raise typer.Exit(code=1)
    return stage_branch


def _create_pr(
    title: str | None = typer.Option(default=None, help="PR title. Defaults to the current branch name."),
    body: str | None = typer.Option(default=None, help="Optional PR body/description."),
    request_human_review: bool = typer.Option(
        True,
        "--request-human-review/--no-request-human-review",
        help="Request review from the configured human reviewer after opening the PR (default: on).",
    ),
) -> None:
    config = load_config_or_exit()
    client = forgejo_client(config)

    branch = current_branch()
    _ensure_task_branch(branch)
    resolved_base = _ensure_stage_exists(config.remotes.review, branch)

    run_git(push_branch_args(config.remotes.review, branch, set_upstream=True))

    payload = build_create_pr_payload(title=title or branch, head=branch, base=resolved_base, body=body)
    pr_raw = client.create_pr(config.forgejo.owner, config.forgejo.repo, payload)
    pr = parse_pr_response(pr_raw)
    human_user = config.forgejo.human_user
    if request_human_review and human_user and human_user != config.forgejo.owner:
        client.request_pr_reviewers(config.forgejo.owner, config.forgejo.repo, pr.number, [human_user])
    typer.echo(f"PR #{pr.number}: {pr.url}")


@app.command("create", help="Create a PR from the current task branch to its Joan stage branch.")
def pr_create(
    title: str | None = typer.Option(default=None, help="PR title. Defaults to the current branch name."),
    body: str | None = typer.Option(default=None, help="Optional PR body/description."),
    request_human_review: bool = typer.Option(
        True,
        "--request-human-review/--no-request-human-review",
        help="Request review from the configured human reviewer after opening the PR (default: on).",
    ),
) -> None:
    _create_pr(
        title=title,
        body=body,
        request_human_review=request_human_review,
    )


@app.command("open", help="Alias for `create`.")
def pr_open(
    title: str | None = typer.Option(default=None, help="PR title. Defaults to the current branch name."),
    body: str | None = typer.Option(default=None, help="Optional PR body/description."),
    request_human_review: bool = typer.Option(
        True,
        "--request-human-review/--no-request-human-review",
        help="Request review from the configured human reviewer after opening the PR (default: on).",
    ),
) -> None:
    _create_pr(
        title=title,
        body=body,
        request_human_review=request_human_review,
    )


@app.command("sync", help="Read approval state and unresolved comment count for the open PR on the current branch.")
def pr_sync() -> None:
    config = load_config_or_exit()
    client = forgejo_client(config)
    pr = current_pr_or_exit(config)

    reviews = parse_reviews(client.get_reviews(config.forgejo.owner, config.forgejo.repo, pr.number))
    comments = parse_comments(client.get_comments(config.forgejo.owner, config.forgejo.repo, pr.number))
    comments = exclude_comments_by_author(comments, config.forgejo.owner)
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
        help="Branch whose open PR should be inspected instead of the current branch",
    ),
) -> None:
    if pr_number is not None and branch is not None:
        typer.echo("Pass either --pr or --branch, not both.", err=True)
        raise typer.Exit(code=2)

    config = load_config_or_exit()
    client = forgejo_client(config)
    pr = current_pr_or_exit(config, pr_number=pr_number, branch=branch.strip() if branch else None)

    comments = parse_comments(client.get_comments(config.forgejo.owner, config.forgejo.repo, pr.number))
    comments = exclude_comments_by_author(comments, config.forgejo.owner)
    typer.echo(format_comments_json(comments, include_resolved=all_comments))


@app.command("reviews", help="List review submissions (with body text) for the open PR on the current branch.")
def pr_reviews() -> None:
    config = load_config_or_exit()
    client = forgejo_client(config)
    pr = current_pr_or_exit(config)

    reviews = parse_reviews(client.get_reviews(config.forgejo.owner, config.forgejo.repo, pr.number))
    typer.echo(format_reviews_json(reviews))


@comment_app.command("resolve")
def pr_comment_resolve(
    comment_id: int = typer.Argument(..., help="Comment ID to resolve on the current branch's active PR.")
) -> None:
    config = load_config_or_exit()
    client = forgejo_client(config)
    pr = current_pr_or_exit(config)

    client.resolve_comment(
        config.forgejo.owner,
        config.forgejo.repo,
        pr.number,
        comment_id,
        human_user=config.forgejo.human_user,
    )
    typer.echo(f"Resolved comment {comment_id}")


@comment_app.command("post")
def pr_comment_post(
    body: str = typer.Option(..., "--body", help="Comment text to post on the current PR."),
) -> None:
    config = load_config_or_exit()
    client = forgejo_client(config)
    pr = current_pr_or_exit(config)
    client.create_issue_comment(config.forgejo.owner, config.forgejo.repo, pr.number, body)
    typer.echo(f"Posted comment on PR #{pr.number}")


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
    help="Merge the approved PR on Forgejo into the current task branch's stage branch.",
)
def pr_finish() -> None:
    config = load_config_or_exit()
    client = forgejo_client(config)
    branch = current_branch()
    _ensure_task_branch(branch)
    expected_base = stage_branch_name(branch)
    pr = current_pr_or_exit(config, branch=branch)
    if pr.base_ref != expected_base:
        typer.echo(
            f"Open PR for '{branch}' targets '{pr.base_ref}', not the expected stage branch '{expected_base}'.",
            err=True,
        )
        raise typer.Exit(code=1)

    reviews = parse_reviews(client.get_reviews(config.forgejo.owner, config.forgejo.repo, pr.number))
    comments = parse_comments(client.get_comments(config.forgejo.owner, config.forgejo.repo, pr.number))
    comments = exclude_comments_by_author(comments, config.forgejo.owner)
    sync = compute_sync_status(reviews, comments)
    if not sync.approved:
        typer.echo("PR is not approved on Forgejo.", err=True)
        raise typer.Exit(code=1)
    if sync.unresolved_comments:
        typer.echo("PR still has unresolved review comments on Forgejo.", err=True)
        raise typer.Exit(code=1)

    client.merge_pr(config.forgejo.owner, config.forgejo.repo, pr.number)
    run_git(["fetch", config.remotes.review])
    typer.echo(f"Merged PR #{pr.number} into {expected_base}")


@app.command("update", help="Update the description of the current branch's open PR.")
def pr_update(
    body: str = typer.Option(..., "--body", help="New PR description/body text."),
) -> None:
    config = load_config_or_exit()
    client = forgejo_client(config)
    pr = current_pr_or_exit(config)
    client.update_pr(config.forgejo.owner, config.forgejo.repo, pr.number, body)
    typer.echo(f"Updated PR #{pr.number} description")


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
    verdict: str = typer.Option(..., "--verdict", help="One of: approve, request_changes, comment."),
    body: str = typer.Option("", "--body", help="Optional review summary/body."),
) -> None:
    config = load_config_or_exit()
    client = forgejo_client_for_agent_or_exit(config, agent)
    client.create_review(
        owner,
        repo,
        pr,
        body=body,
        verdict=verdict,
        comments=[],
    )
    typer.echo(f"Posted review ({verdict}) on PR #{pr}")
