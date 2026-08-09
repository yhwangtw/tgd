---
name: tgd-support-wiki
description: Compiles CodeGraph + Understand-Anything outputs into a self-contained single-file HTML wiki (wiki.html) plus a plain-Markdown docs tree. Every scanned repo gets the same fixed DeepWiki-style structure — home, overview, architecture, modules, flows, onboarding, source browser, search — only the data varies per project. Zero runtime dependencies beyond Python 3 stdlib; no node, npm, or build step. Standalone / manual skill — NOT part of the /tgd-map pipeline. Use when you explicitly want to generate or regenerate a project wiki from an existing knowledge graph under $TGD_DIR/.scans/.
---

# tGD Wiki Generation (Single-File HTML, Multi-Repo)

## Overview

Compile every repo graph under `$TGD_DIR/.scans/` into coordinated outputs at
`$TGD_DIR/wiki/`:

- `wiki.html`: a self-contained, offline human overview with fixed navigation,
  repo switching, KPIs, module/flow pages, inlined Mermaid, source browser, and
  client-side search. It opens directly without a server or build step.
- `docs/`: complete GitHub-flavored Markdown with manifests, repo pages,
  modules, flows, diagrams, and one explained page per source file.

Every project uses the same page skeleton from `assets/wiki-template.html` and
`scripts/generate-wiki.py`; only graph/source data changes. Artifact-side theme
or structure customization is unsupported—patch the skill assets instead.

## When to Use

Run manually after `/tgd-map` produced graphs, or regenerate after refreshing
those graphs. This skill is standalone and is **not** part of the Map pipeline.

## Inputs

Required: `$TGD_DIR` and
`.scans/<repo>/.understand-anything/knowledge-graph.json` for every scanned repo.

Optional:
- `.scans/<repo>/.codegraph/` when the CodeGraph CLI is available
- `wiki/wiki-prose.json` authored prose; missing/unreadable content degrades to
  deterministic graph-derived descriptions, never a hard dependency
- `--primary <slug>`, `--dashboard-url URL`, and `--max-source-lines N`
  (`--primary` defaults to the first scan, dashboard URL applies to that repo,
  and the source cap defaults to 1500 lines per file)

## Output Contract

`wiki.html` is the curated, shareable overview. `docs/` is the complete scalable
reference; its file subtree contains every source file's explanation, symbols,
and capped source. CONTEXT.md and `.scans/` remain untouched.

Each repo always gets home, overview, architecture, onboarding, files, one module
page per layer, one flow page per tour step, architecture/dependency diagram
sources, and a manifest. Top-level docs contain home, sources, and a manifest.

For concrete shapes, optionally load [Wiki Generation
Patterns](../../references/wiki-generation-patterns.md); this skill owns policy.

## Prose Sidecar

Resolve every prose slot as **Understand-Anything field → `wiki-prose.json` →
deterministic graph-derived sentence**.

The invoking agent may synthesize sidecar prose from the graph and source before
generation. Every key is optional. Per-file `hash` enables unchanged summaries
to be reused. Keep the sidecar under `$TGD_DIR/wiki/`, never the code repo.

All prose is Markdown: `docs/` emits it verbatim for GitHub, while the vendored
escape-first HTML renderer supports paragraphs, subheadings, emphasis, code,
lists, blockquotes, and links limited to `#` or HTTP(S); raw HTML is escaped.
Ground every claim in graph/source evidence—project-agnostic filler is invalid.

Content expectations: overview 2–4 paragraphs; architecture 1–3; onboarding a
narrated reading path; layers/modules 2–4 sentences; flows a sequence narrative;
files 1–2 sentences plus public-symbol notes.

The generator prints authored/derived coverage per repo, reports unmatched
sidecar repo keys, and makes missing/malformed sidecars visible rather than
silently ignoring them.

## Execution and Dependencies

```bash
: "${SKILL_DIR:?resolve the directory containing this SKILL.md}"
: "${TGD_DIR:?resolve the tGD artifacts directory}"
python3 "$SKILL_DIR/scripts/generate-wiki.py" "$TGD_DIR"
```

Python 3.8+ stdlib is the only required runtime; CodeGraph is optional. Mermaid
is vendored and inlined, degrading to readable source if absent. The command
normally takes about a second and hard-fails only when `$TGD_DIR` or every graph
is missing.

## Regeneration

Regeneration overwrites `wiki.html` and `docs/` and recreates manifests. Never
hand-edit generated outputs. Identical inputs produce identical structure aside
from timestamps, and stale generated files must not survive.

## Safety and Pitfalls

- Write only under `$TGD_DIR/`; never the code repo, home, or unrelated temp paths.
- Keep `wiki.html` fully offline: no CDN, fonts, fetches, or external scripts.
- Preserve `</` → `<\/` escaping inside embedded JSON to prevent raw
  `</script>` termination.
- Enforce `--max-source-lines` with a visible truncation marker; unbounded source
  makes the single-file overview unusable.
- Every manifest lists every page actually written and references only graph
  nodes that exist.

## Common Rationalizations

| Rationalization | Reality |
|---|---|
| "Use a static-site generator" | It restores dependencies, builds, and version drift. |
| "Let users theme the artifact" | Uniform structure is the design guarantee. |
| "Embed all source" | Explicit caps preserve the single-file promise. |
| "HTML alone is enough" | Agents and GitHub consume the Markdown/manifests. |

## Red Flags

- Output outside `$TGD_DIR/` or network activity from opened `wiki.html`
- Missing/stale pages or manifests that disagree with disk
- Descriptions blank despite the deterministic fallback
- Project-specific page structures instead of fixed structure
- Unsafe embedded JSON or uncapped source

## Verification

- [ ] `wiki.html` opens offline without console errors and renders home, overview, architecture Mermaid, modules, flows, source line links, and search.
- [ ] `docs/index.md`, `docs/manifest.json`, and top-level source inventory exist.
- [ ] Every scan has repo home/overview/architecture/onboarding/files, one file page per source, modules, optional tour flows, diagrams, and repo manifest.
- [ ] No description is blank; coverage output identifies authored/derived prose.
- [ ] Top-level manifest has one repo entry per scan and a `wikiHtml` key.
- [ ] No output exists outside `$TGD_DIR/`; opened HTML makes no network request.
- [ ] Re-running identical input is structurally idempotent and leaves no stale files.

## Related Skills

- `tgd-map`: produces scans but never auto-invokes this skill
- `understand`: produces the required knowledge graph
- `tgd-core-router`: routes explicit standalone wiki requests
