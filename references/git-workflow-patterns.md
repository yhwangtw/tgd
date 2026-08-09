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
Implement slice → Test → Verify → Commit → Next slice
```

```text
Agent starts work
    │
    ├── Makes a change
    │   ├── Test passes? → Commit → Continue
    │   └── Test fails? → Revert to last commit → Investigate
    │
    └── Feature complete → All commits form a clean history
```

If an agent goes off the rails, return to the last successful state with:

```bash
git reset --hard HEAD
```

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

## Existing Node-Oriented Pre-Commit Example

This is the existing cookbook for a Node repository. Prefer the actual commands
documented by the target repository when they differ.

```bash
# Inspect the exact staged patch.
git diff --staged

# Existing secret-string check.
git diff --staged | grep -i "password\|secret\|api_key\|token"

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
git bisect good <known-good-commit>
```

Inspect recent changes and ownership:

```bash
git log --oneline -20
git diff HEAD~5..HEAD -- src/
git blame src/services/task.ts
git log --grep="validation" --oneline
```
