from __future__ import annotations

import socket
import subprocess
from pathlib import Path

import typer

from joan.cli._common import forgejo_client, load_config_or_exit
from joan.shell.forgejo_client import ForgejoError

app = typer.Typer(help="Manage SSH key setup for Forgejo access.")


@app.callback()
def ssh_app() -> None:
    """SSH-related commands."""
    return None


def _default_key_path() -> Path:
    return Path.home() / ".ssh" / "id_ed25519_joan"


def _ensure_keypair(private_key_path: Path, comment: str) -> bool:
    public_key_path = private_key_path.with_suffix(".pub")
    private_exists = private_key_path.exists()
    public_exists = public_key_path.exists()

    if private_exists and public_exists:
        return False
    if private_exists != public_exists:
        raise RuntimeError(
            f"Keypair is incomplete. Expected both {private_key_path} and {public_key_path} to exist."
        )

    private_key_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ssh-keygen",
        "-t",
        "ed25519",
        "-f",
        str(private_key_path),
        "-N",
        "",
        "-C",
        comment,
    ]
    proc = subprocess.run(cmd, check=False, text=True, capture_output=True)
    if proc.returncode != 0:
        msg = proc.stderr.strip() or proc.stdout.strip() or "ssh-keygen failed"
        raise RuntimeError(msg)
    return True


@app.command("setup")
def ssh_setup(
    key_path: Path = typer.Option(
        default_factory=_default_key_path,
        help="Private key path to create/use (public key uses the same path with .pub).",
    ),
    title: str | None = typer.Option(
        default=None,
        help="Forgejo SSH key title. Defaults to joan-<hostname>.",
    ),
) -> None:
    config = load_config_or_exit()
    key_path = key_path.expanduser().resolve()
    key_title = title or f"joan-{socket.gethostname()}"

    try:
        created = _ensure_keypair(key_path, comment=key_title)
    except RuntimeError as exc:
        typer.echo(f"SSH key setup failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    public_key_path = key_path.with_suffix(".pub")
    public_key = public_key_path.read_text(encoding="utf-8").strip()
    if not public_key:
        typer.echo(f"SSH key setup failed: {public_key_path} is empty", err=True)
        raise typer.Exit(code=1)

    client = forgejo_client(config)
    try:
        existing = client.list_ssh_keys()
        if any(str(item.get("key", "")).strip() == public_key for item in existing):
            if created:
                typer.echo(f"Created SSH keypair at {key_path}")
            else:
                typer.echo(f"Using existing SSH keypair at {key_path}")
            typer.echo("Public key already exists on Forgejo.")
            return
        client.create_ssh_key(title=key_title, key=public_key)
    except ForgejoError as exc:
        typer.echo(f"Forgejo SSH key upload failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    if created:
        typer.echo(f"Created SSH keypair at {key_path}")
    else:
        typer.echo(f"Using existing SSH keypair at {key_path}")
    typer.echo(f"Uploaded public key to Forgejo as '{key_title}'.")
