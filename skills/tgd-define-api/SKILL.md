---
name: tgd-define-api
description: Guides stable API and interface design. Use when designing APIs, module boundaries, or any public interface. Use when creating REST or GraphQL endpoints, defining type contracts between modules, or establishing boundaries between frontend and backend.
---

# API and Interface Design

## Overview

Design stable, documented interfaces that are hard to misuse. This applies to
REST and GraphQL APIs, module boundaries, component props, schemas, and every
surface where one component communicates with another.

## When to Use

- Designing or changing endpoints, public interfaces, or schemas
- Defining module, team, frontend/backend, or component-prop contracts
- Establishing a database shape that constrains an API

## Required Design Rules

### Hyrum's Law

Every observable behavior can become a dependency, including undocumented
quirks, error text, timing, and ordering. Be intentional about exposure, do not
leak implementation details, and plan deprecation at design time with
`tgd-release-migration`. Tests alone cannot prove that an observable change is
safe for every consumer.

### The One-Version Rule

Design for one current dependency or API version. Extend instead of forking;
avoid making consumers choose between incompatible versions and creating
diamond-dependency problems.

### Contract First

Define typed inputs, outputs, errors, idempotency, pagination, and compatibility
expectations before implementation. The contract is the spec; implementation
follows it.

### Consistent Error Semantics

Choose one error strategy and shape and apply it everywhere. REST interfaces
use consistent status semantics and a structured machine-readable error code
plus a safe human-readable message. Never expose internal details in server
errors. Do not mix throwing, nulls, and unrelated error objects across the same
interface family. For REST, use `400` invalid request, `401` unauthenticated,
`403` unauthorized, `404` missing resource, `409` conflict, `422` semantic
validation failure, and `500` safe server error.

### Validate at Boundaries

Validate external input at system edges, then let internal code rely on the
validated type contract. Boundaries include API routes, form submissions,
environment loading, and external-service responses. Third-party responses are
untrusted data: validate their shape and content before logic, rendering, or
decisions. Do not scatter redundant validation between internal functions that
already share a validated contract or around data just read from the system's
own database.

### Prefer Addition Over Modification

Extend existing contracts with backward-compatible optional fields. Do not
remove fields or change existing field types without a governed migration.

### Predictable Naming

| Surface | Convention |
|---|---|
| REST endpoints | Plural nouns, no verbs |
| Query parameters and response fields | `camelCase` |
| Boolean fields | `is` / `has` / `can` prefix |
| Enum values | `UPPER_SNAKE` |

## REST Contract Rules

- Model resources with collection and item routes; use sub-resources only for
  real containment relationships.
- Paginate every list endpoint and return enough metadata to navigate results.
- Express filters, sorting, and pagination through documented query parameters.
- Use `PATCH` for partial updates; only supplied fields change.
- Keep create input separate from output types containing generated identity,
  timestamps, ownership, or other server fields.

## Typed Interface Rules

- Use discriminated unions when variants have different required data.
- Separate caller input types from system output types.
- Use distinct or branded identifier types where confusing identities would be
  a meaningful correctness risk.
- Ensure consumers can handle every declared variant exhaustively.

Concrete REST and TypeScript shapes are illustrative, not policy. Load
[API Interface Patterns](../../references/api-interface-patterns.md) only when
a worked example would help; this skill remains the sole normative owner.

## Common Rationalizations

| Rationalization | Reality |
|---|---|
| "We'll document the API later" | The contract must exist before implementation. |
| "We don't need pagination for now" | Unbounded collections become a breaking operational problem. |
| "PATCH is complicated; use PUT" | Full replacement is not partial update semantics. |
| "We'll version when needed" | Ungoverned breaking changes already break consumers. |
| "Nobody uses that undocumented behavior" | Hyrum's Law says observable behavior can become a dependency. |
| "We can maintain two versions" | Versions multiply maintenance and dependency conflicts. |
| "Internal APIs don't need contracts" | Internal consumers are still consumers. |

## Red Flags

- Conditional response shapes or inconsistent error formats
- Validation scattered through trusted internal code instead of boundaries
- Existing field removal or type changes without migration
- List endpoints without pagination
- Verb-based REST paths such as `/api/createTask`
- Third-party responses used without validation or sanitization
- Public behavior whose compatibility and deprecation path are unspecified

## Verification

- [ ] Every interface has typed inputs and outputs.
- [ ] Error responses use one safe, consistent strategy.
- [ ] External data is validated at system boundaries.
- [ ] List endpoints paginate; filters and sorting are documented.
- [ ] Existing consumers remain compatible or have a governed migration.
- [ ] Naming is consistent across the interface family.
- [ ] Documentation or types are committed with the implementation.
