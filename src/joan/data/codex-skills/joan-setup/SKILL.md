---
name: joan-setup
description: >-
  Set up Joan for local code review via Forgejo. This skill should be used when
  initializing Joan in a repository, connecting to a local Forgejo instance,
  running joan init, adding the joan-review remote, or getting started with the
  Joan review workflow. Trigger phrases: "set up joan", "initialize joan",
  "configure forgejo", "connect to forgejo", "prepare repo for review".
disable-model-invocation: true
---

# Joan Setup

## What Joan Is

Joan is a local code review gate. AI agents push work to a local Forgejo instance, a human reviews it there, and only approved work gets pushed to the real upstream (GitHub, GitLab, etc.). This skill walks you through the one-time setup for a repository.

## Prerequisites

Before starting, verify the following:

1. **Git repo**: You must be inside a git repository. Run `git rev-parse --is-inside-work-tree` to confirm.

2. **Forgejo running**: Check that the local Forgejo instance is reachable:
   ```
   curl -sf http://localhost:3000/api/v1/version
   ```
   If this fails, Forgejo is not running. Start it with:
   ```
   cd forge/ && docker compose up -d
   ```
   The `forge/docker-compose.yml` in the Joan repo runs Forgejo on port 3000. The first user created in the Forgejo web UI becomes admin.

3. **`uv` available**: Joan is run via `uv run joan`. Verify `uv` is installed:
   ```
   uv --version
   ```

## Step 1: Run Init

Run `uv run joan init` and **let the user handle the interactive prompts**. Do NOT try to pipe input or automate this command — it uses `typer.prompt` for interactive input.

The command will prompt for:
- **Forgejo URL** (default: `http://localhost:3000`)
- **Forgejo admin username**
- **Forgejo admin password** (hidden input)
- **Forgejo repo** (default: current directory name)

It creates or reuses the Forgejo user `joan`, creates an API token for that account, records the admin username as the default human reviewer, and writes `.joan/config.toml` with the connection details.

Expected output on success:
```
Wrote config: .joan/config.toml
Next step: run `uv run joan remote add`.
```

If authentication fails, verify the admin username and password are correct and that the Forgejo URL is reachable.

## Step 2: Add Review Remote

Run:
```
uv run joan remote add
```

This command:
- Creates a private repo on Forgejo (or reuses an existing one)
- Grants the configured human user admin access to that review repo
- Adds a `joan-review` git remote pointing to the Forgejo repo
- Pushes the current branch to `joan-review`

Expected output:
```
Added remote joan-review -> http://localhost:3000/{owner}/{repo}.git
Pushed {branch} to joan-review
```

## Step 3: Verify

Confirm setup is complete by checking all three conditions:

1. **Config exists**: `.joan/config.toml` should be present and contain `[forgejo]` and optionally `[remotes]` sections.

2. **Remote exists**: Run `git remote -v` and confirm `joan-review` points to the Forgejo URL.

3. **Gitignore**: Ensure `.joan/` is listed in `.gitignore`. The config contains an API token — it must never be committed. If `.joan/` is not in `.gitignore`, add it:
   ```
   echo '.joan/' >> .gitignore
   ```

If any check fails, re-run the relevant step above.

## Next Steps

Setup is done. For the daily review workflow — creating PRs, checking feedback, and pushing approved work upstream — invoke `$joan-review`.
