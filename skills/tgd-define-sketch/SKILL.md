---
name: tgd-define-sketch
description: "Throwaway HTML mockups: context-grounded design variants to compare when a UI direction is not already approved."
version: 1.0.0
author: Hermes Agent (adapted from gsd-build/get-shit-done)
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [sketch, mockup, design, ui, prototype, html, variants, exploration, wireframe, comparison]
    related_skills: [spike, claude-design, popular-web-designs, excalidraw]
---

# Sketch

## Overview

Build disposable, interactive HTML variants so a user can compare genuinely
different UI directions before committing. These are visual decision tools,
not production components.

## When to Use

- The user wants to see, compare, or mock up 2–3 UI directions
- Early design exploration benefits from visual evidence before implementation

Do not use for an approved direction. Production components or polished HTML
belong to `claude-design`; diagrams belong to `excalidraw`.

## Variant Location and Count

Inside `/tgd-define`, write only under
`$TGD_DIR/<feature-name>/prototype/` and obey the recorded mode:

- Existing approved design: **0 variants**; do not run this skill.
- Extend existing UI: **2 variants**, `conservative/` and `strong-fit/`.
- New experience: **3 variants**, adding `divergent/`.

Ad-hoc sketching produces 2–3 stance-named variants at a user-selected scratch
location. Never write sketches into the code repository root.

Outside tGD only, an installed `gsd-sketch` may provide persistent state and
audits. Inside Define, always use this skill because lifecycle gates inspect the
tGD prototype directory.

## Core Method

`intake → variants → head-to-head → pick or iterate`

### 1. Context-Grounded Intake

Inside tGD, read CONTEXT.md first, then follow `UI Landscape` paths to the real
design-system components, tokens, global styles, responsive definitions, and
approved external source. **CONTEXT.md is navigation, not the visual source of truth.** Read PRD.md
for the primary user, problem, and core action. Never invent a replacement
theme when the product already has one.

Unless already answered, ask **one question at a time**, briefly reflecting
each answer:

1. Desired feel: concrete adjectives, emotions, or vibe.
2. Real product/site references for that feel.
3. The screen's single most important user action.

### 2. Build Distinct Stances

Obey lifecycle count exactly; ad-hoc work gets 2–3. Build complete HTML rather
than describing options. Variants differ in a meaningful stance—density,
emphasis, aesthetic, layout, or grounding—not only color or pixel values.

`conservative` stays closest to the product, `strong-fit` is the recommended
evolution, and `divergent` appears only in three-variant exploration. Ad-hoc
names describe the stance, never a number.

### 3. Make Each Variant Real

Each stance contains `index.html` and README.md. HTML is self-contained with
inline CSS, no build step, realistic content, clickable affordances, hover, and
at least one meaningful state transition. System fonts, one linked Google Font,
or Tailwind CDN are acceptable for a throwaway mockup.

Open every file with `tgd-verify-browser` or platform browser tooling over
`file://`, capture and inspect a screenshot, fix visible failures, and re-check.
Source inspection is not visual evidence.

### 4. Explain and Compare

Each README names its design stance, key layout/type/color/interaction choices,
tradeoffs, strengths/weaknesses, and best-fit audience/use case.

After building all variants, show an opinionated head-to-head table across
meaningful dimensions, state which direction is strongest and why, identify the
weakest, then let the user pick, combine, or request another round.

Copyable folder, HTML reset, README, comparison, and token examples are
optional. Load [Sketch Patterns](../../references/sketch-patterns.md) only when
a concrete shape helps; this skill remains the normative owner.

## Theming

When a visual identity exists, place a minimal shared token file at
`prototype/themes/tokens.css` and import it from variants. Preserve existing
product tokens; do not over-tokenize disposable work—roughly three colors and
one font is usually enough.

## Interactivity Bar

A valid sketch lets the user:

1. click a primary action and see a visible result;
2. exercise one meaningful transition such as filter/toggle/open-close;
3. hover recognizable buttons, rows, or tabs.

More is over-engineering; less is effectively a screenshot.

## Frontier Mode

When asked what to sketch next, inspect existing work for consistency gaps,
unsketched referenced screens, missing empty/loading/error/large-data states,
responsive gaps, and untested interaction patterns. Propose 2–4 named
candidates and let the user choose.

## Output

- One stance directory with `index.html` and README.md per required variant.
- tGD output under the feature prototype path; ad-hoc output at the selected
  scratch path, never repository root.
- Give the platform command for opening each file (`open`, `xdg-open`, or
  `start`) and present screenshots/comparison.
- Keep sketches disposable. Promote a chosen direction into real project code
  rather than curating the prototype as production source.

## Common Rationalizations

- **“Build one version.”** One version is a prototype, not a comparison.
- **“Skip README.”** Without rationale, the user compares pixels, not choices.
- **“More variants are safer.”** More than three prevents meaningful comparison.

## Red Flags

- Recolors presented as alternatives
- Static or visibly unverified HTML
- Intake skipped despite missing feel, references, or core action
- More than three variants or production-quality overinvestment
- Output outside the required prototype/scratch boundary

## Verification

- [ ] Variant count and names match the lifecycle/ad-hoc mode.
- [ ] Every stance is materially different and grounded in real UI sources.
- [ ] Browser screenshots prove rendering and required interactivity.
- [ ] Each README explains choices and tradeoffs.
- [ ] Comparison is opinionated and recommends a direction.

## Attribution

Adapted from GSD `/gsd-sketch`, MIT © 2025 Lex Christopherson
([gsd-build/get-shit-done](https://github.com/gsd-build/get-shit-done)).
