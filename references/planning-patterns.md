# Planning Patterns

Illustrative examples only. Canonical fields, ordering, immutability, and gates
live in [`tgd-plan-breakdown`](../skills/tgd-plan-breakdown/SKILL.md) and the
repository TASKS.md/TRACKING-PLAN templates.

## Dependency Shape

```text
Database schema
├── API models and types
│   ├── endpoints
│   │   └── frontend client
│   │       └── UI components
│   └── validation logic
└── seed data and migrations
```

## Horizontal and Vertical Contrast

```text
Horizontal:
1. Build every database table
2. Build every endpoint
3. Build every component
4. Connect everything

Vertical:
1. User registration: schema + API + UI + test
2. Login: auth contract + API + UI + test
3. Task creation: schema + API + UI + test
4. Task list: query + API + UI + test
```

## Checkpoint Shape

```markdown
## Checkpoint: After Tasks 1-3
- [ ] All tests pass (`npm test`)
- [ ] Application builds (`npm run build`)
- [ ] Core user flow command passes (`npm run test:e2e -- registration`)
```

Repository-specific commands replace the illustrative npm commands.

## Instrumentation Criterion

```markdown
- **AC-4.1** — **Given** a user completes registration **When** the server
  responds 201 **Then** `sign_up_completed` is emitted with `method` and
  `platform`, and contains no PII
  - **Regression**: No
  - **Test**: [filled during /tgd-develop]
```

## Sizing Examples

| Size | Files | Illustrative scope |
|---|---:|---|
| XS | 1 | One function or configuration rule |
| S | 1–2 | One component or endpoint |
| M | 3–5 | One feature slice |
| L | 5–8 | Multi-component feature; split it |
| XL | 8+ | Too large; split it |
