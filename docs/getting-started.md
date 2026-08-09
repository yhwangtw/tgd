# Getting Started with tGD

tGD works with any AI coding agent that accepts Markdown instructions. This guide covers the universal approach. For tool-specific setup, see the dedicated guides.

## How Skills Work

Each skill is a Markdown file (`SKILL.md`) that describes a specific engineering workflow. When loaded into an agent's context, the agent follows the workflow — including verification steps, anti-patterns to avoid, and exit criteria.

**Skills are not reference docs.** They're step-by-step processes the agent follows.

## Quick Start (Any Agent)

### 1. Clone the repository

```bash
git clone https://github.com/yhwangtw/tgd.git
```

### 2. Choose a skill

Browse the `skills/` directory. Each subdirectory contains a `SKILL.md` with:
- **When to use** — triggers that indicate this skill applies
- **Process** — step-by-step workflow
- **Verification** — how to confirm the work is done
- **Common rationalizations** — excuses the agent might use to skip steps
- **Red flags** — signs the skill is being violated

### 3. Load the skill into your agent

Copy the relevant `SKILL.md` content into your agent's system prompt, rules file, or conversation. The most common approaches:

**System prompt:** Paste the skill content at the start of the session.

**Rules file:** Add skill content to your project's rules file (CLAUDE.md, .cursorrules, etc.).

**Conversation:** Reference the skill when giving instructions: "Follow the tgd-develop-tdd process for this change."

### 4. Use the core rules and intent router

Load `tgd-core-rules` before any tGD action. When no lifecycle command already supplies the pipeline and the request still needs routing, load `tgd-core-router` after the core rules and use its single Intent Routing table to select the applicable skill.

## Recommended Setup

### Minimal (Start here)

Load `tgd-core-rules`, plus three essential capability skills into your rules file:

1. **tgd-define-spec** — For defining what to build
2. **tgd-develop-tdd** — For proving it works
3. **tgd-review-quality** — For verifying quality before merge

These three cover the most critical quality gaps in AI-assisted development.

### Full Lifecycle

For comprehensive coverage, invoke the seven canonical lifecycle commands in order. Each command owns its complete phase pipeline, including its pre-flight checks, gates, and transition:

```
/tgd-map → /tgd-define → /tgd-plan → /tgd-develop → /tgd-verify → /tgd-review → /tgd-release
```

### Context-Aware Loading

Don't load all skills at once — it wastes context. Load skills relevant to the current task:

- Working on UI? Load `tgd-develop-ui`
- Debugging? Load `tgd-verify-debug`
- Setting up CI? Load `tgd-release-ci`

## Skill Anatomy

Every skill follows the same structure:

```
YAML frontmatter (name, description)
├── Overview — What this skill does
├── When to Use — Triggers and conditions
├── Core Process — Step-by-step workflow
├── Examples — Code samples and patterns
├── Common Rationalizations — Excuses and rebuttals
├── Red Flags — Signs the skill is being violated
└── Verification — Exit criteria checklist
```

See [skill-anatomy.md](skill-anatomy.md) for the full specification.

## Using Agents

The `agents/` directory contains pre-configured agent personas:

| Agent | Purpose |
|-------|---------|
| `code-reviewer.md` | Five-axis code review |
| `test-engineer.md` | Test strategy and writing |
| `security-auditor.md` | Vulnerability detection |

Load an agent definition when you need specialized review. For example, ask your coding agent to "review this change using the code-reviewer agent persona" and provide the agent definition.

## Using Commands

The `.claude/commands/` directory contains slash commands for Claude Code. The same commands are available on all platforms — Hermes Agent registers them via a Python plugin, Codex/OpenCode use `.md` prompts, Gemini uses `.toml`, and Pi uses a TypeScript extension.

| Command | Canonical responsibility |
|---------|--------------------------|
| `/tgd-map` | Map project context and establish the evidence tier |
| `/tgd-define` | Resolve intent and produce the approved specification |
| `/tgd-plan` | Produce verifiable tasks and conditionally preview or sync Jira |
| `/tgd-develop` | Implement the plan, test each task, and record review evidence |
| `/tgd-verify` | Prove acceptance criteria and cross-feature regression status |
| `/tgd-review` | Review quality and all applicable specialist axes |
| `/tgd-release` | Enforce sign-offs, merge, release, and update operational records |

The commands decide **when** a phase capability runs. Skills define **how** that capability works. Do not reconstruct a lifecycle command by chaining entries from the router's Intent Routing table.

## Using References

The `references/` directory contains supplementary checklists:

| Reference | Use With |
|-----------|----------|
| `testing-patterns.md` | tgd-develop-tdd |
| `performance-checklist.md` | tgd-review-performance |
| `security-checklist.md` | tgd-review-security |
| `accessibility-checklist.md` | tgd-develop-ui |

Load a reference when you need detailed patterns beyond what the skill covers.

## Spec and task artifacts

The `/tgd-define` and `/tgd-plan` commands create working artifacts (`$TGD_DIR/<feature>/PRD.md`, `$TGD_DIR/<feature>/TASKS.md`). Treat them as **living documents** while the work is in progress:

- Keep them in version control during development so the human and the agent have a shared source of truth.
- Update them when scope or decisions change.
- If your repo doesn’t want these files long‑term, delete them before merge or add the folder to `.gitignore` — the workflow doesn’t require them to be permanent.

## Tips

1. **Start with tgd-define-spec** for any non-trivial work
2. **Always load tgd-develop-tdd** when writing code
3. **Don't skip verification steps** — they're the whole point
4. **Load skills selectively** — more context isn't always better
5. **Use the agents for review** — different perspectives catch different issues
