# Changelog

All notable changes to tGD will be documented in this file.

Format based on [Keep a Changelog](https://keepachangelog.com/). Versions follow [CalVer](https://calver.org/) (YYYY.MM.DD).

## v2026.07.06.1

### ✨ Features
- rebuild the intro deck as a 12-slide narrative (`f62918d`)
### 🐛 Bug Fixes
- ship pi commands as native prompt templates, not a sendUserMessage extension (`e490f08`)
- stop /tgd-map from skipping UA when it cannot spawn a subagent (`b5bcd85`)


## v2026.07.06

### ✨ Features
- prose coverage report + sidecar typo detection (`43bf23f`)
- wiki prose synthesis + deterministic fallback + per-file docs (`90c543c`)
- auto-launch the UA dashboard per repo in /tgd-map, open wiki + dashboards (`62b39ee`)
### 🐛 Bug Fixes
- list the per-file docs tree in the repo manifest (`34b55ff`)
- correct intro deck facts and align it with the landing page (`f6af833`)
### 📝 Documentation
- make the wiki report a single unambiguous human entry point (`4a177e6`)


## v2026.07.05

### ✨ Features
- redesign the landing page — funnel architecture, new visual system, rewritten copy (`9c40c8a`)
- wire PRD success metrics into an enforceable instrumentation chain (`a1e5e7c`)
### 🐛 Bug Fixes
- default the landing page to English (`4cd54a3`)
- enforce the release-phase gates the docs promised (`92785a1`)
- wire the review personas into the lifecycle they were written for (`f84d731`)
- the coverage gate failed on every runner regardless of coverage (`b2f61ae`)
- close the develop-phase gaps in the AC traceability chain (`1a38a76`)
- unify the plan phase on one TASKS.md format and repair jira-sync (`e5205ef`)
- repair the define-phase pipeline (`ca2b7a7`)
### 📝 Documentation
- add metrics artifacts to site pages and desktop setup guide (`b135b0c`)
- sync READMEs and one-pager with the metrics chain artifacts (`b153e9d`)
- sync all READMEs and web pages — 29 skills, translation parity, blue branding, mobile fixes (`db69a84`)
### ♻️ Refactoring
- split release into prepare (script) and publish (CI) (`249a539`)
### 🔧 Chores
- add README parity check; document commit convention (`39ed573`)


## v2026.07.04.1

### 🐛 Bug Fixes
- repair lifecycle command bugs and add tiered degradation to tgd-map (`1360d50`)
  - gate scripts were invoked from the artifacts dir where they don't exist ($TGD_DIR → $TGD_REPO_ROOT)
  - /tgd-develop merged to main before verify/review; merge moved to /tgd-release
  - feature-dir scan no longer matches infrastructure dirs (.scans/, wiki/)
  - /tgd-map degrades by tier (CONTEXT.md always; deep scan when tools exist; dashboard opt-in) with mandatory Degraded Mode logging
- enforce Node >= 22 in setup.sh prerequisite check; warn when jq is missing (`abefdfc`)
- regression gate looked for the catalog in the wrong directory — it had never actually gated; now executes every catalog entry individually with a retry-once flaky policy (`50594ae`)

### ✨ Features
- replace Docusaurus wiki with a single self-contained wiki.html — python3 stdlib only, ~1s, opens by double-clicking; identical page structure across projects; Markdown twin for agents/GitHub (`71306d4`)
- generate platform command mirrors (codex/opencode/gemini/pi) from .claude/commands as single source, with a "Mirror sync" CI gate that fails on drift (`b0bc087`)
- machine-checked requirement coverage: AC-<task>.<n> ids in TASKS.md cross-referenced to tests by scripts/ac-trace.py as a mandatory /tgd-verify gate; [R] criteria must name their test file (`f28e614`)

### 🔧 Chores
- write commitlint config to a filename commitlint actually loads — the Conventional Commits check had failed on every PR with [empty-rules] (`a8dcf01`)


## v2026.07.04

### 🐛 Bug Fixes
- resolve 46 lint, parity, and staleness issues (`b1ec8c0`)
- always create default ~/.hermes even if missing (`a54a30f`)
- install tGD into all profiles (`f8f17ea`)


## v2026.07.02

### Added
- **DeepWiki-style wiki generation** — generate human-readable wiki pages from CodeGraph and Understand-Anything outputs (`9e3dc1a`)
- **Docusaurus 3 wiki site output** — render generated wiki content with a uniform DeepWiki-style web layout (`573da88`)
- **Multi-repo wiki navigation** — add per-repo trees and a navbar dropdown for multi-repo scans (`a852eba`)
- **Offline symbol navigation** — add source jump links from generated wiki pages without requiring external services (`31ca617`)
- **Offline local search** — add local search for generated wiki sites (`29907c9`)

### Changed
- **Wiki artifact layout** — nest generated wiki artifacts under `$TGD_DIR/wiki/` (`39ee3b4`)
- **Setup support for wiki sites** — auto-install Docusaurus 3 dependencies needed by the tGD Wiki site flow (`960d4a7`)

### Fixed
- **Hermes plugin packaging** — unignore `.hermes/plugins/tgd/`, which had been blocked by the repo gitignore rule (`f00f739`)
- **Pi tgd-map flow** — promote Dashboard to a first-class Step 5 in the Pi command flow (`64062eb`)
- **Release script flag parsing** — skip `--yes` and `-y` when resolving the release version (`3ea3671`)

### Removed
- **Overbuilt wiki verification gate** — remove the layout/brand contract gate after determining it was unnecessary for real failures (`169bc2e`)

### Chores
- **Legacy runtime ignores** — ignore legacy CodeWiki runtime directories (`data/`, `storage/`, `tmp/`) (`8a370d5`)


## v2026.07.01

### ✨ Features
- enforce minimum coverage floors (80/60/90) with machine gate (`828bbe3`)
- capture raw test output as machine-checkable evidence (`c85d124`)
- machine-gate the cross-feature regression check (`95db43f`)
- sharpen [R] regression rule — MUST-mark list + fail-closed enforcement (`0c02d3b`)
- add Hermes Agent as the 6th supported platform (`00490ee`)
### 📝 Documentation
- update CHANGELOG.md for v2026.06.30 (`3e7e4e3`)


## v2026.06.30

### ✨ Features
- add Goals & Non-Goals section to PRD template (`df17e78`)
### 🐛 Bug Fixes
- sync PRD guidance with new template structure (`07750b3`)
- reorder PRD — Problem Statement before Goals (`1b89e92`)
- disambiguate Goals (outcomes) vs Scope (deliverables) in PRD template (`c0ebe06`)
- quote tgd-agent-browser description to avoid YAML plain-scalar trap (`16af44c`)
### 📝 Documentation
- update skill paths to use tgd- prefix in claude-desktop-setup.md (`ebe9023`)
- replace Chinese examples with English in claude-desktop-setup.md (`6832da8`)
### ♻️ Refactoring
- discuss feature before naming — move interview/idea-refine before branch setup (`cc648ce`)


---

## v2026.06.28

### Changed
- **All 27 tGD skills renamed to `tgd-` prefix** — every tGD skill directory and frontmatter `name:` now carries the `tgd-` prefix (e.g. `skills/spec-driven-development/` → `skills/tgd-spec-driven-development/`, `name: spec-driven-development` → `name: tgd-spec-driven-development`). `tgd-rules` unchanged. `using-tgd` (mixed-case form) renamed to `tgd-router`. Affects: 28 skill directories, 28 SKILL.md files, 28 command files (4 platform copies + 1 Gemini TOML), 48 cross-skill references in SKILL.md, 108 cross-skill references in command files
- **setup.sh upgrade migration** — added `purge_old_tgd_symlinks` function that auto-removes pre-prefix tGD symlinks on `bash setup.sh --upgrade` (double-checked against `understand-anything` third-party symlinks)
- **`tgd-agent-browser` SKILL.md YAML fix** — wrapped `description` in double quotes (was a YAML plain scalar containing `task: navigating`, which strict YAML parsers — like Pi's `yaml` package — flagged as a nested mapping). Discovered when Pi agent auto-fixed the file in-session. Other 27 skills verified clean (no plain scalar with `:` patterns).

### Migration (breaking)
- **If you installed a previous version, run `bash setup.sh --upgrade`** — this removes the old un-prefixed symlinks and links the new `tgd-` prefixed ones
- **Custom commands / scripts that invoke skills by name** — update `agent-browser` → `tgd-agent-browser`, `using-tgd` / `tgd-using-tgd` → `tgd-router`, and any other old names
- **Reference** — see [README § How Skills Work](../../README.md#how-skills-work) and `skills/tgd-router/SKILL.md` for the full `tgd-` namespace

---

## v2026.06.27

### Changed
- **Removed unsupported platform references** — Cursor / Copilot / Antigravity / Windsurf / Kiro removed from `AGENTS.md` and all 4 README translations. tGD officially supports only the 5 platforms deployed by `setup.sh`: Claude Code, Codex, OpenCode, Gemini CLI, Pi (`4c4bf44`)

---

## v2026.06.26

### Changed
- **`/tgd-ship` → `/tgd-release`** — stage name and command renamed across all 5 platforms (Claude Code, Codex, Gemini, OpenCode, Pi) for consistency with pipeline terminology. Affects 30 files: command files, README ×4, AGENTS.md, docs, skills, landing page (`b6d8811`)
- **One-pager redesign** — complete rewrite as standalone HTML with table-based pipeline layout, KPI chart (Anthropic editorial style), and role color coding (blue=Agent, purple=Human) (`cf90dc8`, `9d4e970`, and 14 follow-up fixes)
- **Pipeline table optimization** — removed arrow column, added gate badges, progressive green gradient left bar, equal-width I/O columns (`75c2093`, `7ddb944`)
- **AGENTS.md slimmed** — 278 → 140 lines; extracted skill authoring guide to `CONTRIBUTING.md` (`36d1647`)

### Added
- **Claude Desktop setup guide** — `docs/claude-desktop-setup.md` with full Custom Instructions, 22-file Knowledge Base upload list, and usage examples. Linked from all 4 README translations (`c59a2f2`)

### Fixed
- **Pipeline I/O column consistency** — all stages now show `<code>` wrapped filenames matching command file content (`1f9fd72`)

### Migration (breaking)
- If you use `/tgd-ship` in your workflow, update to `/tgd-release`. The command file was renamed; old slash command no longer resolves.

---

## v2026.06.23

### Fixed
- **setup.sh CWD assumption** — relative paths in hooks install (`hooks/hooks.json`, `.gemini/settings.json`) and agent-browser detection silently failed when setup.sh was invoked from outside the repo directory; added `cd "$TGD_DIR"` after directory resolution (`5a5ba84`)
- **Version comparison dead code** — `TGD_VERSION` and `INSTALLED_VERSION` both read `.tgd-version` (git-tracked), making upgrade detection always equal; `VERSION_FILE` now points to `~/.tgd-installed-version` (local-only) (`5a5ba84`)
- **`--version` output** — `setup.sh --version` returned `0.0.0` due to grep/cut parsing itself; now reads `.tgd-version` directly, consistent with `tgd -v` (`5a5ba84`)
- **Misleading error messages** — hooks install failures reported "python3 required" regardless of actual cause (usually path-related); messages now point to the correct source file (`5a5ba84`)
- **Chrome path typo** — `/user/bin/google-chrome` (nonexistent path) removed; `/usr/bin/google-chrome` already handled above (`5a5ba84`)

### Changed
- **tgd-rules symlinks** — added `command -v` guards for Codex, OpenCode, Gemini, and Pi to avoid creating empty directories for uninstalled tools (`5a5ba84`)
- **Uninstall cleanup** — `~/.tgd-installed-version` is now removed during uninstall (`5a5ba84`)

### Fixed
- **validate-skills.js false positives** — vendor (Understand-Anything) skills now included in `knownSkills`, eliminating 10 spurious dead-reference warnings for `understand`, `understand-domain`, `understand-diff`, `understand-onboard`, `understand-dashboard` (`5a5ba84`)

## v2026.06.20

### Changed
- **AC format — BDD mandatory** — reverted flexible AC policy; all acceptance criteria must use BDD (Given/When/Then) for consistency between TASKS.md and REGRESSION-CATALOG.md (`f49c3a9`)

### Fixed
- **Cross-platform parity** — Pi tgd-commands aligned with all 4 other platforms; tgd-review content unified across Gemini and Pi (`4ee6b10`, `3764e3a`)

### Docs
- **One-pager redesign** — rebuilt as html-ppt single slide with agentic PDLC narrative, human roles per stage, light theme with tGD design language (`4ece9f8`, `81a94f0`, `b9b98db`, `532ee64`, `8bdedf5`)
- **Agentic PDLC narrative** — unified messaging across README (4 languages), intro slides, and GitHub Pages: "Your PDLC was built for humans. Now agents do the work." (`de3e80d`, `c8a4140`, `f27eef0`)
- **A4 marketing overview** — added one-page A4 layout for at-a-glance summary (`3737ccf`, `f936a52`)

## v2026.06.16

### Changed
- **`$TGD_DIR` symlink → env var + sibling fallback** — removed `tGD/` symlink, all commands now resolve via `$TGD_DIR` env var or `../<project>-tGD/` sibling (`1d78056`)
  - `tgd-map`: env var first → sibling fallback → first-time user confirmation → CI silent skip
  - 28 skills: all hardcoded `tGD/` paths replaced with `$TGD_DIR`
  - `.codegraph` / `.understand-anything` symlinks point directly to `$TGD_DIR/.scans/<repo>/`
- **Skill name syntax** — bare name `` `understand` `` instead of `/understand` (slash is Claude-only) across all 5 platforms + skills + READMEs (`e5ae16b`)
- **AC format** — BDD (Given/When/Then) mandatory for all tasks, ensuring consistency between TASKS.md and REGRESSION-CATALOG.md (`23a7d69`, reverted `de3e80d`)

### Fixed
- **Pre-flight stale references** — all lifecycle commands (define through ship) still referenced removed `tGD/` symlink for resolution and feature scanning (`1a7dd50`)
- **README + GitHub Pages** — 4-language READMEs, `index.html`, and `web/` dashboard updated to reflect direct symlink architecture (`c49d3c3`, `3d643d0`)

## v2026.06.15

### Added
- **REGRESSION-CATALOG mechanism** — cumulative cross-feature regression tracking across shipped features (`c0e2a63`)
  - `/tgd-plan`: `[R]` marks ensure a corresponding test is created during `/tgd-develop` (TDD)
  - `/tgd-ship`: writes `[R]` entries to `REGRESSION-CATALOG.md` (cumulative — every shipped feature preserved)
  - `/tgd-ship`: **Catalog Audit** — prunes stale/missing/deprecated entries on each ship, prevents zombie catalog
  - `/tgd-verify`: **Cross-Feature Regression Gate** — reads catalog, re-runs ALL entries before approve, hard fail on any regression

### Fixed
- **5-platform parity** — 19 files synced across Claude / OpenCode / Codex / Gemini / Pi (`c0e2a63`)
  - `tgd-map`: dashboard per repo, subagent allowance, Step 5 verification
  - `tgd-verify`: Cross-Feature Regression Gate + Catalog Audit
  - `tgd-ship`: Regression Catalog Update + Audit
  - Codex 4 commands: add Step 0 + Pre-flight + codegraph
  - OpenCode 3 commands: add codegraph + /understand-diff
  - Gemini verify: webwright → agent-browser
  - Pi verify: test pyramid + agent-browser gate

### Docs
- README (EN/zh-TW/JA/DE) — updated regression section + pipeline table to reflect REGRESSION-CATALOG
- docs/tGD-intro.html — verify slide adds Cross-Feature Regression Gate, ship slide adds Catalog Update + Audit
- docs/web/js/phases.js — verify + ship phase definitions updated
- docs/index.html — pipeline table + regression section updated
- docs/getting-started.md — pipeline table updated

---

## v2026.06.13

### Added
- **Multi-repo task tagging in `/tgd-define` and `/tgd-plan`** — agents now tag SPEC.md sections and TASKS.md tasks with `[repo-name]` for multi-repo projects (`6fef3d2`)
- **`$TGD_DIR` resolution in `/tgd-map`** — defines sibling-directory + symlink pattern, prevents agent guesswork (`ca38ed4`)
- **Centralized scan storage** — `.codegraph/` and `.understand-anything/` moved to `$TGD_DIR/.scans/<repo>/` with symlinks (`cc2fb1a`)
- **Decisions/ folder in `/tgd-review`** — creates ADRs when architectural decisions are made (`5bf47ff`)

### Changed
- **`understand-dashboard`** auto-opens browser on launch (`07a678f`)
- **3 understand skills** now explicitly tell agents they ARE the LLM — prevents accidental external API calls (`6b88f7f`)

### Fixed
- **HTML pages** — corrected artifact names (`VERIFY.md` → `TEST-REPORT.md`, `SHIP.md` → `CHANGELOG.md`), JA/DE command count (8→7), slide numbering, removed `glow-breathe` animation that broke GitLab Pages rendering (`37f6945`)
- **commands `verify`/`review`/`ship`** now explicitly create their required artifacts — TEST-REPORT.md, REVIEW.md, CHANGELOG.md, decisions/ (`6442a2f`)
- **Global rules pollution** — removed `~/.claude/rules/tgd.md` symlink, agents load rules per-project only (`5bf47ff`)
- **Map step symlinks** point to `.scans/<repo>/` not project root (`cc2fb1a`)

### Docs
- All 4 READMEs (EN/zh-TW/JA/DE) — added "Updating to Latest" one-liner in Quick Start, fixed command count, consistent terminology (`f6dc091`, `0f5e833`, `226d0fa`, `f3b2fec`)
- EN README — fixed `an 7-stage` typo, deduped CLI tables, `Who is this for` converted to bullet list (`226d0fa`, `f3b2fec`)
- All 4 READMEs — added comprehensive testing strategy (BDD, TDD, TEST-REPORT, regression, Ship gate) (`111e290`)

---

## v2026.06.12

### Added
- **Favicon redesign**: Blue "GD" on dark rounded square — unified across GitHub Pages and Intro page (`f039b46`, `8fe79a9`)

### Changed
- **Jira Integration Gate in `/tgd-plan`** — 3 iterations to get it right:
  - Made Jira gate mandatory (auto-sync if configured, block if not) (`c0460c2`)
  - Moved gate before verification to prevent agent from skipping (`8f427dd`, `be306b5`)
  - Final: conversational prompt after TASKS.md — asks "要同步到 Jira 嗡？(y/n)", saves credentials to `$TGD_DIR/.env` for future runs (`e25743c`)
  - Updated across all 5 platforms: Claude, OpenCode, Gemini, Codex, Pi

### Fixed
- **setup.sh registry safety**: Refuses `npm install -g pnpm` and `pnpm install` when registry is default `registry.npmjs.org` — prompts user to configure their own registry first (`aec19c8`)

## v2026.06.11

### ✨ Features
- feat(setup): link tGD skills to OpenCode/Gemini/Pi for faster skill discovery (`dadc955`)
- feat(dashboard): remove token gate — dashboard opens directly on localhost (`26ad0d3`)
- docs: add Sign-off + TEST-REPORT + regression markers to intro page outputs (`6161d6d`)
- docs: add Sign-off format example to zh-TW/JA/DE READMEs (`d9194aa`)

### 🐛 Bug Fixes
- fix(setup): 7 issues — cd bug, duplicate logic, symlink chain, prereq checks (`71c4214`)
- fix(setup): uninstall cleanup for ~/.agents/skills/ and case-sensitive tGD pattern (`dadc955`)
- fix(dashboard): remove unused crypto import and NO_AUTH references (`26ad0d3`)

### 🔧 Chores
- chore: bump version to v2026.06.11 (`5683984`)

---

## v2026.06.10

### ✨ Features
- feat: add Human Roles, Sign-off Protocol, and TEST-REPORT to lifecycle (`5fba481`)
- feat: add TEST-REPORT, regression markers, and Human Roles to all READMEs (`5093c0e`)
- refactor: Sign-off table→checkbox, coverage optional, test runner config, rejection flow (`ff25035`)

### 🐛 Bug Fixes
- fix: add padding-bottom to slides to prevent footer overlap (`0b3301a`)

### 🔧 Chores
- chore: bump version to v2026.06.10

---

## v2026.06.09

### ✨ Features
- feat: auto-categorized release notes with CHANGELOG.md|bfacd3e`)
- feat(cli): add --release command to tgd CLI|ed904ea`)
- feat: add GitHub Release and Tag automation|913c2ea`)
- feat(define): add sketch skill for HTML prototype generation|a801f27`)
- feat: add phase-specific Tone Guide to AGENTS.md|0331de7`)
- feat(define): improve Feature Name Resolution to analyze user intent first|cc6b9f4`)
- feat(map): add Context Discovery step and make Understand-Anything mandatory|dde3f3b`)
- feat: tGD Web Dashboard — 8-phase pipeline visualization with theme toggle|8bfc825`) *(historical — pipeline is now 7-phase)*
- feat: tGD Web Dashboard MVP — 8-phase pipeline visualization|86a4bdf`) *(historical — pipeline is now 7-phase)*
- feat: tgd CLI with CalVer versioning|0e344a7`)
- feat: sync Pi extension with all other platforms|887d733`)
- feat: enforce 'Selection Protocol' across all platforms|9a9d3c1`)
- feat: integrate CodeGraph/UA usage across all PDLC commands|8c79c10`)
- feat: synthesize CONTEXT.md from CodeGraph & UA data|5b9a812`)
- feat: add /understand-dashboard to tgd-map outputs|26f6258`)
- feat: symlink .understand-anything into $TGD_DIR/|e460aec`)
- feat: add UA output to /tgd-map across all platforms|aa5ff15`)
- feat: bind Understand-Anything into all 6 PDLC phases|6e7b6cb`)
- feat: auto-build Understand-Anything in setup.sh|ef24f74`)
- feat: bundle Understand-Anything directly instead of submodule|44ce665`)
- feat: bundle Understand-Anything as submodule|4b672f4`)
- feat: wire CodeGraph into 6 tGD lifecycle skills|eb012d8`)
- feat(rules): add CodeGraph usage hints to tgd-rules|d734d91`)
- feat: add 'tgd' CLI command|0df1724`)
- feat(setup): add --version flag|49eb2f9`)

### 🐛 Bug Fixes
- fix: comprehensive audit — 42 issues across AGENTS.md, README, platform commands, and docs|5e603c1`)
- fix: commit categorization — match scoped prefixes like feat(scope):|52e39df`)
- fix: resolve CI failures — shell pattern escaping + sketch skill validation|67089a6`)
- fix: unify version source — tgd -v reads .tgd-version, release.sh syncs both files|a41e1c6`)
- fix(release): handle --help flag in release script|15d3489`)
- fix: Pi extension tgd-verify references agent-browser|f65fd1e`)
- fix: replace all webwright/browser-testing-with-devtools references with agent-browser|692c3a1`)
- fix: update cross-references from browser-testing-with-devtools to agent-browser|7efe774`)
- fix: enforce mandatory UI Design Gate check in /tgd-define|35841d2`)

