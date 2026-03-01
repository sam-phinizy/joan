from __future__ import annotations

import json
from datetime import UTC, datetime

from joan.core.forgejo import (
    _parse_dt,
    build_create_pr_payload,
    build_create_repo_payload,
    compute_sync_status,
    format_comments_json,
    format_reviews_json,
    parse_comments,
    parse_pr_response,
    parse_reviews,
)
from joan.core.models import Comment, Review


def test_payload_builders() -> None:
    assert build_create_repo_payload("repo") == {"name": "repo", "private": True}
    assert build_create_repo_payload("repo", private=False) == {"name": "repo", "private": False}

    assert build_create_pr_payload("t", "h", "b") == {"title": "t", "head": "h", "base": "b"}
    assert build_create_pr_payload("t", "h", "b", body="desc") == {
        "title": "t",
        "head": "h",
        "base": "b",
        "body": "desc",
    }


def test_parse_pr_response() -> None:
    pr = parse_pr_response(
        {
            "number": 12,
            "title": "Hello",
            "html_url": "http://x/pull/12",
            "state": "open",
            "head": {"ref": "feature"},
            "base": {"ref": "main"},
        }
    )
    assert pr.number == 12
    assert pr.title == "Hello"
    assert pr.url.endswith("/12")
    assert pr.head_ref == "feature"
    assert pr.base_ref == "main"


def test_parse_reviews_and_comments() -> None:
    reviews = parse_reviews(
        [
            {
                "id": 1,
                "state": "APPROVED",
                "body": "some body text",
                "submitted_at": "2026-02-27T00:00:00Z",
                "user": {"login": "sam"},
            }
        ]
    )
    comments = parse_comments(
        [
            {
                "id": 3,
                "body": "Fix this",
                "path": "src/a.py",
                "line": 9,
                "resolved": False,
                "created_at": "2026-02-27T00:00:00Z",
                "user": {"login": "reviewer"},
            }
        ]
    )

    assert reviews[0].submitted_at == datetime(2026, 2, 27, 0, 0, tzinfo=UTC)
    assert reviews[0].body == "some body text"
    assert comments[0].created_at == datetime(2026, 2, 27, 0, 0, tzinfo=UTC)
    assert comments[0].author == "reviewer"


def test_compute_sync_status() -> None:
    reviews = [
        Review(id=1, state="COMMENTED", body="", submitted_at=None, user="a"),
        Review(id=2, state="APPROVED", body="", submitted_at=None, user="b"),
    ]
    comments = [
        Comment(id=1, body="x", path="f", line=1, resolved=False, author="a", created_at=None),
        Comment(id=2, body="y", path="f", line=2, resolved=True, author="a", created_at=None),
    ]
    status = compute_sync_status(reviews, comments)
    assert status.approved is True
    assert status.unresolved_comments == 1
    assert status.latest_review_state == "APPROVED"


def test_format_comments_json_filters_resolved() -> None:
    comments = [
        Comment(
            id=1,
            body="open",
            path="x",
            line=1,
            resolved=False,
            author="a",
            created_at=datetime(2026, 2, 27, tzinfo=UTC),
        ),
        Comment(
            id=2,
            body="closed",
            path="x",
            line=2,
            resolved=True,
            author="a",
            created_at=datetime(2026, 2, 27, tzinfo=UTC),
        ),
    ]

    unresolved = json.loads(format_comments_json(comments, include_resolved=False))
    all_comments = json.loads(format_comments_json(comments, include_resolved=True))

    assert len(unresolved) == 1
    assert unresolved[0]["id"] == 1
    assert unresolved[0]["created_at"].endswith("Z")
    assert len(all_comments) == 2


def test_parse_dt_handles_invalid_values() -> None:
    assert _parse_dt(None) is None
    assert _parse_dt("") is None
    assert _parse_dt("not-a-date") is None


def test_format_reviews_json_returns_expected_shape() -> None:
    reviews = [
        Review(
            id=7,
            state="REQUESTED_CHANGES",
            body="Please fix the auth module",
            submitted_at=datetime(2026, 2, 28, 14, 0, 0, tzinfo=UTC),
            user="reviewer",
        )
    ]
    payload = json.loads(format_reviews_json(reviews))
    assert len(payload) == 1
    assert payload[0]["id"] == 7
    assert payload[0]["state"] == "REQUESTED_CHANGES"
    assert payload[0]["body"] == "Please fix the auth module"
    assert payload[0]["author"] == "reviewer"
    assert payload[0]["submitted_at"] == "2026-02-28T14:00:00Z"


def test_format_reviews_json_handles_none_submitted_at() -> None:
    reviews = [
        Review(id=3, state="APPROVED", body="", submitted_at=None, user="reviewer")
    ]
    payload = json.loads(format_reviews_json(reviews))
    assert payload[0]["id"] == 3
    assert payload[0]["state"] == "APPROVED"
    assert payload[0]["author"] == "reviewer"
    assert payload[0]["body"] == ""
    assert payload[0]["submitted_at"] is None


def test_format_reviews_json_empty_list() -> None:
    assert json.loads(format_reviews_json([])) == []
