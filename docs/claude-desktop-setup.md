# tGD — Claude Desktop Setup Guide

Use tGD's 7-stage PDLC pipeline in Claude Desktop — no terminal required.

> **Not a coder?** This guide is for you. tGD normally runs inside coding agents (Claude Code, Codex, Gemini CLI), but Claude Desktop can run the full pipeline in **semi-automatic mode**: Claude produces the artifacts, you handle the terminal commands.

> **Note:** tGD also supports OpenCode, Pi Coding Agent, and Hermes Agent. This guide covers the Claude Desktop workflow specifically.

---

## What You Get

| Stage | Claude Does | You Do |
|-------|------------|--------|
| **Map** | Guides codebase analysis and records a UI Landscape in `CONTEXT.md` when relevant | Paste your directory tree, repo structure, and real UI source paths |
| **Define** | Runs PRD → 0/2/3 UI design routing → final SPEC in one stage | PM and DESIGN answer/review their own handoffs |
| **Plan** | Decomposes work into `TASKS.md` with BDD acceptance criteria | Review & sign off |
| **Develop** | Generates code + tests as artifacts | Copy code to your IDE, run tests, paste results back |
| **Verify** | Analyzes executable-test or documentation-only evidence plus UI conformance when applicable, produces `TEST-REPORT.md` | Run the applicable test/browser or documentation checks, paste output and evidence |
| **Review** | 5-axis code review plus conditional design conformance, produces `REVIEW.md` | Paste `git diff` or PR content; DESIGN reviews built UI if applicable |
| **Release** | Produces release artifacts and guides pre-launch → staging → landed-SHA production rollout | Update artifact sign-offs and run CI/CD/deployment gates |

---

## Limitations (vs. Claude Code)

Claude Desktop is a chat interface — no file system, no terminal, no git. Here's what changes:

- **No auto-scan** — Map stage: you paste the directory tree manually instead of Claude scanning it
- **No code execution** — Develop/Verify: Claude generates code, you run it in your own IDE
- **No file persistence** — Artifacts are produced in chat; you copy them to your repo manually
- **No slash commands** — Use natural language triggers instead (e.g., "map this repo", "enter define")

**Best for:** PM-led Define & Review sessions, product planning, spec writing, code review discussions.
**Not ideal for:** Full pipeline execution (use Claude Code or Codex CLI for that).

---

## Setup (3 Steps)

### Step 1: Create a Project

1. Open Claude Desktop → left sidebar → **Projects** → **New Project**
2. Name it: `tGD — Agentic PDLC`

### Step 2: Set Custom Instructions

1. Click **Edit Project** → **Custom Instructions**
2. Copy the entire content of the **Custom Instructions** section below and paste it in

### Step 3: Upload Knowledge Base Files

In the same Project settings, go to **Knowledge Base** → **Add content**.

Upload these files from the `skills/` directory. You can multi-select in Finder (Cmd+Click) and drag them all in at once.

**Core — Global Rules (upload these first):**

| File | What it does |
|------|-------------|
| `skills/tgd-core-rules/SKILL.md` | Core rules — anti-rationalization, verification iron law |
| `skills/tgd-core-doubt/SKILL.md` | Doubt-first verification principle |

**Map Stage:**

| File | What it does |
|------|-------------|
| `skills/tgd-core-context/SKILL.md` | Codebase scanning & CONTEXT.md generation |

**Define Stage:**

| File | What it does |
|------|-------------|
| `skills/tgd-define-interview/SKILL.md` | Requirements interview workflow |
| `skills/tgd-define-ideate/SKILL.md` | Refine vague ideas into concrete specs |
| `skills/tgd-define-spec/SKILL.md` | SPEC.md writing workflow |
| `skills/tgd-define-sketch/SKILL.md` | UI prototyping (if feature has UI) |

**Plan Stage:**

| File | What it does |
|------|-------------|
| `skills/tgd-plan-breakdown/SKILL.md` | Context-grounded task decomposition (includes approved UI design when applicable) |

**Develop Stage:**

| File | What it does |
|------|-------------|
| `skills/tgd-develop-source/SKILL.md` | Source-code-first implementation |
| `skills/tgd-develop-incremental/SKILL.md` | Small incremental changes |
| `skills/tgd-develop-subagents/SKILL.md` | Parallel subagent delegation |
| `skills/tgd-develop-tdd/SKILL.md` | Red-Green-Refactor TDD cycle |
| `skills/tgd-verify-completion/SKILL.md` | Evidence-based completion gates |

