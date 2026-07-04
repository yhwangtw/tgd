---
name: tgd-planning-and-task-breakdown
description: Breaks work into ordered tasks. Use when you have a spec or clear requirements and need to break work into implementable tasks. Use when a task feels too large to start, when you need to estimate scope, or when parallel work is possible.
---

# Planning and Task Breakdown

## Overview

Decompose work into small, verifiable tasks with explicit acceptance criteria. Good task breakdown is the difference between an agent that completes work reliably and one that produces a tangled mess. Every task should be small enough to implement, test, and verify in a single focused session.

## When to Use

- You have a spec and need to break it into implementable units
- A task feels too large or vague to start
- Work needs to be parallelized across multiple agents or sessions
- You need to communicate scope to a human
- The implementation order isn't obvious

**When NOT to use:** Single-file changes with obvious scope, or when the spec already contains well-defined tasks.

## The Zero-Context Rule

**Plans must assume the executor has:**
- **Zero context** about the codebase
- **Limited knowledge** of the problem domain
- **Questionable taste** in design decisions
- **Weak test design skills**

This means every task must contain:
- **Exact file paths** (not "the config file")
- **Exact commands** to run (not "run the tests")
- **Code blocks** with actual implementation hints (not "implement the function")
- **Expected outputs** (not "verify it works")

**Never write:**
- "Similar to Task N" (tasks may be read out of order)
- "TBD" or "TODO" or "fill in details"
- "Add appropriate error handling" (specify which errors, which handling)
- Steps that describe *what* without showing *how*

## The Planning Process

### Step 0: Feature Name Resolution
Before planning, determine and validate `<feature-name>`:
1. **Verify**: Scan `$TGD_DIR/` for **feature directories** — subdirectories containing `SPEC.md` or `PRD.md`. Infrastructure dirs (`.scans/`, `wiki/`, and any dot-directories) are NOT features — always exclude them. If exactly one feature directory exists, lock that name.
2. **Ask (if ambiguous)**: If multiple feature directories exist, list them and ask the user to pick. If none exist, STOP — run `/tgd-define` first.
3. **Lock**: All planning artifacts go into `$TGD_DIR/<feature-name>/`.

### Step 1: Enter Plan Mode (Read-Only Analysis)

Before writing any code, operate in read-only mode to gather context from all available tGD artifacts:

- **Read `$TGD_DIR/CONTEXT.md`**: Understand existing project structure, tech stack, and conventions.
- **Read `$TGD_DIR/<feature-name>/PRD.md`**: Understand the business goals, user pain points, and scope boundaries.
- **Read `$TGD_DIR/<feature-name>/SPEC.md`**: Analyze technical requirements, API contracts, and database schemas.
- **Read `$TGD_DIR/<feature-name>/DESIGN.md` (if present)**: Review component trees and UI flows.

**Synthesis:** Map dependencies between existing code and new requirements. Note risks and unknowns. If `.codegraph/` exists, run `codegraph impact "<core-symbol>"` on any symbol the feature will modify to assess blast radius and inform task ordering. If planning a large refactor, run the `understand-diff` skill to visualize the impact of proposed changes before breaking down tasks.

**Do NOT write code during planning.** Write a plan document at `$TGD_DIR/<feature-name>/TASKS.md` covering: dependency graph, ordered task list with acceptance criteria, verification checkpoints, and risks with mitigations.

**TASKS.md template (save to `$TGD_DIR/<feature-name>/TASKS.md`):**

