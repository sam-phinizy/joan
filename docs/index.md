# Joan

Joan is a local code review gate for AI agents. Agents push work to a local [Forgejo](https://forgejo.org) instance, a human reviews it there, and only approved work gets pushed to the real upstream.

## How it works

```text
agent commits -> joan pr create -> human reviews on Forgejo -> joan pr finish -> local base branch -> joan pr push -> origin
```

Joan enforces the review gate at `joan pr finish`: it will not finish a PR that is unapproved or still has unresolved comments.

## Core guides

- [Getting started](getting-started.md)
- [Review workflow](review-workflow.md)
- [Phil local AI reviewer](phil.md)
- [Configuration and command reference](reference.md)

## Project docs

- [Implementation plan](plans/2026-02-27-phil-implementation.md)
- [Phil code review bot design](plans/2026-02-27-phil-code-review-bot-design.md)
- [Joan PR comment design](plans/2026-03-01-joan-pr-comment-design.md)
- [Joan PR comment implementation](plans/2026-03-01-joan-pr-comment-implementation.md)
- [Joan resolve PR design](plans/2026-03-01-joan-resolve-pr-design.md)
- [Joan resolve PR implementation](plans/2026-03-01-joan-resolve-pr-implementation.md)
- [Phil up queue worker UAT](uat/2026-02-28-phil-up-queue-worker-uat.md)
