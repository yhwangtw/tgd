---
name: tgd-develop-incremental
description: Delivers changes incrementally. Use when implementing any feature or change that touches more than one file. Use when you're about to write a large amount of code at once, or when a task feels too big to land in one step.
---

# Incremental Implementation

## Overview

Build one thin, complete slice; test and verify it; commit it; then expand.
Every increment leaves the project working and independently reviewable.

## When to Use

- Any multi-file feature or refactor
- A planned task that is too large for one safe change
- Before writing roughly 100 lines without intermediate verification

Skip only an already-minimal single-file, single-function change.

## Increment Cycle

For each slice, in order:

1. **Scope:** when `.codegraph/` exists, inspect callers of modified functions;
   for unfamiliar code, run `understand` first.
2. **Implement:** make the smallest complete behavior change.
3. **Test:** write or run the focused test, then relevant existing tests.
4. **Verify:** observe tests, build, and applicable runtime/manual evidence.
5. **Commit:** create one descriptive atomic commit per logical change using
   `tgd-core-git` safeguards.
6. **Continue:** carry the verified state into the next slice; never restart or
   batch several unverified slices.

## Slicing Strategy

Prefer a complete vertical user path across needed layers. When teams can work
in parallel, define the shared contract first, implement consumers against it,
then integrate. Put the highest technical uncertainty first so failure is
discovered before dependent investment.

Diagrams, code, and prompt shapes are optional examples. Load
[Incremental Development Patterns](../../references/incremental-development-patterns.md)
only when a worked slice helps; this skill remains the normative owner.

## Implementation Rules

### 0. Simplicity First

Implement the naive, obviously correct version before abstraction or
optimization. Ask whether every abstraction earns its complexity, whether the
same behavior needs fewer lines, and whether it serves the current task rather
than hypothetical future work. Three clear similar lines beat a premature
framework.

### 0.5. Scope Discipline

Touch only what the task requires. Do not clean adjacent code, rewrite imports,
remove unfamiliar comments, modernize read-only files, or add “useful” features.
Record unrelated opportunities or bugs for a separate task; never silently fix
them in the current increment.

### 1. One Logical Change

Do not combine a feature, refactor, and configuration change in one increment.
Separate concerns into independently testable and revertible commits.

### 2. Keep It Compilable

After each increment, the build and all existing tests pass. Never leave a
broken intermediate state for the next slice.

### 3. Hide Incomplete Features

Use a safe-default feature flag when incomplete increments may reach main at
Release. Work remains on `feature/<name>` until `/tgd-release`; the flag keeps
unfinished behavior invisible if merged.

### 4. Safe Defaults

New behavior defaults to conservative, opt-in operation. A missing option must
not silently enable notification, mutation, access, or another risky effect.

### 5. Rollback-Friendly Changes

Keep edits additive or minimal. Supply rollback migrations for database
changes. Avoid deleting and replacing a system in one commit; separate the
steps so each increment can be reverted independently.

## Verification Per Increment

Use the repository commands from CONTEXT.md or its rules file, not assumed npm
commands:

- [ ] The increment completes one logical behavior.
- [ ] Focused and all existing tests pass.
- [ ] Build, types, and lint pass when affected.
- [ ] Applicable runtime behavior is observed.
- [ ] A descriptive atomic commit records the slice.

Run a gate again only after a change that could affect it. Repeating the same
command on unchanged code adds no evidence.

## Common Rationalizations

| Rationalization | Reality |
|---|---|
| "Test everything at the end" | An early defect invalidates later slices. |
| "One big change is faster" | Large diffs hide cause and block rollback. |
| "These edits are too small to separate" | Concern-separated commits are cheap evidence. |
| "Add the feature flag later" | Incomplete behavior must remain invisible now. |
| "Include this nearby refactor" | Mixed concerns weaken review and diagnosis. |
| "Run the same build again" | Unchanged input produces no new evidence. |

## Red Flags

- More than roughly 100 changed lines without a test run
- Multiple concerns, scope expansion, or unrelated cleanup in one slice
- Broken tests/build between increments or large uncommitted accumulation
- Premature abstractions or one-use utility files
- Missing safe flag/default or rollback path
- Repeated identical verification without intervening change

## Verification

- [ ] Every increment was independently tested, verified, and committed.
- [ ] The full test suite and build pass after integration.
- [ ] The specified feature works end-to-end.
- [ ] No uncommitted changes remain.
