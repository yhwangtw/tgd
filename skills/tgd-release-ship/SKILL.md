---
name: tgd-release-ship
description: Prepares production launches. Use when preparing to deploy to production. Use when you need a pre-launch checklist, when setting up monitoring, when planning a staged rollout, or when you need a rollback strategy.
---

# Shipping and Launch

## Overview

Ship safely with monitoring, a ready rollback plan, and explicit success criteria. Every launch must be reversible, observable, and incremental.

> **Stack note:** Use the project's actual commands from `$TGD_DIR/CONTEXT.md`. The gates below are mandatory; the Node, React, rollout, and rollback material in [Release and migration patterns](../../references/release-patterns.md) is optional and illustrative only.

## When to Use

- Deploying a feature to production for the first time
- Releasing a significant change to users
- Migrating data or infrastructure
- Opening a beta or early access program
- Any deployment that carries risk (all of them)

## Required Workflow

Execute the release in this order:

1. Complete every pre-launch gate below.
2. Document rollback triggers and steps, confirm monitoring, and configure the feature flag when applicable.
3. Deploy staging; run the full suite and manually smoke-test critical flows.
4. Deploy production with the feature flag off; verify the health check and error monitoring.
5. Enable for the team, then canary and increase exposure only when the decision thresholds pass.
6. Roll back immediately when a red threshold or critical trigger occurs; otherwise monitor at every stage.
7. At full rollout, monitor for one week, then remove the feature flag and dead code.

## Pre-Launch Gates

### Code Quality

- [ ] All tests pass (unit, integration, e2e)
- [ ] Build succeeds with no warnings
- [ ] Lint and type checking pass
- [ ] Code reviewed and approved
- [ ] No TODO comments that should be resolved before launch
- [ ] No `console.log` debugging statements in production code
- [ ] Error handling covers expected failure modes

### Security

- [ ] No secrets in code or version control
- [ ] `npm audit` shows no critical or high vulnerabilities
- [ ] Input validation on all user-facing endpoints
- [ ] Authentication and authorization checks in place
- [ ] Security headers configured (CSP, HSTS, etc.)
- [ ] Rate limiting on authentication endpoints
- [ ] CORS configured to specific origins (not wildcard)

### Performance

- [ ] Core Web Vitals within "Good" thresholds
- [ ] No N+1 queries in critical paths
- [ ] Images optimized (compression, responsive sizes, lazy loading)
- [ ] Bundle size within budget
- [ ] Database queries have appropriate indexes
- [ ] Caching configured for static assets and repeated queries

### Accessibility

- [ ] Keyboard navigation works for all interactive elements
- [ ] Screen reader can convey page content and structure
- [ ] Color contrast meets WCAG 2.1 AA (4.5:1 for text)
- [ ] Focus management correct for modals and dynamic content
- [ ] Error messages are descriptive and associated with form fields
- [ ] No accessibility warnings in axe-core or Lighthouse

### Infrastructure

- [ ] Environment variables set in production
- [ ] Database migrations applied (or ready to apply)
- [ ] DNS and SSL configured
- [ ] CDN configured for static assets
- [ ] Logging and error reporting configured
- [ ] Health check endpoint exists and responds

### Documentation

- [ ] README updated with any new setup requirements
- [ ] API documentation current
- [ ] ADRs written for any architectural decisions
- [ ] Changelog updated
- [ ] User-facing documentation updated (if applicable)

For detailed domain checklists, see `references/security-checklist.md`, `references/performance-checklist.md`, and `references/accessibility-checklist.md`.

## Feature Flag Gate

Feature flags decouple deployment from release. Their lifecycle is:

1. Deploy with the flag off.
2. Enable for the team or beta users.
3. Roll out to 5% → 25% → 50% → 100%.
4. Monitor error rates, performance, and user feedback at every stage.
5. Remove the flag and dead code after full rollout.

Rules:

- Every feature flag has an owner and expiration date.
- Clean up flags within 2 weeks of full rollout.
- Do not nest feature flags; nested flags create exponential combinations.
- Test both on and off states in CI.

