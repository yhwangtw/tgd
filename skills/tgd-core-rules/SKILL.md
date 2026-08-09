---
name: tgd-core-rules
description: Core tGD rules that MUST be followed at all times — lifecycle order, the Verification Iron Law, selection protocol, per-phase tone, the Command Closing Report, and human sign-off. Load this at the start of every tGD action and whenever a command references it.
---

# tGD Core Rules

## Overview

This skill is the unique owner of rules that apply across every tGD phase.
Exact phase pipelines belong to `.claude/commands/tgd-*.md`; artifact schemas
and scope belong to `templates/manifest.yaml` and its indexed templates.

## When to Use

- Before any tGD action, including a lifecycle command or routed skill.
- Before a completion claim, phase transition, or human sign-off decision.

## Resolving `$TGD_REPO_ROOT`

Gate scripts live under `$TGD_REPO_ROOT/scripts/`, not in the artifact-only
`$TGD_DIR`. Resolve the repo root once, in this order:

1. `$TGD_REPO_ROOT`, when set.
2. `~/tGD`, the default clone location.
3. The real path of an installed tGD skill symlink. Strip the trailing skill
   path (for example `/skills/tgd-core-rules`, or `/skills` when a platform
   links the whole tGD skill directory).

The resolved directory MUST contain `scripts/generate-mirrors.py`. If no
candidate does, STOP, report that the tGD clone cannot be located, and do not
skip or substitute any gate script.

## Global Operating Invariants

- **Execute applicable skills.** Before any work, check whether a skill
  applies. A matching skill is a required workflow: load it, satisfy its
  prerequisites, and follow its steps in order before implementation.
- **Surface non-obvious assumptions.** State assumptions that affect
  requirements, architecture, or scope before acting; do not silently turn
  uncertainty into fact.
- **Resolve conflicts.** When sources disagree or a requirement is ambiguous,
  STOP the work, name the conflict, present the tradeoff or question, and wait
  for resolution before continuing.
- **Push back with evidence.** Identify a concrete downside, propose an
  alternative, and accept the human's informed decision.
- **Prefer simplicity.** Use the smallest clear solution whose abstractions earn
  their cost.
- **Protect scope.** Do not clean up, refactor, delete, or add adjacent work
  without authorization; preserve changes that are outside the current task.
- **Preserve required work when delegation is unavailable.** Inability to
  delegate changes where work runs, never whether it runs; execute mandatory
  implementation or review steps inline.

## Lifecycle Order

Run the seven phases in order and do not skip a phase:

1. `/tgd-map`
2. `/tgd-define`
3. `/tgd-plan`
4. `/tgd-develop`
5. `/tgd-verify`
6. `/tgd-review`
7. `/tgd-release`

Role handoffs resume the same Define phase; they do not create another phase.
Use the canonical `.claude/commands/tgd-*.md` files for exact pipelines,
pre-flight checks, gates, and transitions. Use `templates/manifest.yaml` for
artifact locations, applicability, schemas, and templates.

## Completion Evidence Gate — Verification Iron Law

**NO COMPLETION CLAIMS WITHOUT FRESH VERIFICATION EVIDENCE.**

Before claiming work is complete, fixed, passing, or ready:

1. **IDENTIFY** the command or direct observation that proves the exact claim.
2. **RUN** the full verification fresh in the current message or turn and
   against the current state being claimed; do not extrapolate from a previous
   turn or partial run. If the relevant `HEAD`, worktree, artifact, runtime, or
   external state changes afterward, the evidence is stale and must be rerun
   before the claim.
3. **READ** the complete result, including exit code and failure count.
4. **MATCH** the evidence to the claim and every relevant requirement. Passing
   one narrower check does not prove a broader claim.
5. **REPORT** the actual status. Include sufficient, concise evidence with
   secrets and sensitive values redacted; if proof fails or is incomplete,
   report the failure or unknown instead of success.

Never treat an agent's success report as proof. Independently inspect its diff,
artifacts, and applicable verification output before relying on it.

