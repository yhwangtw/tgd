---
description: Plan — decompose specs into small, verifiable tasks with acceptance criteria
---

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
- [ ] Read PRD `## UI Design`. If the section is missing, STOP and resume `/tgd-define` to classify it in place. If the mode is **1, 2, or 3**: Status is `direction-approved`, `$TGD_DIR/<feature-name>/DESIGN.md` exists, `check-doc-sections.py DESIGN` exits 0, and its Sign-off contains `[x] **DESIGN**: Direction Approved`.
- [ ] If the PRD mode is **4 — No user-facing UI**, no DESIGN.md is required.
- **If a required design artifact or direction approval is missing:** STOP. Tell user: "Design direction is incomplete. Resume `/tgd-define`; this is a role handoff inside Define, not a new lifecycle phase."

**🔁 Re-plan check (BEFORE writing anything):** if `$TGD_DIR/<feature-name>/TASKS.md` already exists, do NOT regenerate it from scratch — `/tgd-develop` backfills `Test:` fields and flips `**Status:**` lines in it, and a fresh rewrite destroys them (breaking the `ac-trace` / regression chain). Count from the file — `M` = tasks with `**Status:** complete` — then ask (Selection Protocol):

> 📋 TASKS.md 已存在（N 個任務，M 個已完成，K 條 `Test:` 已回填）
>
> 1. 增量更新 — 保留已完成任務與所有 `Test:` 欄位；只新增/修改受 spec 變更影響的任務（預設）
> 2. 整份重來 — 丟棄現有 TASKS.md（含完成狀態與 Test: 回填）。只在舊計畫已作廢時選這個。
>
> Choose one (default 1):

Incremental rules: completed tasks and their `AC-<task>.<n>` ids are immutable — never renumber existing ids; new tasks continue the numbering; an *unstarted* task invalidated by the spec change may be rewritten in place. Preserve the document-level `> **Jira-Source-ID**:` and every existing task's `**Jira:**` and `**Jira-Sync-ID:**` values byte-for-byte, regardless of task status. For a new TASKS.md, generate one `tgd-source-<lowercase UUID v4>` value once; for a legacy TASKS.md without the field, add one during re-plan and then preserve it forever. If an old task heading contains one standalone Jira key such as `[ENG-1234]`, preserve that token and initialize the two new Jira fields to `—`; only the Jira CLI may remove the token after a digest-confirmed, remotely verified `adopt`. Never copy the bracket key into `**Jira:**` manually.

Run the `tgd-plan-breakdown` skill. Decompose the specification into small, verifiable tasks with acceptance criteria and dependency ordering.

**Mandatory Reading:**
1. **Read `$TGD_DIR/CONTEXT.md`**: Understand existing project structure and tech stack.
2. **Read `$TGD_DIR/<feature-name>/PRD.md`**: Understand business goals and user pain points.
3. **Read `$TGD_DIR/<feature-name>/SPEC.md`**: Analyze technical requirements and API contracts.
4. **For UI modes 1–3, read `$TGD_DIR/<feature-name>/DESIGN.md` and the real UI source files linked by CONTEXT.md**: Review the approved flow, component mapping, tokens, responsive rules, states, and allowed deviations. CONTEXT.md locates the sources; it does not replace them.

**Output:** `$TGD_DIR/<feature-name>/TASKS.md`.

Each task should be implementable in isolation with clear success criteria. Order tasks by dependencies so they can be executed in the right sequence.

**Multi-Repo Tagging:** If CONTEXT.md lists multiple repos, each task in TASKS.md MUST be prefixed with `[repo-name]`:
```markdown
## Task 1: [my-project-backend] Create auth endpoint (Story ID: US-01)
...
## Task 2: [my-project-frontend] Login form component (Story ID: US-02)
...
```
These are heading examples only; every task body still uses the complete canonical schema from `tgd-plan-breakdown`. This ensures each task is assigned to the correct repo and can be executed in the right context.

