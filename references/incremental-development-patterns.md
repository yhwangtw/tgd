# Incremental Development Patterns

Illustrative examples only. Slice order, scope, safety, verification, and commit
requirements live in
[`tgd-develop-incremental`](../skills/tgd-develop-incremental/SKILL.md).

## Cycle

```text
Scope → Implement → Test → Verify → Commit → Next slice
```

## Vertical Slice Example

```text
1. Create task: schema + API + basic UI + tests
2. List tasks: query + API + UI + tests
3. Edit task: update + API + UI + tests
4. Delete task: delete + API + confirmation + tests
```

## Contract-First Example

```text
0. Define API types/interfaces/OpenAPI contract
1a. Backend implements the contract with API tests
1b. Frontend implements against matching fixture data
2. Integrate and verify end-to-end
```

## Risk-First Example

```text
1. Prove the WebSocket connection under realistic conditions
2. Build updates on the proven connection
3. Add offline behavior and reconnection
```

## Simplicity Contrast

```text
One notification:
  avoid a generic EventBus middleware framework
  use a direct, tested function call

Two similar components:
  avoid an abstract factory
  use clear components with a small shared utility
```

## Feature Flag Shape

```typescript
const ENABLE_TASK_SHARING = process.env.FEATURE_TASK_SHARING === 'true';

if (ENABLE_TASK_SHARING) {
  renderTaskSharing();
}
```

## Safe Default Shape

```typescript
export function createTask(
  data: TaskInput,
  options?: { notify?: boolean },
) {
  const shouldNotify = options?.notify ?? false;
  // Existing task creation follows.
}
```

## Scoped Agent Prompt

```text
Implement the current planned task in the supplied worktree.

For this increment, change only the database schema and API endpoint.
Do not touch the UI. Use the repository's exact focused-test and build commands,
then return the changed files, observed results, and commit SHA.

Report unrelated improvements or bugs; do not fix them in this increment.
```
