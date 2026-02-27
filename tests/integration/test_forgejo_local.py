from __future__ import annotations

import os
from datetime import UTC, datetime

import httpx
import pytest

from joan.shell.forgejo_client import ForgejoClient, ForgejoError

pytestmark = pytest.mark.integration


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        pytest.skip(f"Missing required env var for integration test: {name}")
    return value


def _forgejo_available(url: str) -> bool:
    try:
        r = httpx.get(f"{url.rstrip('/')}/api/v1/version", timeout=2.0)
        return r.is_success
    except Exception:  # noqa: BLE001
        return False


def test_local_forgejo_create_token() -> None:
    url = os.getenv("FORGEJO_URL", "http://localhost:3000").strip()
    if not _forgejo_available(url):
        pytest.skip(f"Forgejo is not reachable at {url}")

    username = _required_env("FORGEJO_USERNAME")
    password = _required_env("FORGEJO_PASSWORD")

    bootstrap = ForgejoClient(url)
    token_name = f"joan-it-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}"
    token = bootstrap.create_token(username=username, password=password, token_name=token_name)

    assert token


def test_local_forgejo_token_auth_user_endpoint() -> None:
    url = os.getenv("FORGEJO_URL", "http://localhost:3000").strip()
    if not _forgejo_available(url):
        pytest.skip(f"Forgejo is not reachable at {url}")

    username = _required_env("FORGEJO_USERNAME")
    password = _required_env("FORGEJO_PASSWORD")

    bootstrap = ForgejoClient(url)
    token_name = f"joan-it-user-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}"
    token = bootstrap.create_token(username=username, password=password, token_name=token_name)

    authed = ForgejoClient(url, token)
    user_data = authed._request_json("GET", "/api/v1/user")

    assert isinstance(user_data, dict)
    assert user_data.get("login") == username

    repo = os.getenv("FORGEJO_REPO", "").strip()
    if repo:
        try:
            pulls = authed.list_pulls(username, repo)
        except ForgejoError as exc:
            pytest.skip(f"Skipping PR listing check for repo {repo}: {exc}")
        assert isinstance(pulls, list)
