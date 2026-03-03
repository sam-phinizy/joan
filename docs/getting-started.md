# Getting Started

## Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/)
- Docker
- A git repository

## Install Joan

Use whichever install mode matches how you want to run it.

### Global install

```bash
uv tool install git+https://github.com/sam-phinizy/joan.git
```

This puts `joan` on your `PATH`.

### Project dependency

```bash
uv add git+https://github.com/sam-phinizy/joan.git
```

### One-shot run

```bash
uvx --from git+https://github.com/sam-phinizy/joan.git joan --help
```

## Install agent integrations

### Claude Code plugin

```bash
/plugin marketplace add sam-phinizy/sams-claude-menagerie
/plugin install joan@sams-claude-menagerie
```

Update later with:

```bash
/plugin update joan@sams-claude-menagerie
```

### Codex skills

```bash
uv run joan skills install --agent codex
```

Or without adding Joan as a project dependency:

```bash
uvx --from git+https://github.com/sam-phinizy/joan.git joan skills install --agent codex
```

## Start Forgejo

Install the bundled Forgejo compose stack once:

```bash
uv run joan services install forgejo ~/joan-forge
```

Then start it:

```bash
cd ~/joan-forge
FORGE_ADMIN_PASSWORD=yourpassword docker compose up -d
```

Forgejo will be available at `http://localhost:3000`.

## Set up Joan in a repo

### 1. Initialize Joan

```bash
uv run joan init
```

This writes `.joan/config.toml`, creates or reuses the Forgejo `joan` user, and stores the default human reviewer.

### 2. Set up SSH access

```bash
uv run joan ssh setup
```

Use a custom key path if needed:

```bash
uv run joan ssh setup --key-path ~/.ssh/id_ed25519_joan_work
```

### 3. Add the review remote

```bash
uv run joan remote add
```

This creates a private Forgejo repo and adds `joan-review` as a git remote.
