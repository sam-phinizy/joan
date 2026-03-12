from __future__ import annotations

from pathlib import Path

import typer

from joan.cli._common import current_pr_or_exit, forgejo_client, load_config_or_exit, print_json
from joan.core.forgejo import exclude_comments_by_author, parse_comments, parse_reviews
from joan.core.review_memory import (
    filter_rules_by_path,
    ingest_feedback,
    load_store,
    save_store,
    suggest_rules,
)
from joan.shell.git_runner import run_git

app = typer.Typer(help="Persist and reuse recurring PR review feedback patterns.")


@app.command("ingest", help="Ingest review feedback from a PR into .joan/review-memory/rules.json.")
def review_memory_ingest(
    pr_number: int | None = typer.Option(None, "--pr", help="PR number to ingest. Defaults to current branch PR."),
) -> None:
    config = load_config_or_exit()
    client = forgejo_client(config)
    pr = current_pr_or_exit(config, pr_number=pr_number)

    reviews = parse_reviews(client.get_reviews(config.forgejo.owner, config.forgejo.repo, pr.number))
    comments = parse_comments(client.get_comments(config.forgejo.owner, config.forgejo.repo, pr.number))
    comments = exclude_comments_by_author(comments, config.forgejo.owner)

    cwd = Path.cwd()
    store = load_store(cwd)
    updated, changed = ingest_feedback(store, reviews, comments)
    path = save_store(cwd, updated)

    typer.echo(f"Ingested review memory from PR #{pr.number}: {changed} rule updates")
    typer.echo(f"Saved {len(updated.get('rules', []))} rules to {path}")


@app.command("list", help="List persisted review-memory rules as JSON.")
def review_memory_list(
    path: str | None = typer.Option(None, "--path", help="Only include rules that apply to this exact file path."),
) -> None:
    store = load_store(Path.cwd())
    rules = store.get("rules", []) if isinstance(store.get("rules"), list) else []
    rules = filter_rules_by_path([rule for rule in rules if isinstance(rule, dict)], path)
    print_json({"version": store.get("version", 1), "rules": rules})


@app.command("suggest", help="Suggest reusable checks from review-memory rules.")
def review_memory_suggest(
    paths_from_git: bool = typer.Option(
        False,
        "--paths-from-git",
        help="Filter suggestions to changed paths from `git diff --name-only --diff-filter=ACMRTUXB`.",
    ),
    format: str = typer.Option("checklist", "--format", help="Output format: checklist or json."),
) -> None:
    output_format = format.strip().lower()
    if output_format not in {"checklist", "json"}:
        typer.echo("format must be one of: checklist, json", err=True)
        raise typer.Exit(code=2)

    store = load_store(Path.cwd())
    rules = [rule for rule in store.get("rules", []) if isinstance(rule, dict)]

    paths: list[str] | None = None
    if paths_from_git:
        changed = run_git(["diff", "--name-only", "--diff-filter=ACMRTUXB"]) 
        paths = [line.strip() for line in changed.splitlines() if line.strip()]

    selected = suggest_rules(rules, paths)

    if output_format == "json":
        print_json({"paths": paths or [], "rules": selected})
        return

    if not selected:
        typer.echo("Review preflight checklist:\n- [ ] No matching review-memory rules.")
        return

    typer.echo("Review preflight checklist:")
    for rule in selected:
        count = int(rule.get("count", 0))
        confidence = float(rule.get("confidence", 0.0))
        pattern = str(rule.get("pattern", "")).strip() or str(rule.get("id", "rule"))
        typer.echo(f"- [ ] {pattern} (seen {count}x, confidence {confidence:.2f})")