## Selection Protocol

When the user must choose (for example a feature name, design direction, or UI
mode), provide a numbered or lettered list and ask for the number or letter.
Do not require an open-ended answer; allow a typed alternative when appropriate.
Canonical skill and command sources stay in English. Render every user-facing
prompt, choice, label, and quoted example in the user's language; English
templates express structure and intent only.

## Tone Guide (Phase-Specific)

| Phase | Tone | Behavior |
|---|---|---|
| MAP | Technical Analyst | Precise, objective, evidence-driven |
| DEFINE | Guided Explorer | One decision at a time, option-based, no hidden assumptions |
| PLAN | Structured List-maker | Bounded tasks and verifiable criteria |
| DEVELOP | Minimal Implementer | Code-first, concise progress |
| VERIFY | Strict Zero-Tolerance | Evidence only; state failures without hedging |
| REVIEW | Critical Constructive | Pair each problem with a concrete remedy |
| RELEASE | Cautious Process | Surface gates, risk, monitoring, and rollback state |

VERIFY tone overrides the others. When the phase is unclear, default to the
concise DEVELOP tone.

## Command Closing Report

End each lifecycle command with a short three-part report, never the raw gate
checklist:

- **📦 Output** — actual artifacts or changes, summarized with verified counts
  or status; never invent evidence.
- **🔎 Checks** — one line: all passed, or the number failed followed only by
  concrete failed checks.
- **➡️ Next** — the next command and why, only after a successful run. On
  failure, omit this part and make the heading identify the failed command.

Keep the emoji and three-part success structure fixed. Render `Output`,
`Checks`, `Next`, `all passed`, and `failed` in the user's language.

## Human Roles & Sign-off Protocol

tGD has four human roles; one person may hold more than one:

| Role | Focus | Primary touchpoints |
|---|---|---|
| **PM** | Product direction and acceptance | Define PRD; final Release sign-off |
| **DESIGN** | Experience direction and implementation conformance | Define DESIGN/prototype; Review UI evidence |
| **DEV** | Implementation quality | Plan, Develop, Review |
| **QA** | Test quality and coverage | Verify, Review |

Each role modifies only its own line in an artifact's `## Sign-off` section:

- Approve: `- [x] **PM**: Approved — YYYY-MM-DD — comment`
- Reject: `- [x] **PM**: Rejected — YYYY-MM-DD — reason`

The `[x] **ROLE**: Approved` form is reserved for `## Sign-off`; approvals
elsewhere must use different wording so release checks remain unambiguous.
Agents must verify the required role lines before proceeding. UI work requires
`[x] **DESIGN**: Direction Approved` in `DESIGN.md` before Plan and
`[x] **DESIGN**: Implementation Approved` in `REVIEW.md` after conformance
review; non-UI work requires neither. Release is a hard gate: every required
sign-off must be checked and approved.

Human review is asynchronous. For UI work, role handoffs resume the same Define phase
after direction approval; later Release waits for the remaining sign-offs.

## Orchestration Invariant

Commands orchestrate when, skills define how, and personas supply perspective; personas do not invoke personas, and multi-persona work uses parallel fan-out plus a merge step. See `agents/README.md` and `references/orchestration-patterns.md`.

## Common Rationalizations

No urgency, confidence, previous result, small scope, or missing delegation
capability overrides the lifecycle, evidence, scope, or inline-fallback rules
above.

## Red Flags

Stop and return to the owning section when a claim lacks matching evidence, a
dependent conflict remains unresolved, work crosses scope, a required phase is
skipped, or delegated output has not been checked independently.

## Verification

- [ ] `$TGD_REPO_ROOT` and any invoked gate scripts were resolved fail-closed.
- [ ] The canonical command and manifest/template, rather than a duplicate
      summary, governed the active phase and artifacts.
- [ ] The completion evidence sequence was applied to each status claim.
- [ ] Required phase order, selection, closing report, and sign-offs were
      applied where relevant.
