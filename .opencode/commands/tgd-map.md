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
- **No env var → MUST ask. Always.** This is not only for first-time setup — an env var does not persist between sessions, so ask at the start of every `/tgd-map` run that has no env var. **The candidate directory already existing is NOT permission to skip the question** — an existing dir changes the wording, not the requirement:

  If `<candidate path>` does **not** exist yet:

  > 📂 tGD artifacts will be stored at: `<candidate path>`
  >
  > 1. Use this path (Enter)
  > 2. Use a different path (enter an absolute path)
  >
  > Choose one (default 1):

  If `<candidate path>` **already exists** (from a previous run):

  > 📂 Found existing tGD artifacts at: `<candidate path>` (CONTEXT.md: yes/no · features: N)
  >
  > 1. Reuse it (Enter)
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

- **Non-interactive mode** (CI, subagent delegation, no TTY) → Skip confirmation, proceed with candidate. Log: "📂 Using $TGD_DIR: `<candidate path>` (non-interactive)". This branch is for environments where asking is *impossible* — an interactive session with an existing dir does not qualify.

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
| **Tier 1 — Core** (always) | 1, 2, 6, 7 | Every `/tgd-map` run, no dependencies | `CONTEXT.md` |
| **Tier 2 — Deep scan + dashboards** | 3, 4, 5 | `codegraph` CLI / `understand` skill available; Step 5 dashboards additionally need `node`/`npm` | `.scans/<repo>/` symbol index + knowledge graph + one live localhost dashboard per repo |

**Degradation rule:** If a tier cannot run, you MUST record it in `CONTEXT.md` under `## Degraded Mode` — which steps were skipped, why (missing tool), and how to enable them later. A skipped step that is not logged is a verification failure. Silent skipping is the failure mode this rule exists to prevent.

**Do not** suggest installing missing tools unprompted beyond the one-line Degraded Mode note.

---

## Step 1: Context Discovery

Before analyzing anything, **ask the user — on every `/tgd-map` run**. An existing CONTEXT.md changes the wording of the question, never the requirement to ask (same rule as Step 0b):

If no `$TGD_DIR/CONTEXT.md` exists yet (first map):

> "除了當前 repo，還有其他需要參考的 repo 嗎？（local path 或 git URL）"

If `$TGD_DIR/CONTEXT.md` **already exists** with a repo list (re-map):

> 📚 上次 map 的 repo 清單：`<primary>` + `<additional repos, or "無">`
>
> 1. 沿用這份清單 (Enter)
> 2. 增加/移除 repo（輸入 local path 或 git URL，或要移除的名稱）
>
> Choose one (default 1):

- Accept **local paths** (e.g. `~/Projects/wayflow`) — resolve to absolute path
- Accept **git URLs** (e.g. `github.com/CopilotKit/CopilotKit`) — clone to `/tmp/tgd-context/<repo-name>`
- If user says "no" or provides nothing, proceed with primary repo only
- Store results for CONTEXT.md (see structure below)

Note: `tgd-context-engineering`'s "read CONTEXT.md's repo list instead of re-asking" rule applies to **downstream** commands (`/tgd-develop`, `/tgd-verify`, …) — it does NOT apply to `/tgd-map` itself. Map owns this question; downstream consumes the answer.

## Step 2: Context Engineering

Run the `tgd-context-engineering` skill. Analyze the current project: tech stack, architecture, dependencies, code organization, and existing patterns.

**⚠️ This is only Step 2. If Tier 2 is available (see Step 0.5), you MUST continue to Step 3 (CodeGraph) and Step 4 (Understand-Anything) before producing CONTEXT.md. If Tier 2 is unavailable, proceed to Step 6 and log the skips under `## Degraded Mode`.**

## Step 3: CodeGraph Setup (Tier 2 — requires `codegraph` CLI)

**Skip condition:** `codegraph` not on PATH → skip, log in `## Degraded Mode`, continue.

For each repo to map (primary + all additional repos from Step 1):

