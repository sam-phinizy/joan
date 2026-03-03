# Phil

Phil is Joan's local AI reviewer. In queue mode, Forgejo webhooks enqueue review jobs in memory and one local worker processes them serially.

## 1. Create Phil's local agent account

```bash
uv run joan phil init
```

This creates `.joan/agents/phil.toml` with Phil's Forgejo token, webhook settings, and worker settings.

By default, Phil's worker command is `codex`. Change `.joan/agents/phil.toml` if you want Phil to drive a different CLI.

## 2. Add a Forgejo webhook

Point your repo webhook at:

```text
http://host.docker.internal:9000/webhook
```

With the bundled Docker Forgejo setup, `http://localhost:9000/webhook` will fail because `localhost` resolves inside the container.

Use the `webhook_secret` from `.joan/agents/phil.toml`.

## 3. Bring Phil online

```bash
uv run joan phil up
```

This starts:

- The FastAPI webhook server
- One embedded worker that processes one review at a time

For debugging, you can still run the two processes separately:

```bash
uv run joan phil serve
uv run joan phil work
```

## On-demand review (no server required)

You can trigger a Phil review directly from Claude Code or Codex without running the webhook server:

```
/joan:phil-review
```

This skill reads the diff from your current branch's open PR, reviews it as Phil, and posts inline comments and a final verdict to Forgejo using the CLI commands below. No webhook or worker process needed.

## How Phil posts review feedback

Phil posts through Joan's CLI.

### Inline comment

```bash
uv run joan pr comment add \
  --agent phil \
  --owner yourname \
  --repo yourrepo \
  --pr 7 \
  --path src/foo.py \
  --line 42 \
  --body "This breaks on empty input."
```

### Final verdict

```bash
uv run joan pr review submit \
  --agent phil \
  --owner yourname \
  --repo yourrepo \
  --pr 7 \
  --verdict request_changes \
  --body "Needs a guard for empty input."
```
