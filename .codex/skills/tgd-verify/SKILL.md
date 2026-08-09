---
name: tgd-verify
description: Verify — prove it works with debugging and test pyramid
---

## Pre-flight

- [ ] Resolve `$TGD_DIR` from its environment variable, then sibling `../<project-name>-tGD/`; require CONTEXT.md or STOP and run `/tgd-map`.
- [ ] Select `<feature-name>` from non-infrastructure subdirectories containing PRD.md or SPEC.md. None means STOP and run `/tgd-define`; multiple means ask. Require SPEC.md.
- [ ] Each repo with tagged tasks has a non-empty `git diff main...feature/<feature-name> --stat` and feature tests in the actual layout recorded by CONTEXT.md.
- [ ] Every completed TASKS.md task has `Spec-Review:` and `Quality-Review:` at `PASS — …`; **a pending review field means `/tgd-develop` skipped its two-stage review. 🛑 STOP: send it back to `/tgd-develop`; do not verify unreviewed work.**
- [ ] When PRD UI mode is 1–3, it is direction-approved, DESIGN.md exists, and `awk '/^## Sign-off/,0' "$TGD_DIR/<feature-name>/DESIGN.md" | grep -qF '[x] **DESIGN**: Direction Approved'` succeeds. Mode 4 is classified not-applicable.

Missing source/tests returns to `/tgd-develop`; missing UI classification/direction returns to `/tgd-define`.

Run all gates inside `../project-<feature-name>` or, for multi-repo work, each `../project-<feature-name>-<repo-name>`; **verifying only one repo is a partial verify**, not a pass.

## Verification pipeline

1. Run `tgd-verify-debug` to reproduce, localize, reduce, fix, and guard.
2. Run `tgd-develop-tdd` across the test pyramid. If CodeGraph is available, use affected-path analysis to prioritize; otherwise run the full relevant suite.
3. **Frontend/UI/DOM?** → **MUST run `tgd-verify-browser`**. Unit tests are NOT sufficient for UI verification. Missing browser execution fails the phase.

Resolve `$TGD_REPO_ROOT` per `tgd-core-rules`; gate scripts live in its `scripts/`, not in `$TGD_DIR`.

### Test evidence

From each feature worktree run:

```bash
bash "$TGD_REPO_ROOT/scripts/capture-test-output.sh" "$TGD_DIR/<feature-name>/TEST-REPORT.md"
# Multi-repo, once per worktree with a stable evidence label:
bash "$TGD_REPO_ROOT/scripts/capture-test-output.sh" "$TGD_DIR/<feature-name>/TEST-REPORT.md" "" "<repo-name>"
```

The script owns suite detection, report skeleton creation from `$TGD_REPO_ROOT/templates/TEST-REPORT.md.tmpl`, raw-output sections, and meta-comment format. Fill summary counts only from its emitted meta-comment.

- **Exit 0** = tests passed, raw output captured. Use the real numbers from the meta-comment in the Summary table below — do NOT invent counts.
- **Exit 1** = tests failed, raw output still captured. Fix the failures, re-run, only then proceed.

### Coverage

```bash
bash "$TGD_REPO_ROOT/scripts/coverage-check.sh"
```

Exit 0 passes; exit 1 fails. **Exit 2 = no coverage tool installed or output unparseable — a configuration problem: install the tool it names (e.g. `npm i -D @vitest/coverage-v8`, `pip install pytest-cov`, `cargo install cargo-tarpaulin`), then re-run. NEVER treat exit 2 as a pass.** Default lines/branches/functions floors are 80/60/90; document environment overrides in `## Coverage Exceptions` with a ramp-up plan.

### AC Traceability Gate (MANDATORY)

Line coverage is not requirement coverage — verify every acceptance criterion has a test:

```bash
python3 "$TGD_REPO_ROOT/scripts/ac-trace.py" "$TGD_DIR/<feature-name>/" .
```

- Exit 0: all AC ids are traced and `[R]` Test files exist.
- Exit 1: untraced criteria or `[R]` entries without valid `Test:` files; add/tag tests and re-run.
- **Exit 2** = TASKS.md missing or carries no AC ids. A plan without AC ids fails closed — fix TASKS.md (see `tgd-plan-breakdown`).

If TRACKING-PLAN.md contains this feature, plain-search each event owned by the current platform and require a test that asserts emission plus expected payload keys.

### Regression gate

Run once per worktree, adding its repo label for multi-repo features:

```bash
bash "$TGD_REPO_ROOT/scripts/regression-gate.sh" ../project-<feature-name> "$TGD_DIR"
# Multi-repo, once per worktree with the repo label as the third argument:
bash "$TGD_REPO_ROOT/scripts/regression-gate.sh" ../project-<feature-name>-<repo-name> "$TGD_DIR" <repo-name>
```

The script owns per-entry runner selection and one retry. Exit 0 passes; exit 2 is a configuration failure. Exit 3 is legitimate only when no catalog exists before the first release. Record pass-on-retry entries under TEST-REPORT `## Flaky Tests`.

**Exit 1** = an entry failed twice, is stale, or lacks a `Test:` reference. 🛑 STOP. Do NOT proceed to review. Report which prior feature's regression broke.

### Design Conformance Gate

For PRD UI modes 1–3:

1. Commit the inspected implementation and record its SHA. Any Verify code change requires commit plus re-running affected gates.
2. Compare the implementation with approved DESIGN.md and the real design-system sources for flow, hierarchy, components, tokens, states, copy, accessibility, responsiveness, and allowed deviations.
3. Use `tgd-verify-browser` at every named viewport and applicable loading, empty, error, success, and disabled state; verify keyboard/focus and critical screen-reader semantics.
4. Store reproducible evidence under `$TGD_DIR/<feature-name>/evidence/ui/` or stable CI URLs. **Evidence MUST identify the tested commit SHA and viewport/state; a statement such as "looks correct" is not evidence.**
5. Write TEST-REPORT `## UI Verification` with SHA, source revision, coverage, evidence, deviations, and Pass/Fail.
6. An unapproved deviation fails: fix it or return for explicit direction approval; **do not silently rewrite DESIGN.md during Verify**.

## Verification Gate

- [ ] Tests pass; capture ran; report counts equal its meta-comment.
- [ ] Coverage and AC trace gates exit 0; any documented exception is valid.
- [ ] Applicable tracking-event payload assertions pass.
- [ ] `regression-gate.sh` exits 0 (or 3 before the first catalog); flaky entries are recorded.
- [ ] UI modes 1–3 have SHA-bound viewport/state/accessibility evidence with no unapproved deviation.
- [ ] **Each worktree is clean at the end of this phase: `git status --porcelain` is empty. Any change made during verify (new tests, AC tagging, fixes) MUST be committed on the feature branch — every gate result above must be reproducible from committed state, and untracked tool residue (coverage output, lockfiles from gate attempts) must be removed, or the release merge ships something other than what was verified.**

End with the closing report per `tgd-core-rules` → **Command Closing Report**: 📦 產出 (TEST-REPORT.md — real passed/failed + coverage) · 🔎 檢查 (gate as one line) · ➡️ 下一步 `/tgd-review` — 檢查程式碼品質. Don't paste the raw checklist above.