1. Ensure the symlink TARGET exists: `mkdir -p $TGD_DIR/.scans/<repo-name>/.codegraph` — the leaf dir included. A symlink to a not-yet-existing target is dangling: the tool's own `mkdir` fails with "File exists" (the symlink) while writes fail with "No such file or directory" (the missing target) — it dies both ways.
2. Create symlink: `rm -rf <repo-path>/.codegraph && ln -s $TGD_DIR/.scans/<repo-name>/.codegraph <repo-path>/.codegraph`
3. cd into the repo and run: `codegraph init -i`

## Step 4: Understand-Anything (Tier 2 — requires the `understand` skill)

**Skip condition (the ONLY one):** the `understand` skill is not loadable in this session → skip, log in `## Degraded Mode`, continue. Nothing else qualifies.

When the skill IS available, this step is **required**, not optional.

**Subagents are an optional optimization, never a prerequisite.** If context is getting long you MAY spawn a fresh subagent per repo to run the `understand` skill. But if you cannot spawn one — the platform doesn't support subagents, or you are yourself a subagent and cannot nest (Claude Code forbids nested subagents) — **run the `understand` skill inline in this context instead.**

> 🚫 **"I can't launch a subagent" is NOT a skip reason.** It is a rationalization the tGD rules exist to catch. The deliverable is the knowledge graph; it gets built inline just as well as in a subagent — delegation only moves *where* the work runs, never *whether* it runs. Skipping UA because delegation is unavailable is a verification failure, not a degraded mode.

For each repo to map (primary + all additional repos from Step 1):

