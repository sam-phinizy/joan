---
name: joan-task
description: >-
  Start or manage a Joan task branch. Use when the user wants to begin a new
  tracked branch, attach Joan to an existing working branch, inspect the task
  state, or push another review round to Forgejo.
---

# Joan Task

Joan now reviews normal working branches against long-lived stage branches on
the Forgejo review remote.

## Model

- Working branch: where code changes happen
- Stage branch: `joan-stage/<working-branch>` on the review remote
- Review PR: `working-branch -> joan-stage/<working-branch>`
- Final publish step: `joan ship`

## Start New Work

Use this when the user is starting a fresh task:

```bash
joan task start <branch-name> --from origin/main
```

This:
- creates and checks out the working branch
- creates the matching stage branch on the review remote
- pushes the working branch to the review remote

## Track Existing Work

Use this when the branch already exists locally and needs to enter Joan:

```bash
joan task track --from origin/main
```

Use `--branch <name>` when the target branch is not checked out.

## Inspect Status

```bash
joan task status
```

This prints JSON with:
- the working branch
- the derived stage branch
- whether those refs exist on the review remote
- whether there is an open PR for the task branch

## Push Another Review Round

```bash
joan task push
```

Use this after new commits are ready for another pass on the same PR.

## Handoff

Once the user has reviewable code:
- use `/joan:joan-review` to open or manage the Forgejo PR

When the staged work is ready for the final GitHub PR:
- run `joan ship`
