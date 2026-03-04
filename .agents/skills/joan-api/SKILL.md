---
name: joan-api
description: >-
  Send raw API requests to the local Forgejo instance. Use when you need to call
  a Forgejo API endpoint directly that isn't covered by other Joan commands, query
  repository data, manage labels/milestones/releases, or perform any Forgejo REST
  API operation.
---

# Joan API – Direct Forgejo API Access

The `joan api` command lets you send arbitrary HTTP requests to the local Forgejo
instance. Authentication and owner/repo substitution are handled automatically.

## Usage

```
uv run joan api <METHOD> <PATH> [--data JSON] [--query key=value ...]
```

### Arguments

| Argument | Description |
|----------|-------------|
| `METHOD` | HTTP method: `GET`, `POST`, `PUT`, `PATCH`, `DELETE` |
| `PATH`   | Forgejo API path. Use `{owner}` and `{repo}` as placeholders — they are auto-filled from `.joan/config.toml` |

### Options

| Option | Description |
|--------|-------------|
| `--data`, `-d` | JSON request body (string) |
| `--query`, `-q` | Query parameter as `key=value`. Repeatable. |

### Output

- Returns pretty-printed JSON on stdout
- Prints HTTP status to stderr on errors
- Exit code 0 on success, 1 on HTTP error, 2 on usage error

## Examples

### List open pull requests
```bash
uv run joan api GET /api/v1/repos/{owner}/{repo}/pulls
```

### List closed PRs
```bash
uv run joan api GET /api/v1/repos/{owner}/{repo}/pulls -q state=closed
```

### Get a specific PR
```bash
uv run joan api GET /api/v1/repos/{owner}/{repo}/pulls/5
```

### Create an issue
```bash
uv run joan api POST /api/v1/repos/{owner}/{repo}/issues -d '{"title": "Bug report", "body": "Details here"}'
```

### List repo labels
```bash
uv run joan api GET /api/v1/repos/{owner}/{repo}/labels
```

### Get current authenticated user
```bash
uv run joan api GET /api/v1/user
```

### List all repos
```bash
uv run joan api GET /api/v1/repos/search -q limit=50
```

### Add a label to an issue
```bash
uv run joan api POST /api/v1/repos/{owner}/{repo}/issues/1/labels -d '{"labels": [1]}'
```

## Forgejo API Reference

The Forgejo API follows the Gitea API v1 spec. Common endpoint patterns:

- `/api/v1/repos/{owner}/{repo}/...` — Repository operations
- `/api/v1/repos/{owner}/{repo}/pulls/...` — Pull request operations
- `/api/v1/repos/{owner}/{repo}/issues/...` — Issue operations
- `/api/v1/user/...` — Authenticated user operations
- `/api/v1/admin/...` — Admin operations

For full API docs, visit `http://localhost:3000/api/swagger` on your Forgejo instance.
