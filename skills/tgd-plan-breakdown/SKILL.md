---
name: tgd-plan-breakdown
description: Breaks work into ordered tasks. Use when you have a spec or clear requirements and need to break work into implementable tasks. Use when a task feels too large to start, when you need to estimate scope, or when parallel work is possible.
---

# Planning and Task Breakdown

## Overview

Decompose a specification into ordered, independently verifiable tasks that a
fresh executor can implement and test in one focused session.

## When to Use

- A spec needs implementable tasks, dependency order, scope, or parallel lanes
- Work is too large or vague to start safely
- Multiple agents, sessions, or humans need a durable plan

Skip this skill for an obvious single-file change or an already complete plan.

## Zero-Context Rule

Assume the executor has zero repository context, limited domain knowledge,
weak design judgment, and weak test design. Every task therefore names exact
paths, commands, implementation guidance, dependencies, and expected outputs.

Never write “similar to Task N,” `TBD`, `TODO`, “appropriate error handling,”
or steps that state only what without enough detail to execute and verify how.

## Planning Workflow

### 0. Resolve the Feature

Scan `$TGD_DIR/` for non-infrastructure directories containing SPEC.md or
PRD.md; exclude `.scans/`, `wiki/`, and dot-directories. Lock the only match,
ask among multiple matches, or STOP and run `/tgd-define` when none exists. All
feature artifacts use `$TGD_DIR/<feature-name>/`.

### 1. Analyze Read-Only Context

Before code, read CONTEXT.md, the feature PRD.md and SPEC.md, and PRD
`## UI Design`. A missing UI section returns to `/tgd-define`. For UI modes
1–3, require `direction-approved`, a valid DESIGN.md, and
`[x] **DESIGN**: Direction Approved`; then read DESIGN.md and the actual UI
sources linked by CONTEXT.md. CONTEXT is navigation, not visual truth.

Map requirements to existing code, risks, and unknowns. When `.codegraph/`
exists, run impact analysis for modified core symbols. For a large refactor,
use `understand-diff` before decomposition. Planning is read-only with respect
to product code.

Write only `$TGD_DIR/<feature-name>/TASKS.md`, using
`$TGD_REPO_ROOT/templates/TASKS.md.tmpl`. This is the sole TASKS.md shape;
`ac-trace.py` fails closed when stable `AC-<task>.<n>` ids are absent.

### 2. Preserve Jira Identity

A new TASKS.md gets one random `tgd-source-<lowercase UUID v4>`
`Jira-Source-ID`; never derive it from names or paths. Every task carries
`**Jira:**` and `**Jira-Sync-ID:**`, initialized to `—`. Only
`scripts/jira-sync.py`, after remote verification, may replace them.

During legacy migration, preserve one standalone `[KEY-123]` heading token and
blank new fields until digest-confirmed `adopt` verifies ownership and performs
locked atomic writeback. Multiple or unverifiable keys fail closed.

### 3. Order the Dependency Graph

Map foundations and consumers explicitly, then implement foundations first.
Database/schema and shared contracts precede services and endpoints; clients
precede consuming UI. Declare each task's dependencies by number or `None`.

### 4. Slice Vertically

Prefer complete, working user paths across required layers over “all database,
then all API, then all UI.” Each slice must leave testable behavior. Put
high-risk work early so it can fail fast.

### 5. Write Canonical Task Blocks

Use the template's complete block: Status → Context & Goal → Technical Design →
BDD acceptance criteria with stable ids, `[R]` decision, and carrier → Files
Likely Touched → Jira fields. Do not invent a simplified layout.

For each task:

- Start `**Status:** pending`; name exact verification commands and outputs.
- Estimate Small (1–2 files) or Medium (3–5). Split Large (5+) work.
- Keep tests inside the task's TDD cycle; never schedule a later standalone
  “write tests” task or duplicate behavior ACs with “tests exist” meta-ACs.
- For UI, cite the governing DESIGN.md section/component and cover applicable
  loading, empty, error, success, disabled, responsive, keyboard/focus, and
  approved-deviation behavior.

### 6. Checkpoint Execution

