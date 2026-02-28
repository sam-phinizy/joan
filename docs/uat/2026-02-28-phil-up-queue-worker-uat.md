# UAT Script: Phil `up` Queue Worker Flow

## Purpose

Validate the new Phil runtime introduced on February 28, 2026:

- `joan phil up` starts the Phil webhook server and one worker
- Forgejo webhooks enqueue work in memory
- one worker processes jobs serially
- Phil can post inline comments with `joan pr comment add`
- Phil can post a final verdict with `joan pr review submit`

This is a manual user-acceptance test for a local ephemeral setup.

## Scope

In scope:

- Phil initialization
- server + worker startup
- webhook acceptance
- queue claim/complete behavior
- targeted PR comment/review commands
- basic end-to-end review loop

Out of scope:

- persistence across restarts
- multi-worker behavior
- production deployment

## Preconditions

- Python 3.13+
- `uv` installed
- Docker running
- a local Forgejo instance available
- a git repo initialized with Joan (`.joan/config.toml` exists)
- a test PR open in the local Forgejo repo
- access to a local agent CLI that can be used as Phil's worker command

Recommended:

- use a throwaway test repo and test PR
- use a simple worker command first if you want to validate queue mechanics before testing a real AI CLI

## Test Data

Use these placeholders during the test:

- Forgejo URL: `http://localhost:3000`
- Repo owner: `<owner>`
- Repo name: `<repo>`
- Test PR number: `<pr_number>`

## Phase 1: Setup Validation

### 1. Initialize Phil

Run:

```bash
uv run joan phil init
```

Expected result:

- command exits successfully
- `.joan/agents/phil.toml` is created
- the file contains:
  - `[forgejo]`
  - `[server]`
  - `[worker]`
- `[worker]` defaults should include:
  - `enabled = true`
  - `api_url = "http://127.0.0.1:9000"`
  - `poll_interval_seconds = 2.0`
  - `timeout_seconds = 600.0`
  - `command = ["codex"]`

Pass criteria:

- Phil config exists and includes the worker section

### 2. Set a Known Test Worker Command

Before testing the queue, set a deterministic worker command in `.joan/agents/phil.toml`.

Recommended temporary command:

```toml
command = ["/bin/sh", "-lc", "cat >/tmp/phil_prompt.txt; printf 'worker received prompt\n'"]
```

Expected result:

- the worker can run without depending on a real AI CLI
- `/tmp/phil_prompt.txt` captures the exact prompt Phil received

Pass criteria:

- the command is saved and Phil can launch it

## Phase 2: Runtime Validation

### 3. Start Phil

Run:

```bash
uv run joan phil up
```

Expected result:

- command stays running
- stdout shows the server bind address
- stdout shows the worker polling URL
- no immediate crash

Pass criteria:

- Phil remains running and idle

### 4. Verify Health Endpoint

In a second terminal, run:

```bash
curl -s http://127.0.0.1:9000/health
```

Expected result:

- HTTP 200
- JSON includes:
  - `"status": "ok"`
  - `"agent": "phil"`
  - `"worker_mode": true`
  - `"queue_depth": 0`

Pass criteria:

- health endpoint reports queue mode correctly

## Phase 3: Queue Mechanics

### 5. Trigger a Review Request Webhook

In a second terminal, send a test webhook payload. Use the `webhook_secret` from `.joan/agents/phil.toml` to generate the signature.

Example payload:

```json
{
  "action": "review_requested",
  "pull_request": { "number": <pr_number> },
  "requested_reviewer": { "login": "phil" },
  "repository": {
    "owner": { "login": "<owner>" },
    "name": "<repo>"
  }
}
```

Expected result:

- webhook returns HTTP 202
- response includes:
  - `"status": "accepted"`
  - `"pr": <pr_number>`
  - `"job_id": "..."`

Pass criteria:

- Phil accepts the webhook and enqueues a job

### 6. Confirm the Worker Processes the Job

Watch the `joan phil up` terminal.

Expected result:

- worker claims the queued job
- the temporary worker command runs
- `/tmp/phil_prompt.txt` is created
- the job completes without manual intervention

