---
name: tgd-core-git
description: Structures git workflow practices. Use when making any code change. Use when committing, branching, resolving conflicts, or when you need to organize work across multiple parallel streams.
---

# Git Workflow and Versioning

## Overview

Git is the safety net for fast agent work. Keep changes small, verified,
reviewable, and reversible; let history explain intent rather than hide it.

## When to Use

Always. Every code change flows through git.

## Workflow Contract

### Branching Default

Prefer trunk-based development: keep `main` deployable and merge short-lived
feature branches within 1-3 days. Release branches are acceptable when a
release must stabilize while `main` moves forward, and feature flags are
preferable to long-lived branches for incomplete work.

This is a recommended default, not a replacement for an established team
strategy. Gitflow or other branching models may retain their model while
following the commit discipline below.

Name branches by intent, such as `feature/<description>`,
`fix/<description>`, `chore/<description>`, or `refactor/<description>`.
Create them from `main` or the team's established default branch.
Delete merged short-lived branches unless repository policy says otherwise.

### Commit Discipline

For each successful increment:

1. Implement one coherent slice.
2. Run the relevant verification.
3. Inspect the exact staged scope.
4. Commit the verified slice before beginning the next one.

Each commit must do one logical thing. Explain intent with a descriptive
message, normally using `<type>: <short description>` and an optional body that
explains why. Common types are `feat`, `fix`, `refactor`, `test`, `docs`, and
`chore`.

Keep concerns separate:

- Do not mix formatting-only changes with behavior changes.
- Keep refactors separate from features, except for a small cleanup accepted
  as part of the same logical change at reviewer discretion.
- Prefer separate commits, and ideally separate PRs, for independently
  reviewable or revertible changes.

Change size is a review heuristic, not a correctness rule: about 100 changed
lines is easy to review, about 300 may still be one coherent change, and work
approaching 1000 lines should normally be split. Use `tgd-review-quality` for
splitting strategies.

### tGD Worktree Ownership

The lifecycle commands own worktree mechanics:

- `/tgd-develop` creates or resumes one isolated worktree per repository,
  keeps `$TGD_DIR/` planning artifacts outside implementation worktrees, and
  performs code and test work there.
- `/tgd-release` owns post-merge worktree and branch cleanup.

Follow the exact paths, branch handling, multi-repository tagging, and commands
in [the Develop command](../../.claude/commands/tgd-develop.md) and
[the Release command](../../.claude/commands/tgd-release.md). Do not recreate a
second worktree procedure here.

### Save Points and Reporting

Commits are known-good save points: change, test, verify, commit, then continue.
If an increment fails, return to the last successful state and investigate.
After any modification, provide a structured change summary that identifies
what changed, what was intentionally left untouched, and potential concerns.
This makes scope decisions and unintended changes visible to reviewers.

The diagrams and copyable examples for save points, messages, branches, change
summaries, hooks, and debugging live in
[Git Workflow Patterns](../../references/git-workflow-patterns.md). They
illustrate this contract; this skill remains the normative owner.

### Pre-Commit Gate

Before every commit:

1. Inspect `git diff --staged` and confirm every staged path is authorized.
2. Check the staged diff for secrets or credentials.
3. Run the repository's required tests.
4. Run required linting and type checks.
5. Read the results and commit only when the relevant gates pass.

The reference retains the existing Node-oriented command and Husky examples;
use repository-specific commands when the project defines them.

### Generated Files

- Commit generated files only when the project expects them, such as lockfiles
  or migrations.
- Do not commit build output, environment files, or private IDE configuration.
- Maintain `.gitignore` coverage for standard project exclusions, including
  dependency directories, build output, `.env` files, and private key files.

## Common Rationalizations

| Rationalization | Reality |
|---|---|
| "I'll commit when the feature is done" | One giant commit is difficult to review, debug, or revert. Commit each verified slice. |
| "The message doesn't matter" | Messages are durable documentation of intent. |
| "I'll squash it all later" | Squashing cannot recover a clean development narrative that never existed. |
| "Branches add overhead" | Short-lived branches isolate work; long-lived branches create the integration cost. |
| "I'll split this change later" | Split before submission, while boundaries are still clear. |
| "I don't need a .gitignore" | Missing exclusions make accidental secret and artifact commits more likely. |

## Red Flags

- Large uncommitted changes accumulating
- Commit messages like `fix`, `update`, or `misc`
- Formatting changes mixed with behavior changes
- No `.gitignore` in the project
- Committing dependency directories, `.env` files, or build artifacts
- Long-lived branches diverging significantly from `main`
- Force-pushing to shared branches

## Verification

For every commit:

- [ ] The commit does one logical thing.
- [ ] The message explains why and follows the repository's type convention.
- [ ] Required tests pass before committing.
- [ ] The staged diff contains no secrets.
- [ ] Formatting-only changes are not mixed with behavior changes.
- [ ] `.gitignore` covers the project's standard exclusions.
