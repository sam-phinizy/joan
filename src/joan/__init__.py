from __future__ import annotations

import typer

from joan.cli.branch import app as branch_app
from joan.cli.forge import app as forge_app
from joan.cli.init import app as init_app
from joan.cli.pr import app as pr_app
from joan.cli.remote import app as remote_app
from joan.cli.ssh import app as ssh_app
from joan.cli.skills import app as skills_app
from joan.cli.worktree import app as worktree_app

app = typer.Typer(help="Joan: local code review gate for AI agents.")
app.add_typer(init_app)
app.add_typer(remote_app, name="remote")
app.add_typer(branch_app, name="branch")
app.add_typer(pr_app, name="pr")
app.add_typer(ssh_app, name="ssh")
app.add_typer(skills_app, name="skills")
app.add_typer(worktree_app, name="worktree")
app.add_typer(forge_app, name="forge")


def main() -> None:
    app()
