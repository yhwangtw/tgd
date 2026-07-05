# /tgd-review

Review before merge — improve code health

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
- [ ] Test files exist for the feature — use the project's actual test layout from `CONTEXT.md` (`tests/`, `spec/`, `*_test.go`, `__tests__/`, …). Do NOT assume a `tests/` directory.
- [ ] `$TGD_DIR/<feature-name>/TEST-REPORT.md` exists (produced by `/tgd-verify`).
- **If missing:** STOP. Tell user: "Tests are missing. Please run `/tgd-verify` first."

**🌳 Worktree:** If `../project-<feature-name>` exists (created by `/tgd-develop`), review the code inside that worktree — the feature branch is not on `main` yet. Review the diff against `main` (`git diff main...feature/<feature-name>`).

Run the `tgd-code-review-and-quality` skill. This is the REVIEW phase. The full pipeline is:

**Core flow:**
1. `tgd-code-review-and-quality` — five-axis review with severity labels (Critical/Important/Nit/FYI), ~100 lines per change
   - Run `codegraph callers <modified-function>` and `codegraph affected <changed-files>` to verify impact coverage.
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

Improve code health before merge. If the change is larger than ~100 lines, split it into smaller reviews.

After completing the review, create `$TGD_DIR/<feature-name>/REVIEW.md` using this template:
 
```markdown
# REVIEW: [Feature Name]
 
> **Date**: YYYY-MM-DD
 
## 1. Code Review Findings
| # | Severity | File:Line | Issue | Recommendation |
|---|----------|-----------|-------|----------------|
 
Severities: 🔴 Critical (must fix before merge) · 🟠 Important (should fix before merge) · 🟡 Nit (optional) · 🟢 FYI (informational)
 
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
 
## Sign-off
- [ ] **QA**: (pending)
- [ ] **DEV**: (pending)
```
 
If any architectural decisions were made, create `$TGD_DIR/<feature-name>/decisions/ADR-NNN-<decision>.md`:
 
```markdown
# ADR-NNN: [Decision Title]
 
**Date**: YYYY-MM-DD
**Status**: Proposed / Accepted / Superseded
 
## Context
[Why is this decision needed? What constraints exist?]
 
## Decision
[What was decided? Be specific.]
 
## Consequences
- **Positive**: [benefits]
- **Negative**: [trade-offs]
- **Risks**: [what to watch for]
```

**Verification Gate:**
- [ ] Code review feedback addressed
- [ ] No critical security or performance warnings remain
- [ ] `$TGD_DIR/<feature-name>/REVIEW.md` exists and is non-empty

If verification passes, suggest the next step: `/tgd-release` to deploy.
