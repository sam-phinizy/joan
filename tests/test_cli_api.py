from __future__ import annotations

import joan
import joan.cli.api as api_mod
from joan.core.models import Config, ForgejoConfig, RemotesConfig
from typer.testing import CliRunner


def make_config() -> Config:
    return Config(
        forgejo=ForgejoConfig(url="http://forgejo.local", token="tok", owner="sam", repo="joan"),
        remotes=RemotesConfig(review="joan-review", upstream="origin"),
    )


def test_api_accepts_data_flag_after_positional_args(monkeypatch) -> None:
    runner = CliRunner()
    config = make_config()
    captured: dict = {}

    class FakeResponse:
        is_success = True
        status_code = 200
        text = '{"ok": true}'

    class FakeClient:
        def _request_raw(self, method, path, **kwargs):
            captured["method"] = method
            captured["path"] = path
            captured["kwargs"] = kwargs
            return FakeResponse()

    monkeypatch.setattr(api_mod, "load_config_or_exit", lambda: config)
    monkeypatch.setattr(api_mod, "forgejo_client", lambda _cfg: FakeClient())

    result = runner.invoke(
        joan.app,
        [
            "api",
            "PATCH",
            "/api/v1/repos/{owner}/{repo}/issues/5",
            "-d",
            '{"body":"test"}',
        ],
    )

    assert result.exit_code == 0, result.output
    assert captured == {
        "method": "PATCH",
        "path": "/api/v1/repos/sam/joan/issues/5",
        "kwargs": {"json": {"body": "test"}},
    }


def test_api_accepts_query_flag_after_positional_args(monkeypatch) -> None:
    runner = CliRunner()
    config = make_config()
    captured: dict = {}

    class FakeResponse:
        is_success = True
        status_code = 200
        text = '{"ok": true}'

    class FakeClient:
        def _request_raw(self, method, path, **kwargs):
            captured["method"] = method
            captured["path"] = path
            captured["kwargs"] = kwargs
            return FakeResponse()

    monkeypatch.setattr(api_mod, "load_config_or_exit", lambda: config)
    monkeypatch.setattr(api_mod, "forgejo_client", lambda _cfg: FakeClient())

    result = runner.invoke(
        joan.app,
        [
            "api",
            "GET",
            "/api/v1/repos/{owner}/{repo}/pulls",
            "-q",
            "state=closed",
            "-q",
            "limit=5",
        ],
    )

    assert result.exit_code == 0, result.output
    assert captured == {
        "method": "GET",
        "path": "/api/v1/repos/sam/joan/pulls",
        "kwargs": {"params": {"state": "closed", "limit": "5"}},
    }


def test_api_swagger_returns_json_document(monkeypatch) -> None:
    runner = CliRunner()
    config = make_config()
    calls: list[tuple[str, str]] = []

    class FakeResponse:
        def __init__(self, status_code: int, text: str) -> None:
            self.status_code = status_code
            self.text = text
            self.is_success = 200 <= status_code < 300

    class FakeClient:
        def _request_raw(self, method, path, **_kwargs):
            calls.append((method, path))
            if path == "/swagger.v1.json":
                return FakeResponse(200, '{"openapi":"3.0.0","info":{"title":"Forgejo"}}')
            return FakeResponse(404, "not found")

    monkeypatch.setattr(api_mod, "load_config_or_exit", lambda: config)
    monkeypatch.setattr(api_mod, "forgejo_client", lambda _cfg: FakeClient())

    result = runner.invoke(joan.app, ["api", "swagger"])

    assert result.exit_code == 0, result.output
    assert '"openapi": "3.0.0"' in result.output
    assert calls[0] == ("GET", "/swagger.v1.json")
