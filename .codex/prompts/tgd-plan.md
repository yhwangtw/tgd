# /tgd-plan

Plan — decompose specs into small, verifiable tasks with acceptance criteria

**🛑 Pre-flight: Environment Check**
- [ ] `$TGD_DIR/CONTEXT.md` exists. No substitutes — `/tgd-map` produces it unconditionally (Tier 1).
- **If missing:** STOP. Tell user: "Project context not mapped. Please run `/tgd-map` first."
- **$TGD_DIR:** Check env var `$TGD_DIR` first. If not set, check sibling `../<project-name>-tGD/`. If neither exists: STOP — run `/tgd-map` first.

**🔑 Step 0: Feature Name Resolution**
1. Scan `$TGD_DIR/` for **feature directories**: subdirectories containing `SPEC.md` or `PRD.md` (e.g., `$TGD_DIR/user-login/`). Infrastructure dirs (`.scans/`, `wiki/`, and any dot-directories) are NOT features — always exclude them.
2. If none found: 🛑 STOP. "No features defined. Run `/tgd-define` first."
3. If exactly one found: Lock it as `<feature-name>`.
4. If multiple found: List them and ask user to specify.
5. **Verify**: Ensure all work targets `$TGD_DIR/`.

**🔒 Pre-flight: Artifact Check**
- [ ] `$TGD_DIR/<feature-name>/PRD.md` exists and is non-empty.
- [ ] `$TGD_DIR/<feature-name>/SPEC.md` exists and is non-empty.
- **If missing:** STOP. Tell user: "Specs are missing. Please run `/tgd-define` first."
- [ ] If SPEC has Frontend/Full-stack: `$TGD_DIR/<feature-name>/DESIGN.md` exists.
- **If missing:** STOP. Tell user: "Design is missing. Please run `/tgd-define` first."

**🔁 Re-plan check (BEFORE writing anything):** if `$TGD_DIR/<feature-name>/TASKS.md` already exists, do NOT regenerate it from scratch — `/tgd-develop` backfills `Test:` fields and flips `**Status:**` lines in it, and a fresh rewrite destroys them (breaking the `ac-trace` / regression chain). Count from the file — `M` = tasks with `**Status:** complete` — then ask (Selection Protocol):

> 📋 TASKS.md 已存在（N 個任務，M 個已完成，K 條 `Test:` 已回填）
>
> 1. 增量更新 — 保留已完成任務與所有 `Test:` 欄位；只新增/修改受 spec 變更影響的任務（預設）
> 2. 整份重來 — 丟棄現有 TASKS.md（含完成狀態與 Test: 回填）。只在舊計畫已作廢時選這個。
>
> Choose one (default 1):

Incremental rules: completed tasks and their `AC-<task>.<n>` ids are immutable — never renumber existing ids; new tasks continue the numbering; an *unstarted* task invalidated by the spec change may be rewritten in place.

Run the `tgd-planning-and-task-breakdown` skill. Decompose the specification into small, verifiable tasks with acceptance criteria and dependency ordering.

**Mandatory Reading:**
1. **Read `$TGD_DIR/CONTEXT.md`**: Understand existing project structure and tech stack.
2. **Read `$TGD_DIR/<feature-name>/PRD.md`**: Understand business goals and user pain points.
3. **Read `$TGD_DIR/<feature-name>/SPEC.md`**: Analyze technical requirements and API contracts.
4. **Read `$TGD_DIR/<feature-name>/DESIGN.md` (if present)**: Review UI flows and components.

**Output:** `$TGD_DIR/<feature-name>/TASKS.md`.

Each task should be implementable in isolation with clear success criteria. Order tasks by dependencies so they can be executed in the right sequence.

**Multi-Repo Tagging:** If CONTEXT.md lists multiple repos, each task in TASKS.md MUST be prefixed with `[repo-name]`:
```markdown
### Task 1: [my-project-backend] Create auth endpoint
**Description:** POST /api/auth/login
**Files Touched:** `src/routes/auth.js`

### Task 2: [my-project-frontend] Login form component
**Description:** React login form with email/password
**Files Touched:** `src/components/LoginForm.tsx`
```
This ensures each task is assigned to the correct repo and can be executed in the right context.

**If UI feature:** Read `DESIGN.md` to understand Component Tree, Design Tokens, Responsive Breakpoints, and Interaction Patterns. Use these to inform task breakdown.

