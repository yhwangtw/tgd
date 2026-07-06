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
| **Tier 2 — Deep scan + wiki + dashboards** | 3, 4, 5, 6 | `codegraph` CLI / `understand` skill available; Step 5 dashboards additionally need `node`/`npm` | `.scans/<repo>/` symbol index + knowledge graph + `wiki/wiki.html` (single-file, python3-only, ~1s) + one live localhost dashboard per repo |

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

## Step 5: Launch Dashboards (Tier 2 — auto-launch, one per repo, requires `node`/`npm`)

**Skip condition:** `node`/`npm` not on PATH, OR Step 4 produced no knowledge graph → skip, log in `## Degraded Mode`, continue. This is **not** opt-in — when its dependencies are present, the dashboard launches automatically, the same as the wiki.

The live dashboard serves **humans**, not the agent — `CONTEXT.md` and the knowledge graph are what downstream `/tgd-*` commands consume. Launch **one dashboard per repo** (primary + every additional repo from Step 1); each repo's knowledge graph gets its own dashboard on its own port.

For each repo:

1. cd into the repo
2. Load the `understand-dashboard` skill to launch the dashboard **in the background** — it must not block the rest of `/tgd-map`.
3. Capture the localhost URL from the skill's output (each repo lands on a distinct port). If it did not come up, log the failure in `## Degraded Mode` and continue with the other repos.
4. **Open it in the browser** — best-effort, per-OS: `open <url>` (macOS) · `xdg-open <url>` (Linux) · `start "" <url>` (Windows). If no display is available (headless / remote / CI session), skip the open silently — the URL is still captured and reported.

Record every dashboard URL for the final report and the CONTEXT.md `## See Also` section.

## Step 6: Generate tGD Wiki (Tier 2 — runs automatically after Step 4)

**Run condition:** Step 4 produced at least one knowledge graph. No other dependencies — python3 only, ~1 second, no build step.

Load and execute the `tgd-wiki-generation` skill.

This compiles the CodeGraph + Understand-Anything outputs into a
**single self-contained HTML file** with a uniform DeepWiki-style layout —
the same page structure (home, overview, architecture, modules, flows,
onboarding, source browser, search) for every project; only the data varies.

**Command:**

```bash
python3 "$TGD_REPO_ROOT/skills/tgd-wiki-generation/scripts/generate-wiki.py" "$TGD_DIR"
```

Resolve `$TGD_REPO_ROOT` to the cloned tGD repo (typically `~/tGD/`).

**Outputs (all under `$TGD_DIR/wiki/`):**

- `wiki.html` — the human-facing wiki. Single file, Mermaid renderer inlined,
  works offline, opens by double-clicking. Share it by sending one file.
- `docs/index.md` — home: repo table
- `docs/sources.md` — source inventory
- `docs/manifest.json` — top-level manifest listing every scanned repo
- `docs/repos/<slug>/` — the SAME Markdown tree per scanned repo:
  - `index.md`, `overview.md`, `architecture.md`, `onboarding.md`
  - `modules/<layer>.md` — one page per architectural layer
  - `flows/<step>.md` — one page per tour step
  - `diagrams/{index.md,architecture.mmd,dependencies.mmd}` — Mermaid source
  - `manifest.json` — per-repo machine-readable index

**Behavior:**

- Re-running overwrites `wiki.html` and `docs/` in place. `manifest.json`
  and `docs/` are the source of truth for agents — do not hand-edit.
- GitHub renders the `docs/*.md` tree (including Mermaid) natively if
  committed anywhere.

**Open and report to the user:**

- **Open** `$TGD_DIR/wiki/wiki.html` in the browser — best-effort, per-OS: `open` (macOS) · `xdg-open` (Linux) · `start ""` (Windows). If headless / remote / CI, skip the open silently.
- Report it as **the one page the user opens** — there is no "which page": `wiki.html` is a single self-contained file that lands on the home view (repo grid / repo home) with everything else (overview, architecture, modules, flows, onboarding, source browser, search) as navigation inside it. Works offline, opens by double-clicking:
  > 👉 Wiki: `$TGD_DIR/wiki/wiki.html`
- Do NOT list `docs/manifest.json` or the `docs/` Markdown tree in the user-facing report — those are the **agent / GitHub** entry point, not something the user opens. Keep them out of the human's line of sight.

## Step 7: Produce CONTEXT.md

**Outputs (all under `$TGD_DIR/`):**
- `CONTEXT.md` — project structure analysis (MUST reference CodeGraph/UA data)
- `.scans/<repo>/.codegraph/codegraph.db` — symbol index (via symlink)
- `.scans/<repo>/.understand-anything/knowledge-graph.json` — full knowledge graph (via symlink)
- `.scans/<repo>/.understand-anything/config.json` — UA configuration
- **Interactive dashboards** — one per repo, launched via the `understand-dashboard` skill (localhost); present only when `node`/`npm` are available (else logged under `## Degraded Mode`)

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
- Wiki: $TGD_DIR/wiki/wiki.html
- Interactive Dashboards (one per repo; only when node/npm present):
  - <primary-repo-name>: http://localhost:<port>
  - <additional-repo-name>: http://localhost:<port>
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
- [ ] `$TGD_DIR/wiki/wiki.html` exists (single-file wiki)
- [ ] `$TGD_DIR/wiki/docs/index.md` and `$TGD_DIR/wiki/docs/manifest.json` exist
- [ ] If `node`/`npm` present: a dashboard was launched for **each** repo and its localhost URL is recorded in `## See Also` (or the skip/failure is logged in `## Degraded Mode`)

**Gate integrity rule:** a Tier 2 checkbox may only be marked N/A if Step 0.5 proved the tool missing AND the skip is logged in Degraded Mode. "Tool probably missing" is not evidence — show the `command -v` output.

If verification passes, suggest the next step: `/tgd-define` to start defining what to build.