**If UI feature:** Derive tasks from the approved DESIGN.md sections and the actual design-system sources. Acceptance criteria MUST cover observable runtime states (loading, empty, error, success, disabled), named viewports, keyboard/focus behavior, and every approved deviation that requires implementation. Cite the relevant DESIGN.md heading in each UI task so implementation and review can trace it without interpretation.

**📊 Instrumentation Tasks (only if PRD §6 names a tracking event that does not exist yet):**
1. Register each new event in `$TGD_DIR/TRACKING-PLAN.md` (create on first use) — the cumulative, platform-agnostic event dictionary. Entry format and the three cross-platform rules (one semantic = one name + `platform` property; semantic triggers, not UI triggers; declared source of truth) are in `tgd-plan-breakdown`.
2. Create one instrumentation task per platform listed in the entry's **Platforms** field — a normal TASKS.md task (multi-repo tagged) with BDD acceptance criteria asserting the event fires with the expected payload keys. Events marked source-of-truth `server` are implemented once, server-side — do NOT duplicate them per client platform.
3. New entries start as `Status: planned` — `/tgd-release` flips them to `live`.

**🔗 Jira Integration Gate** → IMMEDIATELY after TASKS.md is written. Do NOT skip this step.
1. **Never write automatically.** Ask via Selection Protocol even when Jira environment variables are already configured:
   ```
   📋 TASKS.md 已完成（N 個任務）。
   🔗 要預覽 Jira 同步嗎？
   1. 預覽（只讀，不會建立、更新或回寫）
   2. 略過

   Choose one (default 2):
   ```
2. **If 1, load the `tgd-plan-jira` skill and use only `scripts/jira-sync.py`.** The CLI reads `JIRA_URL` and `JIRA_TOKEN` from the process environment. Never ask the user to paste a PAT into chat, pass it as a CLI argument, log it, or save it in `$TGD_DIR/.env` or any other file. If either required environment variable is missing, STOP and ask the user to export it outside the conversation, then resume this gate.
3. **Always list Projects before planning a sync.** Show every Jira Project returned by the CLI as exact key + name. A configured `JIRA_PROJECT` may be displayed as a default hint only; never select it silently. Require the user to choose one exact returned Project key.
4. **Discover and ask every non-automatic required field.** Run the CLI `fields` command for the exact Project and issue type before planning. Project, summary, issue type, description, priority, and stable label are filled automatically. For every other field Jira marks required, ask the user what to enter; if `allowed_values` are returned, present those exact choices, otherwise ask for a value matching the reported schema. Let the user apply one answer to all create tasks or override it per Task. Sprint has no special rule: if Jira metadata marks it required, ask for it exactly like Component, Fix Version, date, or any other field. Do not call Jira Agile APIs or silently invent a value.
   - Store answers only in a new private mode-`0600` JSON file with `defaults` and `tasks` objects; never put field values directly in command arguments. Pass it to `plan --answers <path>`. If no non-automatic required fields exist, omit `--answers`.
5. **Dry-run first.** Build a read-only plan for that exact Project and current TASKS.md. It must perform no Jira mutation and no TASKS.md writeback. Show the Project key/name, every required-field answer, plan digest, and every proposed `create` / `adopt` / `update` / `skip` / `conflict` action.
   - The plan command's only local write is a private mode-`0600` JSON plan artifact; it never overwrites an existing path. If it reports any `conflict` or exits non-zero, show the candidate issue keys, STOP the Jira gate, and reconcile before creating a new dry-run. Never offer apply for a conflicted plan.
   - `adopt` is only for migrating one unambiguous legacy heading key. It must name that exact issue, verify the selected Project, and show the action explicitly. A missing, duplicate, differently owned, or unverifiable legacy issue is a conflict and must never fall through to `create`.
6. **Confirm the digest explicitly.** Only after a conflict-free complete dry-run is visible, ask via Selection Protocol:
   ```
   套用上面的 Jira 計畫？
   1. 套用到 <PROJECT_KEY>（digest: <SHA-256>）
   2. 取消

   Choose one (default 2):
   ```
   Only choice 1 authorizes apply. A stale digest, changed TASKS.md, changed Project, or missing confirmation must abort without writes.
