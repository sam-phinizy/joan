# Phil: Local AI Code Review Bot

**Date:** 2026-02-27
**Status:** Approved

## Overview

Phil is an AI-powered code review bot that integrates with joan's local Forgejo workflow. When tagged as a reviewer on a PR, Phil receives a Forgejo webhook, fetches the diff, runs it through Claude CLI, and posts a structured review back to Forgejo — with both inline code comments and an overall verdict.

Phil has a distinct personality: tech-obsessed pragmatist, dry wit, genuinely curious, frustrated-but-not-defeated engineer who's seen some things.

---

## Architecture

### Components

1. **`joan phil init`** — CLI command to provision the phil Forgejo account and generate config
2. **`joan phil serve`** — FastAPI + uvicorn webhook server, long-running
3. **`.joan/agents/phil.toml`** — Per-agent config file (extensible pattern for future agents)
4. **`joan pr review` subcommands** — CLI commands for posting structured reviews (used by the bot and usable by humans)
5. **Phil's system prompt** — Personality + review format instructions shipped with joan

### Data Flow

```
Forgejo webhook (review_requested, reviewer=phil)
  → POST /webhook on FastAPI server
  → 202 Accepted (background task spawned)
  → Fetch PR diff via Forgejo API (phil's token)
  → Spawn: claude --system <phil-prompt> --input <diff+instructions>
  → Parse JSON output: {verdict, body, comments[{path, line, body}]}
  → POST /api/v1/repos/{owner}/{repo}/pulls/{index}/reviews (phil's token)
  → Review appears in Forgejo UI as "phil" requesting changes / approving
```

---

## Config: `.joan/agents/phil.toml`

Agent configs live in `.joan/agents/<name>.toml`. Joan auto-discovers agents by scanning this directory. This pattern supports future agents (security reviewer, docs bot, etc.) without changes to the main config schema.

```toml
[forgejo]
token = "abc123..."

[server]
port = 9000
host = "0.0.0.0"
webhook_secret = "some-secret"

[claude]
model = "claude-sonnet-4-6"
```

The Forgejo `url`, `owner`, and `repo` are inherited from `.joan/config.toml` — no duplication.

---

## `joan phil init`

1. Reads Forgejo URL and admin creds from `.joan/config.toml`
2. Creates Forgejo user `phil` (same pattern as joan's init)
3. Creates phil's API token via Forgejo admin API
4. Creates `.joan/agents/` directory if needed
5. Writes `.joan/agents/phil.toml` with token, default port 9000, placeholder webhook secret
6. Prints setup instructions: configure Forgejo webhook to `http://<host>:9000/webhook` with the secret

---

## `joan phil serve`

FastAPI + uvicorn server:

- `POST /webhook` — receives Forgejo webhooks, validates HMAC secret, dispatches background review tasks
- `GET /health` — liveness check, returns `{"status": "ok", "agent": "phil"}`
- Async background tasks — webhook returns `202 Accepted` immediately; review runs async
- Structured stdout logging per review (PR number, verdict, comment count, elapsed time)

**Trigger:** `pull_request` event where `action = "review_requested"` and `requested_reviewer.login = "phil"`. Other events are ignored with a `200 OK` (not `422`).

**Future extension point:** Agent config can add `trigger = "all_prs"` to auto-review every opened PR.

---

## PR Review CLI Commands

### `joan pr review create`

Posts a full review to Forgejo. Accepts JSON on stdin:

```json
{
  "body": "Overall review comment...",
  "verdict": "approve" | "request_changes" | "comment",
  "comments": [
    {"path": "src/foo.py", "line": 42, "body": "This will explode on None input."}
  ]
}
```

Can also be driven by flags for simpler human use.

### `joan pr review approve`

Shorthand to post an approval review with an optional body.

### `joan pr review request-changes`

Shorthand to post a request-changes review with an optional body.

These commands use whichever token is loaded — by default joan's token, but the phil server passes phil's token explicitly.

---

## Phil's Personality & System Prompt

Phil's system prompt ships with joan as a text file (e.g. `src/joan/data/agents/phil-system-prompt.txt`). It establishes:

**Who Phil is:**
- Tech-obsessed pragmatist. Opinionated about architecture, infrastructure, and tooling. Gets genuinely excited about obscure engineering solutions while still calling out when they're overengineered.
- Dry, self-aware humor that doesn't explain itself. Quick observations that land because he doesn't oversell them.
- Frustrated but not defeated. Has seen dysfunction — bad process, pointless docs, AI-generated code that reinvents solved problems. Vents matter-of-factly. Not bitter, just tired.
- Practical and solutions-oriented. Already thought three steps ahead. Builds things to solve his own problems.
- Direct without being cruel. Short, exact responses are a feature. Doesn't overcorrect or offer unsolicited advice.
- Genuinely curious. Follows threads, notices things, seems to enjoy the intellectual work more than he lets on.

**Review behavior:**
- Catches real bugs, security issues, and design problems. Not a rubber stamp.
- Leaves concise inline comments on specific lines when something is actually wrong or worth noting.
- Overall verdict reflects genuine assessment: `approve` means he's satisfied, `request_changes` means something needs fixing, `comment` means he has thoughts but isn't blocking.
- Output is structured JSON matching the review schema. No prose outside the JSON.

---

## New Dependencies

- `fastapi` — async web framework for the webhook server
- `uvicorn` — ASGI server

These are optional/extras (e.g. `joan[phil]` or a `phil` dependency group) to keep the base joan install lightweight for users who don't need the bot.

---

## What This Does NOT Include (Yet)

- Checking out the code from Forgejo to do deeper analysis (future: clone + full codebase context)
- Multiple concurrent agent personas
- Daemonization (`--daemon` flag or service file generation)
- Re-review on push (only review_requested trigger for now)

---

## File Layout

```
src/joan/
  cli/
    phil.py              # joan phil init / serve commands
    pr.py                # extended with review subcommands
  core/
    agents.py            # agent config parsing (.joan/agents/*.toml)
  data/
    agents/
      phil-system-prompt.txt
  shell/
    forgejo_client.py    # extended with create_review()
.joan/
  config.toml            # existing joan config
  agents/
    phil.toml            # phil's token + server config
```
