# Reference

## Core Commands

| Command | Description |
|---------|-------------|
| `joan init` | Interactive setup for the current repository |
| `joan remote add` | Create or repair the Forgejo review remote |
| `joan task start <branch> [--from REF]` | Create a new task branch and its stage branch |
| `joan task track --from REF [--branch NAME]` | Attach Joan to an existing working branch |
| `joan task status [--branch NAME]` | Show task and PR state as JSON |
| `joan task push` | Push the current task branch to the review remote |
| `joan pr create` | Create a Forgejo PR from the task branch to its stage branch |
| `joan pr open` | Alias for `joan pr create` |
| `joan pr sync` | Show PR approval and unresolved comment state |
| `joan pr comments` | List PR comments |
| `joan pr reviews` | List review submissions |
| `joan pr comment resolve <id>` | Resolve a PR comment |
| `joan pr comment post --body TEXT` | Post a PR-level comment |
| `joan pr comment add ...` | Post one inline comment using an agent token |
| `joan pr update --body TEXT` | Replace the PR body |
| `joan pr review create --json-input TEXT` | Post a structured review |
| `joan pr review approve [--body TEXT]` | Approve the current PR |
| `joan pr review request-changes [--body TEXT]` | Request changes on the current PR |
| `joan pr review submit ...` | Post a review on a specific PR using an agent token |
| `joan pr finish` | Merge the approved PR into the stage branch |
| `joan ship [--as BRANCH]` | Create or refresh the publish branch and push it upstream |

## Other Commands

| Command | Description |
|---------|-------------|
| `joan doctor` | Health checks for local setup |
| `joan ssh ...` | SSH key setup helpers |
| `joan services ...` | Service bundle helpers |
| `joan skills ...` | Install Joan skills for Claude or Codex |
| `joan phil ...` | Phil webhook and review helpers |
| `joan worktree ...` | Managed worktree helpers |
