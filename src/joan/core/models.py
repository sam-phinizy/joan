from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(slots=True)
class ForgejoConfig:
    url: str
    token: str
    owner: str
    repo: str


@dataclass(slots=True)
class RemotesConfig:
    review: str = "joan-review"
    upstream: str = "origin"


@dataclass(slots=True)
class Config:
    forgejo: ForgejoConfig
    remotes: RemotesConfig = field(default_factory=RemotesConfig)


@dataclass(slots=True)
class PullRequest:
    number: int
    title: str
    url: str
    state: str
    head_ref: str
    base_ref: str


@dataclass(slots=True)
class Review:
    id: int
    state: str
    submitted_at: datetime | None
    user: str


@dataclass(slots=True)
class Comment:
    id: int
    body: str
    path: str
    line: int | None
    resolved: bool
    author: str
    created_at: datetime | None


@dataclass(slots=True)
class PRSyncStatus:
    approved: bool
    unresolved_comments: int
    latest_review_state: str | None
