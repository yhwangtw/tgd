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
- **Read PRD `## UI Design`**: Determine the selected UI mode. A missing section returns to `/tgd-define` for in-place classification. For modes 1–3, Status must be `direction-approved`, DESIGN.md must exist, pass its section check, and contain `[x] **DESIGN**: Direction Approved` before planning begins; otherwise return to `/tgd-define`.
- **Read `$TGD_DIR/<feature-name>/DESIGN.md` and the actual UI sources linked by CONTEXT.md (UI modes 1–3)**: Review the approved flow, hierarchy, component mapping, token changes, responsive rules, interaction states, accessibility, and allowed deviations. CONTEXT.md is navigation, not the visual source of truth.

**Synthesis:** Map dependencies between existing code and new requirements. Note risks and unknowns. If `.codegraph/` exists, run `codegraph impact "<core-symbol>"` on any symbol the feature will modify to assess blast radius and inform task ordering. If planning a large refactor, run the `understand-diff` skill to visualize the impact of proposed changes before breaking down tasks.

**Do NOT write code during planning.** Write a plan document at `$TGD_DIR/<feature-name>/TASKS.md` covering: dependency graph, ordered task list with acceptance criteria, verification checkpoints, and risks with mitigations.

**TASKS.md template (save to `$TGD_DIR/<feature-name>/TASKS.md`):**


> Canonical template: `$TGD_REPO_ROOT/templates/TASKS.md.tmpl`.

**This is the ONLY TASKS.md format.** Everything below describes how to fill
it in — do not invent alternative task layouts; `ac-trace.py` (run by
`/tgd-verify`) fails closed on task lists without `AC-<task>.<n>` ids.

`> **Jira-Source-ID**:` is the durable namespace for this TASKS document. On
first creation, replace the template instruction with `tgd-source-` plus one
lowercase UUID v4 (for example, `tgd-source-123e4567-e89b-42d3-a456-426614174000`).
It is not a secret. Never derive it from a feature name, repo name, or path,
and never change it during re-plan or repository moves.

`**Jira:**` stores the verified Jira issue key. `**Jira-Sync-ID:**` stores the
stable identity used to reconcile that task across repeated syncs. New tasks
start with an em dash (`—`). Only `scripts/jira-sync.py` may replace those
placeholders, and only after it verifies the remote issue. Planning must never
infer, clear, or regenerate either value.

Legacy TASKS.md files may have one standalone Jira key such as `[ENG-1234]` in
a task heading. During schema migration, preserve that token and add the two
new Jira fields as `—`. Do not infer ownership or copy the key into the new
field: `scripts/jira-sync.py` must show a digest-confirmed `adopt`, verify the
exact Project/key and absence of conflicting tGD ownership, then remove the old
token while atomically filling both fields. Multiple or unverifiable legacy
keys fail closed.

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
template above** (`**Status:** pending` line → Context & Goal → Technical
Design → Acceptance Criteria with `AC-<task>.<n>` ids, `[R]` decision, and
`Test:` field → Files Likely Touched), including the `**Jira:** —` and
`**Jira-Sync-ID:** —` placeholders. Do not use a simplified layout — the AC
ids and `Test:` fields are machine-checked downstream, the `Status:` line is
what `/tgd-develop`'s resume rule and `/tgd-plan`'s re-plan protocol read, and
the Jira fields carry stable sync state.

Per-task quality bar (in addition to the template fields):
- **Verification is explicit**: name the exact command (`npm test -- --grep "x"`),
  not "run the tests" (Zero-Context Rule)
- **Dependencies declared**: task numbers this depends on, or "None"
- **Scope estimated**: Small (1-2 files) / Medium (3-5) / Large (5+ → split it)
- **No standalone "write tests" tasks**: tests are each task's AC carriers,
  written inside that task's TDD cycle — never a separate task scheduled after
  the implementation. A "Task N: write the test suite" decomposition
  structurally encourages test-after (the implementation task completes
  untested, then the test task rubber-stamps it) and produces meta-criteria
  ("tests exist and pass") that trace to the same test lines as the behavior
  criteria they duplicate. If a task's tests feel like a separate work item,
  the task is too big — split the task, not the testing.
- **UI work is traceable to approved design**: cite the exact DESIGN.md heading or mapped component in every UI task. BDD criteria must assert observable loading, empty, error, success, and disabled states where applicable; named responsive viewports; keyboard/focus behavior; and any approved deviation that affects runtime output.

### Step 5: Order and Checkpoint

Arrange tasks so that:

1. Dependencies are satisfied (build foundation first)
2. Each task leaves the system in a working state
3. Verification checkpoints occur after every 2-3 tasks
4. High-risk tasks are early (fail fast)

Add explicit checkpoints:

```markdown
## Checkpoint: After Tasks 1-3
- [ ] All tests pass (`npm test`)
- [ ] Application builds without errors (`npm run build`)
- [ ] Core user flow works end-to-end
```

Checkpoint items must be **machine-checkable commands** — `/tgd-develop` runs
them when it reaches the checkpoint and stops only on failure; it does NOT
pause for a human. Human review is concentrated in `/tgd-release`'s sign-off
gate, not mid-execution.

