---
name: tgd-review-simplify
description: Simplifies code for clarity. Use when refactoring code for clarity without changing behavior. Use when code works but is harder to read, maintain, or extend than it should be. Use when reviewing code that has accumulated unnecessary complexity.
---

# Code Simplification

> Inspired by the [Claude Code Simplifier plugin](https://github.com/anthropics/claude-plugins-official/blob/main/plugins/code-simplifier/agents/code-simplifier.md). Adapted as a model-agnostic, process-driven skill.

## Overview

Reduce complexity while preserving exact behavior. The goal is faster comprehension, not fewer lines. A simplification succeeds only when a new team member would understand it faster.

## When to Use

- Working, tested code is heavier than necessary
- Review flags readability, nesting, length, naming, duplication, or inconsistency
- Refactoring code written under time pressure or consolidating scattered related logic

**Do not use** when the code is already clear, you do not yet understand it, simpler code would measurably harm a critical path, or the module is about to be discarded.

## Five Principles

1. **Preserve behavior exactly.** Inputs, outputs, side effects, ordering, errors, and edge cases must remain identical. Existing tests must pass without modification. If uncertain, do not make the change.
2. **Follow project conventions.** Read project rules and neighboring code; match import, module, declaration, naming, error, and type conventions. External preference is churn, not simplification.
3. **Prefer clarity over cleverness.** Explicit code is better than compact code that requires a mental pause.
4. **Maintain balance.** Do not inline useful names, combine unrelated responsibilities, remove abstractions that provide extensibility/testability, or optimize for line count.
5. **Scope to what changed.** Default to recently modified code. Do not perform unrelated drive-by refactors without authorization.

## Simplification Process

### Step 1: Understand Before Touching

Apply Chesterton's Fence. Establish the code's responsibility, callers/callees, edge and error paths, tests, original context from history/blame, and any performance or platform constraint. If you cannot explain why the current shape exists, read more before changing it.

### Step 2: Identify Concrete Opportunities

Look for signals, not vague taste:

- **Structure:** nesting of 3+ levels, 50+ line multi-responsibility functions, nested ternaries, positional boolean flags, and repeated conditionals
- **Naming:** generic, abbreviated, or misleading names; comments that restate what instead of preserving why
- **Redundancy:** duplicated logic, confirmed dead code, value-free wrappers, one-implementation factories/strategies, and redundant type assertions

Use guard clauses or named helpers, split responsibilities, replace opaque flags with options or separate functions, retain why-comments, and remove only redundancy whose purpose is understood.

### Step 3: Apply Incrementally

For each simplification: make one change, run tests, then keep it only if tests pass. Do not batch unrelated transformations. Submit refactors separately from behavior changes.

**Rule of 500:** If the refactor touches more than 500 lines, use automation such as a codemod or AST transform rather than error-prone manual edits.

### Step 4: Verify the Whole Result

Compare before and after. Confirm the result is easier to understand, consistent with the codebase, cleanly reviewable, and free of new patterns. Revert any attempt that makes comprehension or review worse.

Illustrative before/after recipes for TypeScript, Python, and React, plus signal tables, are in [`../../references/simplification-patterns.md`](../../references/simplification-patterns.md). They are examples only; the principles and workflow above are authoritative.

## Common Rationalizations

| Rationalization | Reality |
|---|---|
| "It's working, no need to touch it" | Hard-to-read code is harder to fix when it breaks. |
| "Fewer lines is always simpler" | Simplicity is comprehension speed, not line count. |
| "I'll quickly simplify unrelated code too" | Unscoped refactoring creates noisy, risky diffs. |
| "The types make it self-documenting" | Types describe structure, not intent. |
| "This abstraction might be useful later" | Speculative abstraction is present complexity for hypothetical value. |
| "The author must have had a reason" | Check history and apply Chesterton's Fence; do not assume either way. |
| "I'll refactor while adding this feature" | Mixed behavior and refactor changes are harder to review and revert. |

## Red Flags

- Existing tests must be modified to accept the simplification
- The result is longer and harder to follow
- Renaming reflects personal taste instead of project convention
- Error handling is removed or weakened
- The code or its constraints are not understood
- Many changes are batched into one hard-to-review commit
- Work extends beyond the authorized scope

## Verification

- [ ] Existing tests pass without modification
- [ ] Build succeeds without new warnings
- [ ] Linter and formatter pass
- [ ] Each change is incremental and reviewable
- [ ] The diff contains no unrelated changes
- [ ] Project conventions were checked and followed
- [ ] Error handling and side-effect ordering are unchanged
- [ ] No dead imports, variables, or branches remain
- [ ] The result is a demonstrable net improvement in comprehension