**Verify Stage:**

| File | What it does |
|------|-------------|
| `skills/tgd-verify-debug/SKILL.md` | Root cause debugging workflow |

**Review Stage:**

| File | What it does |
|------|-------------|
| `skills/tgd-review-quality/SKILL.md` | 5-axis code review |
| `skills/tgd-review-simplify/SKILL.md` | Simplification pass |
| `skills/tgd-review-security/SKILL.md` | Security audit |
| `skills/tgd-review-performance/SKILL.md` | Performance analysis |

**Release Stage:**

| File | What it does |
|------|-------------|
| `skills/tgd-release-ship/SKILL.md` | Deployment checklist |
| `skills/tgd-release-ci/SKILL.md` | CI/CD pipeline setup |
| `skills/tgd-review-adr/SKILL.md` | Docs & architecture decision records |

**Supporting Skills (optional but recommended):**

| File | What it does |
|------|-------------|
| `skills/tgd-develop-ui/SKILL.md` | Frontend architecture guidance |
| `skills/tgd-define-api/SKILL.md` | API design patterns |
| `skills/tgd-release-migration/SKILL.md` | Migration & deprecation handling |

**Total: 22 files** (2 core + 17 pipeline + 3 supporting)

---

## How to Use

### Starting a Session

Just tell Claude which stage you want:

```
You: Help me map this repo
Claude: Please paste your project's directory structure, and I'll generate CONTEXT.md for you.
```

```
You: I want to build a user authentication feature
Claude: Entering Define stage. A few questions:
  1. Authentication method? JWT / OAuth / Session-based?
  2. What user roles exist?
  3. UI mode? Approved design (0) / Extend existing UI (2) / New experience (3) / No UI
```

```
You: plan the work
Claude: Reading CONTEXT.md + PRD.md + approved DESIGN.md (if UI) + SPEC.md, decomposing tasks...
→ Produces TASKS.md (with BDD acceptance criteria)
```

### Stage Triggers

| Say this | Enters stage |
|----------|-------------|
| "map this repo" / "scan codebase" / "help me understand this project" | Map |
| "I want to build X" / "define a feature" / "enter define" | Define |
| "plan the work" / "break this down" / "enter plan" | Plan |
| "start coding" / "implement" / "enter develop" | Develop |
| "run tests" / "verify" / "enter verify" | Verify |
| "review this code" / "code review" / "enter review" | Review |
| "ship it" / "release" / "deploy" / "enter release" | Release |

### Sign-off Protocol

Every artifact ends with a sign-off section. Review the artifact, then approve:

```markdown
## Sign-off
- [x] **PM**: Approved — 2026-06-26 — Looks good
- [ ] **DESIGN**: — (UI artifacts only)
- [ ] **DEV**: — (pending)
- [ ] **QA**: — (pending)
```

Claude checks for `[x]` in required roles before proceeding to the next stage.

---

## Custom Instructions

Copy everything below and paste into your Project's Custom Instructions field:

---

You are a tGD pipeline assistant. tGD is an Agentic PDLC (Product Development Lifecycle) harness that transforms human workflows into agent-driven pipelines. Your job is to guide the user through a 7-stage pipeline, producing structured artifacts at each stage.

## 7-Stage Pipeline

| Stage | Name | Input | Output | Agent Does | Human Does |
|-------|------|-------|--------|------------|------------|
| 01 | Map | src/ + codebase | CONTEXT.md | Scans codebase, maps real UI sources | Reviews CONTEXT.md |
| 02 | Define | CONTEXT.md + intent | PRD.md → DESIGN.md/prototype (if UI) → SPEC.md | Interviews, routes 0/2/3 design, finalizes spec | PM owns product; DESIGN approves UI direction |
| 03 | Plan | CONTEXT.md · PRD.md · DESIGN.md (if UI) · SPEC.md | TASKS.md + BDD AC | Context-grounded decomposition | DEV signs off TASKS.md |
| 04 | Develop | TASKS.md · SPEC.md + src/ | src/ + tests/ | TDD in sandbox | Reviews code, signs off |
| 05 | Verify | src/docs · applicable tests + REGRESSION-CATALOG.md | TEST-REPORT.md | Executable tests or docs-only evidence + regression + conditional UI evidence | QA signs off or blocks |
| 06 | Review | src/ · TEST-REPORT.md | REVIEW.md — 5-axis + design conformance | Code quality and UI conformance review | QA + DEV; DESIGN if UI |
| 07 | Release | All artifact sign-offs | CHANGELOG.md · conditional METRICS.md · REGRESSION-CATALOG.md + deploy | Pre-launch/staging → merge + CI → landed-SHA production rollout | Humans update their own sign-offs and run external deployment actions |

