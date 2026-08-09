---
name: tgd-develop-source
description: Grounds every implementation decision in official documentation. Use when you want authoritative, source-cited code free from outdated patterns. Use when building with any framework or library where correctness matters.
---

# Source-Driven Development

## Overview

Every framework- or library-specific implementation decision is verified
against official documentation for the project's exact version. Do not rely on
memory when APIs, deprecations, compatibility, or current practices matter.

## When to Use

- Framework/library code, reusable boilerplate, starters, or copied patterns
- Forms, routing, data fetching, state, auth, or another versioned API surface
- Review or implementation requiring current, documented behavior

Skip only version-independent edits such as renames, typos, moves, or pure
language logic, or when the user explicitly chooses speed over verification.

## Mandatory Process

### 1. Detect Stack and Versions

Read repository manifests and lock/configuration files and state the exact
framework, library, runtime, and relevant tool versions found. If the applicable
version is missing or ambiguous, ask; never guess which API generation applies.

### 2. Fetch the Specific Official Source

Retrieve the smallest official page that governs the feature—not a homepage,
generic search result, or entire documentation site.

| Priority | Acceptable primary source |
|---:|---|
| 1 | Official API/framework documentation |
| 2 | Official project blog, release notes, or migration guide |
| 3 | Standards sources such as MDN, web.dev, or specifications |
| 4 | Browser/runtime compatibility sources |

Stack Overflow, third-party tutorials/blogs, AI summaries, and training memory
are not primary authority. Extract current signatures, required patterns,
deprecations, migrations, and compatibility evidence.

When official sources conflict, surface the discrepancy and determine which
source applies to the detected version before implementation.

### 3. Implement the Documented Pattern

Use documented current signatures and flows. Do not use a deprecated approach
because it is familiar. When official docs do not support a needed pattern,
label it unverified rather than presenting it as established guidance.

If current documentation conflicts with established project code, show the
exact conflict, sources, and tradeoff and ask which direction to follow. Do not
silently choose modernization or local consistency.

### 4. Cite Every Non-Trivial Decision

- Cite every framework-specific pattern; do not leave copied API usage
  unsupported.
- Give full authoritative URLs, preferably a stable deep link or anchor.
- Cite the source next to the code or explanation it supports.
- Quote the relevant passage when a non-obvious decision needs direct evidence,
  within applicable quotation limits.
- Include browser/runtime support evidence for platform-feature recommendations.
- State `UNVERIFIED` explicitly when official evidence cannot be found and
  require verification before production use.

Manifest mappings, fetch contrasts, conflict prompts, and citation shapes are
illustrative. Load
[Source Grounding Patterns](../../references/source-grounding-patterns.md) only
when an example helps; this skill remains the normative owner.

## Common Rationalizations

| Rationalization | Reality |
|---|---|
| "I'm confident about this API" | Confidence is not current version evidence. |
| "Fetching docs wastes tokens" | Debugging a stale signature costs more. |
| "The docs won't cover it" | That absence is material evidence. |
| "I'll say it may be outdated" | Verify it or clearly mark it unverified. |
| "This task is simple" | Simple stale patterns become copied templates. |

## Red Flags

- Framework code written before version and official-source checks
- API claims phrased as belief rather than cited evidence
- Third-party content presented as primary authority
- Deprecated APIs copied from memory
- Broad docs-site fetches instead of the relevant page
- Missing citations or hidden docs-versus-project conflicts

## Verification

- [ ] Relevant versions came from repository files, not assumptions.
- [ ] Official documentation was retrieved for versioned patterns.
- [ ] Code follows the current documented signatures and migration guidance.
- [ ] Non-trivial decisions cite full authoritative URLs.
- [ ] Platform recommendations include compatibility evidence.
- [ ] Docs/project or official-source conflicts were surfaced.
- [ ] Unsupported patterns are explicitly `UNVERIFIED` before production use.
