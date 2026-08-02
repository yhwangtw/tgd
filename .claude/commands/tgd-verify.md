---
description: Verify — prove it works with debugging and test pyramid
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
- [ ] The feature branch has source changes: `git diff main...feature/<feature-name> --stat` is non-empty (multi-repo: in each repo with tagged tasks).
- [ ] Test files exist for the feature — use the project's actual test layout from `CONTEXT.md` (`tests/`, `spec/`, `*_test.go`, `__tests__/`, …). Do NOT assume a `src/`+`tests/` layout.
- [ ] Every task with `**Status:** complete` in TASKS.md has `Spec-Review:` and `Quality-Review:` fields reading `PASS — …` (not `pending`) — a pending review field means `/tgd-develop` skipped its two-stage review. 🛑 STOP: send it back to `/tgd-develop`; do not verify unreviewed work.
- [ ] Read PRD `## UI Design`. For modes 1–3, Status is `direction-approved`, DESIGN.md exists, and its Sign-off contains `[x] **DESIGN**: Direction Approved`. A missing required design artifact is a hard failure, not a non-UI feature.
- **If missing:** STOP. Report the specific missing artifact: source/tests return to `/tgd-develop`; UI classification or design direction returns to `/tgd-define`.

**🌳 Worktree:** If `../project-<feature-name>` exists (created by `/tgd-develop`), run all commands in this phase inside that worktree — the feature branch is not on `main` yet. Multi-repo features (TASKS.md has `[repo-name]` prefixes) have one worktree PER repo (`../project-<feature-name>-<repo-name>`) — run each repo's tests inside ITS worktree; verifying only one repo is a partial verify, not a pass.

Run the `tgd-verify-debug` skill. This is the VERIFY phase. The full pipeline is:

**Core flow:**
1. `tgd-verify-debug` — five-step triage: reproduce → localize → reduce → fix → guard
2. `tgd-develop-tdd` — verify with the test pyramid (80% unit, 15% integration, 5% E2E)
   - **If `codegraph` is available** (the `/tgd-map` Step 0.5 probe): use `codegraph affected <changed-files>` to identify which tests to prioritize based on actual dependency paths. If not installed, skip — run the full relevant suite instead; this enrichment is Tier 2, its absence is not a failure.

**Conditional (Frontend Mandatory):**
- **Frontend/UI/DOM?** → **MUST run `tgd-verify-browser`**. Unit tests are NOT sufficient for UI verification.
  - Use `tgd-verify-browser` (preferred) to open the browser, perform the user action, and verify the DOM state.
  - **Verification Gate Failure**: If the feature touches frontend code but `tgd-verify-browser` did not run, the verification is FAILED.

Verify that the feature works correctly before proceeding to review. Tests are proof — "seems right" is never sufficient.

Run the test-output capture first — this is the raw evidence that backs the report.

The gate scripts live in the **tGD repo itself** (`$TGD_REPO_ROOT/scripts/`), NOT in `$TGD_DIR` (the artifacts directory contains no scripts). Resolve `$TGD_REPO_ROOT` per `tgd-core-rules` → **Resolving $TGD_REPO_ROOT** (env var → `~/tGD` → installed-skill symlink).

```bash
# Run from the WORKTREE (../project-<feature-name>/ — that's where the feature
# branch's code and tests live; fall back to the repo root only if no worktree
# exists). Creates the report file if needed, runs the suite, appends a
# "## Raw Test Output" section + meta-comment with real pass/fail counts.
bash "$TGD_REPO_ROOT/scripts/capture-test-output.sh" "$TGD_DIR/<feature-name>/TEST-REPORT.md"
# Multi-repo: run once per worktree, passing the repo name as the LABEL (3rd
# arg; "" = auto-detect the test command). Each repo gets its own
# "## Raw Test Output (<repo-name>)" section — without the label, the second
# repo's run REPLACES the first repo's evidence.
bash "$TGD_REPO_ROOT/scripts/capture-test-output.sh" "$TGD_DIR/<feature-name>/TEST-REPORT.md" "" "<repo-name>"
```

