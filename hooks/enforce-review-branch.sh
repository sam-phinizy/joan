#!/bin/bash
# Blocks git commit when not on a joan review branch.
# A review branch is one whose upstream tracks the joan-review remote.
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

# Allow if the current branch's upstream is on the joan-review remote
upstream=$(git rev-parse --abbrev-ref --symbolic-full-name @{upstream} 2>/dev/null || true)
if echo "$upstream" | grep -q "joan-review/"; then
    exit 0
fi

# Block — not on a review branch
printf '{"hookSpecificOutput":{"permissionDecision":"deny"},"systemMessage":"Commit blocked: not on a joan review branch.\nCreate one first with: uv run joan branch create <name>\nThen stage and commit on that branch."}\n'
