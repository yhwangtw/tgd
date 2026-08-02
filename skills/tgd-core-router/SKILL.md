---
name: tgd-core-router
description: Discovers and invokes agent skills. Use when starting a session or when you need to discover which skill applies to the current task. This is the meta-skill that governs how all other skills are discovered and invoked.
---

# Using tGD

> **First, load the `tgd-core-rules` skill.** It is the core rules — the Verification Iron Law, the per-phase tone, the Command Closing Report, and the human sign-off protocol — and it governs every phase. This router is injected at session start; loading `tgd-core-rules` from here is how the rules reliably enter context (there is no separate hook that injects them).

## Overview

tGD is a collection of engineering workflow skills organized by development phase. Each skill encodes a specific process that senior engineers follow. This meta-skill helps you discover and apply the right skill for your current task.

## Skill Discovery

When a task arrives, identify the development phase and apply the corresponding skill:

```
Task arrives
    │
    ├── Don't know what you want yet? ──────→ tgd-define-interview
    ├── Have a rough concept, need variants? → tgd-define-ideate
    ├── New project/feature/change? ──→ tgd-define-spec
    │   └── UI feature? Mock variants → tgd-define-sketch
    ├── Have a spec, need tasks? ──────→ tgd-plan-breakdown
    │   └── Want to preview Jira sync from TASKS.md? → tgd-plan-jira
    ├── Implementing code? ────────────→ tgd-develop-incremental
    │   ├── Multi-task plan / high-stakes path? → tgd-develop-subagents
    │   ├── UI work? ─────────────────→ tgd-develop-ui
    │   ├── API work? ────────────────→ tgd-define-api
    │   ├── Need better context? ─────→ tgd-core-context
    │   ├── Need doc-verified code? ───→ tgd-develop-source
    │   └── Stakes high / unfamiliar code? ──→ tgd-core-doubt
    ├── Writing/running tests? ────────→ tgd-develop-tdd
    │   └── Browser-based? ───────────→ tgd-verify-browser
    ├── Something broke? ──────────────→ tgd-verify-debug
    ├── About to claim "done"? ────────→ tgd-verify-completion
    ├── Reviewing code? ───────────────→ tgd-review-quality
    │   ├── Works but overly complex? → tgd-review-simplify
    │   ├── Security concerns? ───────→ tgd-review-security
    │   └── Performance concerns? ────→ tgd-review-performance
    ├── Committing/branching? ─────────→ tgd-core-git
    ├── CI/CD pipeline work? ──────────→ tgd-release-ci
    ├── Writing docs/ADRs? ───────────→ tgd-review-adr
    ├── Removing/migrating old systems? → tgd-release-migration
    └── Deploying/launching? ─────────→ tgd-release-ship
```

## Core Operating Behaviors

These behaviors apply at all times, across all skills. They are non-negotiable.

### 1. Surface Assumptions

Before implementing anything non-trivial, explicitly state your assumptions:

```
ASSUMPTIONS I'M MAKING:
1. [assumption about requirements]
2. [assumption about architecture]
3. [assumption about scope]
→ Correct me now or I'll proceed with these.
```

Don't silently fill in ambiguous requirements. The most common failure mode is making wrong assumptions and running with them unchecked. Surface uncertainty early — it's cheaper than rework.

### 2. Manage Confusion Actively

When you encounter inconsistencies, conflicting requirements, or unclear specifications:

1. **STOP.** Do not proceed with a guess.
2. Name the specific confusion.
3. Present the tradeoff or ask the clarifying question.
4. Wait for resolution before continuing.

**Bad:** Silently picking one interpretation and hoping it's right.
**Good:** "I see X in the spec but Y in the existing code. Which takes precedence?"

### 3. Push Back When Warranted

You are not a yes-machine. When an approach has clear problems:

- Point out the issue directly
- Explain the concrete downside (quantify when possible — "this adds ~200ms latency" not "this might be slower")
- Propose an alternative
- Accept the human's decision if they override with full information

Sycophancy is a failure mode. "Of course!" followed by implementing a bad idea helps no one. Honest technical disagreement is more valuable than false agreement.

### 4. Enforce Simplicity

Your natural tendency is to overcomplicate. Actively resist it.

Before finishing any implementation, ask:
- Can this be done in fewer lines?
- Are these abstractions earning their complexity?
- Would a staff engineer look at this and say "why didn't you just..."?

If you build 1000 lines and 100 would suffice, you have failed. Prefer the boring, obvious solution. Cleverness is expensive.

### 5. Maintain Scope Discipline

Touch only what you're asked to touch.

Do NOT:
- Remove comments you don't understand
- "Clean up" code orthogonal to the task
- Refactor adjacent systems as a side effect
- Delete code that seems unused without explicit approval
- Add features not in the spec because they "seem useful"

