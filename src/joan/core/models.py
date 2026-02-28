from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(slots=True)
class ForgejoConfig:
    url: str
    token: str
    owner: str
    repo: str
    human_user: str | None = None


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


@dataclass(slots=True)
class AgentForgejoConfig:
    token: str


@dataclass(slots=True)
class AgentServerConfig:
    port: int = 9000
    host: str = "0.0.0.0"
    webhook_secret: str = ""


@dataclass(slots=True)
class AgentClaudeConfig:
    model: str = "claude-sonnet-4-6"


def default_worker_command() -> list[str]:
    return ["codex"]


@dataclass(slots=True)
class AgentWorkerConfig:
    enabled: bool = False
    api_url: str = ""
    poll_interval_seconds: float = 2.0
    timeout_seconds: float = 600.0
    command: list[str] = field(default_factory=default_worker_command)


@dataclass(slots=True)
class AgentConfig:
    name: str
    forgejo: AgentForgejoConfig
    server: AgentServerConfig = field(default_factory=AgentServerConfig)
    claude: AgentClaudeConfig = field(default_factory=AgentClaudeConfig)
    worker: AgentWorkerConfig = field(default_factory=AgentWorkerConfig)
