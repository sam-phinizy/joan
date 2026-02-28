from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import typer

from joan.core.models import Config
from joan.shell.config_io import read_config
from joan.shell.forgejo_client import ForgejoClient, ForgejoError
from joan.shell.git_runner import run_git

app = typer.Typer(help="Check local Joan setup.", invoke_without_command=True)


@dataclass(slots=True)
class CheckResult:
    status: str
    message: str


def _record(results: list[CheckResult], status: str, message: str) -> None:
    results.append(CheckResult(status=status, message=message))
    typer.echo(f"{status.upper():4} {message}")


def _check_git_repo(results: list[CheckResult]) -> None:
    try:
        inside = run_git(["rev-parse", "--is-inside-work-tree"])
    except Exception as exc:  # noqa: BLE001
        _record(results, "fail", f"Not inside a git repository: {exc}")
        return
    if inside.lower() == "true":
        _record(results, "ok", "Inside a git repository.")
        return
    _record(results, "fail", "Current directory is not inside a git repository.")


def _load_config(results: list[CheckResult]) -> Config | None:
    try:
        config = read_config(Path.cwd())
    except FileNotFoundError:
        _record(results, "fail", "Missing .joan/config.toml. Run `joan init` first.")
        return None
    except Exception as exc:  # noqa: BLE001
        _record(results, "fail", f"Failed to read .joan/config.toml: {exc}")
        return None
    _record(results, "ok", "Loaded .joan/config.toml.")
    return config


def _remote_points_to_repo(remote_url: str, config: Config) -> bool:
    expected = f"{config.forgejo.owner}/{config.forgejo.repo}.git"
    parsed = urlparse(remote_url)
    if parsed.path.rstrip("/").endswith(f"/{expected}"):
        return True
    return remote_url.rstrip("/").endswith(expected)


def _check_review_remote(config: Config, results: list[CheckResult]) -> None:
    try:
        remotes = set(run_git(["remote"]).splitlines())
    except Exception as exc:  # noqa: BLE001
        _record(results, "warn", f"Could not list git remotes: {exc}")
        return

    review_remote = config.remotes.review
    if review_remote not in remotes:
        _record(results, "warn", f"Git remote '{review_remote}' is missing. Run `joan remote add`.")
        return

    try:
        remote_url = run_git(["remote", "get-url", review_remote])
    except Exception as exc:  # noqa: BLE001
        _record(results, "warn", f"Could not read git remote '{review_remote}': {exc}")
        return

    if _remote_points_to_repo(remote_url, config):
        _record(results, "ok", f"Git remote '{review_remote}' points to {config.forgejo.owner}/{config.forgejo.repo}.")
        return

    _record(
        results,
        "warn",
        (
            f"Git remote '{review_remote}' does not look like "
            f"{config.forgejo.owner}/{config.forgejo.repo}: {remote_url}"
        ),
    )


def _check_forgejo(config: Config, results: list[CheckResult], user: str | None) -> None:
    client = ForgejoClient(config.forgejo.url, config.forgejo.token)

    try:
        current_user = client.get_current_user()
    except ForgejoError as exc:
        _record(results, "fail", f"Forgejo token check failed: {exc}")
        return

    login = str(current_user.get("login") or current_user.get("username") or "unknown")
    _record(results, "ok", f"Forgejo token authenticated as '{login}'.")

    try:
        repo = client.get_repo(config.forgejo.owner, config.forgejo.repo)
    except ForgejoError as exc:
        if "Forgejo API 404" in str(exc):
            _record(
                results,
                "fail",
                (
                    f"Configured repo '{config.forgejo.owner}/{config.forgejo.repo}' "
                    "was not found or Joan cannot access it."
                ),
            )
            return
        _record(results, "fail", f"Forgejo repo check failed: {exc}")
        return

    _record(results, "ok", f"Repo '{config.forgejo.owner}/{config.forgejo.repo}' is reachable on Forgejo.")

    permissions = repo.get("permissions")
    if isinstance(permissions, dict):
        if permissions.get("admin"):
            _record(results, "ok", "Joan token has admin access to the review repo.")
        else:
            _record(results, "warn", "Joan token can reach the review repo but does not report admin access.")

    effective_user = user or config.forgejo.human_user
    if not effective_user:
        return

    try:
        permission = client.get_repo_collaborator_permission(
            config.forgejo.owner,
            config.forgejo.repo,
            effective_user,
        )
    except ForgejoError as exc:
        if "Forgejo API 404" in str(exc):
            _record(
                results,
                "fail",
                (
                    f"Forgejo user '{effective_user}' is not a collaborator on "
                    f"{config.forgejo.owner}/{config.forgejo.repo}."
                ),
            )
            return
        _record(results, "fail", f"Collaborator check failed for '{effective_user}': {exc}")
        return

    access = str(permission.get("permission") or "").strip().lower()
    if access == "admin":
        _record(results, "ok", f"Forgejo user '{effective_user}' has admin access to the review repo.")
        return
    if access:
        _record(results, "fail", f"Forgejo user '{effective_user}' has '{access}' access, not admin.")
        return
    _record(results, "warn", f"Forgejo did not report a permission level for user '{effective_user}'.")


@app.callback()
def doctor_command(
    user: str | None = typer.Option(
        None,
        "--user",
        help="Optional Forgejo username to verify has admin access to the review repo.",
    ),
) -> None:
    results: list[CheckResult] = []
    _check_git_repo(results)
    config = _load_config(results)

    if config is not None:
        _check_review_remote(config, results)
        _check_forgejo(config, results, user.strip() if user else None)

    failures = sum(1 for result in results if result.status == "fail")
    warnings = sum(1 for result in results if result.status == "warn")
    typer.echo(f"Summary: {failures} failed, {warnings} warning(s).")
    if failures:
        raise typer.Exit(code=1)
