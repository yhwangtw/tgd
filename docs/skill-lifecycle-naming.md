# Skill Lifecycle Naming

The tGD pack keeps the seven public lifecycle commands stable:

`tgd-map` · `tgd-define` · `tgd-plan` · `tgd-develop` · `tgd-verify` · `tgd-review` · `tgd-release`

Internal skills now use `tgd-<phase>-<capability>` when they have one clear
phase owner. Cross-cutting skills use `tgd-core-*`; standalone utilities use
`tgd-support-*`.

## Rename map

| Previous ID | Current ID |
|---|---|
| `tgd-agent-browser` | `tgd-verify-browser` |
| `tgd-api-and-interface-design` | `tgd-define-api` |
| `tgd-ci-cd-and-automation` | `tgd-release-ci` |
| `tgd-code-review-and-quality` | `tgd-review-quality` |
| `tgd-code-simplification` | `tgd-review-simplify` |
| `tgd-context-engineering` | `tgd-core-context` |
| `tgd-debugging-and-error-recovery` | `tgd-verify-debug` |
| `tgd-deprecation-and-migration` | `tgd-release-migration` |
| `tgd-documentation-and-adrs` | `tgd-review-adr` |
| `tgd-doubt-driven-development` | `tgd-core-doubt` |
| `tgd-frontend-ui-engineering` | `tgd-develop-ui` |
| `tgd-git-workflow-and-versioning` | `tgd-core-git` |
| `tgd-idea-refine` | `tgd-define-ideate` |
| `tgd-incremental-implementation` | `tgd-develop-incremental` |
| `tgd-interview-me` | `tgd-define-interview` |
| `tgd-jira-auto-sync` | `tgd-plan-jira` |
| `tgd-performance-optimization` | `tgd-review-performance` |
| `tgd-planning-and-task-breakdown` | `tgd-plan-breakdown` |
| `tgd-router` | `tgd-core-router` |
| `tgd-rules` | `tgd-core-rules` |
| `tgd-security-and-hardening` | `tgd-review-security` |
| `tgd-shipping-and-launch` | `tgd-release-ship` |
| `tgd-sketch` | `tgd-define-sketch` |
| `tgd-source-driven-development` | `tgd-develop-source` |
| `tgd-spec-driven-development` | `tgd-define-spec` |
| `tgd-subagent-driven-development` | `tgd-develop-subagents` |
| `tgd-test-driven-development` | `tgd-develop-tdd` |
| `tgd-verification-before-completion` | `tgd-verify-completion` |
| `tgd-wiki-generation` | `tgd-support-wiki` |

## Upgrade behavior

Run `bash setup.sh` again after updating a checkout. The installer removes an
old skill symlink only when its target can be proven to belong to a tGD
checkout. Foreign skill directories and user-owned files are preserved. The
new ID is then installed and recorded in the ownership manifest.

Existing references in project instructions should be updated to the current
ID. The lifecycle command names do not change.