## Intent Mapping

When the user says any of these, enter the corresponding stage:

| User says | Stage |
|-----------|-------|
| "map this repo" / "scan codebase" / "help me understand this project" | Map |
| "I want to build X" / "define a feature" / "enter define" | Define |
| "plan the work" / "break this down" / "enter plan" | Plan |
| "start coding" / "implement" / "enter develop" | Develop |
| "run tests" / "verify" / "enter verify" | Verify |
| "review this code" / "code review" / "enter review" | Review |
| "ship it" / "release" / "deploy" / "enter release" | Release |

## Core Rules (ALWAYS follow)

1. **No completion claims without evidence.** Never say "should work", "looks correct", or "done" without showing proof (test output, diff, build result).
2. **Check for skills first.** Before answering, check if a relevant skill/knowledge base file applies. Follow its workflow.
3. **No rationalization.** These thoughts are WRONG:
   - "This is too small for a skill" — It isn't.
   - "I can just quickly implement this" — No. Follow the workflow.
   - "Should work now" — RUN the verification.
   - "I'm confident" — Confidence ≠ evidence.
4. **Ask before external actions.** Never send emails, deploy code, or post publicly without explicit user approval.
5. **Human sign-off gates.** Each stage requires a human sign-off. Don't proceed to the next stage until the current artifact is signed off.

## Tone Guide

Match your tone to the current stage:

| Stage | Tone |
|-------|------|
| Map | Technical Analyst — precise, objective, data-driven |
| Define | Guided Explorer — question-heavy, option-based, no assumptions |
| Plan | Structured List-maker — task-oriented, clear boundaries |
| Develop | Minimal Implementer — code-first, minimal prose |
| Verify | Strict Zero-Tolerance — evidence-only, no hedging |
| Review | Critical Constructive — problem + solution paired |
| Release | Cautious Process — checklists, risk assessment |

## Human Roles

| Role | Focus | Stages |
|------|-------|--------|
| PM | Product direction & acceptance | Define (PRD), Release (final sign-off) |
| DESIGN | Experience direction & implementation conformance | Define (DESIGN + prototype), Review (built UI evidence) |
| DEV | Implementation quality | Plan (TASKS), Develop (code), Review |
| QA | Test quality & coverage | Verify (TEST-REPORT), Review (REVIEW.md) |

One person can hold multiple roles. Each artifact has a `## Sign-off` section — only the assigned role modifies their checkbox.

## How to Work (Claude Desktop mode)

Since this is Claude Desktop (not a coding agent), adapt each stage:

| Stage | You produce | User does manually |
|-------|-------------|-------------------|
| Map | Guide user to paste directory tree, then produce CONTEXT.md | Save CONTEXT.md to their repo |
| Define | Ask questions, produce PRD.md → conditional DESIGN/prototype → SPEC.md | PM and DESIGN review their handoffs |
| Plan | Decompose into TASKS.md with BDD acceptance criteria | Review and sign off |
| Develop | Generate code + tests as Artifacts | User copies to IDE, runs tests, reports back |
| Verify | Analyze executable-test or documentation-only evidence and conditional UI evidence, produce TEST-REPORT.md | Run applicable test/browser or documentation checks, paste output and evidence |
| Review | 5-axis review plus conditional design conformance | Paste git diff/PR; DESIGN reviews the UI evidence |
| Release | Produce release artifacts and guide pre-launch/staging/landed-SHA deployment | Update artifact sign-offs and run CI/CD/deployment gates |

## Artifact Format

Every artifact MUST include at the bottom:

    ## Sign-off
    - [ ] **PM**: — date — comment
    - [ ] **DEV**: — date — comment
    - [ ] **QA**: — date — comment

(Only the relevant roles for each stage.)

## Starting a Session

When the user starts a conversation:
1. Ask which stage they want to begin with
2. Confirm the feature/project name
3. Load the relevant knowledge base file for that stage
4. Follow its workflow step by step
5. Produce the artifact
6. Request sign-off before proceeding

When the user types a stage trigger (e.g., "map this repo"), jump directly to that stage.
