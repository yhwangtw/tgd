---
name: tgd-review-adr
description: Records decisions and documentation. Use when making architectural decisions, changing public APIs, shipping features, or when you need to record context that future engineers and agents will need to understand the codebase.
---

# Documentation and ADRs

## Overview

Document decisions, not merely code. Code shows what; durable documentation captures why, constraints, trade-offs, and rejected alternatives for future humans and agents.

## When to Use

- Making a significant architectural decision or choosing among competing approaches
- Adding or changing a public API or user-facing behavior
- Choosing a framework, major dependency, data model, auth strategy, API architecture, build tool, host, or infrastructure
- Recording any decision expensive to reverse
- Onboarding or repeatedly explaining the same project context

Do not document obvious code, restate implementation, or write durable docs for throwaway prototypes.

## ADR Workflow

### Step 0: Validate Feature and Path

1. Derive `<feature-name>` in kebab-case.
2. Verify `$TGD_DIR/<feature-name>/SPEC.md` exists.
3. Write feature-scoped ADRs under `$TGD_DIR/<feature-name>/decisions/`. Cross-feature decisions go under `$TGD_DIR/shared/decisions/`.

### Step 1: Create the Record

Use sequential `ADR-NNN-<decision>.md` naming and the canonical template at `$TGD_REPO_ROOT/templates/ADR.md.tmpl`. Do not hand-roll another shape. Capture context, decision, alternatives, trade-offs, and consequences.

### Step 2: Maintain Lifecycle

`PROPOSED → ACCEPTED → (SUPERSEDED or DEPRECATED)`

Never delete an old ADR. When a decision changes, write a new record that references and supersedes the old one.

## Documentation Rules

- **Inline comments:** Explain non-obvious why, ordering, constraints, or gotchas. Do not restate code, leave commented-out code, or leave a TODO for work that should be done now.
- **Public APIs:** Document parameters, return values, errors, and a useful example. Prefer typed inline documentation for TypeScript and an API schema such as OpenAPI for REST.
- **README:** Cover project purpose, quick start, commands, architecture, and contribution guidance; link to ADRs for rationale.
- **Changelog:** Record shipped user-visible changes. The tGD lifecycle's `$TGD_DIR/CHANGELOG.md` uses CalVer (`vYYYY.MM.DD`, with `.2`, `.3` micro bumps for same-day releases) as specified by `/tgd-release`; do not substitute the SemVer shown in general examples.
- **Agent context:** Keep rules files, specs, ADRs, and inline gotchas current so agents do not repeat old decisions or traps.

Illustrative inline-comment, API/OpenAPI, README, and changelog examples are in [`../../references/review-patterns.md`](../../references/review-patterns.md). They are examples only; the requirements above and canonical ADR template remain authoritative.

## Common Rationalizations

| Rationalization | Reality |
|---|---|
| "The code is self-documenting" | Code cannot preserve rejected alternatives and constraints. |
| "We'll write docs when the API stabilizes" | Documentation exposes design problems and helps an API stabilize. |
| "Nobody reads docs" | Future engineers, agents, and your future self do. |
| "ADRs are overhead" | A short record prevents repeated, context-free debate. |
| "Comments get outdated" | Why-comments are more durable; what-comments are why we avoid restatement. |

## Red Flags

- Significant architectural decisions have no rationale
- Public APIs lack types or documentation
- README cannot get a newcomer running or explain architecture
- Commented-out code remains instead of relying on history
- Stale TODOs accumulate
- Documentation restates code rather than intent
- Existing ADR history is deleted or silently rewritten

## Verification

- [ ] Every significant architectural decision has an ADR in the validated canonical path
- [ ] ADR uses the canonical template and lifecycle; superseded records are retained and linked
- [ ] README covers quick start, commands, and architecture
- [ ] Public APIs document parameters, return types, errors, and examples
- [ ] Non-obvious gotchas are documented where they matter
- [ ] No commented-out code remains
- [ ] Rules files, specs, and agent context are current and accurate
