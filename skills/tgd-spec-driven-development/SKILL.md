---
name: tgd-spec-driven-development
description: Creates specs before coding. Use when starting a new project, feature, or significant change and no specification exists yet. Use when requirements are unclear, ambiguous, or only exist as a vague idea.
---

# Spec-Driven Development

## Overview

Write a structured specification before writing any code. The spec is the shared source of truth between you and the human engineer — it defines what we're building, why, and how we'll know it's done. Code without a spec is guessing.

## When to Use

- Starting a new project or feature
- Requirements are ambiguous or incomplete
- The change touches multiple files or modules
- You're about to make an architectural decision
- The task would take more than 30 minutes to implement

**When NOT to use:** Single-line fixes, typo corrections, or changes where requirements are unambiguous and self-contained.

## The Gated Workflow

Spec-driven development has four phases. Do not advance to the next phase until the current one is validated.

**Step 0: Feature Name Resolution**
Before writing any content, determine the `<feature-name>`:
0. **Existing-feature check first**: scan `$TGD_DIR/` for feature dirs (subdirs with `PRD.md`/`SPEC.md`). If one plausibly matches this ask, offer to revise it in place instead of minting a new name (same rule as `/tgd-define` step 3) — never silently create a duplicate directory for the same feature.
1. **Propose**: Based on the user's request, propose 3 distinct kebab-case `<feature-name>` options with brief descriptions (e.g., "user-auth", "login-system", "access-control").
2. **Wait**: Ask the user to pick one or provide their own. Do NOT proceed until the name is locked.
3. **Create directory**: `mkdir -p $TGD_DIR/<feature-name>/`.
4. **Verify**: If `$TGD_DIR/<feature-name>/` already exists, use it. If not, the previous step must have created it.
5. **Lock**: Use this exact `<feature-name>` for all subsequent files (PRD.md, SPEC.md, TASKS.md, etc.).

**🌿 No git operations in this phase.** PRD/SPEC live in `$TGD_DIR` (outside the code repo) — there is nothing to commit yet. The `feature/<feature-name>` branch is created by `/tgd-develop`'s worktree step (`git worktree add -b`); creating and checking it out here would make that step fail, because git refuses to check out a branch that is already checked out in another worktree.

```
SPECIFY ──→ PLAN ──→ TASKS ──→ IMPLEMENT
   │          │        │          │
   ▼          ▼        ▼          ▼
 Human      Human    Human      Human
 reviews    reviews  reviews    reviews
```

### Phase 1: Specify

Start with a high-level vision. Ask the human clarifying questions until requirements are concrete.

**Surface assumptions immediately.** Before writing any spec content, list what you're assuming:

```
ASSUMPTIONS I'M MAKING:
1. This is a web application (not native mobile)
2. Authentication uses session-based cookies (not JWT)
3. The database is PostgreSQL (based on existing Prisma schema)
4. We're targeting modern browsers only (no IE11)
→ Correct me now or I'll proceed with these.
```

Don't silently fill in ambiguous requirements. The spec's entire purpose is to surface misunderstandings *before* code gets written — assumptions are the most dangerous form of misunderstanding.

**Map existing code first.** If `.codegraph/` exists, run `codegraph context "<feature>" --no-code` to find entry points and related symbols before writing the spec. This prevents speccing features that conflict with existing architecture.

**Map business domain.** Run the `understand-domain` skill to map code structures to business processes — essential for writing a PRD that reflects real-world workflows, not just technical components.

**Write a PRD document covering these product areas:**

1. **Problem** — What is broken? What is the pain point?
2. **Goals & Non-Goals** — What outcomes must we achieve? What is explicitly out of scope?
3. **User Stories** — "As a [user], I want [goal], so that [benefit]."
4. **Success Criteria** — Measurable metrics for completion.

**PRD.md template (save to `$TGD_DIR/<feature-name>/PRD.md`):**

