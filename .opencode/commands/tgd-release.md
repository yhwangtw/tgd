---
description: Release to production — faster is safer
---

## Release path selection (HARD ROUTING GATE)

Classify the release before resolving `$TGD_DIR`. The default is the downstream
feature path; the framework maintenance path is available only when every
condition below is true:

1. One resolved repository root contains all six canonical tGD markers:
   `skills/tgd-core-rules/SKILL.md`, `.claude/commands/tgd-release.md`,
   `scripts/generate-mirrors.py`, `scripts/release.sh`,
   `.github/workflows/release.yml`, and `VERSION`.
   Resolve that root with `git rev-parse --show-toplevel`; every marker must be
   a tracked regular file at that exact root.
2. The requested release is for that repository's tGD framework, installer,
   lifecycle commands, skills, templates, mirrors, tests, or documentation —
   not for a downstream product that uses tGD.
3. No downstream `$TGD_DIR` feature has been selected for this release. If the
   user or current workflow selected one, the downstream path wins even when
   its artifacts are incomplete.
4. Missing lifecycle artifacts alone never qualify a release for this path.
   Repository identity and maintenance scope must both be established from
   current evidence.

This exception changes routing, not evidence standards or authority. Chat
approval cannot turn a downstream feature into framework maintenance, repair
missing downstream sign-offs, or authorize merge/publish by itself.

- **Downstream feature** → continue with **Downstream feature pre-flight**.
- **Framework maintenance** → skip the downstream artifact/sign-off sections
  and run **Framework maintenance release path**. Do not run both paths.

## Downstream feature pre-flight

- [ ] Resolve `$TGD_DIR` from its environment variable, then sibling `../<project-name>-tGD/`; require CONTEXT.md or STOP and run `/tgd-map`.
- [ ] Select `<feature-name>` from non-infrastructure subdirectories containing PRD.md or SPEC.md. None means STOP and run `/tgd-define`; multiple means ask. Require SPEC.md.
- [ ] **Review passed**: REVIEW.md exists and every 🔴 finding is `fixed`; TEST-REPORT contains passing executable-test/coverage evidence or explicit documentation-only N/A fields with passing AC trace and documentation checks.
- [ ] When PRD UI mode is 1–3, DESIGN.md exists and REVIEW Design Conformance is `✅ Pass` for the reviewed feature SHA.

**If missing:** STOP. Tell user: "Review or tests incomplete. Please run `/tgd-review` first."

## Sign-off Gate (HARD GATE)

Release alone blocks for humans. Run these scoped fixed-string checks (never file-wide grep):

```bash
awk '/^## Sign-off/,0' "$TGD_DIR/<feature-name>/TEST-REPORT.md" | grep -qF '[x] **QA**: Approved'
awk '/^## Sign-off/,0' "$TGD_DIR/<feature-name>/REVIEW.md" | grep -qF '[x] **QA**: Approved'
awk '/^## Sign-off/,0' "$TGD_DIR/<feature-name>/REVIEW.md" | grep -qF '[x] **DEV**: Approved'
awk '/^## Sign-off/,0' "$TGD_DIR/<feature-name>/PRD.md" | grep -qF '[x] **PM**: Approved'
```

Chat or session approval does not replace an artifact sign-off and cannot expand Release authority. The PM must update the PM line in PRD.md. UI modes 1–3 additionally run the same scoped fixed-string check for DESIGN.md `[x] **DESIGN**: Direction Approved` and REVIEW.md `[x] **DESIGN**: Implementation Approved`.

**If any grep exits non-zero** (line unchecked, missing, or `Rejected`): 🛑 STOP. List the pending roles and wait — humans review async. Do NOT proceed "provisionally".

## Framework maintenance release path

This path is only for the repository identified by all six markers above. It
does not use a synthetic `$TGD_DIR`, fabricated feature artifacts, or the
product-deployment gates in `tgd-release-ship`.

1. Run `tgd-core-git`. Require an attached, intent-named branch based on the
   repository's current default branch, an empty `git status --porcelain`, and
   an exact remote branch head equal to local `HEAD`.
