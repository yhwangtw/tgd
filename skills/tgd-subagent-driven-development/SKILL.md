---
name: tgd-subagent-driven-development
description: Execute implementation plans by dispatching fresh subagents per task with two-stage review. Use when executing a multi-task implementation plan, when context is getting too long for quality output, or when you want maximum isolation between tasks.
---

# Subagent-Driven Development

## Overview

Execute implementation plans by dispatching **fresh subagents per task** with two-stage review: **spec compliance first, then code quality**.

**Core Principle:** Fresh subagent per task + two-stage review = high quality, fast iteration

**Why Subagents:**
- Each task gets a clean context window — no pollution from prior tasks
- Subagents receive precisely crafted instructions — focus and success
- Your main context is preserved for coordination — you stay in control
- Quality doesn't degrade as context grows — every task starts fresh

## When to Use

- Executing a multi-task implementation plan (TASKS.md)
- Context is getting long and output quality is degrading
- Tasks are mostly independent (can be executed sequentially)
- You want the highest quality output per task

**When NOT to use:**
- Single, small changes (use `tgd-incremental-implementation` instead)
- Tasks that are tightly coupled and need constant cross-reference
- Exploration/prototyping where you don't have a plan yet

## The Process

```
Read TASKS.md
    │
    ▼
┌─ For each task ──────────────────────────────────────┐
│                                                       │
│  1. Dispatch implementer subagent                     │
│     - Provide: task spec, relevant files, context     │
│     - Subagent implements, tests, commits             │
│                                                       │
│  2. Dispatch spec reviewer subagent                   │
│     - Provide: task spec + subagent's output          │
│     - Checks: does code match the spec?               │
│     - If NO → implementer fixes spec gaps             │
│                                                       │
│  3. Dispatch code quality reviewer subagent           │
│     - Provide: code diff + quality checklist           │
│     - Checks: readability, patterns, test quality     │
│     - If NO → implementer fixes quality issues        │
│                                                       │
│  4. Mark task complete                                │
│                                                       │
└───────────────────────────────────────────────────────┘
    │
    ▼
Final review of entire implementation
```

## Continuous Execution

**Do not pause to check in between tasks.** Execute all tasks from the plan without stopping.

**Only reasons to stop:**
- BLOCKED status you cannot resolve
- Ambiguity that genuinely prevents progress
- All tasks complete

**Never:** Use "Should I continue?" prompts or progress summaries — waste the user's time.

## Subagent Prompts

### Implementer Prompt Template

```
You are implementing a single task from an implementation plan.

WORKING DIRECTORY:
{worktree_path}   ← all reads, writes, and commands happen HERE
                    (the isolated worktree, not the main checkout)

TASK:
{task_description_including_AC_ids}

RELEVANT FILES:
{file_list}

CONTEXT:
{relevant_context}

RULES:
1. Implement exactly what the task specifies — nothing more, nothing less
2. Write tests before code (TDD Red-Green-Refactor)
3. Every test verifying a criterion MUST mention its AC-<task>.<n> id in
   the test name, docstring, or a comment — this is machine-checked later
4. Commit when the task is complete with a clear commit message
5. Do NOT modify files outside your task scope
6. If you encounter ambiguity, state it clearly and stop

EXPECTED OUTPUT:
- Code changes committed
- Tests written and passing
- For EACH acceptance criterion: the AC id and the test file path that
  verifies it (the orchestrator records these in TASKS.md Test: fields)
- Brief summary of what was done
```

**Orchestrator duty after each implementer completes:** take the AC-id → test-path
pairs from the output and backfill the `Test:` fields in
`$TGD_DIR/<feature-name>/TASKS.md`. Subagents cannot reliably write outside the
worktree — the orchestrator owns the artifacts directory.

### Spec Reviewer Prompt Template

```
You are reviewing code for spec compliance.

TASK SPEC:
{task_description}

CODE CHANGES:
{diff_or_file_list}

CHECK:
1. Does the code implement everything the spec requires?
2. Are there any spec requirements that were missed?
3. Does the code do anything NOT in the spec? (scope creep)
4. Are edge cases from the spec handled?

OUTPUT:
- PASS: Code matches spec
- FAIL: List specific gaps between spec and implementation
```

### Code Quality Reviewer Prompt Template

```
You are reviewing code for quality.

CODE CHANGES:
{diff_or_file_list}

CHECK:
1. Readability: Is the code clear and well-structured?
2. Patterns: Does it follow existing codebase conventions?
3. Test quality: Are tests meaningful (not just for coverage)?
4. Error handling: Are failure cases handled?
5. Performance: Any obvious performance issues?
6. Security: Any obvious security issues?

OUTPUT:
- PASS: Code meets quality standards
- FAIL: List specific issues with severity (critical/important/nit)
```

## Integration with tGD

This skill is invoked by `/tgd-develop` when executing a task plan. It replaces the default single-session execution with subagent-based execution for higher quality.

**Trigger conditions:**
- TASKS.md exists with multiple tasks
- Tasks are mostly independent
- User wants maximum quality (not maximum speed)

**Fallback:** If subagent delegation is not available, fall back to `tgd-incremental-implementation`.

## Common Rationalizations

| Rationalization | Reality |
|---|---|
| "I'll just do it in this session" | Context pollution degrades quality per task |
| "Subagents will mess it up" | Fresh context + clear spec = higher quality |
| "Two-stage review is overkill" | Spec compliance + code quality catch different bugs |
| "It's faster without review" | Faster now, slower when bugs surface later |

## Red Flags

- Subagent output claims "done" without showing diff or test results
- Skipping spec review and going straight to code review
- Modifying files outside the task scope
- Implementer and reviewer getting the same overly broad context
- Reviewer passes without listing specific checks performed

## Verification

- [ ] Each subagent produced verifiable output (diff, test results, or commit SHA)
- [ ] Spec reviewer confirmed all requirements met (PASS or gaps listed)
- [ ] Code quality reviewer found no critical issues
- [ ] Tests are tagged with their `AC-<task>.<n>` ids and TASKS.md `Test:` fields are backfilled
- [ ] All tasks in TASKS.md marked complete
- [ ] Final integration test passes
