from __future__ import annotations

import json
from datetime import datetime

from joan.core.models import Comment, PRSyncStatus, PullRequest, Review


def build_create_repo_payload(name: str, private: bool = True) -> dict:
    return {"name": name, "private": private}


def build_create_pr_payload(title: str, head: str, base: str, body: str | None = None) -> dict:
    payload = {"title": title, "head": head, "base": base}
    if body:
        payload["body"] = body
    return payload


def parse_pr_response(raw: dict) -> PullRequest:
    return PullRequest(
        number=int(raw["number"]),
        title=str(raw.get("title", "")),
        url=str(raw.get("html_url", "")),
        state=str(raw.get("state", "")),
        head_ref=str(raw.get("head", {}).get("ref", "")),
        base_ref=str(raw.get("base", {}).get("ref", "")),
    )


def parse_reviews(raw_reviews: list[dict]) -> list[Review]:
    return [
        Review(
            id=int(item["id"]),
            state=str(item.get("state", "")),
            submitted_at=_parse_dt(item.get("submitted_at")),
            user=str(item.get("user", {}).get("login", "")),
        )
        for item in raw_reviews
    ]


def parse_comments(raw_comments: list[dict]) -> list[Comment]:
    out: list[Comment] = []
    for item in raw_comments:
        out.append(
            Comment(
                id=int(item["id"]),
                body=str(item.get("body", "")),
                path=str(item.get("path", "")),
                line=item.get("line"),
                resolved=bool(item.get("resolved", False)),
                author=str(item.get("user", {}).get("login", "")),
                created_at=_parse_dt(item.get("created_at")),
            )
        )
    return out


def compute_sync_status(reviews: list[Review], comments: list[Comment]) -> PRSyncStatus:
    latest_state = reviews[-1].state if reviews else None
    approved = any(r.state.upper() == "APPROVED" for r in reviews)
    unresolved = sum(1 for c in comments if not c.resolved)
    return PRSyncStatus(
        approved=approved,
        unresolved_comments=unresolved,
        latest_review_state=latest_state,
    )


def format_comments_json(comments: list[Comment], include_resolved: bool = False) -> str:
    selected = comments if include_resolved else [c for c in comments if not c.resolved]
    payload = [
        {
            "id": c.id,
            "body": c.body,
            "path": c.path,
            "line": c.line,
            "resolved": c.resolved,
            "author": c.author,
            "created_at": c.created_at.isoformat().replace("+00:00", "Z") if c.created_at else None,
        }
        for c in selected
    ]
    return json.dumps(payload, indent=2)


def _parse_dt(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
