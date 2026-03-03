# Getting Started

Joan only supports the staged branch workflow now.

## 1. Initialize Joan

```bash
uv run joan init
```

This creates `.joan/config.toml`.

## 2. Add the review remote

```bash
uv run joan remote add
```

This creates or repairs the Forgejo review remote (default name: `joan-review`).

## 3. Start a task

```bash
uv run joan task start feature/redshift-query --from origin/main
```

This creates:
- your local working branch: `feature/redshift-query`
- a remote stage branch: `joan-stage/feature/redshift-query`

## 4. Open a Forgejo PR

```bash
uv run joan pr create --title "Add Redshift query task"
```

The PR target will be `joan-stage/feature/redshift-query`.

## 5. Finish the review

After approval and comment resolution:

```bash
uv run joan pr finish
```

That merges the PR into the stage branch.

## 6. Prepare the final GitHub branch

```bash
uv run joan ship --as sam/redshift-query
```

This creates or refreshes a clean local publish branch from the stage branch and
pushes it to the upstream remote. Open the final GitHub PR manually.

## Breaking Change

The old `joan branch ...`, `joan plan ...`, and `joan pr push` commands are no
longer part of Joan’s workflow.
