# Joan Docs

Joan now uses one workflow:

- work on a normal task branch
- review incrementally into `joan-stage/<task-branch>` on the Forgejo review remote
- publish upstream later with `uv run joan ship`

Start here:

1. [Getting Started](./getting-started.md)
2. [Review Workflow](./review-workflow.md)
3. [Reference](./reference.md)

Breaking change: the old `joan branch ...`, `joan plan ...`, and `joan pr push`
flows have been removed.