2. Record the reviewed PR head SHA. Require a PR targeting `main` whose body
   states Summary, Impact, Verification, and `Framework maintenance release
   exception`; require it to be ready for review (not draft), mergeable, free
   of unresolved required reviews, and green on every required check for that
   exact head SHA.
3. Merge only after step 2 passes, then wait until the provider reports the PR
   merged. An opened PR remains pending. Record the landed `main` SHA and prove
   that the reviewed PR content landed; a local merge or an unverified branch
   head is not release evidence.
4. From a clean attached branch created at that exact landed `main` state, run
   `bash scripts/release.sh --dry-run` first. Review the computed immutable
   CalVer and CHANGELOG entry; the dry run must leave the worktree unchanged.
5. Run `bash scripts/release.sh --yes` only after the dry run passes. The script
   prepares and pushes the VERSION/CHANGELOG release commit; it does not publish
   a tag or GitHub Release. If repository policy does not explicitly permit the
   release commit to be pushed directly to `main`, prepare it on a dedicated
   release branch, open a PR, and again wait for merge and required CI.
6. Publishing starts only after the VERSION-changing release commit reaches
   `main`. Wait for `.github/workflows/release.yml`, then verify required CI is
   green, the immutable tag resolves to that release commit, the tag's VERSION
   and CHANGELOG entry match, and the GitHub Release exists at a recorded URL.
7. Delete the maintenance/release branches or worktrees only after step 6
   passes. A failed check, merge, tag, or publication blocks cleanup and the
   closing report must name the last verified state.

After step 7, continue only to the framework-maintenance verification list and
the closing report below; do not run the downstream release pipeline.

## Release pipeline

Run the `tgd-release-ship` skill. This is the Release phase. The full pipeline is:

1. Run `tgd-core-git` for clean trunk-based history.
2. Load `tgd-release-ship`; complete its Pre-Launch Gates, document rollback triggers and exact steps, confirm monitoring, and configure the feature flag when applicable. These gates happen before merge.
3. Run the pre-merge Regression Catalog Audit below.
4. Deploy staging from the verified feature branch; run the full applicable suite and smoke-test critical flows.
5. Land the feature on `main` using the merge or PR policy below. An opened PR is pending, so wait for merge and required CI.
6. Record the landed `main` SHA and continue `tgd-release-ship` from that exact SHA: deploy production with the flag off, verify health/error monitoring, then use its staged-rollout thresholds and rollback rules.
7. Clean up worktrees and landed branches only after the initial production health and rollback-readiness checks pass.

Conditional routing:

- **CI/CD pipeline work? → `tgd-release-ci`**
- **Removing old systems? → `tgd-release-migration`**
- New architecture or API → `tgd-review-adr`.

### Regression Catalog Audit

**🧹 Regression Catalog Audit — BEFORE merging** (MANDATORY if `$TGD_DIR/REGRESSION-CATALOG.md` exists). Run it in the worktree (`../project-<feature-name>`; multi-repo features have one per repo — `../project-<feature-name>-<repo-name>` — audit each), so a failure stops the release before anything lands on `main`:

1. Read every catalog entry. Remove entries for missing/moved test files and log them under CHANGELOG `## Catalog Cleanup`; also remove entries deprecated by this migration cycle.
2. Run `bash "$TGD_REPO_ROOT/scripts/regression-gate.sh" <worktree> "$TGD_DIR" [repo-name]` once per worktree.
3. Exit 0 passes. Exit 1 blocks for regression repair. Exit 2 is an invocation/configuration failure. Exit 3 means no catalog yet.
4. Continue only with a catalog containing existing, passing tests.

### Land, deploy, and cleanup

Repeat per repo with tasks:

1. Require empty `git status --porcelain` in the feature worktree. Commit verified-state changes; delete only tool residue.
2. Merge `feature/<feature-name>` into `main`, or open a PR per team policy and wait for it to land.
3. Opening a PR is a pending state, not a successful Release gate. Keep the worktree and branch while review or CI is pending; resume only after the provider reports the PR merged and required CI passed.
4. Record the landed `main` SHA, verify it contains the reviewed feature content, and deploy production from that SHA — never from the feature worktree or an unverified local HEAD.
5. Run the initial production health, error-monitoring, critical-flow, log, and rollback-readiness checks from `tgd-release-ship`. A failure triggers rollback and blocks cleanup.
6. **Only after the merge landed and the initial production checks passed**, remove the worktree with `git worktree remove ../project-<feature-name>` (multi-repo: `../project-<feature-name>-<repo-name>`), then delete the landed branch with `git branch -d feature/<feature-name>`.

## Release artifacts

### CHANGELOG

Before merge, draft the candidate entry in `$TGD_DIR/CHANGELOG.md` (create it from the canonical template when absent) so the pre-launch documentation gate can be reviewed. After the landed SHA passes initial production checks, finalize the release version, date, and reference; never mark it released before production success. Include:

- CalVer: `vYYYY.MM.DD`, adding `.2`, `.3`, and so on for same-day releases.
- Feature name/summary, ship date, and key changes.
- Use `$TGD_REPO_ROOT/templates/CHANGELOG.md.tmpl` when creating it.

### Metrics handoff

**Skip this step entirely if PRD §6 is `N/A` (with its PM sign-off) — do NOT generate an empty sheet.** Otherwise create METRICS.md from the canonical template and copy every PRD §6 row verbatim, leaving Actual and Filled on blank. Do not chase or schedule data collection. In TRACKING-PLAN.md change this feature's entries from **`Status: planned` to `Status: live`**, recorded as `Status: live since vYYYY.MM.DD`.

### Regression catalog update

After release, ensure REGRESSION-CATALOG.md exists. If absent, seed it from `$TGD_REPO_ROOT/templates/REGRESSION-CATALOG.md.tmpl`, set the audit date, and remove the placeholder entry. Then, for every TASKS.md Acceptance Criteria marked `[R]`, copy its AC id/BDD criterion and its already-validated `Test:` path using the template's entry shape. Do not infer test paths. A release with no `[R]` criteria still leaves the empty seeded catalog so a later missing file cannot masquerade as a first release.

**This catalog is cumulative — every shipped feature's `[R]` tests are preserved for future regression checks. Future features will re-run ALL catalog entries during `/tgd-verify` (and again in this command's pre-merge audit).**

## Verification Gate

Apply only the list for the path selected by the routing gate.

### Downstream feature

- [ ] All role/design sign-offs passed.
- [ ] `tgd-release-ship` pre-launch/rollback/monitoring gates and staging checks passed before merge.
- [ ] Pre-merge regression audit passed in every repo.
- [ ] Git commit created with clean history.
- [ ] The change landed on `main`; required CI passed; the recorded landed SHA was the production deployment source. A merely opened PR does not pass.
- [ ] Initial production health, monitoring, critical-flow, logs, and rollback readiness passed before worktree/branch cleanup.
- [ ] CHANGELOG is updated; METRICS/TRACKING-PLAN handling matches signed-off PRD §6.
- [ ] REGRESSION-CATALOG.md exists; every new `[R]` AC is represented in it.

### Framework maintenance

- [ ] All six repository markers and the maintenance-only scope were verified; no selected downstream feature was bypassed.
- [ ] The exact PR head SHA was pushed, ready, mergeable, and green before merge; the provider then reported it merged to the recorded `main` SHA.
- [ ] `scripts/release.sh --dry-run` passed without changes before `scripts/release.sh --yes` prepared the release commit.
- [ ] The VERSION-changing commit landed on `main`; required CI and `release.yml` passed for current evidence.
- [ ] The immutable tag, tagged VERSION/CHANGELOG, and GitHub Release URL all resolve to the verified release commit.
- [ ] Cleanup happened only after publication verification passed.

End with the closing report per `tgd-core-rules` → **Command Closing Report**: 📦 Output (landed SHA + production release + CHANGELOG/METRICS/REGRESSION-CATALOG updates) · 🔎 Checks (gate as one line) · ➡️ Next state the active monitoring window, owner, and rollback trigger (Release is terminal; there is no next lifecycle command). Don't paste the raw checklist above.
