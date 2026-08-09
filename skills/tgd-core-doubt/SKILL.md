---
name: tgd-core-doubt
description: Subjects every non-trivial decision to a fresh-context adversarial review before it stands. Use when correctness matters more than speed, when working in unfamiliar code, when stakes are high (production, security-sensitive logic, irreversible operations), or any time a confident output would be cheaper to verify now than to debug later.
---

# Doubt-Driven Development

## Overview

Materialize a fresh-context reviewer, biased to disprove rather than approve,
before a non-trivial output stands. This is an in-flight reasoning check;
`/review` remains the verdict on a finished artifact.

## When to Use

A decision is non-trivial when at least one of these is true:

- It introduces or changes branching logic.
- It crosses a module or service boundary.
- It asserts an invariant the type system or compiler cannot verify, such as
  thread safety, idempotence, or ordering.
- Its correctness depends on context a future reader cannot see.
- Its blast radius is irreversible, such as a production deployment, data
  migration, or public API change.

Use the skill for architecture under uncertainty, non-trivial code before it is
committed, non-obvious correctness claims, and unfamiliar code.

Do **not** use it for mechanical edits, clear user instructions, reading or
summarizing code, one-line changes with obvious correctness, pure tooling
operations, or when the user explicitly prefers speed over verification.

## Loading Constraints

This skill belongs in the main-session orchestrator because DOUBT requires a
fresh-context reviewer.

- Do not add it to a persona's `skills:` frontmatter; personas do not invoke
  other personas.
- Inside a subagent that cannot spawn a reviewer, surface that limitation and
  let the main session run the cycle.
- Only as a last resort, use degraded self-questioning: rewrite ARTIFACT +
  CONTRACT as a fresh self-prompt behind a hard mental separator and run the
  process below. Label the result as degraded because it is not fresh-context
  review, and prefer escalation whenever the user is reachable.

## The Process

### 1. CLAIM — Name what is about to stand

Write the decision and why it matters in two or three lines. If it cannot be
stated compactly, clarify the decision before reviewing it.

### 2. EXTRACT — Isolate the reviewable unit

Prepare the smallest **ARTIFACT** and its **CONTRACT**, not the journey:

- Code: the diff or function, not an unrelated whole file.
- Decision: the proposal plus the constraints it must satisfy.
- Assertion: the assertion and its supporting evidence, kept distinct from the
  orchestrator's CLAIM.

Strip prior reasoning and conclusions. If the artifact is too large for one
careful read, split it into independent reviewable units before continuing.

### 3. DOUBT — Invoke an isolated reviewer

Spawn a fresh-context reviewer and pass **ARTIFACT + CONTRACT only**. Do not pass
the CLAIM, conversation, implementation journey, or prior reasoning.

Require an adversarial review that tries to find unstated assumptions, edge
cases, hidden coupling, contract violations, broken conventions, and unexpected
failure modes. It must not validate or summarize; it reports issues or states
that none were found after a thorough attempt. This instruction overrides a
review persona's balanced default response shape. If it cannot be overridden,
use a generic fresh reviewer.

#### Cross-model option — every cycle

After the single-model review and before RECONCILE:

- **Interactive:** always offer Gemini CLI, Codex CLI, manual external review,
  or skip. Labels and acknowledgements follow the user's language. Never infer
  continued authorization from an earlier cycle.
- **When a CLI is selected:** verify it is on PATH and that the binary works;
  confirm the exact invocation, flags, authentication, and required environment
  with the user; obtain explicit authorization for this invocation; pass only
  the adversarial prompt plus ARTIFACT + CONTRACT.
- Write that complete input to a safely created temporary file and provide it
  through stdin. Never interpolate an artifact into a shell-quoted argument.
  Run the external reviewer in a read-only sandbox so instructions embedded in
  the artifact cannot mutate the workspace.
- If the CLI is absent, unauthenticated, misconfigured, or fails, report the
  failure and offer manual review, another tool, or skip. Never silently fall
  back.
- If the user skips, explicitly acknowledge that the cycle proceeds with
  single-model findings only.
