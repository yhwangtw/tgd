---
name: tgd-map
description: Map — scan and understand the existing project context before making changes
---

**⚠️ Closing requirement — read this FIRST:** the run's LAST message MUST be the **Step 8 Final Report** (exact format at the end of this command). Plan for it from the start — a run that ends with a free-form summary instead fails the Verification Gate.

## Step 0: Resolve `$TGD_DIR`

$TGD_DIR is where ALL tGD artifacts live. It is a **sibling directory** outside your code repo.

Resolve the candidate in order: the `$TGD_DIR` environment variable, then `../<project-name>-tGD/`.

- If the environment variable is set, report `📂 Using $TGD_DIR: <path>` and proceed.
- **No env var → MUST ask. Always.** This is not only for first-time setup — an env var does not persist between sessions, so ask at the start of every `/tgd-map` run that has no env var. **The candidate directory already existing is NOT permission to skip the question** — an existing dir changes the wording, not the requirement:

  ```text
  📂 <"tGD artifacts will be stored at" or "Found existing tGD artifacts at">: <candidate>
  1. <"Use this path" or "Reuse it"> (Enter)
  2. Use a different path (enter an absolute path)

  Choose one (default 1):
  ```

  For an existing directory also show `CONTEXT.md: yes/no · features: N`. Choice 1 uses the candidate; choice 2 requires an absolute user-provided path. Then `mkdir -p "$TGD_DIR"` and export it.
- Non-interactive mode, where asking is impossible, may use the candidate without confirmation and must log `📂 Using $TGD_DIR: <candidate> (non-interactive)`.

All later commands use this resolved `$TGD_DIR`.

## Step 0.5: Probe dependencies and resolve tiers

Probe the environment BEFORE starting, and decide which tiers run. Do this explicitly — steps must never be silently skipped:

```bash
command -v codegraph && echo "codegraph: OK" || echo "codegraph: MISSING"
command -v node && command -v npm && echo "node/npm: OK" || echo "node/npm: MISSING"
# understand is loadable when it appears in available skills or
# ~/.understand-anything/repo exists.
```

| Tier | Steps | Condition | Output |
|---|---|---|---|
| **Tier 1 — Core** | 1, 2, 6, 7 | Always | `CONTEXT.md` |
| **Tier 2 — Deep scan + dashboards** | 3, 4, 5 | Step 3 needs `codegraph`; Step 4 needs `understand`; Step 5 needs Step 4 output plus node/npm. Run every available step independently. | symbol index, knowledge/domain graphs, dashboard per repo |

If a tier cannot run, you MUST record it in `CONTEXT.md` under `## Degraded Mode` — which steps were skipped, why (missing tool), and how to enable them later. A skipped step that is not logged is a verification failure. **Silent skipping is the failure mode** this rule exists to prevent. Do not suggest installations beyond that one-line note.

## Step 1: Select repositories

Before analyzing anything, **ask the user — on every `/tgd-map` run**. An existing CONTEXT.md changes the wording of the question, never the requirement to ask (same rule as Step 0b):

- First map: `除了當前 repo，還有其他需要參考的 repo 嗎？（local path 或 git URL）`
- Re-map: show the previous primary/additional repo list, then ask:

  ```text
  1. 沿用這份清單 (Enter)
  2. 增加/移除 repo（輸入 local path 或 git URL，或要移除的名稱）

  Choose one (default 1):
  ```

Accept local paths (resolve them to absolute paths) and git URLs (clone to `/tmp/tgd-context/<repo-name>`). An empty/no answer means the primary repo only. Store the selection in CONTEXT.md. The downstream no-re-ask rule in `tgd-core-context` does not apply here; Map owns this question.

## Step 2: Map core context

Run `tgd-core-context` across every selected repo for stack, architecture, dependencies, organization, patterns, and UI landscape. **If Tier 2 is available (see Step 0.5), you MUST continue to Step 3 (CodeGraph) and Step 4 (Understand-Anything) before producing CONTEXT.md. If Tier 2 is unavailable, proceed to Step 6** and log the skips under `## Degraded Mode`.

## Step 3: Build the CodeGraph index when available

For each repo, if `codegraph` exists:

1. Create `$TGD_DIR/.scans/<repo-name>/.codegraph` before linking it.
2. Replace `<repo-path>/.codegraph` with a symlink to that directory.
3. Run `codegraph init -i` from the repo.

