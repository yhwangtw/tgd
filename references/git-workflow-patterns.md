# Git Workflow Patterns

This reference contains optional diagrams and copyable examples for
[`tgd-core-git`](../skills/tgd-core-git/SKILL.md). The skill owns the policy;
these examples illustrate it and do not create a second contract.

## Trunk and Branch Shape

```text
main ──●──●──●──●──●──●──●──●──●──  (always deployable)
        ╲      ╱  ╲    ╱
         ●──●─╱    ●──╱    ← short-lived feature branches (1-3 days)
```

Example intent-oriented names:

```text
feature/task-creation
feature/user-settings
fix/duplicate-tasks
chore/update-deps
refactor/auth-module
```

## Increment and Save-Point Shape

```text
Implement slice → Test → Verify → Authorized commit → Next slice
```

```text
Agent starts work
    │
    ├── Makes a change
    │   ├── Test passes? → Authorized commit → Continue
    │   └── Test fails? → Inspect and preserve → Repair exact slice
    │
    └── Feature complete → Verified commits form a clean history
```

Before discarding any failed work, resolve the exact scope:

```bash
agent_owned_path='src/example.ts' # Replace with the exact authorized path.
git status --short --branch
git diff --name-status -- "$agent_owned_path"
git diff --staged --name-status -- "$agent_owned_path"
```

Preserve unrelated staged, unstaged, and untracked changes. Prefer repairing
the failed slice manually. If discarding an exact tracked path is authorized,
use a path-scoped restore only after recording or backing up anything that must
remain recoverable; move exact untracked paths to a recovery location rather
than deleting them. Before inspecting patch contents, follow the same secret
scanner or explicitly owner-confirmed non-logged review gate as a commit.

## Atomic History and Messages

Example atomic history:

```text
a1b2c3d Add task creation endpoint with validation
d4e5f6g Add task creation form component
h7i8j9k Connect form to API and add loading state
m1n2o3p Add task creation tests (unit + integration)
```

Avoid mixed messages such as:

```text
x1y2z3a Add task feature, fix sidebar, update deps, refactor utils
```

Example message that explains intent:

```text
feat: add email validation to registration endpoint

Prevents invalid email formats from reaching the database.
Uses Zod schema validation at the route handler level,
consistent with existing validation patterns in auth.ts.
```

Avoid messages that merely restate a filename, such as `update auth.ts`.

Separate concerns in history:

After the active lifecycle step or user authorizes the commits and the full
pre-commit gate passes:

```bash
git commit -m "refactor: extract validation logic to shared utility"
git commit -m "feat: add phone number validation to registration"
```

## Change Summary Example

This copyable shape implements the structured change-summary rule in the main
skill.

```text
CHANGES MADE:
- src/routes/tasks.ts: Added validation middleware to POST endpoint
- src/lib/validation.ts: Added TaskCreateSchema using Zod

THINGS I DIDN'T TOUCH (intentionally):
- src/routes/auth.ts: Has similar validation gap but out of scope
- src/middleware/error.ts: Error format could be improved (separate task)

POTENTIAL CONCERNS:
- The Zod schema is strict — rejects extra fields. Confirm this is desired.
- Added zod as a dependency (72KB gzipped) — already in package.json
```

## Node-Oriented Pre-Commit Example

This is the existing cookbook for a Node repository. Prefer the actual commands
documented by the target repository when they differ.

```bash
# Inspect staged scope without printing its contents.
git diff --staged --name-status

# Run the repository-configured secret scanner here. Keep matching values out
# of terminal and agent logs. Without one, require an explicitly identified
# user or local repository owner to inspect and confirm the patch in a
# non-logged local context; stop if that confirmation is unavailable.

# After the scanner passes, or as the owner-confirmed fallback review, inspect
# the exact patch in an authorized local context that does not copy possible
# secrets into agent or shared logs.
git diff --staged

# Project gates used by the example stack.
npm test
npm run lint
npx tsc --noEmit
```

Example `lint-staged` configuration with Husky:

```json
{
  "lint-staged": {
    "*.{ts,tsx}": ["eslint --fix", "prettier --write"],
    "*.{json,md}": ["prettier --write"]
  }
}
```

## Git Debugging Commands

Find the commit that introduced a bug:

```bash
git bisect start
git bisect bad HEAD
known_good_commit='abc1234' # Replace with the verified known-good commit.
git bisect good "$known_good_commit"
```

Inspect recent changes and ownership:

```bash
git log --oneline -20
git diff HEAD~5..HEAD -- src/
git blame src/services/task.ts
git log --grep="validation" --oneline
```
