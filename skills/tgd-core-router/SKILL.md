---
name: tgd-core-router
description: Routes natural-language intent to the applicable tGD skill. Use only when no lifecycle command supplies the pipeline and intent needs routing. Always load tgd-core-rules first.
---

# Using tGD

First, load the `tgd-core-rules` skill. It owns all global invariants, proof,
selection, tone, closing-report, and sign-off rules; this file only routes
intent.

## Intent Routing

| Intent | Route |
|---|---|
| The user does not yet know what they want | `tgd-define-interview` |
| Rough concept needs alternatives | `tgd-define-ideate` |
| Define a new project, feature, or change | `tgd-define-spec` |
| Create UI mock variants | `tgd-define-sketch` |
| Turn a spec into tasks | `tgd-plan-breakdown` |
| Preview or sync TASKS.md with Jira | `tgd-plan-jira` |
| Implement a small or direct change | `tgd-develop-incremental` |
| Implement a multi-task plan or high-stakes path | `tgd-develop-subagents` |
| Build production UI | `tgd-develop-ui` |
| Design an API or interface contract | `tgd-define-api` |
| Load relevant project and task context | `tgd-core-context` |
| Ground implementation in official documentation | `tgd-develop-source` |
| Cross-examine a high-stakes or unfamiliar decision | `tgd-core-doubt` |
| Write or run tests | `tgd-develop-tdd` |
| Verify through a browser | `tgd-verify-browser` |
| Reproduce, localize, and fix a failure | `tgd-verify-debug` |
| Prove a completion claim | `tgd-verify-completion` |
| Review code quality | `tgd-review-quality` |
| Simplify working but complex code | `tgd-review-simplify` |
| Review security | `tgd-review-security` |
| Review performance | `tgd-review-performance` |
| Commit, branch, or manage worktrees | `tgd-core-git` |
| Create or improve CI/CD | `tgd-release-ci` |
| Write documentation or ADRs | `tgd-review-adr` |
| Generate or regenerate a project wiki from existing scan graphs | `tgd-support-wiki` |
| Remove or migrate an old system | `tgd-release-migration` |
| Deploy or launch | `tgd-release-ship` |

## Combination and Fallback Rules

- An explicit lifecycle command owns its complete pipeline; do not replace it
  with an ad hoc chain from this table.
- When several intents apply, combine the matching skills in lifecycle order
  and follow each skill's applicability conditions. Do not invoke unrelated
  skills merely because they are available.
- For an underspecified request, start with `tgd-define-interview`; for a
  non-trivial change with clear intent but no specification, start with
  `tgd-define-spec`.
- If an optional tool or delegation surface is unavailable, follow the owning
  command or skill's fallback and the inline-fallback invariant in
  `tgd-core-rules`; never silently skip required work.
