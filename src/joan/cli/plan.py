from __future__ import annotations

from datetime import date
from pathlib import Path

import typer

from joan.cli._common import current_branch, forgejo_client, load_config_or_exit
from joan.core.forgejo import build_create_pr_payload, parse_pr_response
from joan.core.git import create_branch_args, push_branch_args, review_branch_name, working_branch_for_review
from joan.core.plans import (
    PlanError,
    default_plan_title,
    normalize_plan_slug,
    plan_branch_topic,
    plan_filename,
    render_plan_template,
)
from joan.shell.git_runner import run_git
from joan.shell.plan_io import PlanIOError, load_plan_template, resolve_plan_path, write_plan_document

app = typer.Typer(help="Put an existing plan document into Joan's review workflow.")


@app.callback()
def plan_app() -> None:
    """Plan review command group."""


@app.command("create", help="Create a plan doc on a review branch and optionally open a PR for feedback.")
def plan_create(
    slug: str = typer.Argument(..., help="Short identifier used in the plan filename and review branch."),
    title: str | None = typer.Option(default=None, help="Optional human-readable plan title."),
    base: str | None = typer.Option(default=None, help="Base branch for the plan review. Defaults to the current branch."),
    open_pr: bool = typer.Option(
        True,
        "--open-pr/--no-open-pr",
        help="Open a plan PR immediately after creating the document (default: on).",
    ),
    request_human_review: bool = typer.Option(
        True,
        "--request-human-review/--no-request-human-review",
        help="Request review from the configured human reviewer after opening the PR (default: on).",
    ),
) -> None:
    config = load_config_or_exit()
    branch = current_branch()
    if working_branch_for_review(branch):
        typer.echo("Current branch is already a review branch. Switch to a base branch before creating a plan PR.", err=True)
        raise typer.Exit(code=2)

    resolved_base = (base or branch).strip()
    if not resolved_base:
        typer.echo("Base branch cannot be empty.", err=True)
        raise typer.Exit(code=2)
    try:
        normalized_slug = normalize_plan_slug(slug)
    except PlanError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc
    review_branch = review_branch_name(resolved_base, plan_branch_topic(normalized_slug))
    created_at = date.today()
    try:
        template = load_plan_template(config.plans.default_template)
    except PlanIOError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc
    resolved_title = (title.strip() if title else "") or default_plan_title(normalized_slug)
    repo_root = Path.cwd()
    filename = plan_filename(created_at, normalized_slug)
    existing_path = resolve_plan_path(repo_root, config.plans.directory, filename)
    if existing_path.exists():
        typer.echo(f"plan already exists: {existing_path}", err=True)
        raise typer.Exit(code=2)

    run_git(push_branch_args(config.remotes.review, resolved_base, set_upstream=False))
    run_git(create_branch_args(review_branch, resolved_base))

    path = write_plan_document(
        repo_root,
        config.plans.directory,
        filename,
        render_plan_template(
            template,
            title=resolved_title,
            slug=normalized_slug,
            base_branch=resolved_base,
            created_at=created_at,
        ),
    )

    typer.echo(f"Created plan: {path}")

    if not open_pr:
        return

    run_git(push_branch_args(config.remotes.review, review_branch, set_upstream=True))

    client = forgejo_client(config)
    pr_raw = client.create_pr(
        config.forgejo.owner,
        config.forgejo.repo,
        build_create_pr_payload(
            title=f"plan: {resolved_title}",
            head=review_branch,
            base=resolved_base,
        ),
    )
    pr = parse_pr_response(pr_raw)
    human_user = config.forgejo.human_user
    if request_human_review and human_user and human_user != config.forgejo.owner:
        client.request_pr_reviewers(config.forgejo.owner, config.forgejo.repo, pr.number, [human_user])
    typer.echo(f"PR #{pr.number}: {pr.url}")
