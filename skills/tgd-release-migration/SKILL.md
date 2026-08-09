---
name: tgd-release-migration
description: Manages deprecation and migration. Use when removing old systems, APIs, or features. Use when migrating users from one implementation to another. Use when deciding whether to maintain or sunset existing code.
---

# Deprecation and Migration

## Overview

Code carries continuing maintenance, security, dependency, documentation, and onboarding costs. Deprecation removes code that no longer earns that cost; migration moves consumers safely from old to new.

## When to Use

- Replacing an old system, API, or library with a new one
- Sunsetting a feature that is no longer needed
- Consolidating duplicate implementations
- Removing dead code that nobody owns but everybody depends on
- Planning the lifecycle of a new system; deprecation planning starts at design time
- Deciding whether to maintain a legacy system or invest in migration

## Core Principles

**Code Is a Liability.** The value of code is its functionality, not its volume. When the same value can be delivered with less code, complexity, or better abstractions, remove the old code after safely migrating its consumers.

**Hyrum's Law Makes Removal Hard.** With enough users, every observable behavior becomes a dependency, including bugs, timing quirks, and undocumented side effects. Deprecation therefore requires active migration, not only an announcement.

**Plan Removal at Design Time.** Ask how a new system would be removed in three years. Clean interfaces, feature flags, and small exposed surfaces make later deprecation safer.

## Deprecation Decision Gate

Answer in this order before deprecating anything:

1. **Does it still provide unique value?** If yes, maintain it; otherwise continue.
2. **How many consumers depend on it?** Quantify the migration scope.
3. **Does a replacement exist?** If not, build it first; never deprecate without an alternative.
4. **What is each consumer's migration cost?** Automate trivial migrations; weigh manual high-effort work against maintenance cost.
5. **What is the cost of not deprecating?** Include security risk, engineering time, and complexity opportunity cost.

Choose the mode only after answering those questions:

| Type | When to use | Mechanism |
|---|---|---|
| **Advisory** | Migration is optional and the old system is stable | Warnings, documentation, and nudges; consumers choose timing |
| **Compulsory** | Security issues, blocked progress, or unsustainable maintenance cost | Hard removal date plus migration tooling |

**Default to advisory.** Compulsory deprecation is justified only by maintenance cost or risk and requires tooling, documentation, and support; never announce a deadline without them.

## Required Migration Sequence

Do not reorder or skip these steps.

### 1. Build and Prove the Replacement
Do not deprecate without a working alternative. It must:

- Cover every critical use case of the old system
- Have documentation and a migration guide
- Be proven in production, not only theoretically better

### 2. Announce and Document
State the deprecated system, effective date, replacement, removal date or advisory status, reason, concrete migration steps, and verification method. An illustrative notice is in [Release and migration patterns](../../references/release-patterns.md).

### 3. Migrate Incrementally
Migrate consumers one at a time. For each consumer:

1. Identify all touchpoints with the deprecated system.
2. Update it to use the replacement.
3. Verify equivalent behavior with tests and integration checks.
4. Remove its references to the old system.
5. Confirm no regressions.

**The Churn Rule:** If you own the infrastructure being deprecated, you are responsible for migrating users or providing backward-compatible updates that require no migration. Do not announce deprecation and leave users to solve it.

### 4. Remove the Old System
Only after all consumers have migrated:

1. Verify zero active usage through metrics, logs, and dependency analysis.
2. Remove the code.
3. Remove associated tests, documentation, and configuration.
4. Remove the deprecation notices.

If usage is not zero or any consumer remains unverified, stop removal and return to incremental migration.

## Migration Pattern Decisions

- **Strangler:** Run old and new in parallel and route traffic incrementally. Use 0% → 10% → 50% → 100%; remove the old system only after it handles 0%.
- **Adapter:** Preserve the old interface while delegating to the new implementation. Use it when consumers cannot migrate together.
- **Feature flag:** Switch consumers individually between old and new. Keep the old path available until verification and rollback needs are satisfied.

Diagrams and code samples for these patterns are optional examples in [Release and migration patterns](../../references/release-patterns.md); the sequence and gates above remain authoritative.

## Zombie Code Decision

Zombie code has active consumers but no effective owner or maintenance. Signs include:

- No commits in 6+ months while consumers remain active
- No assigned maintainer or team
- Failing tests that nobody fixes
- Known vulnerable dependencies that nobody updates
- Documentation referring to systems that no longer exist

Either assign an owner and maintain it properly, or deprecate it with a concrete migration plan. It cannot remain in limbo.

## Common Rationalizations

| Rationalization | Reality |
|---|---|
| "It still works, why remove it?" | Working unmaintained code accumulates security debt and complexity. |
| "Someone might need it later" | Keeping unused code just in case often costs more than rebuilding it. |
| "The migration is too expensive" | Compare it with 2–3 years of ongoing maintenance; migration is usually cheaper long-term. |
| "We'll deprecate it after the new system" | Plan deprecation during design, before priorities move again. |
| "Users will migrate on their own" | They will not. Provide tooling, documentation, incentives, or perform the migration under the Churn Rule. |
| "We can maintain both indefinitely" | Duplicate systems double maintenance, testing, documentation, and onboarding cost. |

## Red Flags

- Deprecated systems with no replacement
- Announcements without migration tooling or documentation
- Advisory deprecations that remain stalled for years
- Zombie code with active consumers and no owner
- New features added to a deprecated system
- Deprecation without measured usage
- Removing code before verifying zero active consumers

## Verification

After completing a deprecation:

- [ ] Replacement is production-proven and covers all critical use cases
- [ ] Migration guide exists with concrete steps and examples
- [ ] All active consumers have migrated, verified by metrics and logs
- [ ] Old code, tests, documentation, and configuration are fully removed
- [ ] No references to the deprecated system remain in the codebase
- [ ] Deprecation notices are removed
