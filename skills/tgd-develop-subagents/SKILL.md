---
name: tgd-develop-subagents
description: Execute implementation plans by dispatching fresh subagents per task with two-stage review. Use when executing a multi-task implementation plan, when context is getting too long for quality output, or when you want maximum isolation between tasks.
---

# Subagent-Driven Development

## Overview

Execute each planned task with a fresh implementer context followed by two
independent gates: **spec compliance first, then code quality**. The main agent
owns coordination and lifecycle artifacts. `/tgd-develop` invokes this skill
for its multi-task or high-risk execution route.

## When to Use

- TASKS.md has multiple mostly independent tasks
- Context growth threatens implementation quality
- Per-task isolation and maximum review quality matter

Use `tgd-develop-incremental` for a single small change, tightly coupled work,
or exploration without an approved plan.

## Mandatory Process

For every non-complete, non-blocked task in order:

1. Dispatch a fresh implementer inside the correct repository worktree with the
   complete task, AC ids, relevant files, context, scope, and verification
   commands.
2. Require TDD, AC-tagged tests, scoped changes, a task commit, AC-id → test-path
   output, and explicit out-of-scope bug reporting.
3. Dispatch a fresh spec reviewer against the task contract and resulting diff.
4. After spec PASS, dispatch a fresh code-quality reviewer against the diff,
   project conventions, tests, errors, performance, and security.
5. Backfill every criterion's `Test:` path; record `Spec-Review:` and
   `Quality-Review:` as `PASS — <one line>` or `FAIL — <one line>`.
6. Only after tests and both reviews pass, mark the task complete. After all
   tasks, run the integration review and required gates.

Concrete prompt bodies are optional scaffolding. Load
[Subagent Prompts](../../references/subagent-prompts.md) when dispatching or
performing the same stages inline; this skill remains the normative owner.

## Bounded Review FAIL Loop

The original implementer context is discarded after its task. On review FAIL,
dispatch a **new** implementer with the same task plus the reviewer's exact
finding list, then rerun that review stage. Allow at most two fix rounds per
stage. If the third review still fails:

- set `**Status:** blocked: review deadlock — <one-line summary>`;
- record the disagreement under `## Risks & Mitigations`;
- continue to the next independent task.

Do not ping-pong indefinitely. A repeated deadlock usually requires a human
decision about an ambiguous contract.

## Orchestrator Duties

- Keep every read, write, test, and commit in the task's correct worktree.
- Update TASKS.md outside the worktree: Status, `Test:`, `Spec-Review:`, and
  `Quality-Review:` fields are orchestrator-owned evidence.
- Record every out-of-scope bug under Risks & Mitigations or add a new task when
  it belongs in the current cycle; never let the report disappear.
- If reviewer delegation is unavailable, execute spec and quality reviews
  INLINE using the same contracts. Inability to delegate never skips a stage.
- `/tgd-verify` fails closed when a completed task still has a pending review.

If implementation delegation itself is unavailable, route execution through
`tgd-develop-incremental`; the two review stages and evidence fields remain
mandatory.

## Continuous Execution

Do not pause between tasks for “Should I continue?” or progress summaries.
Continue until all tasks finish, a genuine ambiguity prevents work, or an
unresolvable blocker is recorded. Work on independent tasks after a blocker.

## Common Rationalizations

| Rationalization | Reality |
|---|---|
| "I'll do it in this growing session" | Fresh context protects task quality. |
| "Subagents will lose context" | Give one precise task and its required evidence. |
| "Two reviews are overkill" | Spec and quality catch different failures. |
| "Skipping review is faster" | Unreviewed mistakes move cost downstream. |

## Red Flags

- “Done” without a diff, test result, or commit SHA
- Quality review before spec review, or either review skipped
- Work outside the tagged task/repository scope
- Broad shared context that defeats task/reviewer independence
- PASS without named checks or evidence
- Pending review fields on a completed task

## Verification

- [ ] Each implementer produced scoped diff/commit and observed test evidence.
- [ ] Every AC-tagged test path was backfilled into TASKS.md.
- [ ] Spec and quality reviews passed or the bounded deadlock was recorded.
- [ ] Task Status is complete or `blocked: <ref>`, never stale pending.
- [ ] Out-of-scope bugs were retained in Risks & Mitigations or new tasks.
- [ ] Final integration tests pass.
