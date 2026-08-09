# Source Grounding Patterns

Illustrative examples only. Version detection, source authority, conflict
handling, implementation, and citation requirements live in
[`tgd-develop-source`](../skills/tgd-develop-source/SKILL.md).

## Manifest Mapping

```text
package.json / lockfile      → Node, React, Vue, Angular, Svelte
composer.json / lockfile     → PHP, Symfony, Laravel
requirements.txt / pyproject.toml → Python, Django, Flask
go.mod                       → Go
Cargo.toml                   → Rust
Gemfile / lockfile           → Ruby, Rails
```

## Detection Report Shape

```text
STACK DETECTED:
- React 19.1.0 (package.json)
- Vite 6.2.0 (package-lock.json)
- Tailwind CSS 4.0.3 (package-lock.json)

Retrieving the official pages relevant to the requested behavior.
```

## Specific Fetch Contrast

```text
Broad:    React homepage
Specific: react.dev/reference/react/useActionState

Broad:    "Django authentication best practices" search results
Specific: docs.djangoproject.com/<detected-version>/topics/auth/
```

## Docs-versus-Project Conflict Shape

```text
CONFLICT DETECTED

Existing project pattern:
  manual state for form submission

Current official pattern for the detected version:
  <documented API and deep source URL>

Options:
A. Adopt the documented current pattern and update the affected boundary.
B. Match the established project pattern and record the compatibility reason.

Which direction should govern this change?
```

## Code Citation Shape

```typescript
// Framework behavior for the detected version.
// Source: https://official.example/reference/api#usage
const result = documentedApi(input);
```

## Conversation Citation Shape

```text
Decision: use <current documented pattern> rather than <legacy pattern>.
Reason: the detected version's official guide deprecates the legacy path.
Source: https://official.example/migration#relevant-section
```

## Unverified Shape

```text
UNVERIFIED: No official documentation was found for this pattern. The current
idea may be outdated or unsupported; verify it before production use.
```