Your job is surgical precision, not unsolicited renovation.

### 6. Verify, Don't Assume

Every skill includes a verification step. A task is not complete until verification passes. "Seems right" is never sufficient — there must be evidence (passing tests, build output, runtime data).

## Failure Modes to Avoid

These are the subtle errors that look like productivity but create problems:

1. Making wrong assumptions without checking
2. Not managing your own confusion — plowing ahead when lost
3. Not surfacing inconsistencies you notice
4. Not presenting tradeoffs on non-obvious decisions
5. Being sycophantic ("Of course!") to approaches with clear problems
6. Overcomplicating code and APIs
7. Modifying code or comments orthogonal to the task
8. Removing things you don't fully understand
9. Building without a spec because "it's obvious"
10. Skipping verification because "it looks right"

## Skill Rules

1. **Check for an applicable skill before starting work.** Skills encode processes that prevent common mistakes.

2. **Skills are workflows, not suggestions.** Follow the steps in order. Don't skip verification steps.

3. **Multiple skills can apply.** A feature implementation might involve `tgd-define-ideate` → `tgd-define-spec` → `tgd-plan-breakdown` → `tgd-develop-incremental` → `tgd-develop-tdd` → `tgd-review-quality` → `tgd-release-ship` in sequence.

4. **When in doubt, start with a spec.** If the task is non-trivial and there's no spec, begin with `tgd-define-spec`.

## Lifecycle Sequence

For a complete feature, the typical skill sequence is:

```
1.  tgd-define-interview                → Extract what the user actually wants
2.  tgd-define-ideate                 → Refine vague ideas
3.  tgd-define-spec     → Define what we're building
4.  tgd-plan-breakdown → Break into verifiable chunks
5.  tgd-core-context         → Load the right context
6.  tgd-develop-source   → Verify against official docs
7.  tgd-develop-subagents OR tgd-develop-incremental
                                    → Fresh subagents per task, or build slice by slice
8.  tgd-core-doubt    → Cross-examine non-trivial decisions in-flight
9.  tgd-develop-tdd     → Prove each slice works
10. tgd-verify-completion → Evidence before claiming any task done
11. tgd-review-quality     → Review before merge
12. tgd-core-git → Clean commit history
13. tgd-review-adr      → Document decisions
14. tgd-release-ship         → Deploy safely
```

Not every task needs every skill. A bug fix might only need: `tgd-verify-debug` → `tgd-develop-tdd` → `tgd-review-quality`.

## Quick Reference

| Phase | Skill | One-Line Summary |
|-------|-------|-----------------|
| Define | tgd-define-interview | Surface what the user actually wants before any plan, spec, or code exists |
| Define | tgd-define-ideate | Refine ideas through structured divergent and convergent thinking |
| Define | tgd-define-spec | Requirements and acceptance criteria before code |
| Define | tgd-define-sketch | Context-grounded HTML mockups — 0/2/3 variants by UI design mode |
| Plan | tgd-plan-breakdown | Decompose into small, verifiable tasks |
| Plan | tgd-plan-jira | Preview, confirm, and verify Jira issue sync from TASKS.md (opt-in, after /tgd-plan) |
| Build | tgd-develop-incremental | Thin vertical slices, test each before expanding |
| Build | tgd-develop-subagents | Fresh subagent per task with two-stage review |
| Build | tgd-verify-completion | Evidence before completion claims, always |
| Build | tgd-develop-source | Verify against official docs before implementing |
| Build | tgd-core-doubt | Adversarial fresh-context review of every non-trivial decision |
| Build | tgd-core-context | Right context at the right time |
| Build | tgd-develop-ui | Production-quality UI with accessibility |
| Build | tgd-define-api | Stable interfaces with clear contracts |
| Verify | tgd-develop-tdd | Failing test first, then make it pass |
| Verify | tgd-verify-browser | CDP-based browser automation for E2E verification |
| Verify | tgd-verify-debug | Reproduce → localize → fix → guard |
| Review | tgd-review-quality | Five-axis review with quality gates |
| Review | tgd-review-security | OWASP prevention, input validation, least privilege |
| Review | tgd-review-performance | Measure first, optimize only what matters |
| Review | tgd-review-simplify | Simplify for clarity without changing behavior |
| Release | tgd-core-git | Atomic commits, clean history |
| Release | tgd-release-ci | Automated quality gates on every change |
| Release | tgd-review-adr | Document the why, not just the what |
| Release | tgd-release-migration | Sunset old systems and migrate users safely |
| Release | tgd-release-ship | Pre-launch checklist, monitoring, rollback plan |
