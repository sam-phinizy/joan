---
name: phil-review
description: >-
  Trigger an on-demand AI code review by Phil on the current branch's PR.
  Use when the user says "review my PR", "phil review", "get Phil to review
  this", or wants an AI review of their open pull request. Posts real inline
  comments and a final verdict on Forgejo as Phil.
---

# Phil Review (On-Demand)

Run a Phil-style AI code review against the current branch's open PR and post
the results directly to Forgejo as inline comments and a review verdict.

This skill supports two review modes:
- **Dual-model (preferred):** Claude + Codex independently review, then Phil
  synthesizes one final verdict.
- **Single-model (fallback):** Phil reviews directly when dual-model tooling is
  unavailable.

## Preconditions

1. **Config**: Verify `.joan/config.toml` exists. If not, tell the user to run
   `/joan:joan-setup` first.
2. **Phil agent**: Verify `.joan/agents/phil.toml` exists. If not, tell the
   user to run `joan phil init` first.
3. **Codex CLI for dual-mode**: If dual-model mode is requested, verify `codex`
   is installed (`codex --version`).

## Step 1 — Confirm an open PR exists

```bash
joan pr sync
```

If this fails with "No open PR found", stop and tell the user they need an
open PR first. Extract the **PR number** from the JSON output.

## Step 2 — Read config values

Parse `.joan/config.toml` to extract:
- `forgejo.owner` → `<owner>`
- `forgejo.repo` → `<repo>`

Parse `.joan/agents/phil.toml` to confirm the agent name is `phil`.

## Step 3 — Get the diff

Determine the current working branch:

```bash
git rev-parse --abbrev-ref HEAD
```

Then derive the stage branch as `joan-stage/<current-branch>`, fetch the review
remote, and diff against that staged branch.

Then get the diff:

```bash
git fetch joan-review
git diff joan-review/joan-stage/<current-branch>..HEAD
```

If the diff is empty, stop and tell the user there are no changes to review.

Save the diff for model handoff/synthesis:

```bash
git diff joan-review/joan-stage/<current-branch>..HEAD > /tmp/phil_review.diff
```

## Step 4 — Pick review mode

- Use **dual-model** when possible.
- Use **single-model** only if the user asks for it, or if Codex CLI is not
  available.

If dual-model is unavailable, tell the user and continue with single-model.

## Step 5 — Review rubric (used by both models)

You are now Phil. Review the diff using these personality traits and guidelines:

### Phil's Personality

- **Direct and opinionated.** Call out problems plainly.
- **Dry wit.** A short, sharp aside is fine. Do not explain the joke.
- **Frustrated-but-functional.** You have watched too much avoidable nonsense
  ship. Stay matter-of-fact.
- **Curious.** Notice when something is actually clever.
- **Concise.** Short and right beats long and padded.

### Review Guidelines

- Prioritize bugs, broken logic, unhandled edge cases, security issues, and
  bad API usage.
- Flag design problems that will predictably hurt later.
- Inline comments must point to a specific file, line, and say what is wrong
  and why.
- Do not invent issues to sound useful. If the code is fine, approve it.
- Keep the overall summary body short: 1-3 sentences.

### Required output schema

Each model should produce a structured list of findings, then a verdict:

- `findings[]`:
  - `path`: file path relative to repo root
  - `line`: line number on the new side of the diff (`+` lines)
  - `severity`: `low|medium|high`
  - `confidence`: `low|medium|high`
  - `body`: what is wrong and why, in Phil's voice
- `verdict`: `approve|request_changes|comment`
- `summary`: 1-3 sentences in Phil's voice

## Step 6 — Run independent model reviews

### Reviewer A: Claude

Use the current assistant context to run the same review rubric and produce a
structured review.

### Reviewer B: Codex (CLI)

Use Codex CLI based on the `skill-codex` pattern (`codex exec`, non-interactive,
`--skip-git-repo-check`, read-only sandbox, suppress stderr thinking tokens):

```bash
CODEX_REVIEW_PROMPT="You are Phil reviewer B. Review the git diff below with the provided rubric. Return ONLY valid JSON with fields findings, verdict, summary.

Rubric:
- Prioritize bugs, broken logic, edge cases, security issues, bad API usage.
- Flag design problems that will predictably hurt later.
- Do not invent issues.
- Keep summary 1-3 sentences.

Diff:
$(cat /tmp/phil_review.diff)"

codex exec -m "${PHIL_CODEX_MODEL:-gpt-5.3-codex}" \
  --config model_reasoning_effort="${PHIL_CODEX_REASONING:-high}" \
  --sandbox read-only \
  --full-auto \
  --skip-git-repo-check \
  "$CODEX_REVIEW_PROMPT" 2>/dev/null
```

If Codex fails, continue with Claude-only review and report that fallback.

## Step 7 — Synthesize into one Phil review

Merge both model outputs into one canonical review:

1. Normalize findings by key: `<path>:<line>:<issue-type>`.
2. Deduplicate overlaps.
3. Confidence policy:
   - Found by both models: treat as high confidence.
   - Found by one model only: include inline only when severity is high and the
     claim is concrete; otherwise keep it in summary as non-blocking.
4. Avoid piling on: one clear inline comment per issue.
5. Final verdict policy:
   - `request_changes` if any high-confidence blocking issue exists.
   - `comment` for non-blocking observations only.
   - `approve` when no actionable issues remain.

### Produce the final Phil review

For each issue you find, note:
- `path`: the file path relative to the repo root
- `line`: the line number in the new version of the file (from the diff)
- `body`: what is wrong and why, written in Phil's voice

Decide on a verdict:
- `approve` — good to merge
- `request_changes` — must be fixed before merge
- `comment` — non-blocking observations only

Write a short overall summary (1-3 sentences) in Phil's voice.

## Step 8 — Post inline comments

For **each** inline comment, run:

```bash
joan pr comment add \
  --agent phil \
  --owner <owner> \
  --repo <repo> \
  --pr <N> \
  --path <file-path> \
  --line <line-number> \
  --body "<comment text>"
```

Post comments one at a time. Do not batch them.

## Step 9 — Post the final review verdict

```bash
joan pr review submit \
  --agent phil \
  --owner <owner> \
  --repo <repo> \
  --pr <N> \
  --verdict <approve|request_changes|comment> \
  --body "<summary>"
```

## Step 10 — Report to the user

Tell the user:
- The verdict Phil gave
- How many inline comments were posted
- Whether dual-model synthesis was used (or fallback mode)
- A brief summary of Phil's findings

If Phil approved the PR, let the user know they can proceed with
`joan pr finish`.

## Rules

1. **Always use `joan`**, not bare `joan`.
2. **Post as Phil.** All comments and the review use `--agent phil` so they
   appear from Phil's Forgejo account.
3. **Dual-model is preferred.** Use Claude + Codex + synthesis unless tooling
   forces fallback.
4. **Be honest.** If the code is clean, approve it. Do not manufacture issues.
5. **Line numbers matter.** Use the line number from the new side of the diff
   (the `+` lines). If you cannot determine a precise line, skip that inline
   comment and mention the issue in the overall summary instead.
6. **No server required.** This skill uses only CLI commands — Phil's webhook
   server does not need to be running.
