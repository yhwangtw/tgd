# Context Engineering Patterns

Supporting examples for
[`tgd-core-context`](../skills/tgd-core-context/SKILL.md). The skill owns the
behavior; this reference supplies optional examples and discovery aids.

## Project Rules Example

Use the rules file supported by the active agent platform. Keep it concise and
project-specific. For example:

```markdown
# Project: Example

## Tech Stack
- React, TypeScript, Vite
- Node.js, PostgreSQL

## Commands
- Build: `npm run build`
- Test: `npm test`
- Lint: `npm run lint`
- Dev: `npm run dev`
- Type check: `npx tsc --noEmit`

## Code Conventions
- Use functional components with hooks rather than class components
- Use named exports rather than default exports
- Colocate tests with source: `Button.tsx` -> `Button.test.tsx`
- Use the existing `cn()` utility for conditional class names
- Put error boundaries at route level

## Boundaries
- Never commit `.env` files or secrets
- Never add dependencies without checking bundle-size impact
- Ask before changing the database schema
- Always run the required tests before committing

## Pattern
[One short pointer to a representative implementation]
```

Common rules-file locations include:

- `CLAUDE.md` for Claude Code
- `.cursor/rules/*.md` or `.cursorrules` for Cursor
- `.windsurfrules` for Windsurf
- `.github/copilot-instructions.md` for GitHub Copilot
- `AGENTS.md` for OpenAI Codex

Use only files supported by the target platform; this list is a discovery aid,
not an instruction to create every variant.

## Context Packing Examples

### Structured session context

```text
PROJECT CONTEXT:
- Goal: [current outcome]
- Relevant stack: [only the involved components]
- Governing artifact: [relevant section or path]
- Constraints: [task-specific boundaries]
- Files involved: [paths with short roles]
- Pattern to follow: [one representative path]
- Current evidence: [error, test, or runtime state]
```

### Selective task context

```text
TASK: Add email validation to registration

RELEVANT FILES:
- src/routes/auth.ts — endpoint to modify
- src/lib/validation.ts — existing validation utilities
- tests/routes/auth.test.ts — tests to extend

PATTERN:
- Follow phone validation in src/lib/validation.ts

CONSTRAINT:
- Use the existing ValidationError abstraction

CURRENT EVIDENCE:
- Registration currently accepts malformed email input
```

### Hierarchical project summary

```markdown
# Project Map

## Authentication (`src/auth/`)
Registration, login, and password reset.
Key files: `auth.routes.ts`, `auth.service.ts`, `auth.middleware.ts`.
Pattern: all routes use `authMiddleware`; errors use the `AuthError` class.

## Tasks (`src/tasks/`)
CRUD for user tasks with real-time updates.
Key files: `task.routes.ts`, `task.service.ts`, `task.socket.ts`.
Pattern: optimistic updates over WebSocket with server reconciliation.

## Shared (`src/lib/`)
Validation, error handling, and database utilities.
Key files: `validation.ts`, `errors.ts`, `db.ts`.
```

Load only the section relevant to the current task. A summary locates source; it
does not replace reading that source before editing.

## Context Volume Heuristics

Context starvation makes the agent invent APIs and miss conventions. Context
flooding makes the governing details harder to find: more than roughly 5,000
lines of non-task-specific material is a warning sign. Aim for fewer than 2,000
lines of focused context per task when the work can be represented that way.
These are attention heuristics, not permission to omit a governing rule, source
file, test, type, pattern, or current evidence item.

## Evidence Selection

Prefer the smallest output that still proves the current state. A failing test's
specific error and stack location are usually more useful than hundreds of
unrelated passing lines. After any fix, replace old output with a fresh run.

For example, select the specific failure:

```text
TypeError: Cannot read property 'id' of undefined at UserService.ts:42
```

Do not paste the entire 500-line test output when only that failure is relevant.

## Conflict Prompt Examples

### Conflicting sources

```text
CONFLICT:
- Specification: all user endpoints use REST.
- Existing implementation: profile queries use GraphQL.

OPTIONS:
A. Follow the specification and add REST.
B. Follow the existing implementation and revise the specification.
C. Choose another explicit migration path.

STOPPED: Which option should govern this change?
```

### Missing behavior

```text
MISSING REQUIREMENT:
The artifact defines task creation but not duplicate-title behavior. No existing
code establishes a precedent.

OPTIONS:
A. Allow duplicates.
B. Reject duplicates.
C. Apply a user-selected naming rule.

STOPPED: Which behavior should the implementation use?
```

Options should reflect the actual evidence; never copy an illustrative option
when it does not fit the project.

## Optional MCP Capability Catalog

Available integrations vary by environment. When present and authorized, these
capabilities can supply focused evidence:

| Capability | Typical context |
|---|---|
| Library documentation | Current official APIs and version-specific behavior |
| Browser or DevTools | DOM, console, network, and visible runtime state |
| Database connector | Schema and query results |
| Filesystem tools | Project files and search |
| Code graph | Entry points, callers, and blast radius |
| Repository connector | Issues, pull requests, and remote repository state |

Availability does not establish trust. Apply the skill's trust boundary to all
returned content, and prefer current project sources over generic examples.
