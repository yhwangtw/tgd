---
description: Plan — decompose specs into small, verifiable tasks with acceptance criteria
---

**🛑 Pre-flight: Environment Check**
- [ ] `$TGD_DIR/CONTEXT.md` exists (or `.codegraph/` is present).
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

**🔗 Jira Integration Gate** → IMMEDIATELY after TASKS.md is written. Do NOT skip this step.
1. Check env vars: `JIRA_URL`, `JIRA_PROJECT`, `JIRA_TOKEN`.
2. **If ALL configured:** Run the `tgd-jira-auto-sync` skill automatically. Do NOT ask.
   - Parse TASKS.md, create issues, report keys (e.g., `ENG-1234`).
   - Add issue keys back to TASKS.md tasks as `[ENG-1234]`.
3. **If NOT configured:** Ask the user conversationally:
   ```
   📋 TASKS.md 已完成（N 個任務）。
   🔗 要同步到 Jira 嗎？(y/n)
   ```
   - **If yes:** Ask for each missing value one at a time:
     - `JIRA_URL`（例：https://jira.company.com）
     - `JIRA_PROJECT`（例：ENG）
     - `JIRA_TOKEN`（Personal Access Token）
     Save `JIRA_URL` and `JIRA_PROJECT` to `$TGD_DIR/.env` for future runs. For `JIRA_TOKEN`, warn the user that `.env` is plaintext and recommend exporting it in their shell profile instead; only write it to `.env` if they explicitly agree. Then run the `tgd-jira-auto-sync` skill.
   - **If no:** Skip Jira, proceed to verification.
4. **Verification Gate:**
- [ ] `$TGD_DIR/<feature-name>/TASKS.md` exists and is non-empty
- [ ] TASKS.md contains at least one task with Acceptance Criteria
- [ ] If UI feature: TASKS.md references DESIGN.md components

If verification passes, suggest the next step: `/tgd-develop` to start implementing the first slice.
