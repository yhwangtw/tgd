---
name: tgd-review
description: Review before merge — improve code health
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
- [ ] Test files exist for the feature — use the project's actual test layout from `CONTEXT.md` (`tests/`, `spec/`, `*_test.go`, `__tests__/`, …). Do NOT assume a `tests/` directory.
- [ ] `$TGD_DIR/<feature-name>/TEST-REPORT.md` exists (produced by `/tgd-verify`).
- [ ] Read PRD `## UI Design`. For modes 1–3, DESIGN.md exists and TEST-REPORT.md contains `## UI Verification`, evidence tied to the reviewed commit SHA, and `Status: Pass`. A missing required DESIGN.md fails closed.
- **If missing:** STOP. Report the specific missing artifact: test evidence returns to `/tgd-verify`; UI classification or direction returns to `/tgd-define`.

**🌳 Worktree:** If `../project-<feature-name>` exists (created by `/tgd-develop`), review the code inside that worktree — the feature branch is not on `main` yet. Review the diff against `main` (`git diff main...feature/<feature-name>`). Multi-repo features (TASKS.md has `[repo-name]` prefixes) have one worktree PER repo (`../project-<feature-name>-<repo-name>`) — review EACH repo's diff; a repo with tagged tasks but an unreviewed diff fails the gate.

Run the `tgd-code-review-and-quality` skill. This is the REVIEW phase. The full pipeline is:

**Core flow:**
1. `tgd-code-review-and-quality` — five-axis review with severity labels (Critical/Important/Nit/FYI), ~100 lines per change
   - **If `codegraph` is available** (the `/tgd-map` Step 0.5 probe): run `codegraph callers <modified-function>` and `codegraph affected <changed-files>` to verify impact coverage. If not installed, skip — trace callers with plain search instead; this enrichment is Tier 2, its absence is not a failure.
2. `tgd-code-simplification` — apply Chesterton's Fence, reduce complexity while preserving exact behavior

**🎭 Persona Fan-Out (MANDATORY for high-stakes features, optional otherwise)**

When the feature has any critical-path `[R]` criterion (auth, payment, data loss, security boundary), touches security-sensitive code, or the diff exceeds ~300 lines: dispatch the three review personas **in parallel** as fresh-context subagents, then merge their reports —

```
fan out ──┬─→ agents/code-reviewer.md    (five-axis review)      ─┐
          ├─→ agents/security-auditor.md (vulnerability audit)    ├─→ merge into REVIEW.md
          └─→ agents/test-engineer.md    (coverage gap analysis) ─┘   sections 1–3
```

Give each persona the diff + spec, NOT your conclusions. This is the only multi-persona pattern the repo endorses (parallel fan-out with merge — see `references/orchestration-patterns.md`); personas never invoke each other. For low-stakes features, the main-session five-axis review in step 1 suffices.

**Conditional (apply when relevant):**
- Security concerns? → `tgd-security-and-hardening`
- Performance concerns? → `tgd-performance-optimization`
- Reviewing large or unfamiliar changes? → the `understand-diff` skill to visualize the full blast radius.
- PRD UI mode is 1–3? → compare the implementation and TEST-REPORT evidence with the approved direction. The designer reviews conformance here; this does not add a lifecycle phase.

Improve code health before merge. If the change is larger than ~100 lines, split it into smaller reviews.

After completing the review, create `$TGD_DIR/<feature-name>/REVIEW.md` using this template:
 
