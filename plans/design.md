# Joan

Joan is a local code review gate for AI agents (Claude Code, Codex, etc.). Agents push work to a local Forgejo instance, where a human reviews it before the agent pushes to the real upstream (GitHub, GitLab, etc.).

Joan is a Python CLI that wraps the Forgejo API and git operations, giving agents a simple interface for the push-review-revise-push cycle.

## Workflow

```
Agent writes code
    |
    v
joan branch create    -- create branch, push to local Forgejo
    |
    v
joan pr create        -- open PR on Forgejo against main
    |
    v
Human reviews in Forgejo web UI (or via joan CLI)
    |
    v
joan pr comments      -- agent fetches review feedback as JSON
    |
    v
Agent addresses comments, commits, pushes to joan-review remote
    |
    v
joan pr comment resolve <id>  -- mark comments resolved
    |
    v
joan pr sync          -- check if PR is approved
    |
    v
joan pr push          -- push approved branch to upstream origin
```

## Commands

### `joan init`

Setup wizard for a new project. Prompts for Forgejo URL and credentials, creates an API token via the Forgejo API, and writes config to `.joan/config.toml`.

- Prompts for Forgejo instance URL (default: `http://localhost:3000`)
- Prompts for username/password
- Creates an API token via `POST /api/v1/users/{username}/tokens`
- Writes `.joan/config.toml` with the URL and token
- Optionally runs `joan remote add` as part of setup

### `joan remote add`

Adds Forgejo as a secondary remote and creates the repo on the Forgejo instance.

- Creates the repo on Forgejo via `POST /api/v1/user/repos`
- Adds a git remote named `joan-review` pointing to the new Forgejo repo
- Pushes current branch state to `joan-review`

### `joan branch create [name]`

Creates a new branch and pushes it to the `joan-review` remote.

- Creates branch locally via `git checkout -b <name>`
- Pushes to `joan-review` remote
- If no name given, generates one from the current context (e.g., timestamp or agent-provided description)

### `joan pr create [--title] [--body] [--base]`

Creates a pull request on the local Forgejo instance.

- Pushes current branch to `joan-review` if not already pushed
- Creates PR via `POST /api/v1/repos/{owner}/{repo}/pulls`
- `--base` defaults to `main`
- Outputs the PR number and Forgejo web URL

### `joan pr sync`

Syncs PR state from Forgejo. Fetches current approval status, comment counts, and whether there are unresolved comments.

- Gets PR details via `GET /api/v1/repos/{owner}/{repo}/pulls/{index}`
- Gets reviews via `GET /api/v1/repos/{owner}/{repo}/pulls/{index}/reviews`
- Outputs structured JSON with: approval status, number of unresolved comments, latest review state

### `joan pr comments`

Fetches all review comments for the current branch's PR as structured JSON.

Output format per comment:
```json
{
  "id": 42,
  "body": "This function should handle the error case",
  "path": "src/handler.py",
  "line": 15,
  "resolved": false,
  "author": "reviewer-username",
  "created_at": "2026-02-27T10:00:00Z"
}
```

- Fetches via `GET /api/v1/repos/{owner}/{repo}/pulls/{index}/reviews` and associated comment endpoints
- Filters to unresolved comments by default
- `--all` flag to include resolved comments
- Agent consumes this JSON and iteratively addresses each comment

### `joan pr comment resolve <id>`

Marks a specific review comment as resolved on Forgejo.

- Calls the appropriate Forgejo API endpoint to resolve the comment thread
- Outputs confirmation with the comment ID

### `joan pr push`

Pushes the approved branch to the real upstream `origin` remote.

- Checks that the PR on Forgejo is approved (fails if not)
- Pushes the current branch to `origin`
- Optionally opens a PR on the upstream forge (future enhancement)

### `joan worktree create [name]`

Basic git worktree management for agents that work in isolated worktrees.

