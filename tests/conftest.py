from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest

from joan.core.models import Comment, Config, ForgejoConfig, PullRequest, RemotesConfig, Review


@pytest.fixture
def sample_config() -> Config:
    return Config(
        forgejo=ForgejoConfig(
            url="http://forgejo.local",
            token="token-123",
            owner="sam",
            repo="joan",
        ),
        remotes=RemotesConfig(review="joan-review", upstream="origin"),
    )


@pytest.fixture
def sample_pr() -> PullRequest:
    return PullRequest(
        number=7,
        title="Demo",
        url="http://forgejo.local/sam/joan/pulls/7",
        state="open",
        head_ref="codex/demo",
        base_ref="main",
    )


@pytest.fixture
def sample_reviews() -> list[Review]:
    return [
        Review(id=1, state="COMMENTED", body="", submitted_at=datetime(2026, 2, 27, tzinfo=UTC), user="r1"),
        Review(id=2, state="APPROVED", body="", submitted_at=datetime(2026, 2, 27, tzinfo=UTC), user="r2"),
    ]


@pytest.fixture
def sample_comments() -> list[Comment]:
    return [
        Comment(
            id=10,
            body="nit",
            path="src/file.py",
            line=3,
            resolved=False,
            author="r1",
            created_at=datetime(2026, 2, 27, tzinfo=UTC),
        ),
        Comment(
            id=11,
            body="done",
            path="src/file.py",
            line=5,
            resolved=True,
            author="r2",
            created_at=datetime(2026, 2, 27, tzinfo=UTC),
        ),
    ]


def httpx_response(status: int, body: str = "", json_data: object | None = None) -> httpx.Response:
    request = httpx.Request("GET", "http://forgejo.local/api")
    if json_data is not None:
        return httpx.Response(status, request=request, json=json_data)
    return httpx.Response(status, request=request, text=body)