- **Exit 0** = tests passed, raw output captured. Use the real numbers from the meta-comment in the Summary table below — do NOT invent counts.
- **Exit 1** = tests failed, raw output still captured. Fix the failures, re-run, only then proceed.

The script **creates the TEST-REPORT.md skeleton if it doesn't exist** from `$TGD_REPO_ROOT/templates/TEST-REPORT.md.tmpl` (sections: Test Summary, Coverage, Failures & Root Causes, Flaky Tests, Regression Status, Sign-off). Do NOT hand-create TEST-REPORT.md before running the capture — let the script emit the skeleton. (If the file somehow exists without a `## Sign-off` section, the script appends one — that section's QA line is what `/tgd-release`'s sign-off grep reads.) Fill in the tables using ONLY the numbers from the appended meta-comment.

For the Coverage table, run the coverage gate first:

```bash
bash "$TGD_REPO_ROOT/scripts/coverage-check.sh"
```

Exit 0 = all floors met, use the printed numbers. Exit 1 = gate failed, do not proceed. Exit 2 = no coverage tool installed or output unparseable — a configuration problem: install the tool it names (e.g. `npm i -D @vitest/coverage-v8`, `pip install pytest-cov`, `cargo install cargo-tarpaulin`), then re-run. NEVER treat exit 2 as a pass. Floors default to 80/60/90 (lines/branches/functions); overrides via `COVERAGE_*_FLOOR` env vars MUST be documented in a "## Coverage Exceptions" section with a ramp-up plan.

**🎯 AC Traceability Gate (MANDATORY)**

Line coverage is not requirement coverage — verify every acceptance criterion has a test:

```bash
python3 "$TGD_REPO_ROOT/scripts/ac-trace.py" "$TGD_DIR/<feature-name>/" .
```

- **Exit 0** = every `AC-<task>.<n>` id in TASKS.md is referenced by at least one test (or, for documentation-only criteria with a `Doc:` carrier, the named file exists and contains the quoted string), and every `[R]` criterion names an existing test file. Proceed.
- **Exit 1** = untraced criteria or `[R]` entries without valid `Test:` files — the output lists exactly which. 🛑 Write the missing tests (or tag the existing ones with the AC id), re-run, only then proceed.
- **Exit 2** = TASKS.md missing or carries no AC ids. A plan without AC ids fails closed — fix TASKS.md (see `tgd-plan-breakdown`).

**📡 Event Test Check (only if `$TGD_DIR/TRACKING-PLAN.md` has entries for this feature)**

For each event whose **Platforms** field includes the platform this worktree implements: at least one test must reference the event name and assert it fires with the expected property keys. A mis-firing event is worse than a missing one — a wrong number gets trusted. Check with a plain search (e.g. `grep -r "sign_up_completed" <test-dirs>`); the instrumentation task's AC id is already covered by `ac-trace.py`, so this check is specifically about the payload assertion. If no test asserts the payload: write it before proceeding — same standard as any other AC.

Run the machine gate — do NOT manually walk the catalog:

```bash
# args: <client-repo> <artifacts-dir>. Pass the WORKTREE as the client repo —
# the catalog's tests must run against the feature branch. The catalog lives in
# the ARTIFACTS dir (../<project>-tGD/REGRESSION-CATALOG.md), not in the tGD repo.
# Multi-repo: run once per worktree, passing the repo name as the 3rd arg —
# entries carry a "Repo:" field and the gate skips (loudly) the ones that
# belong to other repos:
#   bash .../regression-gate.sh ../project-<feature>-<repo-name> "$TGD_DIR" <repo-name>
bash "$TGD_REPO_ROOT/scripts/regression-gate.sh" ../project-<feature-name> "$TGD_DIR"
```

