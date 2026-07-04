---
description: Map — scan and understand the existing project context before making changes
---

**🔑 Step 0: $TGD_DIR Resolution**

$TGD_DIR is where ALL tGD artifacts live. It is a **sibling directory** outside your code repo.

**Step 0a: Resolve candidate path** (in order):
1. If env var `$TGD_DIR` is set → candidate = `$TGD_DIR`
2. Otherwise → candidate = `../<project-name>-tGD/`

**Step 0b: Confirm $TGD_DIR with user:**

- **$TGD_DIR already set (env var)** → Inform user: "📂 Using $TGD_DIR: `$TGD_DIR`" and proceed. No need to block.
- **First-time setup** (no env var) → **MUST ask:**

  > 📂 tGD artifacts will be stored at: `<candidate path>`
  >
  > 1. Use this path (Enter)
  > 2. Use a different path (enter an absolute path)
  >
  > Choose one (default 1):

  - **Choice 1 (or Enter)** → `mkdir -p "$TGD_DIR" && export TGD_DIR="$TGD_DIR"`
  - **Choice 2** →
    ```
    TGD_DIR="<user-provided-path>"
    mkdir -p "$TGD_DIR"
    export TGD_DIR="$TGD_DIR"
    ```

- **Non-interactive mode** (CI, subagent delegation, no TTY) → Skip confirmation, proceed with candidate. Log: "📂 Using $TGD_DIR: `<candidate path>` (non-interactive)"

Result:
```
~/my-project/              ← your code (current dir)
├── src/

~/my-project-tGD/          ← $TGD_DIR (all artifacts here)
├── CONTEXT.md
├── .scans/
└── <feature>/
```

After this step, ALL subsequent commands use `$TGD_DIR` env var.

---

**🔍 Step 0.5: Dependency Check & Tier Resolution**

Probe the environment BEFORE starting, and decide which tiers run. Do this explicitly — steps must never be silently skipped:

```bash
command -v codegraph && echo "codegraph: OK" || echo "codegraph: MISSING"
command -v node && command -v npm && echo "node/npm: OK" || echo "node/npm: MISSING"
# understand skill: check whether the `understand` skill is loadable in this session
```

| Tier | Steps | Runs when | Output |
|------|-------|-----------|--------|
| **Tier 1 — Core** (always) | 1, 2, 7, 8 | Every `/tgd-map` run, no dependencies | `CONTEXT.md` |
| **Tier 2 — Deep scan** | 3, 4 | `codegraph` CLI / `understand` skill available | `.scans/<repo>/` symbol index + knowledge graph |
| **Tier 3 — Human-facing docs** (opt-in) | 5, 6 | User passed `--wiki` (or explicitly asks) AND Tier 2 completed AND `node`/`npm` present | Dashboard + Docusaurus wiki |

**Degradation rule:** If a tier cannot run, you MUST record it in `CONTEXT.md` under `## Degraded Mode` — which steps were skipped, why (missing tool), and how to enable them later. A skipped step that is not logged is a verification failure. Silent skipping is the failure mode this rule exists to prevent.

**Do not** suggest installing missing tools unprompted beyond the one-line Degraded Mode note.

---

## Step 1: Context Discovery

Before analyzing anything, ask the user:

> "除了當前 repo，還有其他需要參考的 repo 嗎？（local path 或 git URL）"

- Accept **local paths** (e.g. `~/Projects/wayflow`) — resolve to absolute path
- Accept **git URLs** (e.g. `github.com/CopilotKit/CopilotKit`) — clone to `/tmp/tgd-context/<repo-name>`
- If user says "no" or provides nothing, proceed with primary repo only
- Store results for CONTEXT.md (see structure below)

## Step 2: Context Engineering

Run the `tgd-context-engineering` skill. Analyze the current project: tech stack, architecture, dependencies, code organization, and existing patterns.

**⚠️ This is only Step 2. If Tier 2 is available (see Step 0.5), you MUST continue to Step 3 (CodeGraph) and Step 4 (Understand-Anything) before producing CONTEXT.md. If Tier 2 is unavailable, proceed to Step 7 and log the skips under `## Degraded Mode`.**

## Step 3: CodeGraph Setup (Tier 2 — requires `codegraph` CLI)