1. Ensure the symlink TARGET exists first: `mkdir -p $TGD_DIR/.scans/<repo-name>/.understand-anything` (a dangling symlink kills the tool's writes — same trap as Step 3). Then create the symlink: `rm -rf <repo-path>/.understand-anything && ln -s $TGD_DIR/.scans/<repo-name>/.understand-anything <repo-path>/.understand-anything`
2. load and execute the `understand` skill to build a full knowledge graph
3. This produces `$TGD_DIR/.scans/<repo-name>/.understand-anything/knowledge-graph.json`
4. If unfamiliar with any repo, load the `understand-onboard` skill for a guided tour

## Step 5: Launch Dashboards (Tier 2 — auto-launch, one per repo, requires `node`/`npm`)

**Skip condition:** `node`/`npm` not on PATH, OR Step 4 produced no knowledge graph → skip, log in `## Degraded Mode`, continue. This is **not** opt-in — when its dependencies are present, the dashboard launches automatically.

The live dashboard serves **humans**, not the agent — `CONTEXT.md` and the knowledge graph are what downstream `/tgd-*` commands consume. Launch **one dashboard per repo** (primary + every additional repo from Step 1); each repo's knowledge graph gets its own dashboard on its own port.

For each repo:

1. Load the `understand-dashboard` skill and launch **in the background** — it must not block the rest of `/tgd-map`.
2. **The launch MUST set `GRAPH_DIR` to the repo's absolute path.** The dev server looks for the knowledge graph ONLY at `$GRAPH_DIR/.understand-anything/` (plus two cwd-relative fallbacks that never match in the tGD layout). Without `GRAPH_DIR`, Vite serves only its own `/public` assets and the graph fetch 404s — the dashboard opens but shows nothing. The exact launch shape (from the `understand-dashboard` skill):
   ```
   cd <ua-plugin-root>/packages/dashboard
   GRAPH_DIR=<absolute-repo-path> npx vite --host 127.0.0.1
   ```
   One instance per repo, each with its own `GRAPH_DIR`; Vite auto-picks the next free port. `<ua-plugin-root>` resolves the same way the `understand` skill resolves it (tGD installs it at `~/.understand-anything/repo`). The repo's `.understand-anything` is a symlink into `$TGD_DIR/.scans/` — that's fine, the server follows it.
3. Capture the localhost URL from the output. If it did not come up, log the failure in `## Degraded Mode` and continue with the other repos.
4. **Open it in the browser** — best-effort, per-OS: `open <url>` (macOS) · `xdg-open <url>` (Linux) · `start "" <url>` (Windows). If no display is available (headless / remote / CI session), skip the open silently — the URL is still captured and reported.

Record every dashboard URL for the final report and the CONTEXT.md `## See Also` section.

## Step 6: Produce CONTEXT.md

**Outputs (all under `$TGD_DIR/`):**
- `CONTEXT.md` — project structure analysis (MUST reference CodeGraph/UA data)
- `.scans/<repo>/.codegraph/codegraph.db` — symbol index (via symlink)
- `.scans/<repo>/.understand-anything/knowledge-graph.json` — full knowledge graph (via symlink)
- `.scans/<repo>/.understand-anything/config.json` — UA configuration
- **Interactive dashboards** — one per repo, launched via the `understand-dashboard` skill (localhost); present only when `node`/`npm` are available (else logged under `## Degraded Mode`)

**Authoring rules — read before writing (this is the ONE `/tgd-map` deliverable, so its quality is the whole point):**

1. **Ground every claim in evidence.** Structure/Summary/Entry Points come from the CodeGraph symbol index and the UA knowledge graph, or from files you actually opened — never from a guess at what a repo "probably" contains. If Tier 2 was skipped, say so per section rather than inventing.
2. **No blank sections, no placeholder text left in.** Every heading below gets real content. If a section genuinely has none (e.g. no CI, no rules file), write one line stating that fact (`No CI config found`) — an empty section or a leftover `<...>` placeholder is a verification failure.
3. **Pointer over copy for anything that changes.** For build/test/run commands and conventions, cite *where you found it* (`package.json` scripts, `Makefile`, `CLAUDE.md`) so a reader can re-verify. CONTEXT.md is a point-in-time snapshot, not a source of truth that outranks the repo — when in doubt it says "verify against `<file>`", it does not silently assert a stale value.
4. **Altitude-appropriate.** A navigational map, not a re-dump of the code. Name the important dirs/files/entry points and *why they matter*; link the detail to the knowledge graph rather than pasting it.

```markdown
# CONTEXT.md

## 1. Primary Repository
**Path:** <absolute path>
**Name:** <repo name>

### Analysis Coverage
<Prove the analysis actually covered the whole repo. State the REAL count from the Step 4 UA run — number of source files analyzed into the knowledge graph, and how many were excluded per `.understandignore` — then point at the graph. Example: "UA analyzed 247 source files across 3 languages; build/vendor/binary files excluded per .understandignore (node_modules, dist, lockfiles, images). Full detail: `.scans/<repo>/.understand-anything/knowledge-graph.json`." If UA was skipped, write exactly: "not analyzed — understand skill unavailable (see ## Degraded Mode)". Never invent a number.>

### Structure
<top 2-3 levels of the dir tree, each top-level dir annotated with what it holds — not an exhaustive `find` dump>

### Key Files
<the handful of files an engineer opens first, each with its one-line role>

### Summary
<tech stack, architecture, and the dominant patterns — synthesized from the UA knowledge graph, not guessed>

### Code Entry Points
<the real entry points from CodeGraph: main()/CLI/HTTP routes/exported API — with file:symbol>

## 2. Build / Test / Run
<The commands to work with this repo, each tagged with where you found it. Write "not detected" for any you cannot find in a real source — never invent one.>
- **Build:** `<cmd>`  _(source: package.json / Makefile / pyproject.toml / … )_
- **Test:** `<cmd>`  _(framework + where tests live, e.g. `jest`, tests in `tests/`)_
- **Lint / format:** `<cmd>`  _(or "none found")_
- **Run locally:** `<cmd>` + required env vars / services  _(from `.env.example`, `docker-compose.yml`, or the README)_

## 3. Conventions & Rules
<Pointers, not a rewrite of the rules. This is what downstream `/tgd-develop` must honor.>
- **Rules files present:** `CLAUDE.md` / `.cursorrules` / `AGENTS.md` / …  → downstream MUST read these before editing (or "none found")
- **Tests live in:** `<path>`, named `<pattern>`
- **Notable conventions:** naming, error handling, module boundaries — cite ONE existing example file per convention so it can be copied, not guessed

## 4. Additional Context Repositories
(For each additional repo provided in Step 1:)

### <repo-name> (<type: local_path | git_url>)
**Source:** <original input>
**Resolved to:** <absolute path or clone path>
**Summary:** <what this repo does>

**Key Insights:**
- <insight 1>
- <insight 2>

**Relevance:** <why this repo is relevant to the primary project>

## 5. Synthesis
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
- Knowledge graph (per repo, agent-readable): `$TGD_DIR/.scans/<repo>/.understand-anything/knowledge-graph.json` — the authoritative "where things live" map. Query it for symbol/file/dependency detail instead of duplicating a file table here (a copied table drifts; the graph is regenerated each `/tgd-map`).
- Interactive Dashboards (one per repo; only when node/npm present):
  - <primary-repo-name>: http://localhost:<port>
  - <additional-repo-name>: http://localhost:<port>
```

## Step 7: Verification Gate (tier-conditional)

**Tier 1 (always required):**
- [ ] `$TGD_DIR/CONTEXT.md` exists and is non-empty
- [ ] **No section is blank and no `<...>` placeholder survives** — every heading has real content or an explicit "not detected" / "none found" line (Authoring rule 2)
- [ ] `## 2. Build / Test / Run` names build, test, lint, and run — each a real command with its source, or "not detected"
- [ ] `## 3. Conventions & Rules` lists any rules files (or "none found") and where tests live
- [ ] `### Analysis Coverage` is present for every repo — either a real file count from the UA run or the exact string "not analyzed — understand skill unavailable (see ## Degraded Mode)"
- [ ] If any Tier 2 step was skipped: `## Degraded Mode` section in CONTEXT.md lists every skip with its reason
- [ ] If additional repos were provided, their summaries appear in CONTEXT.md
- [ ] The run ends with the **Step 8 Final Report** — every line a real value or an explicit `skipped — <reason>`; a run that ends without it fails this gate

**Tier 2 (required if the tools were available — cross-check against Step 0.5 probe):**
- [ ] `$TGD_DIR/.scans/<repo>/.codegraph` symlink exists
- [ ] `$TGD_DIR/.scans/<repo>/.understand-anything` symlink exists
- [ ] `$TGD_DIR/.scans/<repo>/.understand-anything/knowledge-graph.json` exists
- [ ] Because UA ran, each repo's `### Analysis Coverage` states a **real file count** (the whole-repo scan happened) — NOT "not analyzed"
- [ ] If `node`/`npm` present: a dashboard was launched for **each** repo and its localhost URL is recorded in `## See Also` (or the skip/failure is logged in `## Degraded Mode`)

**Gate integrity rule:** a Tier 2 checkbox may only be marked N/A if Step 0.5 proved the tool missing AND the skip is logged in Degraded Mode. "Tool probably missing" is not evidence — show the `command -v` output.

## Step 8: Final Report (MANDATORY — the run's LAST message)

The LAST message of every `/tgd-map` run MUST be this report, fully filled in. Links recorded mid-run don't count — the user reads the end, not the middle. A run that finishes without this report fails the gate. **Every line must be either a real value or `skipped — <reason from Degraded Mode>`. Silence is not an option for any line.**

```
✅ /tgd-map 完成

📂 $TGD_DIR: <path>
📚 Repos mapped: <primary> (+ <additional>, or 無)
📊 Dashboards:
   - <repo-name>: http://localhost:<port>
   - <repo-name>: http://localhost:<port>
   or: skipped — <reason, e.g. "node/npm missing (Degraded Mode)">
⚠️ Degraded Mode: <none / one line per skipped step with its reason>

Next: /tgd-define
```
