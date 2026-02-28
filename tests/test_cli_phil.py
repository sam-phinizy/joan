from __future__ import annotations

from pathlib import Path
import sys
import types

import joan.cli.phil as phil_mod
from joan.core.models import AgentClaudeConfig, AgentConfig, AgentForgejoConfig, AgentServerConfig, AgentWorkerConfig
from typer.testing import CliRunner


def make_phil_config() -> AgentConfig:
    return AgentConfig(
        name="phil",
        forgejo=AgentForgejoConfig(token="phil-token"),
        server=AgentServerConfig(port=9000, host="0.0.0.0", webhook_secret="secret"),
        claude=AgentClaudeConfig(model="claude-sonnet-4-6"),
        worker=AgentWorkerConfig(
            enabled=True,
            api_url="http://127.0.0.1:9000",
            poll_interval_seconds=2.0,
            timeout_seconds=600.0,
            command=["codex"],
        ),
    )


def test_default_webhook_url_targets_host_gateway() -> None:
    assert phil_mod._default_webhook_url(9000) == "http://host.docker.internal:9000/webhook"


def test_phil_init_creates_agent_config(monkeypatch, tmp_path: Path) -> None:
    runner = CliRunner()

    prompts = iter(
        [
            "http://forgejo.local",
            "admin",
            "secret",
        ]
    )
    monkeypatch.setattr(phil_mod.typer, "prompt", lambda *_a, **_kw: next(prompts))

    class FakeForgejoClient:
        def __init__(self, _url):
            pass

        def create_user(self, **_kwargs):
            return {"id": 2, "login": "phil"}

        def create_token(self, **_kwargs):
            return "phil-token-xyz"

    written: list = []
    monkeypatch.setattr(phil_mod, "ForgejoClient", FakeForgejoClient)
    monkeypatch.setattr(
        phil_mod,
        "write_agent_config",
        lambda cfg, name, _cwd: written.append((cfg, name)) or (tmp_path / ".joan" / "agents" / "phil.toml"),
    )
    monkeypatch.setattr(phil_mod, "Path", type("FakePath", (), {"cwd": staticmethod(lambda: tmp_path)}))

    result = runner.invoke(phil_mod.app, ["init"])

    assert result.exit_code == 0, result.output
    assert len(written) == 1
    cfg, name = written[0]
    assert name == "phil"
    assert cfg.forgejo.token == "phil-token-xyz"
    assert cfg.worker.enabled is True
    assert cfg.worker.api_url == "http://127.0.0.1:9000"
    assert cfg.worker.command == ["codex"]
    assert "webhook" in result.output.lower()


def test_phil_init_existing_user(monkeypatch, tmp_path: Path) -> None:
    runner = CliRunner()

    prompts = iter(["http://forgejo.local", "admin", "secret"])
    monkeypatch.setattr(phil_mod.typer, "prompt", lambda *_a, **_kw: next(prompts))

    from joan.shell.forgejo_client import ForgejoError

    class FakeForgejoClient:
        def __init__(self, _url):
            pass

        def create_user(self, **_kwargs):
            raise ForgejoError("user already exists")

        def create_token(self, **_kwargs):
            return "phil-token-xyz"

    monkeypatch.setattr(phil_mod, "ForgejoClient", FakeForgejoClient)
    monkeypatch.setattr(
        phil_mod,
        "write_agent_config",
        lambda cfg, name, _cwd: (tmp_path / ".joan" / "agents" / "phil.toml"),
    )
    monkeypatch.setattr(phil_mod, "Path", type("FakePath", (), {"cwd": staticmethod(lambda: tmp_path)}))

    result = runner.invoke(phil_mod.app, ["init"])
    assert result.exit_code == 0, result.output
    assert "existing" in result.output.lower()


def test_phil_work_runs_loop(monkeypatch) -> None:
    runner = CliRunner()
    phil_config = make_phil_config()
    called: dict[str, object] = {}

    monkeypatch.setattr(phil_mod, "_load_configs", lambda: (object(), phil_config))

    def fake_run_worker_loop(api_url, runner_obj, poll_interval, stop_event=None):
        called["api_url"] = api_url
        called["runner"] = runner_obj
        called["poll_interval"] = poll_interval
        called["stop_event"] = stop_event

    monkeypatch.setattr(phil_mod, "run_worker_loop", fake_run_worker_loop)

    result = runner.invoke(phil_mod.app, ["work"])
    assert result.exit_code == 0, result.output
    assert called["api_url"] == "http://127.0.0.1:9000"
    assert called["poll_interval"] == 2.0
    assert called["stop_event"] is None


def test_phil_up_starts_server_and_worker(monkeypatch) -> None:
    runner = CliRunner()
    phil_config = make_phil_config()
    calls: dict[str, object] = {}

    monkeypatch.setattr(phil_mod, "_load_configs", lambda: (object(), phil_config))
    monkeypatch.setattr(phil_mod, "_repo_root", lambda: Path("/tmp/test-repo"))

    class FakeThread:
        def __init__(self, target, args, daemon, name):
            calls["thread_target"] = target
            calls["thread_args"] = args
            calls["thread_daemon"] = daemon
            calls["thread_name"] = name

        def start(self):
            calls["started"] = True

        def join(self, timeout=None):
            calls["join_timeout"] = timeout

    monkeypatch.setattr(phil_mod.threading, "Thread", FakeThread)

    class FakeStopEvent:
        def __init__(self):
            self.set_called = False

        def set(self):
            self.set_called = True
            calls["stop_set"] = True

    monkeypatch.setattr(phil_mod.threading, "Event", FakeStopEvent)

    class FakeUvicorn:
        @staticmethod
        def run(app_instance, host, port):
            calls["uvicorn_app"] = app_instance
            calls["uvicorn_host"] = host
            calls["uvicorn_port"] = port

    monkeypatch.setitem(sys.modules, "uvicorn", FakeUvicorn)

    sentinel_app = object()
    monkeypatch.setitem(
        sys.modules,
        "joan.phil.server",
        types.SimpleNamespace(create_app=lambda *_a, **_kw: sentinel_app),
    )

    result = runner.invoke(phil_mod.app, ["up", "--port", "9012"])
    assert result.exit_code == 0, result.output
    assert calls["started"] is True
    assert calls["uvicorn_app"] is sentinel_app
    assert calls["uvicorn_port"] == 9012
    assert calls["thread_args"][0] == "http://127.0.0.1:9012"
    assert calls["join_timeout"] == 5
    assert calls["stop_set"] is True
