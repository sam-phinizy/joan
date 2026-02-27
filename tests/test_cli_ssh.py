from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

import joan.cli.ssh as ssh_mod
from joan.core.models import Config, ForgejoConfig, RemotesConfig


def make_config() -> Config:
    return Config(
        forgejo=ForgejoConfig(url="http://forgejo.local", token="tok", owner="sam", repo="joan"),
        remotes=RemotesConfig(review="joan-review", upstream="origin"),
    )


def test_ssh_setup_creates_and_uploads(monkeypatch, tmp_path: Path) -> None:
    runner = CliRunner()
    key_path = tmp_path / "keys" / "id_ed25519_joan"

    class DummyProc:
        returncode = 0
        stdout = ""
        stderr = ""

    def fake_run(cmd, **_kwargs):
        assert cmd[0] == "ssh-keygen"
        key_path.write_text("private", encoding="utf-8")
        key_path.with_suffix(".pub").write_text("ssh-ed25519 AAA joan", encoding="utf-8")
        return DummyProc()

    class FakeClient:
        def list_ssh_keys(self):
            return []

        def create_ssh_key(self, **_kwargs):
            return {"id": 1}

    monkeypatch.setattr(ssh_mod, "load_config_or_exit", make_config)
    monkeypatch.setattr(ssh_mod, "forgejo_client", lambda _cfg: FakeClient())
    monkeypatch.setattr(ssh_mod.subprocess, "run", fake_run)

    result = runner.invoke(ssh_mod.app, ["setup", "--key-path", str(key_path), "--title", "joan-test"])
    assert result.exit_code == 0, result.output
    assert "Created SSH keypair" in result.output
    assert "Uploaded public key to Forgejo" in result.output


def test_ssh_setup_reuses_existing_and_skips_duplicate_upload(monkeypatch, tmp_path: Path) -> None:
    runner = CliRunner()
    key_path = tmp_path / "keys" / "id_ed25519_joan"
    key_path.parent.mkdir(parents=True, exist_ok=True)
    key_path.write_text("private", encoding="utf-8")
    key_path.with_suffix(".pub").write_text("ssh-ed25519 AAA joan", encoding="utf-8")

    class FakeClient:
        def list_ssh_keys(self):
            return [{"id": 3, "key": "ssh-ed25519 AAA joan"}]

        def create_ssh_key(self, **_kwargs):
            raise AssertionError("create_ssh_key should not be called for duplicates")

    monkeypatch.setattr(ssh_mod, "load_config_or_exit", make_config)
    monkeypatch.setattr(ssh_mod, "forgejo_client", lambda _cfg: FakeClient())

    result = runner.invoke(ssh_mod.app, ["setup", "--key-path", str(key_path)])
    assert result.exit_code == 0, result.output
    assert "Using existing SSH keypair" in result.output
    assert "Public key already exists on Forgejo." in result.output