The gate executes **every catalog entry individually** (jest/vitest/npm/pytest/go per-file) — full-suite green is not accepted as proof, because a file can exist yet be excluded by runner config. Flaky policy: a failing entry is retried once; pass-on-retry counts as a pass but is reported as FLAKY and MUST be recorded in TEST-REPORT.md "## Flaky Tests" with a follow-up.

- **Exit 0** = all catalog entries executed and passed. Record any FLAKY entries, then proceed.
- **Exit 1** = an entry failed twice, is stale, or lacks a `Test:` reference. 🛑 STOP. Do NOT proceed to review. Report which prior feature's regression broke.
- **Exit 2** = configuration failure (artifacts dir unresolvable, no test runner). Fix the configuration — this is NOT a pass.
- **Exit 3** = no catalog file yet. Legitimate only before the first `/tgd-release`.

**Why machine-gated**: Manually walking the catalog is exactly the failure mode this gate prevents — agents skip entries, run the wrong file, or trust stale references. The script enforces "every entry runs" without exception.

**Verification Gate Failure**: A broken regression test means your feature broke a previously shipped critical path. This is a hard fail — no exceptions.

**🎨 Design Conformance Gate (MANDATORY for PRD UI modes 1–3):**

This is implementation QA against the approved direction, not another design phase.

1. Ensure the implementation being inspected is committed, then record `git rev-parse HEAD`. If Verify changes code, commit it and re-run every affected test/gate against the new SHA before reporting success.
2. Read DESIGN.md and the actual design-system/token/component sources linked by CONTEXT.md. Verify the implemented user flow, information hierarchy, component mapping, token changes, interaction/state matrix, content, accessibility rules, responsive behavior, and allowed deviations.
3. Exercise the UI at every named viewport with `tgd-verify-browser`. Capture the loading, empty, error, success, and disabled states that apply; verify keyboard traversal, visible focus, labels, and critical screen-reader semantics.
4. Save reproducible evidence under `$TGD_DIR/<feature-name>/evidence/ui/` (screenshots, traces, or concise text evidence) or record stable CI artifact URLs. Evidence MUST identify the tested commit SHA and viewport/state; a statement such as "looks correct" is not evidence.
5. Append a `## UI Verification` section to TEST-REPORT.md with: commit SHA, source revision, viewports/states checked, evidence links/paths, deviations found, and `Status: Pass` or `Status: Fail`.
6. Any implementation difference not listed under DESIGN.md `Allowed Deviations` is a failure. Fix the implementation or return to `/tgd-define` for explicit direction approval; do not silently rewrite DESIGN.md during Verify.

**Verification Gate:**
- [ ] Tests pass for the implemented feature
- [ ] `capture-test-output.sh` ran and appended raw output + meta-comment to TEST-REPORT.md
- [ ] Summary table counts match the meta-comment (no fabrication)
- [ ] `coverage-check.sh` exits 0 (or exceptions documented in "## Coverage Exceptions")
- [ ] `ac-trace.py` exits 0 — every acceptance criterion traced to a test
- [ ] If TRACKING-PLAN.md has entries for this feature: each event owned by this platform has a test asserting it fires with the expected properties
- [ ] `regression-gate.sh` exits 0 (or 3 = no catalog yet); FLAKY entries recorded in "## Flaky Tests"
- [ ] If PRD UI mode is 1–3: Design Conformance Gate passed and TEST-REPORT.md contains `## UI Verification` tied to the tested commit SHA, with viewport/state/accessibility evidence and no unapproved deviation
- [ ] Each worktree is clean at the end of this phase: `git status --porcelain` is empty. Any change made during verify (new tests, AC tagging, fixes) MUST be committed on the feature branch — every gate result above must be reproducible from committed state, and untracked tool residue (coverage output, lockfiles from gate attempts) must be removed, or the release merge ships something other than what was verified.

End with the closing report per `tgd-core-rules` → **Command Closing Report**: 📦 產出 (TEST-REPORT.md — real passed/failed + coverage) · 🔎 檢查 (gate as one line) · ➡️ 下一步 `/tgd-review` — 檢查程式碼品質. Don't paste the raw checklist above.
