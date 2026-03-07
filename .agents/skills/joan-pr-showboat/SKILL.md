---
name: joan-pr-showboat
description: >-
  Draft a Showboat walkthrough prompt for the current Joan PR. Use when the
  user wants a deep-dive interactive explanation of the code changes, wants to
  prepare a Showboat page for a Joan review PR, or asks for a walkthrough
  prompt they can edit before handing off to a Showboat-focused sub-agent.
---

# Joan PR Showboat

Prepare an editable prompt for a Showboat-style deep dive of the current Joan
review PR. This skill does not publish anything by default. Its job is to
gather the right context, produce a focused draft prompt, and hand that prompt
back to the user for editing in Claude CLI before any Showboat-specific
workflow runs.

## Intent

Use this when the user wants:
- a deep explanation of what the current PR changes do
- a guided walkthrough/tutorial for the changed code paths
- a Showboat prompt draft based on the current Joan PR

Do not use this skill to:
- replace the Joan PR body with long-form explanation text
- auto-publish docs or static assets unless the user explicitly asks
- generate a generic whole-repo overview unrelated to the current PR

## Preconditions

1. Verify `.joan/config.toml` exists. If not, tell the user to run
   `/joan:joan-setup` first.
2. Confirm the current branch has an open Joan PR:
   ```bash
   joan pr sync
   ```
   If this fails with "No open PR found", stop and tell the user they need an
   open Joan PR first.

## Inputs

Collect the following context:
- current working branch
- derived Joan stage branch
- repo owner and repo name from `.joan/config.toml`
- current PR number
- current HEAD commit SHA
- diff between the stage branch and `HEAD`
- any concise PR summary already available from the current context
- optional author-supplied explanatory text from the user

The optional explanatory text should be treated as steering notes, not as a
replacement for the PR context. Use it to emphasize intent, audience, or areas
that deserve extra explanation.

## Workflow

### 1. Gather PR context

Determine the current branch:

```bash
git rev-parse --abbrev-ref HEAD
```

Derive the stage branch as `joan-stage/<current-branch>`, then gather the diff:

```bash
git fetch joan-review
git diff joan-review/joan-stage/<current-branch>..HEAD
```

If the diff is empty, stop and tell the user there are no changes to explain.

Also read `.joan/config.toml` to obtain:
- `forgejo.owner`
- `forgejo.repo`

Extract the PR number from `joan pr sync`.

Determine the current HEAD SHA:

```bash
git rev-parse HEAD
```

### 2. Build a short focus summary

Before drafting the Showboat prompt, summarize:
- the likely purpose of the change
- the most important files or subsystems touched
- the main reading path a reviewer should follow
- any risks, edge cases, or tradeoffs worth deeper explanation

Keep this summary short and practical. It is for orienting the user before they
edit the generated prompt.

### 3. Draft the Showboat prompt

Produce a draft prompt the user can edit before handing it to a Showboat-style
sub-agent. The prompt must:
- focus on the code changed in the current PR
- explain what the changes do and how the changed code works
- avoid generic repo-wide exposition unless it is necessary to explain the PR
- incorporate optional author notes when provided
- position the output as a deep-dive companion to the Joan PR, not as the PR
  summary itself

Use this structure:

```text
Create an interactive walkthrough for this Joan review PR.

Goal:
Explain what the code changes do, how the changed code works, and how to follow
the main execution paths touched in this PR.

Audience:
A reviewer or contributor who wants a deeper explanation than the Joan PR body
provides.

Scope:
Focus on the code changed in this PR. Do not write a generic whole-repo overview
unless it is necessary to explain the change.

Context:
- Repo: <owner>/<repo>
- Working branch: <branch>
- Stage branch: <joan-stage/branch>
- PR number: <N>
- Head commit: <sha>

Author notes:
<optional user-provided explanatory text or "None">

PR summary:
<short summary from current context>

Focus areas:
- <key file, module, or code path>
- <key file, module, or code path>

Diff:
```diff
<diff>
```

Instructions:
- Start by explaining the purpose of the change.
- Walk through the key files/functions in a useful reading order.
- Explain control flow and changed behavior concretely.
- Use before/after behavior when helpful.
- Call out important tradeoffs, risks, and notable implementation details.
- Prefer explanation of real code paths over generic summaries.
- Treat this as a deep-dive companion to the PR, not the PR summary itself.
```

### 4. Hand off cleanly

After drafting the prompt:
- show the focus summary
- show the draft prompt
- tell the user to edit the prompt in Claude CLI as needed
- stop unless the user explicitly asks to continue into a Showboat-specific
  generation or publishing step

## Output Contract

The response should contain:
1. A short focus summary
2. A draft Showboat prompt
3. A brief handoff note that the prompt is intended to be edited before running
   a Showboat-oriented sub-agent

Do not automatically:
- update the PR body
- post PR comments
- publish static assets
- claim a Showboat page was created when none was created

## Relationship to Joan PR Text

Joan PR text should remain concise and review-oriented.

Recommended split:
- PR body: compact summary, review focus, risks, latest link if one exists
- Showboat walkthrough: deeper explanation/tutorial of the code changes

If the user later asks to link a generated walkthrough from the PR, prefer a
small PR section such as:

```md
## Interactive Walkthrough

Deep dive for the current PR head: <url>
```

Do not expand the PR body into the full tutorial.
