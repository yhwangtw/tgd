---
name: tgd-develop
description: Develop — implement with fresh subagents per task and two-stage review
---

## Pre-flight

- [ ] Resolve `$TGD_DIR` from its environment variable, then sibling `../<project-name>-tGD/`; require CONTEXT.md or STOP and run `/tgd-map`.
- [ ] Select `<feature-name>` from non-infrastructure subdirectories containing PRD.md or SPEC.md. None means STOP and run `/tgd-define`; multiple means ask. Require SPEC.md.
- [ ] `$TGD_DIR/<feature-name>/TASKS.md` exists, PRD.md exists, and `$TGD_DIR/<feature-name>/SPEC.md` exists, all non-empty.

**If missing:** STOP. Tell user: "Specs are missing. Please run `/tgd-define` first."

This is BUILD. It runs in isolated worktrees.

## Worktree isolation

Determine repos with work from `[repo-name]` task prefixes; no prefixes means the current single repo. Create **one worktree PER repo with tasks**:

- Single repo: `git worktree add ../project-<feature-name> -b feature/<feature-name> main`
- Multi-repo, from each repo: `git -C <repo-path> worktree add ../project-<feature-name>-<repo-name> -b feature/<feature-name> main`
- Resume an existing branch with the same command without `-b`. If another worktree has it checked out, return that checkout to main and retry.

**All coding, testing, and commits MUST happen inside the worktree of the repo the current task is tagged for. A `[shop-frontend]` task implemented in the backend worktree is a routing failure, not a detail.**

**Resume rule**: tasks with `**Status:** complete` in TASKS.md (with their `Test:` fields filled) are SKIPPED — re-entering `/tgd-develop` continues from the first task whose Status is `pending`/`in-progress`; it never redoes or rewrites finished ones. `blocked` tasks stay skipped until their blocker is cleared (see the blocked handling below).

## Execution routing

Route on risk first, then size:

- Any critical-path `[R]` criterion (auth, payment, data loss, security boundary) or Large task (5+ files) → `tgd-develop-subagents`.
- Otherwise, **< 3 tasks** → `tgd-develop-incremental`.
- Otherwise (**≥ 3 tasks**) → `tgd-develop-subagents`. Dispatch subagents to implement and review within the worktree directory.

For both modes run, in order:

1. `tgd-core-context`; when CodeGraph is available, check callers before modifying a symbol.
2. `tgd-develop-source` for official-source grounding.
3. The routed incremental or subagent executor.
4. `tgd-develop-tdd`; each criterion test names/comments its `AC-<task>.<n>`.
5. Start a task by setting Status `in-progress`. After its tests pass, backfill every criterion's `Test:` path (mandatory for `[R]`) and set Status `complete`.
6. Run the two-stage spec then quality review and record `Spec-Review:` / `Quality-Review:` as `PASS — <one line>` or `FAIL — <one line>`; fix and re-review failures.
7. Run `tgd-verify-completion`.

Each task's two-stage review (spec-compliance first, then code-quality — run both INLINE if you cannot dispatch subagents; per `tgd-core-rules`, inability to delegate moves *where* work runs, never *whether*) records its outcome in the task's `Spec-Review:` and `Quality-Review:` fields: `PASS — <one line>` or `FAIL — <one line>` (fix, re-review, then flip to PASS). **A task is not complete while either field reads `pending` — `/tgd-verify` fails closed on it.**

Conditional skills: unfamiliar code → `understand`; UI → `tgd-develop-ui`; API design → `tgd-define-api`; high-stakes decision → `tgd-core-doubt`.

Blocked by a bug you can't fix within the task's scope? → `tgd-verify-debug` → **Blocked Task Handling**: set the task's `**Status:** blocked: <issue-ref>`, file the bug, and continue only with independent non-blocked tasks. A blocked task is recorded progress, never a passing Develop gate: do not hand off to Verify while any in-scope task remains blocked. Resolve it, or return to `/tgd-plan` for an explicit scope deferral, then rerun Develop.

At each TASKS.md checkpoint, execute every listed command; continue only when all pass. Do not pause between tasks unless blocked.

## Hand-off

After every in-scope task is complete and none is blocked, commit all work on each feature branch and keep its worktree for Verify/Review. **Do NOT merge to `main` here.** Merging happens in `/tgd-release`, after verify and review pass. Use safe-default feature flags for incomplete features.

## Verification Gate

- [ ] `git diff main...feature/<feature-name> --stat` is non-empty in each repo with tasks.
- [ ] New-logic tests pass and trace their AC ids; all criteria Test fields are filled and every in-scope task Status is `complete` — `blocked` is a failed gate, not a pass.
- [ ] Every completed task has both review fields at PASS.
- [ ] **Each worktree is clean: `git status --porcelain` is empty — everything the gates above certified is committed on the feature branch.**
- [ ] Verification output was observed, not assumed.

On a passing gate, end with the closing report per `tgd-core-rules` → **Command Closing Report**: 📦 Output (implemented task count + file summary; worktree retained, not merged) · 🔎 Checks (gate as one line) · ➡️ Next `/tgd-verify` — prove it works. If any task is blocked, report the failed gate and omit Next. Don't paste the raw checklist above.