```markdown
# TASKS.md: [Feature Name]

> **Corresponding PRD**: [PRD.md](PRD.md)
> **Tech Stack**: [List from SPEC]

## Overview
[One paragraph summary of what we're building]

## Architecture Decisions
- [Key decision 1 and rationale]
- [Key decision 2 and rationale]

---

## Task 1: [User Story Title] (Story ID: US-01)

### 1. Context & Goal
[What is the goal of this task? Why is it important?]
- **Priority**: [High/Medium/Low]
- **Dependencies**: [None / Task N]

### 2. Technical Design

**Database Schema (if any):**
```[Language]
// Example: Prisma Schema or SQL
```

**API Contract:**
- **Method** `/endpoint`
- **Input**: `{ ... }`
- **Output**: `Status Code { ... }`

### 3. Acceptance Criteria (BDD)
- Every task must use **BDD** (Given/When/Then) format — this ensures all criteria are behavior-level, testable, and consistent with REGRESSION-CATALOG entries.
- Every criterion carries a **stable ID**: `AC-<task>.<n>` (AC-1.1, AC-1.2, …). The verifying test MUST mention this ID in its name, docstring, or a comment — `ac-trace.py` cross-references them during `/tgd-verify`.

- **AC-1.1** — **Given** [initial context] **When** [event happens] **Then** [expected outcome]
  - **Regression**: [Yes `[R]` / No]
  - **Test**: [`tests/path/to/test.ts` — filled during `/tgd-develop`; MANDATORY for `[R]` criteria]

- **`[R]` marking rules** — must mark `[R]` if the criterion matches ANY of:
  - (a) Verifies an acceptance criterion from the PRD's User Stories table (a US-xx row's "Acceptance Criteria" column) or a PRD Success Metric. (Note the namespaces: PRD rows are `US-xx`; the `AC-<task>.<n>` ids exist only in TASKS.md.)
  - (b) Covers a critical user path (auth, payment, data loss, security boundary)
  - (c) Catches a previously-fixed bug from `REGRESSION-CATALOG.md`
  - **SHOULD NOT mark `[R]`** if criterion is: cosmetic, internal refactor, dev-only tooling, single-use migration
  - **When in doubt**: mark `[R]`. The cost of an extra catalog entry is low; the cost of missing a regression is high.
  - **If `[R]`**: a corresponding test MUST be created during `/tgd-develop` (TDD) and its path recorded in the criterion's `Test:` field. It will be added to `$TGD_DIR/REGRESSION-CATALOG.md` during `/tgd-release`.
  - **Enforcement (machine-gated)**: `/tgd-verify` runs `python3 $TGD_REPO_ROOT/scripts/ac-trace.py $TGD_DIR/<feature>/ <client-repo>` — it fails when any AC id is unreferenced by tests, when any `[R]` criterion lacks a `Test:` file, or when that file is missing on disk. A TASKS.md without AC ids fails closed.

### 4. Files Likely Touched
- `path/to/file.ts`
- `tests/path/to/test.ts`

---

## Checkpoint: Verification
✅ All tests pass (`npm test`)
✅ Build succeeds
✅ Lint clean

## Risks & Mitigations
| Risk | Impact | Mitigation |
|------|--------|------------|
| [Risk] | High/Med/Low | [Strategy] |

## Open Questions
- [Question needing human input]

## Sign-off
- [ ] **DEV**: (pending)
```

**This is the ONLY TASKS.md format.** Everything below describes how to fill
it in — do not invent alternative task layouts; `ac-trace.py` (run by
`/tgd-verify`) fails closed on task lists without `AC-<task>.<n>` ids.

### Step 2: Identify the Dependency Graph

Map what depends on what:

```
Database schema
    │
    ├── API models/types
    │       │
    │       ├── API endpoints
    │       │       │
    │       │       └── Frontend API client
    │       │               │
    │       │               └── UI components
    │       │
    │       └── Validation logic
    │
    └── Seed data / migrations
```

Implementation order follows the dependency graph bottom-up: build foundations first.

### Step 3: Slice Vertically

Instead of building all the database, then all the API, then all the UI — build one complete feature path at a time:

**Bad (horizontal slicing):**
```
Task 1: Build entire database schema
Task 2: Build all API endpoints
Task 3: Build all UI components
Task 4: Connect everything
```

