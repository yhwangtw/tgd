---
name: tgd-release-ci
description: Automates CI/CD pipeline setup. Use when setting up or modifying build and deployment pipelines. Use when you need to automate quality gates, configure test runners in CI, or establish deployment strategies.
---

# CI/CD and Automation

## Overview

Automate quality gates so that no change reaches production without passing tests, lint, type checking, and build. CI/CD enforces the other skills consistently on every change.

**Shift Left:** Move checks upstream — static analysis before tests, tests before staging, staging before production.

**Faster is Safer:** Smaller batches and frequent releases reduce risk because they are easier to diagnose and build confidence in the release process.

> **Stack note:** Discover the project's commands and CI platform from `$TGD_DIR/CONTEXT.md`. The gates are mandatory; the Node/npm and GitHub Actions recipes in [CI and deployment patterns](../../references/ci-deployment-patterns.md) are optional, illustrative examples only.

## When to Use

- Setting up a new project's CI pipeline
- Adding or modifying automated checks
- Configuring deployment pipelines
- When a change should trigger automated verification
- Debugging CI failures

## Required Workflow

Execute these decisions in order:

1. Read `$TGD_DIR/CONTEXT.md` and map each required gate to the project's real command and CI platform.
2. Configure the pipeline to run on every pull request and every push to `main`.
3. Run the quality gates in this order: lint → type check → unit tests → build → integration tests → optional E2E → security audit → bundle-size check.
4. Require all configured checks and at least one approval before merge; protect `main` from force-pushes. Auto-merge is allowed only after checks pass and approval exists.
5. Deploy and verify staging from the release candidate before merge. After the change lands and required CI passes, deploy production from the landed `main` SHA and run at least a 15-minute initial health observation. That observation never authorizes traffic expansion; `tgd-release-ship` owns rollout thresholds and decision windows.
6. Keep every deployment reversible with a rollback mechanism.
7. Feed any failure back into the development loop, fix and verify it locally, then push and let CI rerun.

**No gate can be skipped.** If lint fails, fix lint — don't disable the rule. If a test fails, fix the code — don't skip the test.

## Failure Handling

- Lint failure → run the project's lint fixer and commit the actual correction.
- Type error → read the reported location and fix the type.
- Test failure → follow `tgd-verify-debug`; never use a blind rerun as the fix.
- Build error → inspect configuration and dependencies.
- Deployment or monitoring error → stop rollout and use the ready rollback mechanism.

The failure output is evidence: pass the specific error to the agent, require a local reproduction or verification, and only then push the fix.

## Deployment Rules

### Preview Deployments

Give every PR a preview deployment for manual testing.

### Feature Flags

Feature flags decouple deployment from release so code can ship disabled, roll back without redeploying, follow the staged exposure policy owned by `tgd-release-ship`, or support an A/B test.

**Flag lifecycle:** Create → Enable for testing → Canary → Full rollout → Remove the flag and dead code. Set a cleanup date when creating the flag; permanent flags become technical debt.

### Deployment Stages and Rollback

The deployment sequence is:

1. Build and deploy the verified release candidate to staging.
2. Verify staging manually and require all merge checks and approval.
3. Merge the PR to `main` and wait for the provider to report it landed.
4. Deploy production from the landed `main` SHA, manually or through the approved pipeline.
5. Observe initial health for at least 15 minutes and roll back on errors. Passing this observation hands control to `tgd-release-ship`; it does not shorten that skill's longer rollout windows.

Every deployment must be reversible. Keep a manually invokable rollback path that accepts a known previous version.

## Environment and Secret Management

- `.env.example` → committed developer template
- `.env` → never committed; local development only
- `.env.test` → committed only when it contains no real secrets
- CI secrets → secrets manager or vault
- Production secrets → deployment platform or vault

CI must never receive production secrets. Use separate test credentials, including for CI-only databases, and never hardcode them.

## Automation and Ownership

- Configure Dependabot or Renovate for dependency updates.
- Assign a Build Cop to keep CI green. When the build breaks, the Build Cop fixes or reverts it so broken builds do not accumulate; responsibility is not left implicitly with the author.
- Require CI status checks and at least one review through branch protection.

## CI Optimization

When the pipeline exceeds 10 minutes, optimize in this order:

1. Cache dependencies.
2. Run independent jobs in parallel.
3. Use path filters to run only what changed; a docs-only change may skip unrelated E2E, but no applicable gate may be skipped.
4. Shard test suites with matrix builds.
5. Optimize the suite; move slow tests off the critical path and run them on a schedule instead.
6. Use larger hosted or self-hosted runners for CPU-heavy builds.

Concrete GitHub Actions, database, E2E, preview, rollback, dependency-update, and parallel-job examples are in [CI and deployment patterns](../../references/ci-deployment-patterns.md). They are cookbook examples, not additional policy.

## Common Rationalizations

| Rationalization | Reality |
|---|---|
| "CI is too slow" | Optimize the pipeline; don't skip it. A 5-minute pipeline prevents hours of debugging. |
| "This change is trivial, skip CI" | Trivial changes break builds. CI is fast for trivial changes anyway. |
| "The test is flaky, just re-run" | Flaky tests mask real bugs and waste everyone's time. Fix the flakiness. |
| "We'll add CI later" | Projects without CI accumulate broken states. Set it up on day one. |
| "Manual testing is enough" | Manual testing doesn't scale and isn't repeatable. Automate what you can. |

## Red Flags

- No CI pipeline in the project
- CI failures ignored or silenced
- Tests disabled in CI to make the pipeline pass
- Production deploys without staging verification
- No rollback mechanism
- Secrets stored in code or CI config files instead of a secrets manager
- Long CI times with no optimization effort

## Verification

After setting up or modifying CI:

- [ ] All quality gates are present (lint, types, tests, build, audit)
- [ ] Pipeline runs on every PR and push to main
- [ ] Failures block merge (branch protection configured)
- [ ] CI results feed back into the development loop
- [ ] Secrets are stored in the secrets manager, not in code
- [ ] Deployment has a rollback mechanism
- [ ] Staging preceded merge, production used the landed `main` SHA, and the initial health observation did not bypass `tgd-release-ship` rollout gates
- [ ] Pipeline runs in under 10 minutes for the test suite
