from __future__ import annotations

import hashlib
import hmac
import json
import subprocess
from importlib.resources import files
from typing import Any

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response

from joan.core.models import AgentConfig, Config
from joan.phil.work_queue import ReviewWorkQueue
from joan.shell.forgejo_client import ForgejoClient


def create_app(joan_config: Config, phil_config: AgentConfig, worker_mode: bool | None = None) -> FastAPI:
    app = FastAPI(title="phil", description="Phil AI code review bot")
    effective_worker_mode = phil_config.worker.enabled if worker_mode is None else worker_mode
    app.state.queue = ReviewWorkQueue()
    app.state.worker_mode = effective_worker_mode

    @app.get("/health")
    async def health() -> dict[str, Any]:
        stats = await app.state.queue.stats()
        return {
            "status": "ok",
            "agent": phil_config.name,
            "worker_mode": effective_worker_mode,
            **stats,
        }

    @app.post("/webhook")
    async def webhook(request: Request, background_tasks: BackgroundTasks) -> Response:
        body = await request.body()
        _validate_signature(request.headers.get("X-Gitea-Signature", ""), body, phil_config.server.webhook_secret)

        try:
            payload = json.loads(body)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail=f"Invalid JSON payload: {exc}") from exc

        if request.headers.get("X-Gitea-Event") != "pull_request":
            return JSONResponse(status_code=200, content={"status": "ignored"})

        action = payload.get("action")
        reviewer = payload.get("requested_reviewer", {}).get("login", "")
        pr_number = payload.get("pull_request", {}).get("number")
        if action != "review_requested" or reviewer != phil_config.name or not isinstance(pr_number, int):
            return JSONResponse(status_code=200, content={"status": "ignored"})

        repo_owner = payload.get("repository", {}).get("owner", {}).get("login", joan_config.forgejo.owner)
        repo_name = payload.get("repository", {}).get("name", joan_config.forgejo.repo)

        if effective_worker_mode:
            diff = ForgejoClient(joan_config.forgejo.url, joan_config.forgejo.token).get_pr_diff(
                str(repo_owner), str(repo_name), pr_number
            )
            prompt = build_review_job_prompt(diff, phil_config.name, str(repo_owner), str(repo_name), pr_number)
            job = await app.state.queue.enqueue_pr_review(str(repo_owner), str(repo_name), pr_number, prompt)
            return JSONResponse(status_code=202, content={"status": "accepted", "pr": pr_number, "job_id": job.id})

        background_tasks.add_task(run_review, joan_config, phil_config, str(repo_owner), str(repo_name), pr_number)
        return JSONResponse(status_code=202, content={"status": "accepted", "pr": pr_number})

    @app.post("/work/claim")
    async def work_claim() -> Response:
        job = await app.state.queue.claim_next()
        if job is None:
            return Response(status_code=204)
        return JSONResponse(status_code=200, content=app.state.queue.serialize_claim(job))

    @app.post("/work/{job_id}/complete")
    async def work_complete(job_id: str, payload: dict[str, Any]) -> dict[str, str]:
        transcript = str(payload.get("transcript", ""))
        try:
            await app.state.queue.complete(job_id, transcript)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=f"unknown job: {job_id}") from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=f"job is not claimed: {job_id}") from exc
        return {"status": "completed"}

    @app.post("/work/{job_id}/fail")
    async def work_fail(job_id: str, payload: dict[str, Any]) -> dict[str, str]:
        error = str(payload.get("error", "job failed"))
        transcript = payload.get("transcript")
        transcript_text = str(transcript) if transcript is not None else None
        try:
            await app.state.queue.fail(job_id, error, transcript_text)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=f"unknown job: {job_id}") from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=f"job is not claimed: {job_id}") from exc
        return {"status": "failed"}

    return app


def build_review_job_prompt(diff: str, agent_name: str, owner: str, repo: str, pr_number: int) -> str:
    system_prompt = _load_system_prompt().strip()
    inline_command = (
        f"joan pr comment add --agent {agent_name} --owner {owner} --repo {repo} "
        f"--pr {pr_number} --path <path> --line <line> --body \"<comment>\""
    )
    review_command = (
        f"joan pr review submit --agent {agent_name} --owner {owner} --repo {repo} "
        f"--pr {pr_number} --verdict <approve|request_changes|comment> --body \"<summary>\""
    )
    return (
        f"{system_prompt}\n\n"
        f"You are reviewing PR #{pr_number} for {owner}/{repo}.\n"
        "Use Joan CLI commands to post your findings.\n"
        "For each concrete issue, post one inline comment immediately using this shape:\n"
        f"{inline_command}\n\n"
        "When you are done, post exactly one final summary review using:\n"
        f"{review_command}\n\n"
        "Only post comments for real issues. After posting the final review, exit the CLI session.\n\n"
        "Review this diff:\n\n"
        f"```diff\n{diff}\n```"
    )


def run_review(
    joan_config: Config,
    phil_config: AgentConfig,
    owner: str,
    repo: str,
    pr_number: int,
) -> None:
    joan_client = ForgejoClient(joan_config.forgejo.url, joan_config.forgejo.token)
    diff = joan_client.get_pr_diff(owner, repo, pr_number)

    system_prompt = _load_system_prompt()
    raw_output = run_claude_review(diff, system_prompt, phil_config.claude.model)

    review = _parse_review_output(raw_output)
    if review is None:
        raise RuntimeError(f"invalid claude review output for PR #{pr_number}")

    phil_client = ForgejoClient(joan_config.forgejo.url, phil_config.forgejo.token)
    phil_client.create_review(
        owner=owner,
        repo=repo,
        index=pr_number,
        body=str(review.get("body", "")),
        verdict=str(review.get("verdict", "comment")),
        comments=list(review.get("comments", [])),
    )


def run_claude_review(diff: str, system_prompt: str, model: str) -> str:
    user_message = f"Please review the following git diff:\n\n```diff\n{diff}\n```"
    result = subprocess.run(
        ["claude", "--print", "--model", model, "--system", system_prompt, user_message],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"claude subprocess failed: {result.stderr.strip()}")
    return result.stdout


def _load_system_prompt() -> str:
    return files("joan.data.agents").joinpath("phil-system-prompt.txt").read_text(encoding="utf-8")


def _parse_review_output(raw: str) -> dict[str, Any] | None:
    payload = raw.strip()
    if payload.startswith("```"):
        lines = payload.splitlines()
        if len(lines) >= 3:
            payload = "\n".join(lines[1:-1])
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    return data


def _validate_signature(signature: str, body: bytes, secret: str) -> None:
    if not secret:
        return
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        raise HTTPException(status_code=403, detail="Invalid signature")