**Skip condition:** `codegraph` not on PATH → skip, log in `## Degraded Mode`, continue.

For each repo to map (primary + all additional repos from Step 1):

1. Ensure output dir exists: `mkdir -p $TGD_DIR/.scans/<repo-name>`
2. Create symlink: `rm -rf <repo-path>/.codegraph && ln -s $TGD_DIR/.scans/<repo-name>/.codegraph <repo-path>/.codegraph`
3. cd into the repo and run: `codegraph init -i`

## Step 4: Understand-Anything (Tier 2 — requires the `understand` skill)

**Skip condition:** `understand` skill not loadable in this session → skip, log in `## Degraded Mode`, continue.

When the skill IS available, this step is **required**, not optional.

**You MAY use subagent delegation to execute this step.** If context is getting long, spawn a fresh subagent to run the `understand` skill on each repo.

For each repo to map (primary + all additional repos from Step 1):

1. Create symlink: `rm -rf <repo-path>/.understand-anything && ln -s $TGD_DIR/.scans/<repo-name>/.understand-anything <repo-path>/.understand-anything`
2. load and execute the `understand` skill to build a full knowledge graph
3. This produces `$TGD_DIR/.scans/<repo-name>/.understand-anything/knowledge-graph.json`
4. If unfamiliar with any repo, load the `understand-onboard` skill for a guided tour

## Step 5: Launch Dashboard (Tier 3 — opt-in)

**Run condition:** user passed `--wiki` or explicitly asked for the dashboard, AND Step 4 completed. Otherwise skip (no Degraded Mode entry needed — Tier 3 is opt-in, not degraded).

The dashboard and wiki serve **humans**, not the agent — `CONTEXT.md` and the knowledge graph are what downstream `/tgd-*` commands consume. Don't pay the cost (npm install, localhost server) unless a human asked for it.

When it runs, for each repo (primary + all additional repos from Step 1):

1. cd into the repo
2. Load the `understand-dashboard` skill to launch the dashboard
3. Verify the dashboard is running (check for localhost URL in output)
4. Report the dashboard URL to the user

## Step 6: Generate tGD Wiki (Tier 3 — opt-in)

**Run condition:** same as Step 5, plus `node`/`npm` present.

Load and execute the `tgd-wiki-generation` skill.

This compiles the CodeGraph + Understand-Anything outputs into a browsable
Docusaurus 3 documentation site with a uniform DeepWiki-style layout — same
brand colors, Grid Cards, and React components across every project.

**Command sequence:**

```bash
python "$TGD_REPO_ROOT/skills/tgd-wiki-generation/scripts/generate-wiki.py" "$TGD_DIR"
python "$TGD_REPO_ROOT/skills/tgd-wiki-generation/scripts/generate-docusaurus-config.py" "$TGD_DIR"
bash   "$TGD_REPO_ROOT/skills/tgd-wiki-generation/scripts/build-site.sh" "$TGD_DIR"
```

Resolve `$TGD_REPO_ROOT` to the cloned tGD repo (typically `~/tGD/`).

**Outputs (all under `$TGD_DIR/wiki/`):**

- `docs/index.mdx` — top-level home with repo selector grid
- `docs/search.mdx` — offline local search UI (repo/module/symbol/source)
- `docs/sources.mdx` — all-repos summary page
- `docs/manifest.json` — top-level manifest listing every scanned repo
- `docs/repos/<slug>/` — one full wiki tree per scanned repo, containing:
  - `index.mdx`, `overview.mdx`, `architecture.mdx`, `onboarding.mdx`
  - `modules/<layer>.mdx` — one page per architectural layer
  - `flows/<step>.mdx` — one page per tour step
  - `source/<file>.mdx` — offline source browser with line anchors for symbol jumps
  - `diagrams/{architecture,dependencies}.mmd` — Mermaid source
  - `manifest.json` — per-repo machine-readable index
- `docusaurus.config.ts`, `sidebars.ts`, `package.json`, `.gitignore` — auto-generated (config has a Repos dropdown when >1 repo scanned)
- `src/components/*.tsx` and `src/css/custom.css` — copied from skill assets (do not edit)
- `build/index.html` — built static site (if `npm` is installed)

**Behavior:**

- MDX content is always produced. If `node`/`npm` is missing, `build-site.sh`
  logs a warning and continues — MDX under `docs/` remains readable.