Then re-check health:

```bash
curl -s http://127.0.0.1:9000/health
```

Expected result:

- `"queue_depth": 0`
- `"claimed": 0`

Pass criteria:

- one queued job is processed to completion and the queue drains

### 7. Validate Prompt Content

Inspect the prompt captured by the temporary worker:

```bash
cat /tmp/phil_prompt.txt
```

Expected result:

- prompt includes Phil's review persona/system guidance
- prompt includes the PR number, owner, and repo
- prompt includes:
  - `joan pr comment add`
  - `joan pr review submit`
- prompt includes the diff

Pass criteria:

- prompt contains the expected control instructions for the agent

## Phase 4: Targeted Command Validation

### 8. Validate Inline Comment Command

Run:

```bash
uv run joan pr comment add \
  --agent phil \
  --owner <owner> \
  --repo <repo> \
  --pr <pr_number> \
  --path <changed_file_path> \
  --line <changed_line_number> \
  --body "UAT inline comment"
```

Expected result:

- command exits successfully
- output confirms the inline comment was posted
- the comment appears on the PR in Forgejo as `phil`

Pass criteria:

- a real inline PR comment is created and attributed to Phil

### 9. Validate Final Review Command

Run:

```bash
uv run joan pr review submit \
  --agent phil \
  --owner <owner> \
  --repo <repo> \
  --pr <pr_number> \
  --verdict comment \
  --body "UAT final review"
```

Expected result:

- command exits successfully
- output confirms the review was posted
- the review appears on the PR in Forgejo as `phil`

Pass criteria:

- a final review verdict is created and attributed to Phil

## Phase 5: End-to-End AI Worker Validation

### 10. Switch to a Real Agent Command

Replace the temporary test worker command in `.joan/agents/phil.toml` with a real CLI, for example:

```toml
command = ["codex"]
```

or:

```toml
command = ["claude"]
```

Restart Phil:

```bash
uv run joan phil up
```

Expected result:

- Phil starts successfully with the real worker command

Pass criteria:

- worker process launches with the intended agent CLI

### 11. Run an End-to-End Review

Trigger another `review_requested` webhook on the same PR or a fresh test PR.

Expected result:

- the worker claims the job
- the agent posts zero or more inline comments with `joan pr comment add`
- the agent posts one final review with `joan pr review submit`
- the job finishes and the queue drains

Pass criteria:

- the full review cycle completes without manual intervention

## Negative Tests

### 12. Invalid Signature

Send the webhook with a bad `X-Gitea-Signature`.

Expected result:

- HTTP 403
- no job is enqueued

Pass criteria:

- invalid webhooks are rejected

### 13. Unknown Job Completion

Call:

```bash
curl -s -X POST http://127.0.0.1:9000/work/job_missing/complete \
  -H 'Content-Type: application/json' \
  -d '{"transcript":"noop"}'
```

Expected result:

- HTTP 404

Pass criteria:

- queue endpoints reject unknown jobs safely

### 14. Worker Failure Path

Set the worker command to fail:

```toml
command = ["/bin/sh", "-lc", "exit 7"]
```

Restart `joan phil up`, then trigger a review webhook.

Expected result:

- webhook is still accepted
- worker claims the job
- worker fails the job
- Phil remains running

Pass criteria:

- one bad worker run does not crash the Phil service

## Final Acceptance Checklist

Mark each item pass/fail:

- `joan phil init` creates `.joan/agents/phil.toml` with worker settings
- `joan phil up` starts the server and one worker
- `/health` reports queue mode and queue stats
- review webhooks enqueue work and return HTTP 202
- one worker processes jobs serially
- queue drains after successful processing
- `joan pr comment add` posts a real inline comment as `phil`
- `joan pr review submit` posts a real final review as `phil`
- invalid webhook signatures are rejected
- worker failure does not crash Phil

## Exit Criteria

UAT passes when:

- all checklist items pass
- at least one real PR receives a Phil-authored inline comment
- at least one real PR receives a Phil-authored final review
- the queue-based `joan phil up` workflow behaves correctly in a local single-process run