**📊 Instrumentation Tasks (only if PRD §6 names a tracking event that does not exist yet):**
1. Register each new event in `$TGD_DIR/TRACKING-PLAN.md` (create on first use) — the cumulative, platform-agnostic event dictionary. Entry format and the three cross-platform rules (one semantic = one name + `platform` property; semantic triggers, not UI triggers; declared source of truth) are in `tgd-planning-and-task-breakdown`.
2. Create one instrumentation task per platform listed in the entry's **Platforms** field — a normal TASKS.md task (multi-repo tagged) with BDD acceptance criteria asserting the event fires with the expected payload keys. Events marked source-of-truth `server` are implemented once, server-side — do NOT duplicate them per client platform.
3. New entries start as `Status: planned` — `/tgd-release` flips them to `live`.

**🔗 Jira Integration Gate** → IMMEDIATELY after TASKS.md is written. Do NOT skip this step.
1. **Load saved config first**: if `$TGD_DIR/.env` exists, source it (`set -a; . "$TGD_DIR/.env"; set +a`) — a previous run may have saved `JIRA_URL`/`JIRA_PROJECT` there. THEN check env vars: `JIRA_URL`, `JIRA_PROJECT`, `JIRA_TOKEN`. (Without this load, values saved "for future runs" are never read and the user gets re-asked every time.)
2. **If ALL configured:** Run the `tgd-jira-auto-sync` skill automatically. Do NOT ask.
   - Parse TASKS.md, create issues, report keys (e.g., `ENG-1234`).
   - Add issue keys back to TASKS.md tasks as `[ENG-1234]`.
3. **If NOT configured:** Ask via Selection Protocol:
   ```
   📋 TASKS.md 已完成（N 個任務）。
   🔗 要同步到 Jira 嗎？
   1. 同步（我會逐項問缺少的連線設定）
   2. 略過

   Choose one (default 2):
   ```
   - **If 1:** Ask for each missing value one at a time:
     - `JIRA_URL`（例：https://jira.company.com）
     - `JIRA_PROJECT`（例：ENG）
     - `JIRA_TOKEN`（Personal Access Token）
     Save `JIRA_URL` and `JIRA_PROJECT` to `$TGD_DIR/.env` for future runs. For `JIRA_TOKEN`, warn the user that `.env` is plaintext and recommend exporting it in their shell profile instead; only write it to `.env` if they explicitly agree. Then run the `tgd-jira-auto-sync` skill.
   - **If 2:** Skip Jira, proceed to verification.

**Verification Gate** (runs regardless of whether Jira sync happened):
- [ ] `$TGD_DIR/<feature-name>/TASKS.md` exists and is non-empty
- [ ] `python3 "$TGD_REPO_ROOT/scripts/check-doc-sections.py" TASKS "$TGD_DIR/<feature-name>/TASKS.md"` exits 0 — required sections present, ≥1 task, ≥1 checkpoint, ≥1 `**Status:**` line (the `## Sign-off` section feeds `/tgd-release`'s sign-off gate — its absence would silently skip that check). Resolve `$TGD_REPO_ROOT` per `tgd-rules` → **Resolving $TGD_REPO_ROOT**.
- [ ] If this was a re-plan (TASKS.md pre-existed): every task that had `**Status:** complete` is still present with its Status line and `Test:` fields intact, and no existing `AC-<task>.<n>` id was renumbered
- [ ] Every acceptance criterion carries a stable `AC-<task>.<n>` id in BDD format — check: `grep -qE 'AC-[0-9]+[.][0-9]+' TASKS.md`. Without ids, `/tgd-verify`'s `ac-trace.py` gate fails closed.
- [ ] Every criterion has an explicit `[R]` Yes/No regression decision
- [ ] If UI feature: TASKS.md references DESIGN.md components
- [ ] If PRD §6 names new events: each has a `$TGD_DIR/TRACKING-PLAN.md` entry (Status: planned) and an instrumentation task with its own AC

End with the closing report per `tgd-rules` → **Command Closing Report**: 📦 產出 (TASKS.md — N 個任務、M 條驗收標準；Jira keys 或「略過」) · 🔎 檢查 (gate as one line) · ➡️ 下一步 `/tgd-develop` — 實作第一片. Don't paste the raw checklist above.