## Instrumentation Tasks and TRACKING-PLAN.md

If the PRD's §6 Success Metrics names a tracking event that does not exist yet (rule 2 in `tgd-spec-driven-development`'s §6 filling rules), planning owns two outputs:

**1. Register the event in `$TGD_DIR/TRACKING-PLAN.md`** — the cumulative event dictionary shared across ALL features and ALL repos of the project (same role as `REGRESSION-CATALOG.md`: append-only, one source of truth). Create the file on first use with this header, then append one entry per event:


> Canonical template: `$TGD_REPO_ROOT/templates/TRACKING-PLAN.md.tmpl`.

**Cross-platform rules (non-negotiable):**

1. **One semantic = one event name; platform is a property, not a suffix.** `sign_up_completed` + `platform: web|ios|android` — never `sign_up_web` / `signUpIos` triplets. Split names silently break every funnel that forgets one variant.
2. **Triggers are defined semantically, not by UI.** "Registration completed = server returns 201", not "register button clicked" — each platform's UI differs; the semantic moment is the single shared definition every implementer maps to.
3. **Every event declares a source of truth.** Conversion-critical events (signup, payment) default to **server-side** — one implementation covers all platforms and survives ad-blockers. Pure interaction events (scroll, hover) are client-side. Often the answer to "do all three platforms need this?" is "no — server emits it once."

**Naming convention:** `object_action` in `snake_case`, property keys also `snake_case` — on every platform. Payload key drift (`plan_type` vs `planType`) is exactly what the dictionary exists to prevent.

**2. Create one instrumentation task per platform listed in the entry's Platforms field** — a normal task in TASKS.md (multi-repo tagged if applicable) with its own BDD acceptance criteria, e.g.:

```markdown
- **AC-4.1** — **Given** a user completes registration **When** the server responds 201 **Then** `sign_up_completed` is emitted with properties `method`, `platform` and no PII
  - **Regression**: No
  - **Test**: [filled during /tgd-develop — the test asserts the event fires with the expected payload keys]
```

A mis-firing event is worse than a missing one — you will trust a wrong number. That is why instrumentation gets tested ACs, not a "remember to add analytics" checklist line.

## Re-planning an Existing TASKS.md

When TASKS.md already exists (spec changed mid-flight, scope grew), the default is an **incremental update**, never a from-scratch rewrite — `/tgd-develop` backfills `Test:` fields and completion state into TASKS.md, and regenerating the file destroys them, breaking `ac-trace.py` and the regression chain downstream.

Incremental rules:
- **Completed tasks are immutable**: any task with `**Status:** complete` keeps its Status line, criteria, and `Test:` fields byte-for-byte. (The `Status:` lines are also how the re-plan prompt counts "M 個已完成" — no marker, no count.)
- **Jira links are immutable across re-plans**: preserve every existing task's `**Jira:**` and `**Jira-Sync-ID:**` values byte-for-byte, regardless of task status. New tasks start with `—`; planning never reassigns or clears a link.
- **The Jira source namespace is immutable**: preserve the document-level `> **Jira-Source-ID**:` value byte-for-byte. Generate it only when creating a new TASKS.md or migrating a legacy TASKS.md that does not have one.
- **Legacy Jira heading keys are migration state**: preserve one standalone `[KEY-123]` token and initialize new Jira fields to `—` until the Jira CLI explicitly adopts it. Planning never removes, copies, or silently converts it.
- **Never renumber existing `AC-<task>.<n>` ids** — tests already reference them.
- New tasks continue the numbering after the highest existing task.
- An *unstarted* task invalidated by the spec change may be rewritten in place (same task number, new content, new criterion ids under it).
- A full rewrite is legitimate only when the old plan is void (feature repurposed) AND the user explicitly chose it (`/tgd-plan`'s re-plan prompt, option 2).

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
- [ ] Every task has a `**Status:**` line, initialized `pending` (`/tgd-develop` resume and re-plan both read it)
- [ ] Every task has `**Jira:**` and `**Jira-Sync-ID:**` fields; new unsynced tasks use `—`, and re-plans preserve existing values
- [ ] TASKS.md has one immutable `> **Jira-Source-ID**: tgd-source-<lowercase UUID v4>` value
- [ ] Every criterion has an explicit `[R]` Yes/No decision; every `[R]` will get a `Test:` file reference during `/tgd-develop`
- [ ] Every task has a verification step
- [ ] Task dependencies are identified and ordered correctly
- [ ] No task touches more than ~5 files
- [ ] Checkpoints exist between major phases
- [ ] The human has reviewed and approved the plan
- [ ] If UI mode is 1–3: PRD UI Design Status is `direction-approved`, `$TGD_DIR/<feature-name>/DESIGN.md` exists, passes the DESIGN section check, and contains `[x] **DESIGN**: Direction Approved`
- [ ] If UI mode is 1–3: every UI task cites its governing DESIGN.md section/component and carries BDD criteria for applicable states, responsive behavior, and keyboard/focus behavior