```markdown
# REVIEW: [Feature Name]
 
> **Date**: YYYY-MM-DD
 
## 1. Code Review Findings
| # | Severity | File:Line | Issue | Recommendation | Resolution |
|---|----------|-----------|-------|----------------|------------|
 
Severities: 🔴 Critical (must fix before merge) · 🟠 Important (should fix before merge) · 🟡 Nit (optional) · 🟢 FYI (informational)
Resolution: `fixed` / `deferred — <justification>` / `open`. Every 🔴 row MUST read `fixed` before Sign-off; 🟠 may be `deferred` only with the justification written in the cell. `/tgd-release` reads this column — a row without it is indistinguishable from an unfixed finding.
 
## 2. Security Scan
- **Tool**: [tool or "manual review"]
- **Findings**: [results or "clean"]
- **Status**: ✅ Pass / ⚠️ Warnings / 🛑 Fail
 
## 3. Performance Analysis
- **Concerns**: [none / list]
- **Status**: ✅ Pass / ⚠️ Warnings
 
## 4. Simplification
- **Applied**: [list or "none needed"]
- **Lines reduced**: [N]

## Design Conformance (if UI)
- **Approved source**: [DESIGN.md revision / external design revision]
- **Verified commit**: [SHA from TEST-REPORT.md]
- **Evidence**: [paths under evidence/ui/ or stable CI artifact URLs]
- **Deviations**: [none / list, each matched to DESIGN.md Allowed Deviations]
- **Status**: ✅ Pass / 🛑 Fail
 
## Sign-off
- [ ] **QA**: (pending)
- [ ] **DEV**: (pending)
- [ ] **DESIGN**: (pending — UI only; approve as `Implementation Approved` after reviewing the evidence and built UI)
```
 
**🔁 Re-test after review changes:** if ANY code changed during this phase (finding fixes or simplification), **commit the changes on the feature branch first**, then re-run the capture in the affected worktree BEFORE sign-off — `bash "$TGD_REPO_ROOT/scripts/capture-test-output.sh" "$TGD_DIR/<feature-name>/TEST-REPORT.md"` (multi-repo: repo name as the 3rd arg). If UI-affecting code changed, also re-run `/tgd-verify`'s Design Conformance Gate and replace `## UI Verification` evidence with the new commit SHA. The TEST-REPORT green light was taken against the pre-review code; a sign-off on top of stale evidence certifies code that was never tested. A review fix left uncommitted is invisible to the release merge, while evidence captured before the commit cannot identify the state it certifies.

If any architectural decisions were made, create an ADR at `$TGD_DIR/<feature-name>/decisions/ADR-NNN-<decision>.md` using the **canonical ADR template in the `tgd-documentation-and-adrs` skill** — it is the single source; do not hand-roll a different shape. Its sections are **Status · Date · Context · Decision · Alternatives Considered · Consequences**. The **Alternatives Considered** section is mandatory: an ADR that doesn't record the rejected options and why isn't an ADR, it's just a note.

**Verification Gate:**
- [ ] Code review feedback addressed — every 🔴 Critical row in the findings table reads `fixed`; 🟠 deferred rows carry a justification
- [ ] No critical security or performance warnings remain
- [ ] If code changed during review: `capture-test-output.sh` re-ran in the affected worktree(s) — TEST-REPORT.md reflects the code that ships
- [ ] Each worktree is clean at the end of this phase: `git status --porcelain` is empty — review changes are committed on the feature branch (the sign-offs certify committed state, nothing else survives the merge)
- [ ] `$TGD_DIR/<feature-name>/REVIEW.md` exists and is non-empty
- [ ] `python3 "$TGD_REPO_ROOT/scripts/check-doc-sections.py" REVIEW "$TGD_DIR/<feature-name>/REVIEW.md"` exits 0 — all required REVIEW sections present (missing ones are listed). Resolve `$TGD_REPO_ROOT` per `tgd-rules` → **Resolving $TGD_REPO_ROOT**.
- [ ] If PRD UI mode is 1–3: `## Design Conformance (if UI)` is `✅ Pass`, evidence matches the reviewed commit, and Sign-off contains `[x] **DESIGN**: Implementation Approved`

End with the closing report per `tgd-rules` → **Command Closing Report**: 📦 產出 (REVIEW.md — 各軸 Pass/Warn/Fail 摘要；ADR 若有) · 🔎 檢查 (gate as one line) · ➡️ 下一步 `/tgd-release` — 部署. Don't paste the raw checklist above.
