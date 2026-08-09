---
name: tgd-develop-ui
description: Builds production-quality UIs. Use when building or modifying user-facing interfaces. Use when creating components, implementing layouts, managing state, or when the output needs to look and feel production-quality rather than AI-generated.
---

# Frontend UI Engineering

## Overview

Build accessible, performant, visually polished interfaces that follow the
actual product system rather than a generic generated aesthetic.

**Before implementing UI, read `$TGD_DIR/CONTEXT.md`, the real UI source files
it identifies, and `$TGD_DIR/<feature-name>/DESIGN.md`.** Apply this exact
precedence: **Existing design system > approved DESIGN.md additions > tGD fallback defaults**.
CONTEXT.md locates sources; it does not replace them.
DESIGN.md owns the approved feature direction, flow, component mapping, states,
and justified additions. This skill must not silently replace the visual system.

## When to Use

- Building or modifying components, pages, layouts, or user-visible states
- Adding interaction, state management, responsiveness, or transitions
- Fixing visual, usability, or accessibility defects

## Component Architecture

- Colocate a component with its tests, stories, focused hooks, and local types.
- Prefer composition over configuration-heavy components.
- Keep components focused; split components that exceed 200 lines.
- Separate remote-data orchestration from presentational rendering.
- Always render meaningful loading, error, and empty states.

## State Management

Choose the smallest scope that preserves behavior:

| State | Default home |
|---|---|
| Component-only UI | Local state |
| Two or three siblings | Lifted state |
| Theme, auth, locale | Context |
| Filters, pagination, shareable views | URL state |
| Cached remote data | Server-state library |
| Complex app-wide client state | Global store |

Avoid prop drilling through more than three levels; restructure or introduce a
proper shared boundary when intermediate components do not use the data.

## Design System Adherence

- Use the project's spacing scale, typography hierarchy, semantic colors,
  radius hierarchy, shadows, and component primitives; never invent arbitrary
  pixels or raw colors when tokens exist.
- Use one page `h1`, preserve heading order, and do not style non-headings as
  headings.
- Meet contrast of 4.5:1 for normal text and 3:1 for large text.
- Never use color as the only state signal.
- Reject generic AI defaults: indiscriminate purple/indigo, excessive
  gradients or rounding, generic heroes, lorem ipsum, uniform card grids,
  oversized padding, and shadow-heavy hierarchy.
- Use realistic content and a layout driven by information priority.

## Accessibility (WCAG 2.1 AA)

Every component must:

- Use native semantic interactive elements where possible and support complete
  keyboard operation.
- Provide visible labels or accessible names for controls and form inputs.
- Preserve a logical focus order, move focus after state changes, and contain
  focus for modal interactions.
- Expose status, error, empty, and loading changes to assistive technology.
- Preserve semantic structure for screen readers.

Load the detailed [Accessibility Checklist](../../references/accessibility-checklist.md)
when implementing or verifying accessibility. Its tool recipes supplement, but
do not replace, the requirements above.

## Responsive Design

Design mobile-first, then expand. Verify at **320px, 768px, 1024px, and
1440px**.

## Loading and Transitions

- Prefer layout-preserving skeletons for content loading and expose busy state.
- Use optimistic updates only with a reliable rollback path.
- Keep loading, error, and empty states coherent.

Concrete component trees and React/CSS recipes are illustrative. Load
[UI Engineering Patterns](../../references/ui-engineering-patterns.md) only
when a worked example helps; this skill remains the sole normative owner.

## Common Rationalizations

| Rationalization | Reality |
|---|---|
| "Accessibility is a nice-to-have" | It is a quality standard and often a legal requirement. |
| "We'll make it responsive later" | Retrofitting responsive behavior is harder than designing it in. |
| "The design isn't final, so skip styling" | Use approved design-system defaults. |
| "This is just a prototype" | Prototypes frequently become production foundations. |
| "The AI aesthetic is fine for now" | It ignores the product's actual visual language. |

## Red Flags

- Components over 200 lines without a clear reason
- Inline styles, raw colors, or arbitrary pixel values despite available tokens
- Missing loading, error, or empty states
- No keyboard or screen-reader verification
- Color-only state signals
- Generic generated visual patterns that conflict with the approved design
- Responsive claims without the required viewport evidence

## Verification

- [ ] UI renders without console errors.
- [ ] All interactions work by keyboard and have accessible names.
- [ ] Screen readers can convey the page's content and structure.
- [ ] 320px, 768px, 1024px, and 1440px layouts pass.
- [ ] Loading, error, and empty states are handled.
- [ ] Spacing, color, typography, radius, and components follow precedence.
- [ ] DevTools or axe-core reports no accessibility violations.