- First run does `npm install` (~2 min). Subsequent runs reuse `node_modules/`.
- Re-running overwrites `docs/`, `src/components/`, `src/css/`, and generated
  config files in place. `manifest.json` and `docs/` are the source of truth
  for agents — do not hand-edit.

**Report to the user:**

- Site URL if built: `http://localhost:3000` (after `cd $TGD_DIR/wiki && npm run serve`)
- Dev mode with hot reload: `cd $TGD_DIR/wiki && npm run start`
- Wiki path: `$TGD_DIR/wiki/docs/index.mdx`
- Manifest path: `$TGD_DIR/wiki/docs/manifest.json`

## Step 7: Produce CONTEXT.md

**Outputs (all under `$TGD_DIR/`):**
- `CONTEXT.md` — project structure analysis (MUST reference CodeGraph/UA data)
- `.scans/<repo>/.codegraph/codegraph.db` — symbol index (via symlink)
- `.scans/<repo>/.understand-anything/knowledge-graph.json` — full knowledge graph (via symlink)
- `.scans/<repo>/.understand-anything/config.json` — UA configuration
- **Interactive dashboard** — launched via the `understand-dashboard` skill (localhost)

**CONTEXT.md Structure:**
When writing `CONTEXT.md`, DO NOT rely solely on visual inspection of code.
Synthesize data from the tools:

```markdown
# CONTEXT.md

## 1. Primary Repository
**Path:** <absolute path>
**Name:** <repo name>

### Structure
<directory tree>

### Key Files
<important files and their roles>

### Summary
<tech stack, architecture, patterns — from UA knowledge graph>

### Code Entry Points
<from CodeGraph>

## 2. Additional Context Repositories
(For each additional repo provided in Step 1:)

### <repo-name> (<type: local_path | git_url>)
**Source:** <original input>
**Resolved to:** <absolute path or clone path>
**Summary:** <what this repo does>

**Key Insights:**
- <insight 1>
- <insight 2>

**Relevance:** <why this repo is relevant to the primary project>

## 3. Synthesis
### Integration Points
- <how repos relate to each other>

### Architecture Decisions
- <key decisions based on combined context>

### Open Questions
- <unresolved questions>

## Degraded Mode
(Only if Tier 2 steps were skipped. List each skipped step, the missing dependency, and how to enable it later. Delete this section if Tier 2 ran in full.)
- Step 3 (CodeGraph): skipped — `codegraph` not installed. Enable: install codegraph, re-run `/tgd-map`.

## See Also
- Interactive Dashboard: http://localhost:<port> (only if Tier 3 ran)
```

## Step 8: Verification Gate (tier-conditional)

**Tier 1 (always required):**
- [ ] `$TGD_DIR/CONTEXT.md` exists and is non-empty
- [ ] If any Tier 2 step was skipped: `## Degraded Mode` section in CONTEXT.md lists every skip with its reason
- [ ] If additional repos were provided, their summaries appear in CONTEXT.md

**Tier 2 (required if the tools were available — cross-check against Step 0.5 probe):**
- [ ] `$TGD_DIR/.scans/<repo>/.codegraph` symlink exists
- [ ] `$TGD_DIR/.scans/<repo>/.understand-anything` symlink exists
- [ ] `$TGD_DIR/.scans/<repo>/.understand-anything/knowledge-graph.json` exists

**Tier 3 (required only if the user opted in):**
- [ ] **Dashboard is running** (localhost URL confirmed)
- [ ] `$TGD_DIR/wiki/docs/index.mdx` and `$TGD_DIR/wiki/docs/manifest.json` exist
- [ ] `$TGD_DIR/wiki/docusaurus.config.ts`, `sidebars.ts`, `package.json` exist
- [ ] `$TGD_DIR/wiki/src/components/ModuleCard.tsx` and `src/css/custom.css` exist (copied from skill)
- [ ] If `npm` is installed: `$TGD_DIR/wiki/build/index.html` exists

**Gate integrity rule:** a Tier 2 checkbox may only be marked N/A if Step 0.5 proved the tool missing AND the skip is logged in Degraded Mode. "Tool probably missing" is not evidence — show the `command -v` output.

If verification passes, suggest the next step: `/tgd-define` to start defining what to build.
