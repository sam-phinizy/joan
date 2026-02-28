from __future__ import annotations

import hashlib
import hmac
import json

import pytest
from fastapi.testclient import TestClient

from joan.core.models import (
    AgentClaudeConfig,
    AgentConfig,
    AgentForgejoConfig,
    AgentServerConfig,
    AgentWorkerConfig,
    Config,
    ForgejoConfig,
    RemotesConfig,
)
from joan.phil import server as server_mod


@pytest.fixture
def joan_config() -> Config:
    return Config(
        forgejo=ForgejoConfig(url="http://forgejo.local", token="joan-tok", owner="sam", repo="myrepo"),
        remotes=RemotesConfig(),
    )


@pytest.fixture
def phil_config() -> AgentConfig:
    return AgentConfig(
        name="phil",
        forgejo=AgentForgejoConfig(token="phil-tok"),
        server=AgentServerConfig(port=9000, host="0.0.0.0", webhook_secret="test-secret"),
        claude=AgentClaudeConfig(model="claude-sonnet-4-6"),
        worker=AgentWorkerConfig(
            enabled=True,
            api_url="http://127.0.0.1:9000",
            poll_interval_seconds=2.0,
            timeout_seconds=600.0,
            command=["codex"],
        ),
    )


def sign_payload(body: bytes, secret: str) -> str:
    sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={sig}"


def test_health_endpoint_includes_queue_stats(joan_config, phil_config) -> None:
    app = server_mod.create_app(joan_config, phil_config, worker_mode=True)
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["agent"] == "phil"
    assert payload["worker_mode"] is True
    assert payload["queue_depth"] == 0
    assert payload["claimed"] == 0
    assert payload["failed"] == 0


