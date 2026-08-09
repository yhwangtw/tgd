---
name: tgd-review-quality
description: Conducts multi-axis code review. Use before merging any change. Use when reviewing code written by yourself, another agent, or a human. Use when you need to assess code quality across multiple dimensions before it enters the main branch.
---

# Code Review and Quality

## Overview

Every change gets reviewed before merge — no exceptions. Approve when the change definitely improves overall code health, even if it is not perfect. Do not block merely because you would have written it differently; require project conventions and a net improvement.

## When to Use

- Before merging any PR or change
- After a feature, refactor, or bug fix; review both a bug fix and its regression test
- When another agent, model, or human produced code you need to evaluate

## The Five-Axis Review

Every review evaluates all five axes:

1. **Correctness:** Match the spec; handle null, empty, boundaries, errors, races, and state consistency. Confirm tests exercise the intended behavior and would catch regression.
2. **Readability and simplicity:** Use clear names and control flow, logical organization, useful non-obvious comments, and no clever or dead artifacts. Ask whether the same result needs fewer lines and whether each abstraction earns its complexity; do not generalize before the third use case.
3. **Architecture:** Follow justified system patterns, clean module boundaries, correct dependency direction, appropriate abstraction, and no avoidable duplication or circular dependencies.
4. **Security:** Treat external data as untrusted; validate it at boundaries. Check secrets, authn/authz, parameterized queries, output encoding, trusted dependencies, and external data flows. Use `tgd-review-security` for detailed guidance.
5. **Performance:** Check N+1 queries, unbounded work or fetching, blocking operations, unnecessary UI renders, missing pagination, and large hot-path allocations. Use `tgd-review-performance` for detailed guidance.

## Change Boundaries

Target about 100 changed lines; about 300 is acceptable for one logical change; about 1000 is too large and must be split. One change is self-contained, addresses one thing, includes related tests, and leaves the system functional. Complete deletions and automated refactors may be large when intent, rather than every line, is what must be verified.

Split by dependency stack, file group, horizontal layer, or vertical feature slice as appropriate. Keep refactoring separate from new behavior; small cleanups are allowed at reviewer discretion.

Every change description must stand alone in history:

- First line: short, imperative, and specific.
- Body: explain what and why, including context, decisions, non-obvious trade-offs, shortcomings, and relevant issue, benchmark, or design-doc links.
- Reject empty descriptions such as "Fix bug", "Fix build", "Add patch", "Moving code", "Phase 1", or "Add convenience functions".

Illustrative splitting strategies and copyable review templates are in [`../../references/review-patterns.md`](../../references/review-patterns.md). They are examples only; this skill owns the policy.

## Review Process

### Step 1: Understand Context and Impact

Establish the change's intent, governing spec/task, and expected behavior. If `.codegraph/` exists, run `codegraph callers "<modified-function>"` and `codegraph affected <changed-files>` to verify dependent code and tests. For large or unfamiliar changes, run `understand-diff` before approval.

### Step 2: Review Tests First

Confirm tests exist, express behavior rather than implementation details, cover edges, use descriptive names, and would fail on regression.

### Step 3: Review Implementation

Walk every changed file against all five axes. Do not replace this with a test-only review.

### Step 4: Categorize Every Finding

This is the single review-phase severity taxonomy used by REVIEW.md, the code-reviewer persona, and this skill:

| Prefix | Meaning | Required action |
|---|---|---|
| **Critical:** | Blocks merge: security vulnerability, data loss, or broken functionality | Must fix before merge |
| **Important:** | Should fix before merge: missing test, wrong abstraction, poor error handling | Fix, or explicitly justify deferral |
| **Nit:** | Minor and optional | May ignore |
| **FYI:** | Information only | No action |

### Step 5: Verify the Verification

Require the author to state which tests and build ran, any manual checks, relevant UI screenshots, and before/after evidence.

## Independent Review and Disagreements

Use a different model or reviewer from the author when available; different reviewers expose different blind spots. A human makes the final call.

Resolve disagreements in this order:

1. Technical facts and data
2. Style guides for style questions
3. Engineering principles for design
4. Codebase consistency when it does not degrade health

Do not accept "I'll clean it up later." Require cleanup before submission unless there is a genuine emergency. When surrounding work is out of scope, require a tracked bug with self-assignment. Comment on code, not people; accept an informed owner override gracefully.

## Review Speed

Respond within one business day at most, and normally shortly after the request so a typical change can complete multiple rounds in one day. Prefer fast individual responses over delaying all feedback for a single final verdict. Ask authors to split oversized changes rather than letting an unreviewable diff block the team.

## Honesty, Dead Code, and Dependencies

- Do not rubber-stamp or soften real defects. Quantify impact when possible, push back on flawed approaches, and provide alternatives.
- After refactoring or implementation, identify unreachable or unused code and list it explicitly. **Ask before deleting** anything whose removal was not already authorized.
- Before adding a dependency, ask whether the existing stack solves the need; check size, maintenance, vulnerabilities, and license. Prefer the standard library and existing utilities.

## Embedded Tech Debt Filing

For known issues intentionally not fixed in this cycle:

- **Always** record them in `$TGD_DIR/<feature-name>/DEBT.md`.
- If `JIRA_URL`, `JIRA_PROJECT`, and `JIRA_TOKEN` are configured, also create the Jira issue and record its key. Do not ask for credentials or stall when Jira is not configured.
- Blockers remain request-changes findings and must not be converted into debt. Fix non-blockers now when they belong in this cycle; otherwise file architecture, performance, or code-quality debt as an `Improvement` with `tech-debt`, low-risk security hardening with `security-hardening`, and test-coverage debt as an `Improvement` with `test-coverage`.
- Add a `TECH-DEBT` comment beside the related completed item in `TASKS.md` and include category, priority, current state, desired state, impact, suggested approach, and acceptance criteria in the debt record or linked Jira issue.

The decision flow, ticket body, and DEBT.md examples in [`../../references/review-patterns.md`](../../references/review-patterns.md) are illustrative and copyable; the rules above remain authoritative.

## Common Rationalizations

| Rationalization | Reality |
|---|---|
| "It works, that's good enough" | Unreadable, insecure, or architecturally wrong code compounds debt. |
| "I wrote it, so I know it's correct" | Authors are blind to their own assumptions. |
| "We'll clean it up later" | Review is the quality gate; require cleanup or explicit tracked deferral now. |
| "AI-generated code is probably fine" | Plausible, confident output needs more scrutiny, not less. |
| "The tests pass, so it's good" | Tests do not prove architecture, security, performance, or readability. |

## Red Flags

- Merge without review, or "LGTM" without evidence
- Reviewing only test status rather than all five axes
- Security-sensitive changes without a focused review
- A change too large to review properly instead of being split
- Bug fixes without regression tests
- Findings without severity labels
- Accepting an untracked promise to fix something later

## Verification

- [ ] All five axes were reviewed against the spec and actual diff
- [ ] Every finding has the canonical severity label
- [ ] All Critical findings are resolved
- [ ] All Important findings are resolved or explicitly deferred with justification and tracking
- [ ] Tests and build pass
- [ ] Verification evidence documents what changed and how it was checked
