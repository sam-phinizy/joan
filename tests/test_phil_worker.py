from __future__ import annotations

import threading

import pytest

from joan.phil import worker as worker_mod


def test_pty_agent_runner_captures_transcript(tmp_path) -> None:
    runner = worker_mod.PTYAgentRunner(
        ["/bin/sh", "-c", 'read line; echo "out:$line"; echo "err:$line" >&2'],
        timeout_seconds=2.0,
        workdir=tmp_path,
    )

    transcript = runner.run("hello world")

    assert "out:hello world" in transcript
    assert "err:hello world" in transcript


def test_pty_agent_runner_times_out(tmp_path) -> None:
    runner = worker_mod.PTYAgentRunner(
        ["/bin/sh", "-c", "sleep 5"],
        timeout_seconds=0.1,
        workdir=tmp_path,
    )

    with pytest.raises(worker_mod.AgentRunError, match="timed out"):
        runner.run("ignored")


def test_run_worker_loop_completes_job(monkeypatch) -> None:
    stop_event = threading.Event()
    calls: list[tuple[str, str]] = []
    job = worker_mod.WorkerJob(
        id="job_1",
        kind="pr_review",
        prompt="review me",
        owner="sam",
        repo="joan",
        pr_number=7,
    )

    class FakeClient:
        def claim(self):
            if calls:
                stop_event.set()
                return None
            return job

        def complete(self, job_id, transcript):
            calls.append((job_id, transcript))
            stop_event.set()

        def fail(self, job_id, error, transcript=""):
            raise AssertionError(f"unexpected fail {job_id} {error} {transcript}")

    class FakeRunner:
        def run(self, prompt):
            assert prompt == "review me"
            return "transcript"

    monkeypatch.setattr(worker_mod, "WorkerClient", lambda _api_url: FakeClient())

    worker_mod.run_worker_loop("http://127.0.0.1:9000", FakeRunner(), 0.01, stop_event)

    assert calls == [("job_1", "transcript")]


def test_run_worker_loop_reports_failures(monkeypatch) -> None:
    stop_event = threading.Event()
    failures: list[tuple[str, str, str]] = []
    job = worker_mod.WorkerJob(
        id="job_2",
        kind="pr_review",
        prompt="review me",
        owner="sam",
        repo="joan",
        pr_number=8,
    )

    class FakeClient:
        def claim(self):
            return job

        def complete(self, job_id, transcript):
            raise AssertionError(f"unexpected complete {job_id} {transcript}")

        def fail(self, job_id, error, transcript=""):
            failures.append((job_id, error, transcript))
            stop_event.set()

    class FakeRunner:
        def run(self, prompt):
            raise worker_mod.AgentRunError("boom", "partial")

    monkeypatch.setattr(worker_mod, "WorkerClient", lambda _api_url: FakeClient())

    worker_mod.run_worker_loop("http://127.0.0.1:9000", FakeRunner(), 0.01, stop_event)

    assert failures == [("job_2", "boom", "partial")]