```markdown
# PRD: [Feature Name]

| Metadata       | Details                           |
|----------------|-----------------------------------|
| **Status**     | Draft / Ready for Dev             |
| **Author**     | Product Manager                   |
| **Date**       | YYYY-MM-DD                        |

## 1. Executive Summary
[Why are we doing this? Business value? Expected impact?]

## 2. Problem Statement
- **Current state:** [What is happening now?]
- **Pain point:** [What is the problem?]
- **Impact:** [How does this affect users/business?]

## 3. Goals & Non-Goals
- **Goals:** (outcomes, not features — what changes for the user?)
  - [e.g., "Users can recover access without an email round-trip" — not "Add SMS OTP"]
- **Non-Goals:**
  - [What is explicitly out of scope for this iteration?]
  - [Things we considered but chose not to do — and why]

## 4. Target Audience
- **Primary:** [Who is this for?]
- **Secondary:** [Who else benefits?]
- **User scale:** [Expected MAU/DAU]

## 5. User Stories
| ID | Story | Priority | Acceptance Criteria |
|----|-------|----------|---------------------|
| US-01 | As a [role], I want [goal], so [benefit] | P0 | [Specific criteria] |

## 6. Success Metrics (KPIs)
| Metric | Target | Measurement Method |
|--------|--------|-------------------|
| [Metric 1] | [Target] | [How to measure] |

## 7. Scope
(deliverables, not outcomes — what gets built and when)
- **Phase 1:** [Must haves]
- **Phase 2:** [Nice to haves]
- **Phase 3:** [Future]
- **Out of Scope:** See §3 Non-Goals

## UI Design
- **Mode:** [1 — Existing approved design / 2 — Extend existing product UI / 3 — Explore a new experience / 4 — No user-facing UI]
- **Owner:** [Design role/person, or N/A]
- **Existing system:** [CONTEXT.md path pointers / external approved source / none]
- **Status:** [pending / direction-approved / not-applicable]

## 8. Risks & Mitigations
| Risk | Impact | Mitigation |
|------|--------|------------|
| [Risk] | High/Med/Low | [Strategy] |

## 9. Competitive Analysis (if applicable)
| Feature | Our Product | Competitor A | Competitor B |
|---------|-------------|--------------|--------------|
| [Feature] | ✅/❌/Phase N | ✅/❌ | ✅/❌ |

## 10. Stakeholder Alignment (if applicable)
- **PM:** [Sign-off on scope]
- **Design:** [Sign-off on UX flow]
- **Engineering:** [Sign-off on feasibility]
- **Security:** [Sign-off on security requirements]

## 11. Timeline (if applicable)
| Phase | Duration | Milestone |
|-------|----------|-----------|
| Phase 1 | [X weeks] | [Milestone] |

## Sign-off
- [ ] **PM**: (pending)
```

The `## Sign-off` section is the PM's **final release approval** — `/tgd-release`'s hard gate greps this exact line and blocks until it reads `[x] **PM**: Approved`. It is NOT §10 Stakeholder Alignment (define-time scope alignment); it is the release-time go/no-go, same convention as TEST-REPORT.md (QA) and REVIEW.md (QA + DEV).

Sections 1–8 plus **UI Design** are always required. **9 Competitive Analysis**, **10 Stakeholder Alignment**, and **11 Timeline** are marked *(if applicable)* — a solo or small feature may omit them. `/tgd-define`'s gate (`check-doc-sections.py`) enforces exactly this: the always-required sections must be present, the *(if applicable)* ones are not forced. To make another section optional, mark it *(if applicable)* here — the gate reads this template as its single source, so nothing else needs to change.

