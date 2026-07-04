---
description: Release to production
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
- [ ] Review passed (no critical issues).
- [ ] `$TGD_DIR/<feature>/REVIEW.md` exists.
- [ ] The feature's tests exist (per the project's layout in `CONTEXT.md`) and pass.
- **If missing:** STOP. Tell user: "Review or tests incomplete. Please run `/tgd-review` first."

Run the `tgd-shipping-and-launch` skill. This is the Release phase. The full pipeline is:

**Core flow:**
1. `tgd-git-workflow-and-versioning` — clean commit history, trunk-based development
2. **🌳 Merge & worktree cleanup** — this is where the feature branch lands on `main` (NOT in `/tgd-develop`):
   1. Merge `feature/<feature-name>` into `main` (or open a PR, per team policy).
   2. Remove the worktree: `git worktree remove ../project-<feature-name>`.
3. `tgd-shipping-and-launch` — pre-launch checklist, staged rollouts, monitoring setup

**Conditional (apply when relevant):**
- CI/CD pipeline work? → `tgd-ci-cd-and-automation`
- Removing old systems? → `tgd-deprecation-and-migration`
- New architecture or API? → `tgd-documentation-and-adrs`

Faster is safer. Deploy in stages, confirm monitoring, and have a rollback plan.

After releasing, update `$TGD_DIR/CHANGELOG.md` (create if it doesn't exist) with:
- Version (CalVer: `vYYYY.MM.DD`)
- Feature name and summary
- Date shipped
- Key changes

**📦 Regression Catalog Update**
After releasing, scan `$TGD_DIR/<feature-name>/TASKS.md` for Acceptance Criteria marked `[R]` (Regression). For EACH `[R]` criterion:
1. Extract the BDD criterion (Given/When/Then).
2. Identify the actual test file that verifies this criterion (from `tests/` in the shipped code).
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
   - **Shipped:** vYYYY.MM.DD
   ```
This catalog is cumulative — every shipped feature's `[R]` tests are preserved for future regression checks. Future features will re-run ALL catalog entries during `/tgd-verify`.

**🧹 Regression Catalog Audit (MANDATORY if `$TGD_DIR/REGRESSION-CATALOG.md` exists)**
Before finalizing the release, audit the existing catalog for staleness:
1. Read every entry in `$TGD_DIR/REGRESSION-CATALOG.md`.
2. For EACH existing entry (not just the current feature's new ones):
   - **Test file exists?** If the path is broken (file deleted, moved, or renamed): remove the entry. Log the removal in `$TGD_DIR/CHANGELOG.md` under a `## Catalog Cleanup` subsection.
   - **Test still passes?** Run it. If it fails: 🛑 STOP — this is a regression. Fix before releasing.
   - **Feature deprecated?** If the feature's code was removed or deprecated in this cycle (`tgd-deprecation-and-migration` ran): remove its entries from the catalog.
3. After audit, the catalog must contain ONLY entries whose test files exist and pass.

This prevents the catalog from becoming a zombie file full of dead references. Every entry should be runnable.

**Verification Gate:**
- [ ] Git commit created with clean history
- [ ] `feature/<feature-name>` merged to `main` (or PR opened) and worktree removed
- [ ] `$TGD_DIR/CHANGELOG.md` exists and is updated
- [ ] `$TGD_DIR/REGRESSION-CATALOG.md` updated with new `[R]` entries (if any)
- [ ] Regression Catalog Audit completed — all entries point to existing, passing test files

If verification passes, confirm that monitoring is active and the rollback plan is documented.
