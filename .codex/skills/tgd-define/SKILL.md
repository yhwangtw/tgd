---
name: tgd-define
description: Start spec-driven development — write a structured specification before writing code
---

## Pre-flight

- [ ] `$TGD_DIR/CONTEXT.md` exists. If missing, STOP: `Project context not mapped. Please run /tgd-map first.`
- Resolve `$TGD_DIR` from its environment variable, then sibling `../<project-name>-tGD/`. **If neither exists: STOP — run `/tgd-map` first.**
- If any `$TGD_DIR/*/METRICS.md` has a blank Actual column, mention the count in one non-blocking line. Do not ask, stop, or fill it.

This is DEFINE: product intent first, approved UI direction when applicable, then the technical contract. Run no code work.

## Pipeline

1. Run `tgd-define-interview` for an underspecified ask and `tgd-define-ideate` for a vague concept.
2. **Existing-feature check (do this BEFORE proposing names).** Scan non-infrastructure subdirectories containing PRD.md or SPEC.md. If the ask plausibly relates to one, use the Selection Protocol to ask whether to update it (default when clearly related) or create a new feature. Updating means revising PRD/SPEC sections in place. **Never silently create a second directory for what is the same feature under a new name.**
3. For a new feature, propose 3 distinct kebab-case `<feature-name>` options that directly reflect the user's intent: literal, action-focused, and domain-specific where applicable. **Wait for the user to select one by number or provide their own before proceeding.** Once locked, create `$TGD_DIR/<feature-name>/`.
4. Run `tgd-define-spec` to write PRD.md from validated product intent.
5. Run UI Design Routing below.
6. Run `tgd-define-spec` again to write/finalize SPEC.md from CONTEXT.md, PRD.md, and approved DESIGN.md when applicable.

### Resume within Define

- PRD.md missing: start at product definition.
- **PRD.md exists and its `## UI Design` status is `pending`, or the required DESIGN.md is missing → resume at UI Design Routing; do not rewrite the approved PRD.**
- DESIGN.md approved but SPEC.md missing/incomplete: resume at SPEC finalization.
- All required artifacts pass: verify only; do not regenerate them.

Always update in place. Do not append duplicate artifact templates.

### Product and repository rules

- PRD §6 Measurement Method must be a concrete existing-tool query, a named tracking event for `/tgd-plan` to register, or `N/A — no user-measurable outcome` with named PM sign-off. Do not fabricate metrics.
- **🌿 No git operations in this phase.** PRD/SPEC live in `$TGD_DIR` (outside the code repo) — there is nothing to commit yet. The `feature/<feature-name>` **branch is created by `/tgd-develop`'s worktree step**, not here.
- If CONTEXT.md lists multiple repos, tag SPEC sections by repo. Preserve this
  existing example:

  ```markdown
  ## Backend (my-project-backend)
  ### API Contracts
  - POST /api/auth/login → ...

  ## Frontend (my-project-frontend)
  ### Components
  - LoginForm.tsx → ...
  ```

  Each section header uses `## <repo-name>` so downstream tasks route to the
  correct repo.

## UI Design Routing

After PRD.md is written and before SPEC.md is finalized, ask which route matches the feature:

1. Existing approved design — use its versioned source; generate **0 variants**.
2. Extend existing product UI — use `tgd-define-sketch`; generate **2 variants**: `conservative/`, `strong-fit/`.
3. Explore a new experience — use `tgd-define-sketch`; generate **3 variants**: those two plus `divergent/`.
4. **No user-facing UI** — omit DESIGN.md/prototypes and finalize SPEC.md.

Do not infer the choice. Record `Mode`, `Owner`, `Existing system`, and `Status` in PRD `## UI Design`; modes 1–3 start `pending`; record `not-applicable` for mode 4.

For modes 1–3, use CONTEXT.md to locate and then read the actual design-system sources. A frontend with missing UI Landscape requires a refreshed `/tgd-map`; do not guess. For mode 1, do not run `tgd-define-sketch`: extract the selected approved source into DESIGN.md and generate no variants. For modes 2–3, give PRD.md and the real sources to `tgd-define-sketch`, which owns direction generation and DESIGN.md authoring. Present variants when they exist.

**DESIGN.md remains pending until its `## Sign-off` contains `[x] **DESIGN**: Direction Approved`; then update PRD `## UI Design` Status to `direction-approved`.**

**Only after direction approval, write/finalize SPEC.md and reconcile its components, API/data contracts, states, events, and testing strategy against DESIGN.md.**

## Verification Gate

After completing the spec, verify the outputs. Resolve `$TGD_REPO_ROOT` per `tgd-core-rules`.

- [ ] `$TGD_DIR/<feature-name>/PRD.md` and SPEC.md exist and are non-empty.
- [ ] `python3 "$TGD_REPO_ROOT/scripts/check-doc-sections.py" PRD "$TGD_DIR/<feature-name>/PRD.md"` exits 0.
- [ ] `python3 "$TGD_REPO_ROOT/scripts/check-doc-sections.py" SPEC "$TGD_DIR/<feature-name>/SPEC.md"` exits 0.
- [ ] PRD §6 has a real source or signed-off N/A; no placeholders.
- [ ] No feature branch was created or checked out.
- [ ] PRD records exactly one UI mode: modes 1–3 are `direction-approved`; mode 4 is `not-applicable` and alone omits DESIGN.md.
- [ ] For modes 1–3, `python3 "$TGD_REPO_ROOT/scripts/check-doc-sections.py" DESIGN "$TGD_DIR/<feature-name>/DESIGN.md"` exits 0 and `[x] **DESIGN**: Direction Approved` is present.
- [ ] Variant count matches the mode; each required variant contains `index.html` and README.md. SPEC references approved DESIGN.md decisions.

End with the closing report per `tgd-core-rules` → **Command Closing Report**: 📦 Output (PRD.md + SPEC.md, and DESIGN.md/prototype if UI) · 🔎 Checks (gate as one line) · ➡️ Next `/tgd-plan` — break the work into tasks. Don't paste the raw checklist above.
