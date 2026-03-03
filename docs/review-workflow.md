# Review Workflow

## Daily flow

```bash
# If this branch predates Joan tracking or was created outside Joan,
# register its parent branch once before the first review:
uv run joan branch adopt --base-ref origin/main

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

`joan pr create` requests review from the configured human user by default. Pass `--no-request-human-review` if you need to skip that.
Use `joan branch adopt` only on the first Joan review for an existing branch, or when the branch is stacked on top of another non-`main` branch and you need to choose the parent explicitly.

## Planning

Use your preferred planning process first, then let Joan review the completed plan document:

```bash
uv run joan plan create cache-invalidation --title "Cache invalidation strategy"
```

This creates a plan file under `docs/plans/`, puts it on a dedicated review branch, and opens a PR for feedback.

After approval, land the plan locally with:

```bash
uv run joan pr finish
```

## Contributor notes

If you are editing Joan itself, the integration assets live here:

- `hooks/` for the Claude hook definition and shell script
- `skills/` for the canonical authored skill tree
- `.agents/skills/` for the repo-local Codex mirror
- `src/joan/data/codex-skills/` for the packaged Codex mirror used by `joan skills install --agent codex`

After editing anything under `skills/`, refresh both Codex mirrors:

```bash
uv run python scripts/sync_skills.py
```
