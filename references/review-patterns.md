# Review and Documentation Patterns

Illustrative, copyable examples for `tgd-review-quality` and `tgd-review-adr`. These examples do not define policy; the owning skill does.

## Change-Splitting Examples

| Strategy | Example use |
|---|---|
| Stack | Submit a prerequisite, then build the dependent change on it |
| File group | Separate changes that need different reviewers |
| Horizontal | Add shared code or stubs before consumers |
| Vertical | Deliver smaller end-to-end feature slices |

## Independent Review Pattern

```text
Model A writes the code
    │
    ▼
Model B reviews correctness and architecture
    │
    ▼
Model A addresses findings
    │
    ▼
Human makes the final call
```

Example prompt:

```text
Review this change for correctness, security, and project conventions.
The spec says [X]. The change should [Y]. Label every finding Critical,
Important, Nit, or FYI.
```

## Dead-Code Handoff Example

```text
DEAD CODE IDENTIFIED:
- formatLegacyDate() in src/utils/date.ts — replaced by formatDate()
- OldTaskCard in src/components/ — replaced by TaskCard
- LEGACY_API_URL in src/config.ts — no remaining references
→ Safe to remove these?
```

## Copyable Review Checklist

```markdown
## Review: [PR/change title]

### Context
- [ ] I understand what this change does and why

### Correctness
- [ ] Matches the governing spec/task
- [ ] Edge and error paths are handled
- [ ] Tests would catch regression

### Readability and architecture
- [ ] Names and control flow are clear
- [ ] Existing patterns and boundaries are respected
- [ ] Complexity and dependencies are justified

### Security and performance
- [ ] External input and auth boundaries are safe
- [ ] No secrets, injection, N+1, or unbounded operations

### Verification and verdict
- [ ] Tests and build pass
- [ ] Manual evidence exists when applicable
- [ ] Approve / Request changes
```

## Tech-Debt Decision Example

```text
Issue found during review
├── Blocks merge? → Request changes; do not file it away as debt
└── Non-blocking
    ├── Belongs in this cycle? → Fix now
    └── Intentionally deferred → Record DEBT.md; mirror to Jira if configured
```

### Copyable Tech-Debt Ticket

```markdown
## Tech Debt Summary
[One-line description]

## Category and Priority
[Architecture / Performance / Security / Code Quality / Test Coverage]
[High / Medium / Low]

## Context
- Feature: <feature-name>
- Files: [path/to/file]
- Review stage: /tgd-review

## Current State
[What exists now]

## Desired State
[What should exist]

## Impact if Not Addressed
[Consequence]

## Suggested Approach
[If known]

## Acceptance Criteria
- [ ] [Criterion 1]
- [ ] [Criterion 2]
```

`TASKS.md` annotation example:

```markdown
- [x] Implement login API  <!-- TECH-DEBT: JIRA-456 - Move hashing to bcrypt -->
```

`DEBT.md` table example:

```markdown
# Tech Debt: <feature-name>

| Issue | Category | Priority | Jira Key |
|---|---|---|---|
| Password hashing | Security | High | JIRA-456 |
| Missing pagination | Performance | Medium | JIRA-457 |
```

## Documentation Examples

### Why-Comment and Gotcha

```typescript
// Rate limiting uses a sliding window so bursts cannot straddle a fixed reset.
if (now - windowStart > WINDOW_SIZE_MS) {
  counter = 0;
  windowStart = now;
}

/**
 * Must run before first render. Calling after hydration flashes unstyled content
 * because theme context is unavailable during SSR. See ADR-003.
 */
export function initializeTheme(theme: Theme): void {
  // ...
}
```

### Typed Public API

```typescript
/**
 * Creates a task.
 * @param input - Title is required; description is optional.
 * @returns The task with server-generated ID and timestamps.
 * @throws {ValidationError} When the title is invalid.
 * @throws {AuthenticationError} When the caller is unauthenticated.
 * @example const task = await createTask({ title: 'Buy groceries' });
 */
export async function createTask(input: CreateTaskInput): Promise<Task> {
  // ...
}
```

### OpenAPI Shape

```yaml
paths:
  /api/tasks:
    post:
      summary: Create a task
      requestBody:
        required: true
      responses:
        '201': { description: Task created }
        '422': { description: Validation error }
```

### README Shape

```markdown
# Project Name
One-paragraph purpose.

## Quick Start
1. Install dependencies.
2. Copy the environment template.
3. Run the development server.

## Commands
| Command | Description |
|---|---|
| `npm test` | Run tests |
| `npm run build` | Build production output |

## Architecture
Key boundaries and links to ADRs.

## Contributing
Standards and review process.
```

### General SemVer Changelog Example

The tGD lifecycle uses CalVer; this generic SemVer example is only for projects whose own policy requires it.

```markdown
## [1.2.0] - 2025-01-20
### Added
- Task sharing (#123)
### Fixed
- Duplicate task creation (#125)
### Changed
- List page size increased to 50 (#126)
```