## Staged Rollout and Decision Gate

1. **Staging:** full test suite and manual smoke test of critical flows.
2. **Production, flag off:** health check succeeds and monitoring shows no new errors.
3. **Team:** internal users exercise the feature during a 24-hour monitoring window.
4. **Canary, 5%:** compare error, latency, behavior, and business metrics against baseline for 24–48 hours. Advance only when all thresholds pass.
5. **Gradual, 25% → 50% → 100%:** repeat monitoring at each step and retain the ability to return to the previous percentage.
6. **Full:** monitor for one week, then clean up the flag.

Use these thresholds at every stage:

| Metric | Advance (green) | Hold and investigate (yellow) | Roll back (red) |
|---|---|---|---|
| Error rate | Within 10% of baseline | 10–100% above baseline | >2x baseline |
| P95 latency | Within 20% of baseline | 20–50% above baseline | >50% above baseline |
| Client JS errors | No new error types | New errors at <0.1% of sessions | New errors at >0.1% of sessions |
| Business metrics | Neutral or positive | Decline <5% (may be noise) | Decline >5% |

## Failure and Rollback Behavior

Roll back immediately if:

- Error rate increases by more than 2x baseline
- P95 latency increases by more than 50%
- User-reported issues spike
- Data integrity issues are detected
- A security vulnerability is discovered

Every deployment needs a documented rollback plan before it happens. The plan must name trigger conditions, exact rollback steps, post-rollback health and monitoring checks, team communication, database rollback/data handling, and expected rollback time. Prefer disabling the feature flag; otherwise deploy or revert to the known previous version.

## Monitoring and Post-Launch Verification

Monitor all three layers:

- Application: total and per-endpoint error rate, p50/p95/p99 response time, request volume, active users, and key business metrics.
- Infrastructure: CPU, memory, database connection pool, disk, network latency, and queue depth.
- Client: Core Web Vitals (LCP, INP, CLS), JavaScript errors, client-visible API error rates, and page-load time.

Error reporting must capture actionable context without exposing internals to users. Logs must be flowing and readable before rollout advances.

In the first hour after launch:

1. Check health endpoint returns 200.
2. Check the error dashboard has no new error types.
3. Check the latency dashboard has no regression.
4. Test the critical user flow manually.
5. Verify logs are flowing and readable.
6. Confirm rollback mechanism works, using a dry run if practical.

Optional error-reporting code, flag examples, rollout diagrams, and a rollback-plan template are in [Release and migration patterns](../../references/release-patterns.md). They do not replace the gates above.

## Common Rationalizations

| Rationalization | Reality |
|---|---|
| "It works in staging, it'll work in production" | Production has different data, traffic patterns, and edge cases. Monitor after deploy. |
| "We don't need feature flags for this" | Every feature benefits from a kill switch. Even "simple" changes can break things. |
| "Monitoring is overhead" | Without monitoring, problems arrive as user complaints instead of dashboard signals. |
| "We'll add monitoring later" | Add it before launch. You can't debug what you can't see. |
| "Rolling back is admitting failure" | Rolling back is responsible engineering. Shipping a broken feature is the failure. |

## Red Flags

- Deploying without a rollback plan
- No monitoring or error reporting in production
- Big-bang releases with no staging
- Feature flags with no expiration or owner
- No one monitoring the deploy for the first hour
- Production environment configuration done from memory, not code
- "It's Friday afternoon, let's ship it"

## Verification

Before deploying:

- [ ] Pre-launch checklist completed (all sections green)
- [ ] Feature flag configured (if applicable)
- [ ] Rollback plan documented
- [ ] Monitoring dashboards set up
- [ ] Team notified of deployment

After deploying:

- [ ] Health check returns 200
- [ ] Error rate is normal
- [ ] Latency is normal
- [ ] Critical user flow works
- [ ] Logs are flowing
- [ ] Rollback tested or verified ready
