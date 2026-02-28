from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from uuid import uuid4


@dataclass(slots=True)
class ReviewJob:
    id: str
    kind: str
    status: str
    created_at: datetime
    claimed_at: datetime | None
    completed_at: datetime | None
    failed_at: datetime | None
    owner: str
    repo: str
    pr_number: int
    prompt: str
    transcript: str | None = None
    error: str | None = None


class ReviewWorkQueue:
    def __init__(self) -> None:
        self._pending: deque[str] = deque()
        self._jobs: dict[str, ReviewJob] = {}
        self._claimed: set[str] = set()
        self._lock = asyncio.Lock()

    async def enqueue_pr_review(self, owner: str, repo: str, pr_number: int, prompt: str) -> ReviewJob:
        async with self._lock:
            job = ReviewJob(
                id=f"job_{uuid4().hex}",
                kind="pr_review",
                status="pending",
                created_at=datetime.now(UTC),
                claimed_at=None,
                completed_at=None,
                failed_at=None,
                owner=owner,
                repo=repo,
                pr_number=pr_number,
                prompt=prompt,
            )
            self._jobs[job.id] = job
            self._pending.append(job.id)
            return job

    async def claim_next(self) -> ReviewJob | None:
        async with self._lock:
            if not self._pending:
                return None
            job_id = self._pending.popleft()
            job = self._jobs[job_id]
            job.status = "claimed"
            job.claimed_at = datetime.now(UTC)
            self._claimed.add(job_id)
            return job

    async def complete(self, job_id: str, transcript: str) -> ReviewJob:
        async with self._lock:
            job = self._require_claimed(job_id)
            job.status = "completed"
            job.completed_at = datetime.now(UTC)
            job.transcript = transcript
            self._claimed.remove(job_id)
            return job

    async def fail(self, job_id: str, error: str, transcript: str | None = None) -> ReviewJob:
        async with self._lock:
            job = self._require_claimed(job_id)
            job.status = "failed"
            job.failed_at = datetime.now(UTC)
            job.error = error
            job.transcript = transcript
            self._claimed.remove(job_id)
            return job

    async def stats(self) -> dict[str, int]:
        async with self._lock:
            failed = sum(1 for job in self._jobs.values() if job.status == "failed")
            return {
                "queue_depth": len(self._pending),
                "claimed": len(self._claimed),
                "failed": failed,
            }

    def serialize_claim(self, job: ReviewJob) -> dict[str, object]:
        return {
            "id": job.id,
            "kind": job.kind,
            "prompt": job.prompt,
            "context": {
                "owner": job.owner,
                "repo": job.repo,
                "pr_number": job.pr_number,
            },
        }

    def snapshot(self, job_id: str) -> dict[str, object]:
        job = self._jobs[job_id]
        payload = asdict(job)
        for key in ("created_at", "claimed_at", "completed_at", "failed_at"):
            value = payload.get(key)
            if isinstance(value, datetime):
                payload[key] = value.isoformat().replace("+00:00", "Z")
        return payload

    def _require_claimed(self, job_id: str) -> ReviewJob:
        if job_id not in self._jobs:
            raise KeyError(job_id)
        if job_id not in self._claimed:
            raise ValueError(job_id)
        return self._jobs[job_id]
