---
name: tgd-core-git
description: Structures git workflow practices. Use when making any code change. Use when committing, branching, resolving conflicts, or when you need to organize work across multiple parallel streams.
---

# Git Workflow and Versioning

## Overview

Git is the safety net for fast agent work. Keep changes small, verified,
reviewable, and reversible; let history explain intent rather than hide it.

## When to Use

Always. Every code change flows through git. This skill defines safe Git
practice; it does not itself authorize creating a commit. Commit only when the
active lifecycle step or the user explicitly authorizes it.

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

For each successful increment whose commit is authorized:

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
If an increment fails, inspect and preserve the full worktree first. Repair or
discard only the exact agent-owned and explicitly authorized slice; never erase
unrelated staged, unstaged, or untracked work to return to a save point.
After any modification, provide a structured change summary that identifies
what changed, what was intentionally left untouched, and potential concerns.
This makes scope decisions and unintended changes visible to reviewers.

The diagrams and copyable examples for save points, messages, branches, change
summaries, hooks, and debugging live in
[Git Workflow Patterns](../../references/git-workflow-patterns.md). They
illustrate this contract; this skill remains the normative owner.

### Pre-Commit Gate

Before every commit:

1. Confirm the active lifecycle step or user authorizes a commit.
2. Inspect `git diff --staged --name-status` and confirm every staged path is
   authorized without printing staged content.
3. Run the repository-configured secret scanner without printing matched secret
   values. If no trusted scanner exists, an explicitly identified user or local
   repository owner must inspect the full patch in a non-logged local context
   and confirm that it contains no secrets. If that confirmation is unavailable,
   stop and do not commit.
4. After the scanner passes, or as the owner-confirmed fallback review, inspect
   the full staged patch in an authorized local context that does not echo
   possible secrets into agent or shared logs.
5. Run the repository's required tests.
6. Run required linting and type checks.
7. Read the results and commit only when the relevant gates pass.

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
- Discarding a broad worktree scope to recover one failed increment
- Treating a raw grep of staged content as a safe secret scan

## Verification

For every commit:

- [ ] The commit was authorized by the active lifecycle step or the user.
- [ ] The commit does one logical thing.
- [ ] The message explains why and follows the repository's type convention.
- [ ] Required tests pass before committing.
- [ ] The staged diff contains no secrets.
- [ ] Formatting-only changes are not mixed with behavior changes.
- [ ] `.gitignore` covers the project's standard exclusions.
