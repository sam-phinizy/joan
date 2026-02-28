# Joan

Local code review gate for AI agents. Agents push work to a local [Forgejo](https://forgejo.org) instance, a human reviews it, and only approved work gets pushed to the real upstream (GitHub, GitLab, etc.).

## How it works

```
agent commits → joan pr create → human reviews on Forgejo → joan pr finish → local base branch → joan pr push → origin
```

Joan enforces approval gates at `joan pr finish`: it refuses to finish a PR if the review is not approved or has unresolved comments.

Joan can also review plan documents without taking over how you create those plans. Use whatever process you prefer (human discussion, Superpowers, your own notes), then use Joan to put the finished draft into a review PR.

## Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/)
- Docker (for the local Forgejo instance)
- A git repository

## Installation

### Install Joan

**Global install** (makes `joan` available on your PATH):

```bash
uv tool install git+https://github.com/sam-phinizy/joan.git
```

After a global install, use `joan` directly instead of `uv run joan` everywhere in this guide.

**Project dependency** (pinned to a specific project):

```bash
uv add git+https://github.com/sam-phinizy/joan.git
```

**One-shot** (no install required):

```bash
uvx --from git+https://github.com/sam-phinizy/joan.git joan --help
```

### Install agent integrations

Joan can install agent-specific instructions that teach the Joan review workflow. Those skills only become available to the agent after you run the relevant `joan skills install` command.

```bash
# Claude Code plugin (run in each repo where Claude should use Joan)
uv run joan skills install --agent claude

# Codex skills (installs to $CODEX_HOME/skills/joan, default: ~/.codex/skills/joan)
uv run joan skills install --agent codex

# Same Codex install directly from GitHub without adding Joan as a dependency
uvx --from git+https://github.com/sam-phinizy/joan.git joan skills install --agent codex
```

- Claude install target: `~/.claude/plugins/joan/` (global, shared across all repos)
- Codex install target: `$CODEX_HOME/skills/joan/` (defaults to `~/.codex/skills/joan/`)

## Bundled Hooks And Skills

Joan ships a small set of agent integrations so Claude Code and Codex can follow the same guarded review workflow.

### Claude plugin bundle

The Claude install places a full plugin bundle in `~/.claude/plugins/joan/`. That bundle includes:

| Item | What it does |
|---------|-------------|
| `.claude-plugin/plugin.json` | Claude plugin metadata for the Joan plugin |
| `.claude-plugin/marketplace.json` | Marketplace metadata for publishing/installing the plugin |
| `hooks/hooks.json` | Registers a `PreToolUse` hook for Claude's `Bash` tool |
| `hooks/enforce-review-branch.sh` | Blocks `git commit` unless the current branch is a Joan review branch |
| `skills/joan-setup/SKILL.md` | Setup workflow guidance |
| `skills/joan-review/SKILL.md` | End-to-end review workflow guidance |
| `skills/joan-resolve-pr-comments/SKILL.md` | Guided PR comment resolution workflow |
| `skills/joan-plan/SKILL.md` | Narrow workflow for putting an existing plan into Joan review |

The `enforce-review-branch.sh` hook is intentionally narrow:

- It only runs for Claude `Bash` tool calls.
- It only blocks commands that include `git commit`.
- It only enforces inside repos that already have `.joan/config.toml`.
- It reads the review remote from `.joan/config.toml` (`[remotes].review`) and falls back to `joan-review`.
- It allows commits when the current branch's upstream tracks that review remote, and denies the commit otherwise.

In practice, this prevents accidental commits on `main` or another non-review branch after Joan is configured.

### Codex skills bundle

The Codex install places Joan skills in `$CODEX_HOME/skills/joan/` (default `~/.codex/skills/joan/`). Codex gets the same four workflow skills, without the Claude-specific hook/plugin wrapper:

| Skill | Purpose |
|---------|-------------|
| `joan-setup` | Walks through one-time repo setup: verify Forgejo is running, run `joan init`, run `joan remote add`, and confirm `.joan/` is ignored |
| `joan-review` | Covers the full review lifecycle: create a review branch, open a PR, check status/comments, finish an approved PR locally, and only push upstream when explicitly requested |
| `joan-resolve-pr-comments` | Turns unresolved review comments into a step-by-step work queue, resolves actionable comments one at a time, and flags PR-level discussion comments that must be handled in Forgejo's UI |
| `joan-plan` | Takes an already-formed plan and puts it into Joan's review flow without replacing your planning process |

### Repo layout for contributors

If you are editing Joan itself, the checked-in integration assets live in:

- `hooks/` for the Claude hook definition and shell script
- `skills/` for the human-readable skill files used in the Claude plugin bundle
- `src/joan/data/codex-skills/` for the packaged Codex skill assets that `joan skills install --agent codex` copies into `$CODEX_HOME`

### Start Forgejo

Joan routes reviews through a local [Forgejo](https://forgejo.org) instance running in Docker. You do not need to clone this repo — Joan bundles the compose file and can install it anywhere.

Install the compose file to a directory of your choice (default: `~/joan-forge`):

```bash
uv run joan forge install ~/joan-forge
```

Then start Forgejo:

```bash
cd ~/joan-forge
FORGE_ADMIN_PASSWORD=yourpassword docker compose up -d
```

Forgejo will be available at `http://localhost:3000`. The admin account is created automatically:

| Env var | Default | Purpose |
|---------|---------|---------|
| `FORGE_ADMIN_PASSWORD` | *(required)* | Admin password |
| `FORGE_ADMIN_USERNAME` | `$USER` (or `forgeadmin`) | Admin username |
| `FORGE_ADMIN_EMAIL` | `admin@example.com` | Admin email |

The `~/joan-forge/` directory is shared across all repos — set it up once.

## Setup (per repo)

**1. Initialize Joan**

Run this once in the repo you want to gate:

```bash
uv run joan init
```

You will be prompted for:
- Forgejo URL (default: `http://localhost:3000`)
- Forgejo admin username and password
- Which Forgejo repo to use (defaults to current directory name)

This creates or reuses the Forgejo user `joan`, creates an API token for that account, stores the admin username as the default human reviewer, and writes `.joan/config.toml`. Add `.joan/` to your `.gitignore` — the config contains an API token and must never be committed.

**2. Set up SSH key for Forgejo (recommended)**

```bash
uv run joan ssh setup
```

Generates `~/.ssh/id_ed25519_joan` if needed and uploads the public key to your Forgejo account.

Use `--key-path` to choose a different key location:

```bash
uv run joan ssh setup --key-path ~/.ssh/id_ed25519_joan_work
```

**3. Add the review remote**

```bash
uv run joan remote add
```

Creates a private repo on Forgejo and adds `joan-review` as a git remote pointing to it.
It also grants the configured human reviewer admin access to the review repo.

## Daily workflow

```bash
# Create a review branch and open a PR
uv run joan branch create
uv run joan pr create --title "Add feature X"

# Check review status
uv run joan pr sync

# See unresolved comments
uv run joan pr comments

# Resolve a comment after addressing it
uv run joan pr comment resolve <id>

# Merge the approved review branch back into the local base branch
uv run joan pr finish

# Push that finished base branch upstream when you're ready
uv run joan pr push
```

`uv run joan pr create` requests review from the configured human user by default. Pass `--no-request-human-review` if you need to skip that.

## Planning

Use your preferred planning workflow first, then let Joan review the resulting plan document:

```bash
uv run joan plan create cache-invalidation --title "Cache invalidation strategy"
```

This creates a plan file in `docs/plans/`, puts it on a dedicated review branch, and opens a PR for feedback by default. You can use the same flow for a higher-level product plan or for a more detailed implementation plan that you want reviewed before code starts.

After the plan PR is approved, use `uv run joan pr finish` to land the plan locally. Implementation is a separate next step and only begins when you explicitly start it.

## Phil (Local AI Reviewer)

Phil is Joan's local AI reviewer. In queue mode, Forgejo webhooks enqueue review jobs in memory and one local worker processes them serially. This is designed for local, ephemeral use: if Phil restarts, the in-memory queue is cleared.

**1. Create Phil's local agent account**

```bash
uv run joan phil init
```

This creates `.joan/agents/phil.toml` with:
- Phil's Forgejo token
- webhook server settings
- worker settings (`enabled`, local API URL, poll interval, timeout, and the CLI command to run)

By default, Phil's worker command is `codex`. If you want Phil to drive a different CLI, edit `.joan/agents/phil.toml` and change `worker.command`.

**2. Add a Forgejo webhook**

Point your repo webhook at:

```text
http://host.docker.internal:9000/webhook
```

`http://localhost:9000/webhook` will fail with the bundled Docker Forgejo setup because `localhost` resolves inside the Forgejo container. If `host.docker.internal` is unavailable in your environment, use any hostname or IP address that the container can reach.

Use the `webhook_secret` from `.joan/agents/phil.toml`.

**3. Bring Phil online**

```bash
uv run joan phil up
```

`joan phil up` starts:
- the FastAPI webhook server
- one embedded worker that polls the local queue and runs one review at a time

For debugging, you can still run the pieces separately:

```bash
uv run joan phil serve
uv run joan phil work
```

### How Phil posts review feedback

Phil now posts through Joan's own CLI commands instead of the server writing reviews on its behalf:

```bash
# Post one inline comment immediately
uv run joan pr comment add \
  --agent phil \
  --owner yourname \
  --repo yourrepo \
  --pr 7 \
  --path src/foo.py \
  --line 42 \
  --body "This breaks on empty input."

# Post the final verdict / summary
uv run joan pr review submit \
  --agent phil \
  --owner yourname \
  --repo yourrepo \
  --pr 7 \
  --verdict request_changes \
  --body "Needs a guard for empty input."
```

## Config

`.joan/config.toml` (auto-generated by `joan init`):

```toml
[forgejo]
url = "http://localhost:3000"
token = "..."        # API token — never commit this
owner = "yourname"
repo = "yourrepo"

[remotes]
review = "joan-review"   # default
upstream = "origin"      # default
```

`.joan/agents/phil.toml` (auto-generated by `joan phil init`):

```toml
[forgejo]
token = "..."            # Phil's API token — never commit this

[server]
port = 9000
host = "0.0.0.0"
webhook_secret = "..."

[claude]
model = "claude-sonnet-4-6"

[worker]
enabled = true
api_url = "http://127.0.0.1:9000"
poll_interval_seconds = 2.0
timeout_seconds = 600.0
command = ["codex"]
```

## Command reference

| Command | Description |
|---------|-------------|
| `joan init` | One-time setup: create token, write config |
| `joan ssh setup [--key-path PATH] [--title TEXT]` | Create/reuse an SSH keypair and upload key to Forgejo |
| `joan remote add` | Create Forgejo repo, add `joan-review` remote |
| `joan branch create [name]` | Create and push a review branch |
| `joan pr create` | Open a PR on Forgejo |
| `joan pr sync` | JSON: approval status + unresolved comment count |
| `joan pr comments` | JSON: list unresolved review comments |
| `joan pr comment add --agent NAME --owner OWNER --repo REPO --pr N --path PATH --line N --body TEXT` | Post one inline PR comment immediately using an agent token |
| `joan pr comment resolve <id>` | Mark a comment resolved |
| `joan pr review submit --agent NAME --owner OWNER --repo REPO --pr N --verdict VERDICT [--body TEXT]` | Post a final review verdict on a specific PR using an agent token |
| `joan pr finish` | Merge an approved review branch back into its local base branch |
| `joan pr push` | Push the current finished local branch to upstream |
| `joan worktree create [name]` | Create an isolated git worktree |
| `joan worktree remove <name>` | Remove a tracked worktree |
| `joan phil init` | Create the local `phil` agent account and write `.joan/agents/phil.toml` |
| `joan phil up` | Start the Phil webhook server and one local queue worker |
| `joan phil serve` | Start the Phil webhook server only |
| `joan phil work` | Start the Phil worker only |
| `joan skills install --agent <claude\|codex>` | Install the Claude plugin or Codex skills |
| `joan forge install [path]` | Copy Forgejo docker-compose.yml to a directory |