def test_webhook_ignores_non_review_requested(joan_config, phil_config) -> None:
    app = server_mod.create_app(joan_config, phil_config, worker_mode=True)
    client = TestClient(app)

    payload = {"action": "opened", "pull_request": {"number": 1}}
    body = json.dumps(payload).encode()
    sig = sign_payload(body, "test-secret")

    resp = client.post(
        "/webhook",
        content=body,
        headers={
            "X-Gitea-Event": "pull_request",
            "X-Gitea-Signature": sig,
            "Content-Type": "application/json",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "ignored"


def test_webhook_rejects_bad_signature(joan_config, phil_config) -> None:
    app = server_mod.create_app(joan_config, phil_config, worker_mode=True)
    client = TestClient(app)

    payload = {"action": "review_requested"}
    body = json.dumps(payload).encode()

    resp = client.post(
        "/webhook",
        content=body,
        headers={
            "X-Gitea-Event": "pull_request",
            "X-Gitea-Signature": "sha256=bad",
            "Content-Type": "application/json",
        },
    )
    assert resp.status_code == 403


def test_webhook_enqueues_job_in_worker_mode(monkeypatch, joan_config, phil_config) -> None:
    class FakeForgejoClient:
        def __init__(self, _url, _token=None):
            pass

        def get_pr_diff(self, owner, repo, index):
            assert owner == "sam"
            assert repo == "myrepo"
            assert index == 5
            return "diff --git a/foo.py b/foo.py\n+new"

    monkeypatch.setattr(server_mod, "ForgejoClient", FakeForgejoClient)

    app = server_mod.create_app(joan_config, phil_config, worker_mode=True)
    client = TestClient(app, raise_server_exceptions=True)

    payload = {
        "action": "review_requested",
        "pull_request": {"number": 5},
        "requested_reviewer": {"login": "phil"},
        "repository": {"owner": {"login": "sam"}, "name": "myrepo"},
    }
    body = json.dumps(payload).encode()
    sig = sign_payload(body, "test-secret")

    resp = client.post(
        "/webhook",
        content=body,
        headers={
            "X-Gitea-Event": "pull_request",
            "X-Gitea-Signature": sig,
            "Content-Type": "application/json",
        },
    )
    assert resp.status_code == 202
    payload = resp.json()
    assert payload["status"] == "accepted"
    assert payload["pr"] == 5
    assert payload["job_id"].startswith("job_")

    claim = client.post("/work/claim")
    assert claim.status_code == 200
    claimed = claim.json()
    assert claimed["kind"] == "pr_review"
    assert claimed["context"]["pr_number"] == 5
    assert "joan pr comment add" in claimed["prompt"]
    assert "joan pr review submit" in claimed["prompt"]


def test_work_claim_returns_204_when_empty(joan_config, phil_config) -> None:
    app = server_mod.create_app(joan_config, phil_config, worker_mode=True)
    client = TestClient(app)
    resp = client.post("/work/claim")
    assert resp.status_code == 204


def test_work_complete_and_fail_update_state(monkeypatch, joan_config, phil_config) -> None:
    class FakeForgejoClient:
        def __init__(self, _url, _token=None):
            pass

        def get_pr_diff(self, _owner, _repo, _index):
            return "diff --git a/foo.py b/foo.py\n+new"

    monkeypatch.setattr(server_mod, "ForgejoClient", FakeForgejoClient)
    app = server_mod.create_app(joan_config, phil_config, worker_mode=True)
    client = TestClient(app)

    queue = app.state.queue
    payload = {
        "action": "review_requested",
        "pull_request": {"number": 5},
        "requested_reviewer": {"login": "phil"},
        "repository": {"owner": {"login": "sam"}, "name": "myrepo"},
    }
    body = json.dumps(payload).encode()
    sig = sign_payload(body, "test-secret")
    resp = client.post(
        "/webhook",
        content=body,
        headers={
            "X-Gitea-Event": "pull_request",
            "X-Gitea-Signature": sig,
            "Content-Type": "application/json",
        },
    )
    assert resp.status_code == 202

    claim = client.post("/work/claim")
    job_id = claim.json()["id"]

    complete = client.post(f"/work/{job_id}/complete", json={"transcript": "all done"})
    assert complete.status_code == 200
    snapshot = queue.snapshot(job_id)
    assert snapshot["status"] == "completed"
    assert snapshot["transcript"] == "all done"

    payload["pull_request"]["number"] = 6
    body_2 = json.dumps(payload).encode()
    sig_2 = sign_payload(body_2, "test-secret")
    resp_2 = client.post(
        "/webhook",
        content=body_2,
        headers={
            "X-Gitea-Event": "pull_request",
            "X-Gitea-Signature": sig_2,
            "Content-Type": "application/json",
        },
    )
    assert resp_2.status_code == 202
    claim_2 = client.post("/work/claim")
    job_2 = claim_2.json()["id"]
    fail = client.post(f"/work/{job_2}/fail", json={"error": "boom", "transcript": "partial"})
    assert fail.status_code == 200
    snapshot_2 = queue.snapshot(job_2)
    assert snapshot_2["status"] == "failed"
    assert snapshot_2["error"] == "boom"
    assert snapshot_2["transcript"] == "partial"


def test_work_complete_rejects_unknown_job(joan_config, phil_config) -> None:
    app = server_mod.create_app(joan_config, phil_config, worker_mode=True)
    client = TestClient(app)
    resp = client.post("/work/job_missing/complete", json={"transcript": "done"})
    assert resp.status_code == 404


def test_webhook_falls_back_to_direct_review_when_worker_mode_disabled(monkeypatch, joan_config, phil_config) -> None:
    called: list[tuple[str, str, int]] = []

    def fake_run_review(_joan, _phil, owner, repo, pr_number):
        called.append((owner, repo, pr_number))

    monkeypatch.setattr(server_mod, "run_review", fake_run_review)

    app = server_mod.create_app(joan_config, phil_config, worker_mode=False)
    client = TestClient(app, raise_server_exceptions=True)

    payload = {
        "action": "review_requested",
        "pull_request": {"number": 5},
        "requested_reviewer": {"login": "phil"},
        "repository": {"owner": {"login": "sam"}, "name": "myrepo"},
    }
    body = json.dumps(payload).encode()
    sig = sign_payload(body, "test-secret")

    resp = client.post(
        "/webhook",
        content=body,
        headers={
            "X-Gitea-Event": "pull_request",
            "X-Gitea-Signature": sig,
            "Content-Type": "application/json",
        },
    )
    assert resp.status_code == 202
    assert called == [("sam", "myrepo", 5)]
