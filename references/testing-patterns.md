# Testing Patterns Reference

Examples and framework recipes for
[`tgd-develop-tdd`](../skills/tgd-develop-tdd/SKILL.md). The main skill owns all
testing policy, gates, thresholds, and required workflow. This file is
illustrative only; use the relevant section when syntax or a worked example is
helpful, and never treat an example here as an alternative policy.

## Table of Contents

- [TDD Cycle](#tdd-cycle)
- [Bug Reproduction](#bug-reproduction)
- [Test Pyramid and Selection](#test-pyramid-and-selection)
- [State-Based Assertions](#state-based-assertions)
- [DAMP Test Stories](#damp-test-stories)
- [Arrange, Act, Assert](#arrange-act-assert)
- [One Concept and Descriptive Names](#one-concept-and-descriptive-names)
- [Common Assertions](#common-assertions)
- [Test Doubles](#test-doubles)
- [React and Component Testing](#react-and-component-testing)
- [API and Integration Testing](#api-and-integration-testing)
- [E2E Testing with Playwright](#e2e-testing-with-playwright)
- [Browser Inspection](#browser-inspection)
- [AC-Tagged Tests](#ac-tagged-tests)
- [Worked Anti-Patterns](#worked-anti-patterns)

## TDD Cycle

```text
    RED                GREEN              REFACTOR
 Write a test    Write minimal code    Clean up the
 that fails  ──→  to make it pass  ──→  implementation  ──→  repeat
      │                  │                    │
      ▼                  ▼                    ▼
 Correct failure      Test passes         Tests stay green
```

```typescript
// RED: createTask does not exist yet, so this should fail for that reason.
it('creates a task with title and default status', async () => {
  const task = await createTask({ title: 'Buy groceries' });
  expect(task).toMatchObject({ title: 'Buy groceries', status: 'pending' });
  expect(task.id).toBeDefined();
  expect(task.createdAt).toBeInstanceOf(Date);
});

// GREEN: the smallest implementation that satisfies the test.
export async function createTask(input: { title: string }): Promise<Task> {
  const task = {
    id: generateId(),
    title: input.title,
    status: 'pending' as const,
    createdAt: new Date(),
  };
  await db.tasks.insert(task);
  return task;
}
```

## Bug Reproduction

```text
Bug report → failing reproduction → minimum fix → reproduction passes
           → full suite passes → inspect affected tests and components
```

```typescript
// Bug: completing a task does not record completedAt.
it('sets completedAt when a task is completed', async () => {
  const task = await createTask({ title: 'Test' });
  const completed = await completeTask(task.id);

  expect(completed.status).toBe('completed');
  expect(completed.completedAt).toBeInstanceOf(Date); // Fails before the fix.
});

export async function completeTask(id: string): Promise<Task> {
  return db.tasks.update(id, {
    status: 'completed',
    completedAt: new Date(),
  });
}
```

An optional reproduction-test subagent can be prompted with only the bug
description and this output constraint: "Write a test that reproduces the bug
and fails against the current code." The main agent still observes the failure
before touching production code.

## Test Pyramid and Selection

```text
          ╱╲
         ╱  ╲         E2E
        ╱────╲        Critical real user flows
       ╱      ╲       Integration
      ╱────────╲      Boundaries and component interaction
     ╱          ╲     Unit
    ╱────────────╲    Pure isolated logic
```

The diagram visualizes relative layering only. Use the portfolio targets,
resource constraints, and selection rules in the main skill.

## State-Based Assertions

```typescript
// Outcome-focused: survives an internal refactor.
it('returns newest tasks first', async () => {
  const tasks = await listTasks({ sortBy: 'createdAt', sortOrder: 'desc' });
  expect(tasks[0].createdAt.getTime())
    .toBeGreaterThan(tasks[1].createdAt.getTime());
});

// Interaction-focused: coupled to the current implementation.
it('calls db.query with an ORDER BY clause', async () => {
  await listTasks({ sortBy: 'createdAt', sortOrder: 'desc' });
  expect(db.query).toHaveBeenCalledWith(
    expect.stringContaining('ORDER BY created_at DESC'),
  );
});
```

## DAMP Test Stories

```typescript
it('rejects tasks with empty titles', () => {
  const input = { title: '', assignee: 'user-1' };
  expect(() => createTask(input)).toThrow('Title is required');
});

it('trims whitespace from titles', () => {
  const input = { title: '  Buy groceries  ', assignee: 'user-1' };
  const task = createTask(input);
  expect(task.title).toBe('Buy groceries');
});
```

The repeated input shape keeps both examples readable without tracing a shared
fixture.

## Arrange, Act, Assert

```typescript
it('marks a task overdue after its deadline', () => {
  // Arrange
  const task = createTask({
    title: 'Test',
    deadline: new Date('2025-01-01'),
  });

  // Act
  const result = checkOverdue(task, new Date('2025-01-02'));

  // Assert
  expect(result.isOverdue).toBe(true);
});
```

## One Concept and Descriptive Names

```typescript
// Each name specifies one behavior.
describe('TaskService.completeTask', () => {
  it('sets status to completed and records the timestamp', () => {});
  it('throws NotFoundError for a missing task', () => {});
  it('is a no-op when the task is already completed', () => {});
  it('sends a notification to the assignee', () => {});
});

// The vague name and mixed concepts make failures hard to diagnose.
it('validates titles correctly', () => {
  expect(() => createTask({ title: '' })).toThrow();
  expect(createTask({ title: '  hello  ' }).title).toBe('hello');
  expect(() => createTask({ title: 'a'.repeat(256) })).toThrow();
});
```

## Common Assertions

```typescript
expect(result).toBe(expected);           // strict equality
expect(result).toEqual(expected);        // deep equality
expect(result).toStrictEqual(expected);  // deep equality and type matching

expect(result).toBeTruthy();
expect(result).toBeFalsy();
expect(result).toBeNull();
expect(result).toBeDefined();
expect(result).toBeUndefined();

expect(result).toBeGreaterThan(5);
expect(result).toBeLessThanOrEqual(10);
expect(result).toBeCloseTo(0.3, 5);

expect(result).toMatch(/pattern/);
expect(result).toContain('substring');
expect(array).toContain(item);
expect(array).toHaveLength(3);
expect(object).toHaveProperty('key', 'value');

expect(() => fn()).toThrow(ValidationError);
await expect(asyncFn()).resolves.toBe(value);
await expect(asyncFn()).rejects.toThrow(Error);
```

## Test Doubles

The main skill defines when each kind of double is acceptable. These snippets
only show Jest syntax for a boundary where a double has already been selected.

```typescript
const stub = jest.fn().mockResolvedValue({ data: 'test' });
expect(stub).toHaveBeenCalledWith('task-1');

jest.mock('./database', () => ({
  query: jest.fn().mockResolvedValue([{ id: 1, title: 'Test' }]),
}));

jest.mock('./utils', () => ({
  ...jest.requireActual('./utils'),
  generateId: jest.fn().mockReturnValue('test-id'),
}));
```

Typical controllable boundaries include databases, HTTP requests, file-system
operations, external APIs, and time. Internal utilities, business rules, data
transforms, validation, and pure functions usually produce a less useful test
when replaced with interaction mocks.

## React and Component Testing

```tsx
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

it('submits the task entered by the user', async () => {
  const onSubmit = jest.fn();
  render(<TaskForm onSubmit={onSubmit} />);

  fireEvent.change(screen.getByRole('textbox', { name: /title/i }), {
    target: { value: 'New Task' },
  });
  fireEvent.click(screen.getByRole('button', { name: /create/i }));

  await waitFor(() => {
    expect(onSubmit).toHaveBeenCalledWith({ title: 'New Task' });
  });
});
```

## API and Integration Testing

```typescript
import request from 'supertest';
import { app } from '../src/app';

it('creates a task and returns 201', async () => {
  const response = await request(app)
    .post('/api/tasks')
    .send({ title: 'Test Task' })
    .set('Authorization', `Bearer ${testToken}`)
    .expect(201);

  expect(response.body).toMatchObject({
    id: expect.any(String),
    title: 'Test Task',
    status: 'pending',
  });
});

it('returns 422 for invalid input', async () => {
  const response = await request(app)
    .post('/api/tasks')
    .send({ title: '' })
    .set('Authorization', `Bearer ${testToken}`)
    .expect(422);

  expect(response.body.error.code).toBe('VALIDATION_ERROR');
});

it('returns 401 without authentication', async () => {
  await request(app)
    .post('/api/tasks')
    .send({ title: 'Test' })
    .expect(401);
});
```

## E2E Testing with Playwright

```typescript
import { test, expect } from '@playwright/test';

test('user can create and complete a task', async ({ page }) => {
  await page.goto('/');
  await page.getByLabel('Email').fill('test@example.com');
  await page.getByLabel('Password').fill('testpass123');
  await page.getByRole('button', { name: 'Log in' }).click();

  await page.getByRole('button', { name: 'New Task' }).click();
  await page.getByLabel('Title').fill('Buy groceries');
  await page.getByRole('button', { name: 'Create' }).click();
  await expect(page.getByText('Buy groceries')).toBeVisible();

  await page.getByLabel('Complete Buy groceries').click();
  await expect(page.getByText('Buy groceries')).toHaveCSS(
    'text-decoration-line',
    'line-through',
  );
});
```

## Browser Inspection

```text
1. REPRODUCE — navigate, trigger the behavior, capture the initial state
2. INSPECT   — console, DOM, computed styles, network, accessibility
3. DIAGNOSE  — compare actual and expected HTML, CSS, JS, and data
4. FIX       — change source code
5. VERIFY    — reload, capture the result, inspect console, run tests
```

Useful evidence includes console errors and warnings, network status and payload
shape, DOM structure and accessibility state, computed styles, performance
signals such as LCP/CLS/INP and long tasks, and before/after screenshots. Follow
the browser trust boundary in the main skill while gathering it.

## AC-Tagged Tests

```typescript
test('AC-1.2: rejects login with an empty password', () => {
  // ...
});
```

```python
def test_ac_1_2_rejects_empty_password():
    """AC-1.2: Given empty password, When login, Then return 400."""
```

## Worked Anti-Patterns

| Example | Failure mode | Illustrative improvement |
|---|---|---|
| Assert an internal call sequence | Breaks when behavior-preserving refactors change internals | Assert inputs and observable outputs |
| Snapshot every result | Large diffs become rubber-stamped | Assert specific meaningful values |
| Share mutable state | Tests pass alone and fail together | Set up and tear down state per test |
| Test third-party behavior | Spends effort outside application responsibility | Exercise the application's boundary behavior |
| Mock every collaborator | Suite passes while real integration breaks | Use real code or a faithful fake where practical |
| Use vague names such as `works` | Failure does not identify the violated behavior | State outcome and condition in the name |
| Forget to await asynchronous work | Errors are swallowed and false passes occur | Await the operation and its assertion |
| Permanently skip a failing test | Hides a regression and creates dead coverage | Repair the test or behavior rather than bypassing it |

These are worked examples, not a separate compliance list. Apply the
rationalizations, red flags, and verification checklist in the main skill.