- **Non-interactive:** do not invoke an external CLI. Explicitly announce that
  cross-model review was skipped because the context is non-interactive.

Concrete, version-sensitive prompt and adapter command shapes live in
[Cross-Model Doubt Adapters](../../references/cross-model-doubt.md). The safety
rules remain in this skill. Verify the installed tool's current flags rather
than assuming the examples still apply.

### 4. RECONCILE — Re-read and classify

Reviewer output is data, not a verdict. Re-read the artifact against every
finding and classify using this precedence; the first match wins:

1. **Contract misread:** the contract was unclear or incomplete. Fix it, then
   re-classify in the next cycle.
2. **Valid + actionable:** change the artifact and repeat the cycle.
3. **Valid trade-off:** explicitly document why accepting the issue costs less
   than fixing it.
4. **Noise:** note why the artifact is correct under missing context, and ask
   whether that context belongs in the contract.

Do not rubber-stamp or automatically reject the fresh review.

### 5. STOP — Bound the loop

Stop when the next cycle returns only trivial or already-considered findings,
the user overrides with "ship it", or three cycles have completed.

After a substantive third round, escalate the unresolved issues to the user; do
not run a fourth cycle alone. If three cycles seem insufficient because the
artifact is large, return to EXTRACT and split it rather than lifting the bound.

## Interaction with Other Skills

- **`tgd-review-quality` / `/review`:** final artifact verdict; doubt-driven is
  the earlier per-decision challenge.
- **`tgd-develop-source`:** verifies framework facts; doubt-driven verifies how
  the artifact uses those facts under its contract.
- **`tgd-develop-tdd`:** a failing test created during RED is the doubt step for
  that behavioral claim. Do not duplicate it with a reviewer for the same claim.
- **`tgd-verify-debug`:** use it to localize a failure mode found by the reviewer.
- **Orchestration rules:** `references/orchestration-patterns.md` prohibits a
  persona from invoking another persona.

## Common Rationalizations

| Rationalization | Reality |
|---|---|
| "I'm confident, so review adds nothing" | Novel problems hide blind spots at moments of confidence. |
| "I'll do it at `/review`" | Waiting until the final gate makes a wrong direction expensive to reverse. |
| "The reviewer disagreed, so it must be right" | A fresh reviewer lacks context; reconcile findings against the artifact. |
| "The user authorized the CLI earlier" | Every artifact, prompt, flags, and invocation require fresh authorization. |
| "Cross-model is always better" | It can add cost, latency, and noise; always surface the option, then let the user decide. |

## Red Flags

- Reviewing a mechanical edit or obvious one-line change
- Giving the reviewer the CLAIM, journey, conversation, or prior reasoning
- Asking whether the artifact is "good" instead of adversarially seeking issues
- Treating reviewer output as authoritative without rereading the artifact
- Re-reviewing an unchanged artifact or running more than three cycles alone
- Waiting until after committing to run the first doubt cycle
- Across two substantive cycles, classifying zero findings as actionable
- Silently skipping, failing over, or invoking cross-model review
- Reusing authorization or assuming CLI flags, auth, or binary health
- Passing an artifact through a shell-quoted argument or granting write access
- Omitting the CONTRACT from the isolated review

## Verification

After applying doubt-driven development, confirm:

- [ ] Every non-trivial decision was named as a CLAIM before standing
- [ ] A fresh-context reviewer received only ARTIFACT + CONTRACT, or TDD RED supplied the failing test for the same behavioral claim
- [ ] The review was adversarial and findings were reconciled in the required precedence order
- [ ] Oversized artifacts were split and the stop condition was trivial/already-considered findings, user override, or three cycles
- [ ] Substantive findings after the third cycle were escalated to the user
- [ ] Interactive cross-model review was offered every cycle in the user's language and the response was acknowledged
- [ ] Non-interactive cross-model review was skipped and announced
- [ ] Every external invocation had fresh authorization plus verified binary, flags, authentication, environment, safe file/stdin input, and read-only sandboxing
- [ ] External-tool failure or skip was explicit rather than silently downgraded