### 📝 Documentation
- docs: sync GitHub Pages hero text with README intro (all 4 languages)|0d28633`)
- docs: update GitHub Pages license from MIT to Apache 2.0|51dfad9`)
- docs: regenerate CHANGELOG.md with proper categorization|b1bdd23`)
- docs: update README examples to show prototype generation|bcf7019`)
- docs: update README examples and runtime output|aef6ee5`)
- docs: rewrite README intro with pain-point hook|e3046a7`)
- docs: update Quick Start to assume first-time install|e23e7d0`)
- docs: add Understand-Anything to README and docs + cleanup uninstall|0b115e5`)
- docs: use --recursive for git clone|b3741aa`)
- docs: sync READMEs and GitHub Pages with new 'tgd' CLI|f4a6ed3`)

### ♻️ Refactoring
- refactor: optimize UA/CodeGraph usage (Active/Passive split)|3ad52fc`)

### 🔧 Chores
- chore: bump version to v2026.06.09|ab433ea`)

### 📦 Other Changes
- license: switch from MIT to Apache 2.0|c1248f5`)
- restore: setup.sh from 0c1615a|3dbfb80`)
- restore: agent-browser/SKILL.md from 0c1615a|81bf581`)
- Revert "restore: 26 skill symlinks from 0c1615a"|4916360`)
- restore: 26 skill symlinks from 0c1615a|db74c56`)
- remove: browser-testing-with-devtools and webwright (replaced by agent-browser)|6d4d8bd`)
- restore: jira-auto-sync/SKILL.md from 0c1615a|03526ea`)
- restore: .gitignore from 0c1615a|4f4efb0`)
- restore: README multilingual and AGENTS.md from 0c1615a|5798616`)
- restore: commands/ from 0c1615a — tgd-verify.md updates|dae7ca9`)
- Revert "restore: skills/ from 0c1615a — agent-browser, jira-auto-sync, webwright removal"|2bb70d6`)
- restore: skills/ from 0c1615a — agent-browser, jira-auto-sync, webwright removal|af69f6c`)
- restore: docs/ presentation files and landing page from 0c1615a|c813ece`)

---
**Full Changelog**: https://github.com/openclawyhwang-hub/tGD/commits/v2026.06.09
