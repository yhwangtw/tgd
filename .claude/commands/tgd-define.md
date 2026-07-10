---
description: Start spec-driven development — write a structured specification before writing code
---

**🛑 Pre-flight: Environment Check**
- [ ] `$TGD_DIR/CONTEXT.md` exists. No substitutes — `/tgd-map` produces it unconditionally (Tier 1), and this phase depends on its repo list, Build/Test/Run, and Conventions.
- **If missing:** STOP. Tell user: "Project context not mapped. Please run `/tgd-map` first."
- **$TGD_DIR:** Check env var `$TGD_DIR` first. If not set, check sibling `../<project-name>-tGD/`. If neither exists: STOP — run `/tgd-map` first.

**📊 FYI (non-blocking):** If any `$TGD_DIR/*/METRICS.md` still has a blank Actual column, mention it in ONE line ("N features shipped with metrics not yet filled in — the sheets are ready for whoever owns the data") and move on. Do NOT stop, do NOT ask, do NOT start filling them — reviewing metrics belongs to the team's own rituals, not to this command.

Run the `tgd-spec-driven-development` skill. Write a PRD (product requirements document) covering objectives, commands, structure, code style, testing strategy, and boundaries before any code is written.

This is the DEFINE phase. The full pipeline is:
1. `tgd-interview-me` — if the ask is underspecified, extract what the user actually wants
2. `tgd-idea-refine` — if the concept is vague, stress-test and expand options
3. **Existing-feature check (do this BEFORE proposing names).** Scan `$TGD_DIR/` for feature directories (subdirs containing `PRD.md` or `SPEC.md`; `.scans/` and dot-dirs are not features). If any exist AND the current ask plausibly relates to one, ask (Selection Protocol):

   > 📂 發現既有 feature：`<name>`（PRD: yes/no · SPEC: yes/no）
   >
   > 1. 修改/續寫這個 feature 的 spec
   > 2. 開一個新 feature
   >
   > Choose one (default 1 if the ask clearly amends it):

   - **Choice 1** → skip name resolution; work IN `$TGD_DIR/<existing-name>/`, updating PRD/SPEC in place (revise sections, don't blindly append). The Verification Gate below applies to the updated files.
   - **Choice 2 (or no related feature exists)** → continue to step 4.
   Never silently create a second directory for what is the same feature under a new name.
4. **Feature Name Resolution** (Selection Protocol) — analyze the request and extract the core action + object (e.g., "user login" → action: login, object: user). Then propose 3 distinct kebab-case `<feature-name>` options that **directly reflect the user's intent**:
   - Option 1: Most literal/direct (e.g., `user-login`)
   - Option 2: Action-focused (e.g., `authenticate-user`)
   - Option 3: Domain-specific if applicable (e.g., `auth-flow`)
   
   **Wait for the user to select one by number or provide their own before proceeding.** Once locked, create `$TGD_DIR/<feature-name>/`.
5. `tgd-spec-driven-development` — write the structured spec (PRD + SPEC)
6. **UI Design Gate** — see below, after SPEC.md is written

**📊 §6 Success Metrics rule** (see the filling rules in `tgd-spec-driven-development`): every metric's Measurement Method must be one of — (a) a concrete query in an existing tool, (b) a named tracking event (registered in `$TGD_DIR/TRACKING-PLAN.md` by `/tgd-plan`, which also creates the instrumentation tasks), or (c) `N/A — no user-measurable outcome` with a named PM sign-off line. "Check analytics" is a placeholder, not a source. Do not invent filler metrics for refactors — an honest N/A beats a fabricated KPI.

**🌿 No git operations in this phase.** PRD/SPEC live in `$TGD_DIR` (outside the code repo) — there is nothing to commit yet. The `feature/<feature-name>` branch is created by `/tgd-develop`'s worktree step (`git worktree add -b`). Creating AND checking out the branch here would make that mandatory worktree step fail: git refuses to check out a branch that is already checked out in another worktree (`fatal: '<branch>' is already used by worktree …`).

**Multi-Repo Tagging:** If CONTEXT.md lists multiple repos, SPEC.md MUST be tagged by repo:
```markdown
## Backend (my-project-backend)
### API Contracts
- POST /api/auth/login → ...

## Frontend (my-project-frontend)
### Components
- LoginForm.tsx → ...
```
Each section header uses `## <repo-name>` so tasks can be traced to their target repo.

**Step 6: UI Design Gate (MANDATORY CHECK via Selection Protocol)**
After writing SPEC.md, you MUST ask the user: "Does this feature have a UI component requiring DESIGN.md?"
**Format:** "1. Yes (Generate design) 2. No (Backend only)"
- If YES: 
  1. Run the `tgd-sketch` skill to generate 2-3 HTML prototype variants in `$TGD_DIR/<feature-name>/prototype/`
  2. Present comparison table → user picks one by letter (or requests iteration)
  3. Write DESIGN.md documenting the chosen design decisions and component tree
  4. Wait for user confirmation before proceeding.
- If NO: skip DESIGN.md and prototype. **You cannot skip this step without explicit user approval.**

After completing the spec, verify the outputs. The gate scripts live in the tGD clone — resolve `$TGD_REPO_ROOT` per `tgd-rules` → **Resolving $TGD_REPO_ROOT**.

**Verification Gate:**
- [ ] `$TGD_DIR/` directory exists
- [ ] `$TGD_DIR/<feature-name>/PRD.md` exists and is non-empty
- [ ] `$TGD_DIR/<feature-name>/SPEC.md` exists and is non-empty
- [ ] `python3 "$TGD_REPO_ROOT/scripts/check-doc-sections.py" PRD "$TGD_DIR/<feature-name>/PRD.md"` exits 0 — every required PRD section is present (`(if applicable)` sections are not forced; missing ones are listed)
- [ ] `python3 "$TGD_REPO_ROOT/scripts/check-doc-sections.py" SPEC "$TGD_DIR/<feature-name>/SPEC.md"` exits 0 — every required SPEC section is present
- [ ] PRD §6 Success Metrics: at least one row names a real data source (concrete tool query or named event) — OR the section is `N/A` with a named PM sign-off line. Placeholder rows (`[Metric 1]`, "check analytics") fail this gate.
- [ ] No feature branch was created or checked out (that happens in `/tgd-develop`)
- [ ] If UI feature: `$TGD_DIR/<feature-name>/DESIGN.md` exists with Component Tree
- [ ] If UI feature: `$TGD_DIR/<feature-name>/prototype/` contains at least 2 HTML variants

End with the closing report per `tgd-rules` → **Command Closing Report**: 📦 產出 (PRD.md + SPEC.md, and DESIGN.md/prototype if UI) · 🔎 檢查 (gate as one line) · ➡️ 下一步 `/tgd-plan` — 拆解成任務. Don't paste the raw checklist above.
