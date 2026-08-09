---
name: tgd-review-performance
description: Optimizes application performance. Use when performance requirements exist, when you suspect performance regressions, or when Core Web Vitals or load times need improvement. Use when profiling reveals bottlenecks that need fixing.
---

# Performance Optimization

## Overview

Measure before optimizing. Performance work without measurement is guessing and can add complexity without improving what matters. Profile, identify the actual bottleneck, fix it, measure again, and guard the result.

## When to Use

- The spec defines load-time budgets, response-time SLAs, or another performance requirement
- Users, monitoring, or a changed metric report slowness
- Core Web Vitals are below target or a change may have regressed them
- Large datasets or high traffic make performance a feature constraint

**Do not use without evidence of a problem.** Premature optimization adds lasting complexity.

## Required Targets

| Metric | Good | Needs improvement | Poor |
|---|---|---|---|
| LCP | ≤ 2.5s | ≤ 4.0s | > 4.0s |
| INP | ≤ 200ms | ≤ 500ms | > 500ms |
| CLS | ≤ 0.1 | ≤ 0.25 | > 0.25 |

Unless the project specifies different budgets, use these defaults and enforce configured budgets in CI: initial JavaScript under 200KB gzipped, CSS under 50KB gzipped, above-the-fold images under 200KB each, fonts under 100KB total, API p95 under 200ms, time to interactive under 3.5s on 4G, and Lighthouse Performance at least 90.

## Optimization Workflow

Follow this order; do not skip directly to a recipe:

1. **Measure:** Establish a reproducible baseline using both synthetic measurements (Lighthouse or DevTools) and real-user data (web-vitals or CrUX). Synthetic data isolates regressions; RUM proves user impact.
2. **Identify:** Trace the measured symptom to the actual bottleneck. For first load, inspect bundle, TTFB, and render blockers; for interaction, inspect long tasks, renders, and layout; for navigation, inspect data waterfalls; for backend, profile queries, CPU, memory, locks, GC, pools, and external calls.
3. **Fix:** Address only the proven bottleneck. Common candidates include N+1 queries, unbounded fetching, unoptimized images, expensive renders, oversized bundles, and absent caching.
4. **Verify:** Repeat the same measurement under comparable conditions and record before/after numbers. Existing functional tests must still pass.
5. **Guard:** Add monitoring, a performance test, or a CI budget that would detect regression.

Detailed diagnostic trees, language/framework recipes, commands, and copyable checklists are in [`../../references/performance-checklist.md`](../../references/performance-checklist.md). They are illustrative; this workflow and the project-specific requirements remain authoritative.

## Safety Boundaries

- Never claim improvement without comparable before/after measurements.
- Do not trade correctness, accessibility, security, or maintainability for an unmeasured gain.
- Do not apply memoization or caching indiscriminately; measure benefit and preserve invalidation correctness.
- Keep list operations bounded and protect request handlers from synchronous heavy computation.

## Common Rationalizations

| Rationalization | Reality |
|---|---|
| "We'll optimize later" | Fix proven anti-patterns now; defer only unmeasured micro-optimization. |
| "It's fast on my machine" | Measure representative hardware, networks, and real users. |
| "This optimization is obvious" | If it was not measured, it is still a guess. |
| "Users won't notice 100ms" | Small delays can affect experience and conversion; use data. |
| "The framework handles performance" | Frameworks cannot eliminate application N+1 queries or oversized bundles. |

## Red Flags

- Optimization without profiling evidence
- N+1 queries, unbounded queries, or list endpoints without pagination
- Images without dimensions, lazy loading, or responsive sizes
- Bundle growth without review
- No production performance monitoring
- Blanket `React.memo` or `useMemo` without measured benefit

## Verification

- [ ] Comparable before/after measurements with specific numbers exist
- [ ] The measured bottleneck, chosen fix, and causal result are documented
- [ ] Core Web Vitals are within Good thresholds
- [ ] Bundle size and other applicable project budgets pass
- [ ] New data fetching contains no N+1 or unbounded operation
- [ ] CI performance guard passes when configured
- [ ] Existing tests pass and behavior remains correct
