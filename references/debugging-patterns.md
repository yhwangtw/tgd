# Debugging Patterns

Illustrative examples only. The ordered workflow, trust boundary, bug-filing
policy, and release gates live in
[`tgd-verify-debug`](../skills/tgd-verify-debug/SKILL.md).

## Reproduction Tree

```text
Can the failure be reproduced?
├── Yes → localize the failing layer
└── No
    ├── Timing-dependent → timestamps, artificial delays, load/concurrency
    ├── Environment-dependent → compare runtime, OS, variables, data, CI
    ├── State-dependent → isolation, suite order, globals, caches
    └── Still intermittent → targeted logs, signature alert, conditions record
```

Example focused test commands vary by repository:

```bash
npm test -- --grep "test name"
npm test -- --verbose
npm test -- --testPathPattern="specific-file" --runInBand
```

## Localization and Bisection

```text
UI/Frontend      → console, DOM, network
API/Backend      → server logs, request and response
Database         → queries, schema, data integrity
Build tooling    → config, dependencies, environment
External service → connectivity, contract changes, rate limits
Test             → expectation, isolation, timing
```

After confirming the exact known-good and known-bad revisions and preserving
unrelated work, an isolated repository can use:

```bash
git bisect start
git bisect bad
git bisect good <known-good-sha>
git bisect run npm test -- --grep "failing test"
```

## Root Cause Contrast

```text
Symptom: the user list shows duplicates

Masking change:
  deduplicate only in the UI

Root-cause change:
  identify the JOIN or data-model behavior producing duplicates,
  repair it, and add a regression test
```

## Regression Example

```typescript
it('finds tasks with special characters in the title', async () => {
  await createTask({ title: 'Fix "quotes" & <brackets>' });
  const results = await searchTasks('quotes');
  expect(results).toHaveLength(1);
  expect(results[0].title).toBe('Fix "quotes" & <brackets>');
});
```

## Verification Command Shape

```bash
npm test -- --grep "specific test"
npm test
npm run build
npm run dev
```

The repository's own test, build, and browser-verification commands replace
these illustrative npm commands.

## Failure Trees

```text
Test failure
├── Covered behavior changed → decide whether code or expectation is wrong
├── Unrelated code changed → inspect shared state, imports, globals
└── Existing flake → inspect timing, order, external dependencies

Build failure
├── Type error → cited types and location
├── Import error → module, export, path
├── Config error → syntax and schema
├── Dependency error → manifest and lockfile
└── Environment error → runtime and OS compatibility

Runtime failure
├── Null/undefined access → trace the value's origin
├── Network/CORS → URL, headers, server policy
├── Render/white screen → boundary, console, component tree
└── No error → log the smallest useful data-flow checkpoints
```

## Fallback Examples

```typescript
function getOptionalChartTitle(): string {
  const value = process.env.CHART_TITLE;
  if (!value) {
    console.warn('CHART_TITLE is unset; using the display-only default');
    return 'Overview';
  }
  return value;
}

function ChartPanel({ data }: { data: ChartData[] }) {
  if (data.length === 0) {
    return <EmptyState message="No data available for this period" />;
  }

  return (
    <ChartErrorBoundary fallback={<ErrorState message="Unable to display chart" />}>
      <Chart data={data} />
    </ChartErrorBoundary>
  );
}
```

These examples illustrate a non-critical default and graceful degradation;
the main skill owns the boundary that forbids hiding correctness, integrity,
or security failures.

## Bug Filing Tree

```text
Bug discovered during Verify
└── Fixable in this session?
    ├── Yes → fix and verify; no issue required
    └── No
        ├── External dependency → bug + dependency evidence
        ├── Design decision → bug + stakeholder context
        ├── Third-party fix → bug + external issue
        └── Unknown cause → bug + logs and reproduction evidence
```

## Bug Ticket Example

```markdown
## Bug Summary
[One-line description]

## Severity
[Critical / High / Medium]

## Environment
- Stage: /tgd-verify
- Feature: <feature-name>
- Commit: <commit hash>

## Steps to Reproduce
1. [Step 1]
2. [Step 2]
3. [Step 3]

## Expected Behavior
[What should happen]

## Actual Behavior
[What actually happens]

## Evidence
- Error logs: [attachment]
- Screenshots: [if applicable]
- Test output: [attachment]

## Root Cause Analysis (if known)
[Current analysis]

## Workaround (if one exists)
[Temporary workaround]
```