Order tasks so dependencies hold and every task leaves a working system. Add a
checkpoint after every 2–3 tasks with exact machine-checkable test/build/flow
commands. `/tgd-develop` runs checkpoints continuously and stops only on
failure; it does not pause for human review. Human sign-off belongs to Release.

## Instrumentation and TRACKING-PLAN.md

When PRD success metrics require an event that does not exist, append its
canonical definition to append-only, project-wide `$TGD_DIR/TRACKING-PLAN.md`
using `templates/TRACKING-PLAN.md.tmpl`. It is the single dictionary across all
features and repos. Then add one normal, tested instrumentation task per listed
platform.

- One semantic has one `object_action` snake_case event name; platform is a
  property, never a name suffix. Property keys are snake_case everywhere.
- Define the semantic trigger, not a UI gesture. Every platform maps to that
  same event moment.
- Declare one source of truth. Conversion-critical events default server-side;
  pure interactions remain client-side.
- Instrumentation ACs assert the event, exact payload keys, platform, and no
  PII. A mis-firing event is worse than a missing checklist item.

## Re-planning Existing TASKS.md

Default to incremental update; regeneration destroys completion and trace
state. Preserve these boundaries:

- **Completed tasks are immutable**: any task with `**Status:** complete` keeps its Status line, criteria, and `Test:` fields byte-for-byte.
- Preserve every existing `**Jira:**`, `**Jira-Sync-ID:**`, and document
  `Jira-Source-ID` byte-for-byte, regardless of status.
- Preserve one legacy heading key until CLI adoption. Planning never copies,
  removes, or converts it.
- **Never renumber existing `AC-<task>.<n>` ids**; tests already reference them.
- New tasks continue after the highest number. An unstarted invalidated task may
  be rewritten in place with new criteria under its existing task number.
- Rewrite the whole plan only when repurposed and the user explicitly chooses
  `/tgd-plan` re-plan option 2.

## Sizing and Parallelization

Use these thresholds: XS = 1 file; S = 1–2; M = 3–5; L = 5–8 and must split;
XL = 8+ and must split. Prefer S/M work. Break down tasks spanning more than
one focused session, more than three criteria, independent subsystems, or an
“and” title.

Parallelize independent vertical slices, already-implemented tests, and docs.
Keep migrations, shared-state changes, and dependency chains sequential. For
shared contracts, define the contract first, then parallelize consumers.

Dependency, task, checkpoint, tracking, and sizing examples are optional. Load
[Planning Patterns](../../references/planning-patterns.md) only when a worked
shape helps; this skill remains the normative owner.

## Common Rationalizations

| Rationalization | Reality |
|---|---|
| "I'll figure it out while coding" | Unwritten dependencies become rework. |
| "The tasks are obvious" | Explicit tasks expose hidden scope and edges. |
| "Planning is overhead" | Planning is part of implementation safety. |
| "I can hold it in my head" | Written plans survive handoff and compaction. |

## Red Flags

- Implementation starts without canonical TASKS.md
- Vague tasks, missing ACs/commands, horizontal slices, or XL work
- Dependencies, high-risk ordering, or checkpoints are absent
- Tests are deferred into separate tasks
- Re-plan overwrites completed, AC, or Jira identity state

## Verification

- [ ] Every task uses the canonical block, pending Status, BDD AC ids, `[R]`, carrier, dependencies, paths, and exact verification.
- [ ] Every `[R]` criterion will receive a concrete `Test:` file during `/tgd-develop`.
- [ ] TASKS.md has one immutable `tgd-source-<lowercase UUID v4>` and every task has Jira fields.
- [ ] Existing completed/AC/Jira state survived any re-plan byte-for-byte.
- [ ] Tasks are vertically sliced, dependency ordered, at most ~5 files, and checkpointed.
- [ ] Instrumentation events/tasks follow semantic naming, source, payload, and no-PII rules.
- [ ] UI modes 1–3 have approved valid DESIGN.md and UI tasks cite it with applicable state/responsive/keyboard criteria.
- [ ] The human reviewed and approved the plan.