**§6 Success Metrics — filling rules (enforced by `/tgd-define`'s gate):**

A metric whose number has no named source is not a metric. Every row's **Measurement Method** must be exactly one of:

1. **A concrete query in an existing tool** — e.g. "GA4 funnel report `sign_up`", "Grafana dashboard `api-latency`, p95 panel". "Check analytics" or "look at usage" is a placeholder, not a source.
2. **A named tracking event that does not exist yet** — write the event name (e.g. `sign_up_completed`). `/tgd-plan` will register it in `$TGD_DIR/TRACKING-PLAN.md` and create an instrumentation task with its own acceptance criteria (see `tgd-planning-and-task-breakdown`).
3. **`N/A — no user-measurable outcome`** — legitimate for refactors, internal tooling, migrations. Requires a named PM sign-off line directly under the table (`Approved N/A — PM, YYYY-MM-DD`). An N/A without sign-off fails the define gate; a fabricated metric ("deploy success rate 100%") is worse than an honest N/A.

At `/tgd-release`, the §6 table becomes `$TGD_DIR/<feature-name>/METRICS.md` — a handoff sheet whose Actual column is filled by whoever owns the data (PM, analyst), on their schedule, in their rituals. tGD's responsibility ends at making that sheet accurate and cheap to fill.

**SPEC.md template (save to `$TGD_DIR/<feature-name>/SPEC.md`):** For backend-only work, write it immediately after PRD approval. For UI modes 1-3, this is the final technical artifact: do not write/finalize it until the Design Routing below has an approved direction. A pre-existing draft may be reconciled in place, but it must not remain stale after DESIGN.md changes the flow, states, components, data needs, or events.

```markdown
# SPEC: [Feature Name]

## Feature Type
- [ ] **Backend** (API / CLI / Service)
- [ ] **Frontend** (UI / Web / Mobile)
- [ ] **Full-stack** (Both)

### UI Requirements (if Frontend or Full-stack)
- **Design Source**: [Figma URL / Screenshot / PDF / None]
- **Pages/Screens**: [List of screens needed]
- **Key Components**: [Component names]
- **Responsive**: [Mobile-first / Desktop-first / Both]

## Tech Stack
[Framework, language, key dependencies with versions]

## Architecture / Data Models
[Data models, endpoints, key algorithms, schema definitions]

## Project Structure
[Directory layout with descriptions]

## API Contract
[Input/Output definitions for key endpoints]

## Testing Strategy
[Framework, test locations, coverage requirements]

## Boundaries
- Always: [...]
- Ask first: [...]
- Never: [...]
```

### Phase 1.5: UI Design Routing (inside DEFINE; not a new lifecycle phase)

After PRD.md and before SPEC.md is finalized, ask via the Selection Protocol:

1. **Existing approved design** — use a versioned Figma frame, screenshot/PDF, or approved design source; **0 variants**.
2. **Extend existing product UI** — ground both alternatives in the current product; **2 variants** (`conservative`, `strong-fit`).
3. **Explore a new experience** — compare materially different UX directions; **3 variants** (`conservative`, `strong-fit`, `divergent`).
4. **No user-facing UI** — no DESIGN.md or prototypes; proceed directly to SPEC.md.

Write the selected Mode, Owner, Existing system, and Status into PRD.md `## UI Design`. Use `pending` initially for modes 1–3 and `not-applicable` for mode 4. The user owns this classification; never silently choose backend-only.

**Source contract for modes 1-3:**

1. Read `$TGD_DIR/CONTEXT.md` as navigation. Open the real design-system, token, global-style, representative-component, responsive, and external-design sources listed under `UI Landscape`. If a frontend exists but this mapping is missing (legacy/stale context), STOP and refresh `/tgd-map` instead of guessing.
2. Read PRD.md for the target user, problem, core action, scope, and success criteria.
3. Apply this exact precedence: **Existing design system > approved DESIGN.md additions > tGD fallback defaults**. Existing brand rules may legitimately use Inter, system fonts, current breakpoints, gradients, or other choices that fallback heuristics would avoid.
4. If an external source is inaccessible or unversioned, request a specific frame export/screenshot and record its path plus revision/date. Do not pretend a fetched page is a stable design specification.

For modes 2-3, run `tgd-sketch`, save the required variants under `$TGD_DIR/<feature-name>/prototype/`, visually verify each one, present the comparison, and let the Design owner select or request a hybrid. Mode 1 skips `tgd-sketch` entirely.

Write DESIGN.md from the approved source/direction, then stop for the Design owner. Its Sign-off remains pending until the role records `[x] **DESIGN**: Direction Approved`; then update PRD `## UI Design` Status to `direction-approved`. Only then write or reconcile SPEC.md against the approved user flow, component mapping, state matrix, responsive behavior, content/copy, API/data needs, events, and test strategy.

**DESIGN.md template (save to `$TGD_DIR/<feature-name>/DESIGN.md`):**
```markdown
# DESIGN: [Feature Name]

## Source & Revision
- **Type:** [Figma / Mockup / Screenshot / PDF]
- **URL/Path:** [stable link or artifact path]
- **Frame/Variant:** [frame/node id or Conservative / Strong-fit / Divergent]
- **Revision/Reviewed:** [source revision, commit, export hash, or YYYY-MM-DD]
- **Context:** [`$TGD_DIR/CONTEXT.md` mapping revision/date]

## Design-System Precedence
**Existing design system > approved DESIGN.md additions > tGD fallback defaults**
- **Component source:** [real path / none]
- **Token source:** [real path / none]
- **Global style / typography source:** [real paths / none]
- **Responsive source:** [real path / none]
- **Fallbacks used:** [none, or list each fallback and why no product source existed]

## Visual Direction
- **Product fit:** [how this continues or intentionally changes the existing product]
- **Vibe:** [specific adjectives grounded in product/user context]
- **Chosen direction:** [why this direction wins]
- **Rejected alternatives:** [what was rejected and the concrete trade-off]

## Primary User & Core Job
- **Primary user:** [specific role/context]
- **Core job:** [single most important action/outcome]
- **Success signal:** [what the user sees/does when the job is complete]

## User Flow
1. [Entry point]
2. [Primary action]
3. [System response]
4. [Success and recoverable failure exits]

## Information Hierarchy
1. [Highest-priority content/action]
2. [Secondary context]
3. [Progressive disclosure / tertiary controls]

## Component Mapping
| UI responsibility | Existing component/pattern | New component | Source path / rationale |
|---|---|---|---|
| [Primary action] | [Button/Form/etc. or none] | [name or none] | [path or reason] |

## Token Changes
| Token | Existing value/source | New value | Why a new/overridden token is necessary |
|---|---|---|---|
| [token or "none"] | [path/value] | [value] | [reason] |

## Responsive
| Product breakpoint / condition | Layout and priority changes | Source / rationale |
|---|---|---|
| [existing breakpoint or content condition] | [behavior] | [path or reason] |

## Interactions
- [Trigger → response → completion/recovery]
- [Keyboard and focus behavior]

## State Matrix
| State | Trigger/data condition | Treatment | User recovery/action |
|---|---|---|---|
| Default | [condition] | [treatment] | [action] |
| Loading | [condition] | [treatment] | [action] |
| Empty | [condition] | [treatment] | [action] |
| Error | [condition] | [treatment] | [action] |
| Success | [condition] | [treatment] | [action] |

## Content & Copy
| Surface | Approved copy / content rule | Localization or length constraint |
|---|---|---|
| [title/CTA/error/empty state] | [real text or rule] | [constraint] |

## Accessibility
- **Keyboard/focus:** [tab order, focus movement, escape behavior]
- **Semantics/name:** [landmarks, headings, accessible names]
- **Contrast/color:** [source tokens and non-color indicators]
- **Motion:** [reduced-motion behavior]

## Allowed Deviations
| Deviation | Reason | Owner approval |
|---|---|---|
| [none or explicit constraint] | [reason] | [pending/approved] |

## Sign-off
- [ ] **DESIGN**: Direction Approved — YYYY-MM-DD — comment
```

### Phase 1.75: Finalize the Technical Specification

For UI modes 1-3, write or reconcile SPEC.md only after DESIGN Direction approval. Explicitly carry over the chosen component mapping, states, responsive behavior, accessibility constraints, data/API needs, events, and testing implications. For mode 4, write SPEC.md immediately after PRD approval. In both cases, SPEC.md is the final DEFINE artifact consumed by `/tgd-plan`.

**Reframe instructions as success criteria.** When receiving vague requirements, translate them into concrete conditions:

```
REQUIREMENT: "Make the dashboard faster"

REFRAMED SUCCESS CRITERIA:
- Dashboard LCP < 2.5s on 4G connection
- Initial data load completes in < 500ms
- No layout shift during load (CLS < 0.1)
→ Are these the right targets?
```

This lets you loop, retry, and problem-solve toward a clear goal rather than guessing what "faster" means.

### Phases 2–4: Plan, Tasks, Implement — owned by later lifecycle stages

This skill's deliverable ends at the validated PRD + SPEC (+ DESIGN if UI). The
remaining phases belong to their own commands and skills — do NOT plan, break
down tasks, or implement from here, and do NOT use ad-hoc task formats:

- **Plan + Tasks** → `/tgd-plan` running `tgd-planning-and-task-breakdown`.
  That skill owns the TASKS.md template — including the `AC-<task>.<n>`
  criterion ids and `[R]`/`Test:` fields that `/tgd-verify`'s `ac-trace.py`
  gate enforces. A task list written from memory here will fail that gate.
- **Implement** → `/tgd-develop` running `tgd-incremental-implementation` or
  `tgd-subagent-driven-development`, with `tgd-test-driven-development` and
  `tgd-context-engineering`.

## Keeping the Spec Alive

The spec is a living document, not a one-time artifact:

- **Update when decisions change** — If you discover the data model needs to change, update the spec first, then implement.
- **Update when scope changes** — Features added or cut should be reflected in the spec.
- **Commit the spec** — The spec belongs in version control alongside the code.
- **Reference the spec in PRs** — Link back to the spec section that each PR implements.

## Common Rationalizations

| Rationalization | Reality |
|---|---|
| "This is simple, I don't need a spec" | Simple tasks don't need *long* specs, but they still need acceptance criteria. A two-line spec is fine. |
| "I'll write the spec after I code it" | That's documentation, not specification. The spec's value is in forcing clarity *before* code. |
| "The spec will slow us down" | A 15-minute spec prevents hours of rework. Waterfall in 15 minutes beats debugging in 15 hours. |
| "Requirements will change anyway" | That's why the spec is a living document. An outdated spec is still better than no spec. |
| "The user knows what they want" | Even clear requests have implicit assumptions. The spec surfaces those assumptions. |

## Red Flags

- Starting to write code without any written requirements
- Asking "should I just start building?" before clarifying what "done" means
- Implementing features not mentioned in any spec or task list
- Making architectural decisions without documenting them
- Skipping the spec because "it's obvious what to build"

## Verification

Before proceeding to implementation, confirm:

- [ ] The spec covers all six core areas
- [ ] The human has reviewed and approved the spec
- [ ] Success criteria are specific and testable
- [ ] Boundaries (Always/Ask First/Never) are defined
- [ ] The spec is saved to `$TGD_DIR/<feature-name>/SPEC.md`
- [ ] No feature branch was created or checked out (that happens in `/tgd-develop`'s worktree step)
- [ ] PRD.md records one UI Design mode and its status
- [ ] If UI mode 1-3: variant count matches the mode (0 / 2 / 3), the Design owner selected a direction, and source revisions are recorded
- [ ] If UI feature: `$TGD_DIR/<feature-name>/DESIGN.md` exists with all required sections
- [ ] If UI feature: DESIGN.md contains `[x] **DESIGN**: Direction Approved` before SPEC finalization or PLAN
- [ ] If UI feature: SPEC.md reflects the approved DESIGN user flow, components, states, responsive behavior, data needs, events, and testing implications
