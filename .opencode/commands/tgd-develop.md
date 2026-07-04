---
description: Develop — implement with fresh subagents per task and two-stage review
---

**🛑 Pre-flight: Environment Check**
- [ ] `$TGD_DIR/CONTEXT.md` exists (or `.codegraph/` is present).
- **If missing:** STOP. Tell user: "Project context not mapped. Please run `/tgd-map` first."
- **$TGD_DIR:** Check env var `$TGD_DIR` first. If not set, check sibling `../<project-name>-tGD/`. If neither exists: STOP — run `/tgd-map` first.

**🔑 Step 0: Feature Name Resolution**
1. Scan `$TGD_DIR/` for **feature directories**: subdirectories containing `SPEC.md` or `PRD.md` (e.g., `$TGD_DIR/user-login/`). Infrastructure dirs (`.scans/`, `wiki/`, and any dot-directories) are NOT features — always exclude them.
2. If none found: 🛑 STOP. "No features defined. Run `/tgd-define` first."
3. If exactly one found: Lock it as `<feature-name>`.
4. If multiple found: List them and ask user to specify.
5. **Verify**: `$TGD_DIR/<feature-name>/SPEC.md` exists (defines scope).

**🔒 Pre-flight: Artifact Check**
- [ ] `$TGD_DIR/<feature-name>/TASKS.md` exists and is non-empty.
- [ ] `$TGD_DIR/<feature-name>/PRD.md` exists and is non-empty.
- [ ] `$TGD_DIR/<feature-name>/SPEC.md` exists and is non-empty.
- **If missing:** STOP. Tell user: "Specs are missing. Please run `/tgd-define` first."

This is the BUILD phase. The pipeline operates in an isolated environment.

**🌳 Step 1: Worktree Isolation (Mandatory)**
Before writing any code, create an isolated workspace. This keeps `$TGD_DIR/` artifacts safe and prevents code mess from polluting the planning directory.
1. **Create** (branch + worktree in one step — the branch must NOT already be checked out anywhere, which is why `/tgd-define` does not create it):
   - Branch doesn't exist yet (normal case): `git worktree add ../project-<feature-name> -b feature/<feature-name> main`
   - Branch already exists (resuming): `git worktree add ../project-<feature-name> feature/<feature-name>` — if git says the branch is "already used by worktree", the main checkout is sitting on it: `git checkout main` there first, then retry.
2. **Action**: All coding, testing, and commits MUST happen inside `../project-<feature-name>/`.

**⚡ Step 2: Execution Mode Routing**
Check the number of tasks in `TASKS.md`:
- **< 3 tasks** (Simple/Fast): `tgd-incremental-implementation`. The main agent switches to the worktree directory and implements directly.
- **≥ 3 tasks** (Complex/Quality): `tgd-subagent-driven-development`. Dispatch subagents to implement and review within the worktree directory.

**Core flow (both modes):**
1. `tgd-context-engineering` — load the right spec sections and source files for the current task
   - Before modifying a file, run `codegraph callers <symbol>` to ensure backward compatibility.
2. `tgd-source-driven-development` — ground framework decisions in official docs, verify and cite
3. `tgd-subagent-driven-development` OR `tgd-incremental-implementation` — execute tasks in worktree
4. `tgd-test-driven-development` — Red-Green-Refactor, write tests alongside each task
5. `tgd-verification-before-completion` — evidence before claims, no exceptions

**Conditional (apply when relevant):**
- Working with unfamiliar code? → the `understand` skill to clarify architectural boundaries.
- Touching UI? → `tgd-frontend-ui-engineering`
- Designing APIs? → `tgd-api-and-interface-design`
- High-stakes decision? → `tgd-doubt-driven-development`

**🧹 Step 3: Hand-off (do NOT merge)**
After all tasks pass verification:
1. Commit all work on `feature/<feature-name>` inside the worktree.
2. **Keep the worktree** — `/tgd-verify` and `/tgd-review` run against it next.
3. **Do NOT merge to `main` here.** Merging happens in `/tgd-release`, after verify and review pass. Merging now would put unverified, unreviewed code on `main` — the exact thing the Review phase exists to prevent.

Use feature flags for incomplete features, safe defaults, and rollback-friendly changes.

**Do not pause between tasks.** Execute all tasks from the plan without stopping unless BLOCKED.

After completing the implementation, verify the outputs.

**Verification Gate:**
- [ ] Source code files created/modified in `src/`
- [ ] Tests written AND passing for new logic in `tests/`
- [ ] Verification commands run and output confirmed (no "should work")

If verification passes, suggest the next step: `/tgd-verify` to prove it works.
