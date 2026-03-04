from __future__ import annotations

import importlib.metadata

import typer

from joan.cli.api import app as api_app
from joan.cli.doctor import app as doctor_app
from joan.cli.init import app as init_app
from joan.cli.phil import app as phil_app
from joan.cli.pr import app as pr_app
from joan.cli.remote import app as remote_app
from joan.cli.services import app as services_app
from joan.cli.ship import ship_command
from joan.cli.ssh import app as ssh_app
from joan.cli.skills import app as skills_app
from joan.cli.task import app as task_app
from joan.cli.worktree import app as worktree_app

app = typer.Typer(
    help=(
        "Joan: local code review gate for AI agents. "
        "Start a task branch, review it incrementally into a Joan stage branch, and ship reviewed work upstream."
    )
)
app.add_typer(api_app, name="api")
app.add_typer(init_app)
app.add_typer(doctor_app, name="doctor")
app.add_typer(phil_app, name="phil")
app.add_typer(remote_app, name="remote")
app.add_typer(task_app, name="task")
app.add_typer(pr_app, name="pr")
app.add_typer(ssh_app, name="ssh")
app.add_typer(services_app, name="services")
app.add_typer(skills_app, name="skills")
app.add_typer(worktree_app, name="worktree")
app.command("ship", help="Create or refresh an upstream publish branch from the current task's Joan stage branch.")(ship_command)


@app.command()
def version() -> None:
    """Print the installed joan version."""
    typer.echo(importlib.metadata.version("joan"))


def main() -> None:
    app()