- Creates a worktree via `git worktree add`
- Tracks the worktree path in joan's context so subsequent commands work from it

### `joan worktree remove [name]`

Removes a worktree.

- Runs `git worktree remove`
- Cleans up any joan tracking state

## Architecture

### Functional Core, Imperative Shell

Joan uses a functional core / imperative shell architecture:

**Functional core** (pure functions, no side effects, easy to test):
- Parsing Forgejo API responses into domain dataclasses
- Building API request payloads from command arguments
- Formatting PR comments into structured JSON output
- Validating config values
- Determining PR approval status from review data
- Building git command argument lists

**Imperative shell** (I/O, wires pure functions together):
- HTTP calls to Forgejo API (via httpx)
- Git subprocess execution
- File I/O for `.joan/config.toml`
- CLI input/output (Typer)
- Prompting user for credentials during init

### Project Structure

```
src/joan/
    __init__.py          # Typer app entry point
    cli/
        __init__.py
        init.py          # joan init
        branch.py        # joan branch *
        pr.py            # joan pr *
        remote.py        # joan remote *
        worktree.py      # joan worktree *
    core/
        __init__.py
        models.py        # Dataclasses: PR, Comment, Config, Review, etc.
        forgejo.py       # Pure functions: parse API responses, build request payloads
        git.py           # Pure functions: build git command args, parse git output
        config.py        # Pure functions: parse/validate TOML config
    shell/
        __init__.py
        forgejo_client.py  # httpx calls to Forgejo API
        git_runner.py      # subprocess calls to git
        config_io.py       # Read/write .joan/config.toml
```

- `cli/` — Typer command definitions. Thin layer that calls shell functions and passes results through core functions.
- `core/` — Pure functions and dataclasses. No imports of httpx, subprocess, or file I/O. All inputs and outputs are plain data.
- `shell/` — Side-effectful I/O. Each module is a thin wrapper: make the HTTP call, run the subprocess, read the file, return raw data for core to process.

### Key Libraries

| Library | Purpose |
|---------|---------|
| typer | CLI framework |
| httpx | HTTP client for Forgejo API |
| tomli / tomli-w | TOML config parsing (tomli is stdlib in 3.11+, tomli-w for writing) |

### Data Flow Example: `joan pr comments`

```
cli/pr.py: comments()
    |
    shell/config_io.py: read_config()  -->  core/config.py: parse_config(raw_toml) -> Config
    |
    shell/forgejo_client.py: get_pr_reviews(config, pr_number)  -->  raw JSON
    |
    core/forgejo.py: parse_reviews(raw_json) -> list[Comment]
    |
    core/forgejo.py: format_comments_json(comments, resolved=False) -> str
    |
    typer.echo(output)
```

## Config

All config is stored in `.joan/config.toml` at the repo root:

```toml
[forgejo]
url = "http://localhost:3000"
token = "abc123..."
owner = "sam"
repo = "my-project"

[remotes]
review = "joan-review"   # name of the forgejo git remote
upstream = "origin"       # name of the real upstream remote

[defaults]
base_branch = "main"
```

Forgejo is the source of truth for all PR state. No local database — joan always queries the API for current status.

`.joan/` should be added to `.gitignore` since it contains credentials and is per-machine config.

## Agent Integration

Joan's output is designed for machine consumption:

- All data commands (`pr comments`, `pr sync`) output structured JSON to stdout
- Status/confirmation messages go to stderr so they don't pollute JSON output
- Exit codes are meaningful: 0 = success, 1 = error, 2 = PR not approved (for `pr push`)
- Error messages include enough context for an agent to understand what went wrong and retry

Agents are expected to:
1. Run `joan pr comments` to get unresolved feedback
2. Address each comment by modifying code and committing
3. Run `joan pr comment resolve <id>` for each addressed comment
4. Push to `joan-review` remote
5. Run `joan pr sync` to check if approved
6. Run `joan pr push` once approved