**Good (vertical slicing):**
```
Task 1: User can create an account (schema + API + UI for registration)
Task 2: User can log in (auth schema + API + UI for login)
Task 3: User can create a task (task schema + API + UI for creation)
Task 4: User can view task list (query + API + UI for list view)
```

Each vertical slice delivers working, testable functionality.

### Step 4: Write Tasks

Write each task using the **canonical per-task block from the TASKS.md
template above** (Context & Goal → Technical Design → Acceptance Criteria
with `AC-<task>.<n>` ids, `[R]` decision, and `Test:` field → Files Likely
Touched). Do not use a simplified layout — the AC ids and `Test:` fields are
machine-checked downstream.

Per-task quality bar (in addition to the template fields):
- **Verification is explicit**: name the exact command (`npm test -- --grep "x"`),
  not "run the tests" (Zero-Context Rule)
- **Dependencies declared**: task numbers this depends on, or "None"
- **Scope estimated**: Small (1-2 files) / Medium (3-5) / Large (5+ → split it)

### Step 5: Order and Checkpoint

Arrange tasks so that:

1. Dependencies are satisfied (build foundation first)
2. Each task leaves the system in a working state
3. Verification checkpoints occur after every 2-3 tasks
4. High-risk tasks are early (fail fast)

Add explicit checkpoints:

```markdown
## Checkpoint: After Tasks 1-3
- [ ] All tests pass
- [ ] Application builds without errors
- [ ] Core user flow works end-to-end
- [ ] Review with human before proceeding
```

## Task Sizing Guidelines

| Size | Files | Scope | Example |
|------|-------|-------|---------|
| **XS** | 1 | Single function or config change | Add a validation rule |
| **S** | 1-2 | One component or endpoint | Add a new API endpoint |
| **M** | 3-5 | One feature slice | User registration flow |
| **L** | 5-8 | Multi-component feature | Search with filtering and pagination |
| **XL** | 8+ | **Too large — break it down further** | — |

If a task is L or larger, it should be broken into smaller tasks. An agent performs best on S and M tasks.

**When to break a task down further:**
- It would take more than one focused session (roughly 2+ hours of agent work)
- You cannot describe the acceptance criteria in 3 or fewer bullet points
- It touches two or more independent subsystems (e.g., auth and billing)
- You find yourself writing "and" in the task title (a sign it is two tasks)

## Parallelization Opportunities

When multiple agents or sessions are available:

- **Safe to parallelize:** Independent feature slices, tests for already-implemented features, documentation
- **Must be sequential:** Database migrations, shared state changes, dependency chains
- **Needs coordination:** Features that share an API contract (define the contract first, then parallelize)

## Common Rationalizations

| Rationalization | Reality |
|---|---|
| "I'll figure it out as I go" | That's how you end up with a tangled mess and rework. 10 minutes of planning saves hours. |
| "The tasks are obvious" | Write them down anyway. Explicit tasks surface hidden dependencies and forgotten edge cases. |
| "Planning is overhead" | Planning is the task. Implementation without a plan is just typing. |
| "I can hold it all in my head" | Context windows are finite. Written plans survive session boundaries and compaction. |

## Red Flags

- Starting implementation without a written task list
- Tasks that say "implement the feature" without acceptance criteria
- No verification steps in the plan
- All tasks are XL-sized
- No checkpoints between tasks
- Dependency order isn't considered

## Verification

Before starting implementation, confirm:

- [ ] Every task has acceptance criteria in BDD format with stable `AC-<task>.<n>` ids (`ac-trace.py` fails closed without them)
- [ ] Every criterion has an explicit `[R]` Yes/No decision; every `[R]` will get a `Test:` file reference during `/tgd-develop`
- [ ] Every task has a verification step
- [ ] Task dependencies are identified and ordered correctly
- [ ] No task touches more than ~5 files
- [ ] Checkpoints exist between major phases
- [ ] The human has reviewed and approved the plan
- [ ] If UI feature: `$TGD_DIR/<feature-name>/DESIGN.md` exists (created in Define phase)