7. **Apply, verify, then write back.** The CLI may create, adopt, or update only after confirmation. It must GET and verify each remote issue, including every required field used during creation, before writing its key and stable identity into that task's `**Jira:**` and `**Jira-Sync-ID:**` fields. A successful legacy adoption also removes the old heading token in the same locked atomic writeback. Use the CLI result keys consistently: `created`, `updated`, `skipped`, `conflicts`, `remote_unknown`, `failed`, `writeback_pending`, and `aborted` (`adopt` is reported under `updated`). Print every successful or pending issue key. Any non-zero `conflicts`, `remote_unknown`, `failed`, `writeback_pending`, or `aborted` result fails the Jira gate and requires reconciliation; do not advance to `/tgd-develop` as if sync succeeded.
8. **State the concurrency limit honestly.** Stable sync IDs and reconciliation make retries idempotent after a successful writeback, but Jira does not provide an exactly-once guarantee across concurrent clients. Conflicts or ambiguous remote results require reconciliation; do not promise exactly-once delivery.
9. **If 2 at either prompt:** make no Jira or TASKS.md sync changes and proceed to verification.

**Verification Gate** (runs regardless of whether Jira sync happened):
- [ ] `$TGD_DIR/<feature-name>/TASKS.md` exists and is non-empty
- [ ] `python3 "$TGD_REPO_ROOT/scripts/check-doc-sections.py" TASKS "$TGD_DIR/<feature-name>/TASKS.md"` exits 0 — required sections present, ≥1 task, ≥1 checkpoint, ≥1 `**Status:**` line (the `## Sign-off` section feeds `/tgd-release`'s sign-off gate — its absence would silently skip that check). Resolve `$TGD_REPO_ROOT` per `tgd-core-rules` → **Resolving $TGD_REPO_ROOT**.
- [ ] If this was a re-plan (TASKS.md pre-existed): every task that had `**Status:** complete` is still present with its Status line and `Test:` fields intact, no existing `AC-<task>.<n>` id was renumbered, and the existing `> **Jira-Source-ID**:` plus every `**Jira:**` / `**Jira-Sync-ID:**` value was preserved
- [ ] TASKS.md has exactly one `> **Jira-Source-ID**: tgd-source-<lowercase UUID v4>` value
- [ ] Every task has `**Jira:**` and `**Jira-Sync-ID:**` fields; unsynced tasks use `—`
- [ ] Every acceptance criterion carries a stable `AC-<task>.<n>` id in BDD format — check: `grep -qE 'AC-[0-9]+[.][0-9]+' TASKS.md`. Without ids, `/tgd-verify`'s `ac-trace.py` gate fails closed.
- [ ] Every criterion has an explicit `[R]` Yes/No regression decision
- [ ] If UI mode is 1–3: DESIGN.md passes its section check, `[x] **DESIGN**: Direction Approved` is present, and every UI task cites the relevant DESIGN.md section/component
- [ ] If UI mode is 1–3: UI acceptance criteria cover required runtime states, responsive viewports, and keyboard/focus behavior from DESIGN.md
- [ ] If PRD §6 names new events: each has a `$TGD_DIR/TRACKING-PLAN.md` entry (Status: planned) and an instrumentation task with its own AC

End with the closing report per `tgd-core-rules` → **Command Closing Report**: 📦 產出 (TASKS.md — N 個任務、M 條驗收標準；Jira「已驗證回寫 keys」／「取消」／「略過」／「未完成：<result keys + issue keys>」) · 🔎 檢查 (gate as one line) · ➡️ conflict-free success/cancel/skip 才顯示 `/tgd-develop`；Jira 未完成時顯示「先對帳並重新 dry-run」，不要宣稱 Plan gate 通過. Don't paste the raw checklist above.
