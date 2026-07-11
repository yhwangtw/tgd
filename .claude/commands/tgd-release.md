---
description: Release to production — faster is safer
---

**🛑 Pre-flight: Environment Check**
- [ ] `$TGD_DIR/CONTEXT.md` exists. No substitutes — `/tgd-map` produces it unconditionally (Tier 1).
- **If missing:** STOP. Tell user: "Project context not mapped. Please run `/tgd-map` first."
- **$TGD_DIR:** Check env var `$TGD_DIR` first. If not set, check sibling `../<project-name>-tGD/`. If neither exists: STOP — run `/tgd-map` first.

**🔑 Step 0: Feature Name Resolution**
1. Scan `$TGD_DIR/` for **feature directories**: subdirectories containing `SPEC.md` or `PRD.md` (e.g., `$TGD_DIR/user-login/`). Infrastructure dirs (`.scans/`, `wiki/`, and any dot-directories) are NOT features — always exclude them.
2. If none found: 🛑 STOP. "No features defined. Run `/tgd-define` first."
3. If exactly one found: Lock it as `<feature-name>`.
4. If multiple found: List them and ask user to specify.
5. **Verify**: `$TGD_DIR/<feature-name>/SPEC.md` exists (defines scope).

**🔒 Pre-flight: Artifact Check**
- [ ] Review passed — no 🔴 Critical finding left unresolved: every 🔴 row in REVIEW.md's findings table reads `fixed` in its Resolution column (a 🔴 row that is `open`, empty, or `deferred` blocks release).
- [ ] `$TGD_DIR/<feature>/REVIEW.md` exists.
- [ ] The feature's tests exist (per the project's layout in `CONTEXT.md`) and pass.
- **If missing:** STOP. Tell user: "Review or tests incomplete. Please run `/tgd-review` first."

**🔏 Pre-flight: Sign-off Gate (HARD GATE)**
Release is the one phase that blocks on human sign-off (see `tgd-rules` → Human Roles & Sign-off Protocol). Check the `## Sign-off` sections:
- [ ] `$TGD_DIR/<feature-name>/TEST-REPORT.md` — **QA** line is `[x] ... Approved`.
- [ ] `$TGD_DIR/<feature-name>/REVIEW.md` — **QA** and **DEV** lines are `[x] ... Approved`.
- [ ] **PM** final approval — `[x] ... Approved` in `$TGD_DIR/<feature-name>/PRD.md`'s Sign-off, or an explicit go-ahead from the user in this session (record it in the CHANGELOG entry).
- **If any required line is unchecked, missing, or `Rejected`:** 🛑 STOP. List the pending roles and wait — humans review async. Do NOT proceed "provisionally".

Run the `tgd-shipping-and-launch` skill. This is the Release phase. The full pipeline is:

**Core flow:**
1. `tgd-git-workflow-and-versioning` — clean commit history, trunk-based development
2. **🧹 Regression Catalog Audit — BEFORE merging** (MANDATORY if `$TGD_DIR/REGRESSION-CATALOG.md` exists). Run it in the worktree (`../project-<feature-name>`; multi-repo features have one per repo — `../project-<feature-name>-<repo-name>` — audit each), so a failure stops the release before anything lands on `main`:
   1. Read every entry in `$TGD_DIR/REGRESSION-CATALOG.md` (not just the current feature's).
   2. **Test file exists?** If the path is broken (file deleted, moved, or renamed): remove the entry. Log the removal in `$TGD_DIR/CHANGELOG.md` under a `## Catalog Cleanup` subsection.
   3. **Feature deprecated?** If the feature's code was removed or deprecated in this cycle (`tgd-deprecation-and-migration` ran): remove its entries from the catalog.
   4. **Every entry still passes?** Run the machine gate — do NOT eyeball it (resolve `$TGD_REPO_ROOT` per `tgd-rules` → **Resolving $TGD_REPO_ROOT**):
      `bash "$TGD_REPO_ROOT/scripts/regression-gate.sh" ../project-<feature-name> "$TGD_DIR"` (multi-repo: once per worktree — `../project-<feature-name>-<repo-name>` as the first arg AND the repo name as the third, so entries tagged `Repo:` for other repos are skipped there instead of failing as missing)
      Exit 0 = pass. Exit 1 = 🛑 STOP — a shipped behavior regressed; fix before merging. Exit 2 = configuration error — fix the invocation, never treat as pass. Exit 3 = no catalog yet — skip this audit.
   5. After the audit, the catalog contains ONLY entries whose test files exist and pass. This prevents the catalog from becoming a zombie file full of dead references.
3. **🌳 Merge & worktree cleanup** — this is where the feature branch lands on `main` (NOT in `/tgd-develop`). Multi-repo features repeat all three steps in EACH repo that has a worktree:
   1. Merge `feature/<feature-name>` into `main` (or open a PR, per team policy).
   2. Remove the worktree: `git worktree remove ../project-<feature-name>` (multi-repo: `../project-<feature-name>-<repo-name>`).
   3. After the merge lands, delete the branch: `git branch -d feature/<feature-name>`.
4. `tgd-shipping-and-launch` — pre-launch checklist, staged rollouts, monitoring setup

**Conditional (apply when relevant):**
- CI/CD pipeline work? → `tgd-ci-cd-and-automation`
- Removing old systems? → `tgd-deprecation-and-migration`
- New architecture or API? → `tgd-documentation-and-adrs`

Faster is safer. Deploy in stages, confirm monitoring, and have a rollback plan.

After releasing, update `$TGD_DIR/CHANGELOG.md` (create if it doesn't exist) with:
- Version (CalVer: `vYYYY.MM.DD`; if that version already exists in the CHANGELOG, append a micro number — `vYYYY.MM.DD.2`, `.3`, … — for additional releases on the same day)
- Feature name and summary
- Date shipped
- Key changes

**📊 METRICS.md — Metrics Handoff**
Skip this step entirely if PRD §6 is `N/A` (with its PM sign-off) — do NOT generate an empty sheet.
Otherwise, create `$TGD_DIR/<feature-name>/METRICS.md` from the PRD §6 table:
```markdown
# METRICS: <feature-name>
> Shipped: vYYYY.MM.DD · Source: PRD §6

| Metric | Target | Data Source / Event | Actual | Filled on |
|--------|--------|---------------------|--------|-----------|
| [from §6] | [from §6] | [from §6] | | |
```
- Copy every §6 row verbatim; leave **Actual** and **Filled on** blank. This sheet is a **handoff** — whoever owns the data (PM, analyst) fills it in their own rituals (weekly review, dashboard check). tGD's job ends at making the sheet accurate; do NOT chase the numbers, do NOT schedule follow-ups.
- In `$TGD_DIR/TRACKING-PLAN.md`, flip this feature's event entries from `Status: planned` to `Status: live since vYYYY.MM.DD`.

**📦 Regression Catalog Update**
After releasing, scan `$TGD_DIR/<feature-name>/TASKS.md` for Acceptance Criteria marked `[R]` (Regression). For EACH `[R]` criterion:
1. Extract the BDD criterion (Given/When/Then) and its AC id.
2. Take the test file from the criterion's `Test:` field in TASKS.md — recorded during `/tgd-develop` and already validated by `ac-trace.py` during `/tgd-verify`. Do NOT guess the file from directory listings.
3. Append entries to `$TGD_DIR/REGRESSION-CATALOG.md` (create if it doesn't exist):
   If creating for the first time, start with this header:
   ```markdown
   # Regression Catalog
 
   > Cumulative catalog of `[R]` regression tests across all shipped features.
   > Every entry must point to an existing, passing test file.
   > Last audited: YYYY-MM-DD
 
   ---
   ```
   Then append each `[R]` criterion as an entry:
   ```markdown
   ### [<feature-name>] Short description
   - **Criterion:** Given X, When Y, Then Z
   - **Test:** `tests/path/to/test.ts`
   - **Repo:** <repo-name>   (multi-repo features ONLY — from the task's `[repo-name]` tag; omit for single-repo. `regression-gate.sh` uses it to run each entry against the right worktree.)
   - **Shipped:** vYYYY.MM.DD
   ```
This catalog is cumulative — every shipped feature's `[R]` tests are preserved for future regression checks. Future features will re-run ALL catalog entries during `/tgd-verify` (and again in this command's pre-merge audit).

**Verification Gate:**
- [ ] Sign-off Gate passed — all required role lines are `[x] Approved`
- [ ] Regression Catalog Audit ran BEFORE the merge — `regression-gate.sh` exit 0 (or 3), all entries point to existing, passing test files
- [ ] Git commit created with clean history
- [ ] `feature/<feature-name>` merged to `main` (or PR opened), worktree removed, branch deleted
- [ ] `$TGD_DIR/CHANGELOG.md` exists and is updated
- [ ] `$TGD_DIR/<feature-name>/METRICS.md` created from PRD §6 with Actual left blank (skipped only for signed-off N/A); TRACKING-PLAN entries flipped to `live`
- [ ] `$TGD_DIR/REGRESSION-CATALOG.md` updated with new `[R]` entries (if any)

End with the closing report per `tgd-rules` → **Command Closing Report**: 📦 產出 (released version + CHANGELOG/METRICS/REGRESSION-CATALOG updates) · 🔎 檢查 (gate as one line) · ➡️ 下一步 確認 monitoring 已啟動、rollback plan 有記錄（發布是終點,不接下一個命令）. Don't paste the raw checklist above.