If unavailable, skip and log it. Never create a dangling scan symlink.

## Step 4: Understand-Anything (Tier 2 — requires the `understand` skill)

**Skip condition (the ONLY one):** `understand` is not loadable. When it is
available, this step is **required**, not optional. Delegation is optional; if
unavailable, run inline.

For each repo:

1. Create `$TGD_DIR/.scans/<repo-name>/.understand-anything` before replacing `<repo-path>/.understand-anything` with a symlink to it.
2. Run `understand`; use `understand-onboard` when unfamiliar.
3. If `domain-graph.json` is absent or older than `knowledge-graph.json`, run `understand-domain`. If validation fails, delete the partial domain graph and log the failure. Keep a newer domain graph unchanged.

The required outputs are `knowledge-graph.json` and, unless its derivation was logged as failed, `domain-graph.json`. Inability to launch a subagent is not degraded mode.

## Step 5: Launch dashboards when available

If Step 4 produced a knowledge graph and node/npm exist, launch `understand-dashboard` automatically, in the background, once per repo. Follow that skill's launch method, setting `GRAPH_DIR` to the repo's absolute path; capture each localhost URL and best-effort open it. Failure or headless inability to launch must not block other repos, but launch failures must be logged. The dashboard is for humans; downstream commands consume CONTEXT.md and graphs.

## Step 6: Produce CONTEXT.md

Write `$TGD_DIR/CONTEXT.md` from `$TGD_REPO_ROOT/templates/CONTEXT.md.tmpl`; scan artifacts stay under `$TGD_DIR/.scans/<repo>/` and include applicable `codegraph.db`, `knowledge-graph.json`, `domain-graph.json`, and UA `config.json` outputs.

- Ground every claim in a graph/index or a file actually read. If Tier 2 was skipped, say so rather than guessing.
- **No blank sections, no placeholder text left in.** Every heading below gets real content. Use an explicit `not detected`/`none found` where appropriate.
- Point changing commands and conventions to their source files; CONTEXT.md is a snapshot, not a higher source of truth.
- Keep it navigational: name important locations and why they matter; link graph detail rather than copying it.
- Record dashboard URLs under `## See Also` and every skipped step under `## Degraded Mode`.

## Step 7: Verification Gate

Tier 1, always:

- [ ] CONTEXT.md exists, is non-empty, has no blank section or placeholder, and conforms to `$TGD_REPO_ROOT/templates/CONTEXT.md.tmpl`.
- [ ] Build/Test/Run gives sourced real commands or `not detected`; Conventions lists rules/test locations; frontend repos name real UI source paths or explicit absences.
- [ ] Every repo has `Analysis Coverage`: a real file count or `not analyzed — understand skill unavailable (see ## Degraded Mode)`.
- [ ] Every repo has `Business Flows`: a real domain-graph table or `not analyzed — see ## Degraded Mode`.
- [ ] Additional repos are represented and all skipped steps appear in `## Degraded Mode`.
- [ ] The run ends with the Step 8 report, with no silent field.

Tier 2, only where Step 0.5 proved dependencies available:

- [ ] Each applicable repo has the required scan symlinks and `knowledge-graph.json`.
- [ ] UA-backed coverage is a real file count; domain graph exists or its derivation failure is logged and no partial file remains.
- [ ] With node/npm, every repo has a recorded dashboard URL or a logged launch failure.

An unavailable Tier 2 check is N/A only with probe evidence plus its Degraded Mode entry.

## Step 8: Final Report

The run's last message must use this filled format. Every line is a real value or `skipped — <reason from Degraded Mode>`.

```text
✅ /tgd-map 完成

📂 $TGD_DIR: <path>
📚 Repos mapped: <primary> (+ <additional>, or 無)
📊 Dashboards:
   - <repo-name>: http://localhost:<port>
   or: skipped — <reason from Degraded Mode>
🧭 Domain: <N domains / M flows — 開 dashboard 的 Domain 視角確認一眼；覺得不對就刪 domain-graph.json 即回復>
   or: skipped — <reason from Degraded Mode>
🔍 繼續探索: /understand-chat <問題> · /understand-explain <檔案> · dashboard Domain 視角
⚠️ Degraded Mode: <none / one line per skipped step with reason>

Next: /tgd-define
```
