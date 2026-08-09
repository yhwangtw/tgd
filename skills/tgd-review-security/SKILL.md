---
name: tgd-review-security
description: Hardens code against vulnerabilities. Use when handling user input, authentication, data storage, or external integrations. Use when building any feature that accepts untrusted data, manages user sessions, or interacts with third-party services.
---

# Security and Hardening

## Overview

Treat every external input as hostile, every secret as sacred, and every authorization check as mandatory. Security is a constraint on every line touching user data, authentication, or external systems.

## When to Use

- Accepting user input or handling uploads, webhooks, or callbacks
- Implementing authentication or authorization
- Storing or transmitting sensitive, payment, or PII data
- Integrating with an external API or service

## Three-Tier Boundary System

### Always Do — No Exceptions

- Validate all external input at system boundaries, using allowlists and schema validation where possible
- Parameterize every database query; never concatenate user input into SQL
- Encode output and retain framework auto-escaping; sanitize any deliberately rendered HTML
- Use HTTPS for every external communication
- Hash passwords with bcrypt, scrypt, or argon2; never store plaintext
- Configure CSP, HSTS, X-Frame-Options, and X-Content-Type-Options
- Use `httpOnly`, `secure`, and `sameSite` cookies for sessions
- Authenticate protected endpoints and authorize every resource/action, including ownership and role checks
- Run `npm audit` or the ecosystem equivalent before every release

### Ask First — Human Approval Required

- Add or change authentication flows
- Store a new category of sensitive data
- Add an external service integration or file-upload handler
- Change CORS, rate limiting, or throttling
- Grant elevated permissions or roles

### Never Do

- Commit secrets or log passwords, tokens, or full card numbers
- Trust client-side validation as a security boundary
- Disable security headers for convenience
- Use `eval()` or `innerHTML` with user-provided data
- Store auth sessions or tokens in client-accessible storage such as localStorage
- Expose stack traces, queries, or internal error details to users

## Security Review Workflow

1. **Map boundaries:** Identify user, API, webhook, file, configuration, log, database, and third-party inputs; treat all as untrusted until validated.
2. **Trace identity and access:** For every protected operation, verify authentication, authorization, ownership/role, session expiry, and least privilege.
3. **Review data flow:** Check validation, parameterization, output encoding, sensitive-field filtering, transport protection, logging, and storage.
4. **Review platform controls:** Check headers, restrictive CORS, rate limits, generic errors, secret handling, and upload type/size/content checks.
5. **Audit dependencies:** Triage vulnerabilities by severity, production reachability, exploitability, and fix availability. Fix reachable critical/high issues immediately. For unreachable or dev-only high issues, fix soon and document rationale. Fix reachable moderate issues in the next release cycle; track dev-only moderate issues in the backlog, and handle low issues during regular updates. Any deferral needs a reason and review date.
6. **Verify:** Exercise the controls, rerun dependency and secret checks, and record evidence.

The OWASP mapping, implementation recipes, commands, and copyable checklist in [`../../references/security-checklist.md`](../../references/security-checklist.md) are illustrative. The boundaries and workflow above remain authoritative.

## Required Control Areas

- **Injection:** Parameterized queries, schema validation, no unsanitized shell or HTML sinks
- **Authentication:** Strong password hashing, expiring sessions/reset tokens, and rate-limited login
- **Access control:** Authorization on every action and ownership check on each resource
- **Misconfiguration:** Security headers, known-origin CORS, minimal permissions, and generic production errors
- **Sensitive data:** Environment-backed secrets, filtered API responses, protected storage and transport
- **Uploads and outbound requests:** Restricted size/type/content and validated or allowlisted URLs

## Common Rationalizations

| Rationalization | Reality |
|---|---|
| "This is an internal tool, security doesn't matter" | Internal tools are still attack paths. |
| "We'll add security later" | Retrofitting is harder than building the boundary correctly. |
| "No one would try to exploit this" | Automated scanners will. Obscurity is not security. |
| "The framework handles security" | Frameworks provide tools, not correct use. |
| "It's just a prototype" | Prototypes often become production. |

## Red Flags

- User input flows directly into database queries, shell commands, redirects, or HTML
- Secrets appear in source, staging diffs, logs, or history
- Protected endpoints lack authentication, authorization, or ownership checks
- CORS is missing or uses wildcard origins
- Authentication endpoints have no rate limiting
- Production responses expose stack traces or internals
- Reachable critical/high dependency vulnerabilities remain unresolved

## Verification

- [ ] `npm audit` shows no critical or high vulnerabilities
- [ ] No secret exists in source, staged diff, logs, or history
- [ ] Every external input is validated at a system boundary
- [ ] Authentication and authorization protect every required endpoint and resource
- [ ] Security headers are present in actual responses
- [ ] CORS is restricted and auth endpoints are rate-limited
- [ ] Error responses expose no internals
- [ ] Sensitive fields are excluded from API responses and logs
