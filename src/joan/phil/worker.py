from __future__ import annotations

import errno
import os
import pty
import select
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path

import httpx


class WorkerClientError(RuntimeError):
    pass


class AgentRunError(RuntimeError):
    def __init__(self, message: str, transcript: str = "") -> None:
        super().__init__(message)
        self.transcript = transcript


@dataclass(slots=True)
class WorkerJob:
    id: str
    kind: str
    prompt: str
    owner: str
    repo: str
    pr_number: int


class WorkerClient:
    def __init__(self, base_url: str, timeout: float = 10.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def claim(self) -> WorkerJob | None:
        response = self._request("POST", "/work/claim")
        if response.status_code == 204:
            return None
        if response.status_code != 200:
            raise WorkerClientError(f"claim failed: HTTP {response.status_code} {response.text.strip()}")
        data = response.json()
        context = data.get("context", {})
        return WorkerJob(
            id=str(data["id"]),
            kind=str(data.get("kind", "")),
            prompt=str(data.get("prompt", "")),
            owner=str(context.get("owner", "")),
            repo=str(context.get("repo", "")),
            pr_number=int(context.get("pr_number", 0)),
        )

    def complete(self, job_id: str, transcript: str) -> None:
        response = self._request("POST", f"/work/{job_id}/complete", json={"transcript": transcript})
        if response.status_code != 200:
            raise WorkerClientError(f"complete failed: HTTP {response.status_code} {response.text.strip()}")

    def fail(self, job_id: str, error: str, transcript: str = "") -> None:
        payload = {"error": error}
        if transcript:
            payload["transcript"] = transcript
        response = self._request("POST", f"/work/{job_id}/fail", json=payload)
        if response.status_code != 200:
            raise WorkerClientError(f"fail failed: HTTP {response.status_code} {response.text.strip()}")

    def _request(self, method: str, path: str, **kwargs: object) -> httpx.Response:
        with httpx.Client(timeout=self.timeout) as client:
            return client.request(method, f"{self.base_url}{path}", **kwargs)


class PTYAgentRunner:
    def __init__(self, command: list[str], timeout_seconds: float, workdir: Path | None = None) -> None:
        self.command = command
        self.timeout_seconds = timeout_seconds
        self.workdir = workdir

    def run(self, prompt: str) -> str:
        if not self.command:
            raise AgentRunError("worker command is empty")

        master_fd, slave_fd = pty.openpty()
        proc: subprocess.Popen[bytes] | None = None
        transcript = bytearray()
        try:
            proc = subprocess.Popen(
                self.command,
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                cwd=str(self.workdir) if self.workdir is not None else None,
                start_new_session=True,
            )
            os.close(slave_fd)
            slave_fd = -1

            os.write(master_fd, prompt.encode("utf-8", errors="replace"))
            os.write(master_fd, b"\n")

            deadline = time.monotonic() + self.timeout_seconds
            while True:
                if time.monotonic() >= deadline:
                    proc.kill()
                    proc.wait(timeout=5)
                    raise AgentRunError("agent process timed out", transcript.decode("utf-8", errors="replace"))

                ready, _, _ = select.select([master_fd], [], [], 0.1)
                if ready:
                    chunk = self._read_chunk(master_fd)
                    if chunk:
                        transcript.extend(chunk)
                        continue

                if proc.poll() is not None:
                    while True:
                        chunk = self._read_chunk(master_fd)
                        if not chunk:
                            break
                        transcript.extend(chunk)
                    break

            output = transcript.decode("utf-8", errors="replace")
            if proc.returncode != 0:
                raise AgentRunError(f"agent process exited with status {proc.returncode}", output)
            return output
        except OSError as exc:
            if proc is not None and proc.poll() is None:
                proc.kill()
                proc.wait(timeout=5)
            raise AgentRunError(f"failed to run agent: {exc}", transcript.decode("utf-8", errors="replace")) from exc
        finally:
            if slave_fd >= 0:
                os.close(slave_fd)
            os.close(master_fd)

    @staticmethod
    def _read_chunk(master_fd: int) -> bytes:
        try:
            return os.read(master_fd, 4096)
        except OSError as exc:
            if exc.errno == errno.EIO:
                return b""
            raise


def run_worker_loop(
    api_url: str,
    runner: PTYAgentRunner,
    poll_interval_seconds: float,
    stop_event: threading.Event | None = None,
) -> None:
    client = WorkerClient(api_url)
    stopper = stop_event or threading.Event()

    while not stopper.is_set():
        try:
            job = client.claim()
        except (httpx.HTTPError, WorkerClientError):
            if stopper.wait(poll_interval_seconds):
                break
            continue

        if job is None:
            if stopper.wait(poll_interval_seconds):
                break
            continue

        try:
            transcript = runner.run(job.prompt)
            client.complete(job.id, transcript)
        except AgentRunError as exc:
            try:
                client.fail(job.id, str(exc), exc.transcript)
            except (httpx.HTTPError, WorkerClientError):
                pass
        except (httpx.HTTPError, WorkerClientError) as exc:
            try:
                client.fail(job.id, str(exc))
            except (httpx.HTTPError, WorkerClientError):
                pass
