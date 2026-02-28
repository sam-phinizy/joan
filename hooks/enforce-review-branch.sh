#!/bin/bash
# Blocks git commit when not on a joan review branch.
# A review branch is one whose upstream tracks the configured review remote
# (read from .joan/config.toml [remotes] review, defaults to "joan-review").
set -euo pipefail

input=$(cat)

# Extract the bash command — fall back gracefully if jq is absent
if command -v jq &>/dev/null; then
    command=$(echo "$input" | jq -r '.tool_input.command // empty')
else
    command=$(echo "$input" | python3 -c "import json,sys; print(json.load(sys.stdin).get('tool_input',{}).get('command',''))")
fi

# Only intercept git commit invocations
if ! echo "$command" | grep -qE 'git\s+commit'; then
    exit 0
fi

# Only enforce in joan-configured repos
if [ ! -f ".joan/config.toml" ]; then
    exit 0
fi

# Read the review remote name from config (requires Python 3.11+ tomllib)
review_remote=$(python3 -c "
import tomllib, sys
with open('.joan/config.toml', 'rb') as f:
    config = tomllib.load(f)
print(config.get('remotes', {}).get('review', 'joan-review'))
" 2>/dev/null || echo "joan-review")

# Allow if the current branch's upstream is on the review remote
upstream=$(git rev-parse --abbrev-ref --symbolic-full-name @{upstream} 2>/dev/null || true)
if echo "$upstream" | grep -q "^${review_remote}/"; then
    exit 0
fi

# Block — not on a review branch
printf '{"hookSpecificOutput":{"permissionDecision":"deny"},"systemMessage":"Commit blocked: not on a joan review branch.\nCreate one first with: uv run joan branch create <name>\nThen stage and commit on that branch."}\n'
