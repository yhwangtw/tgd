# OpenCode Setup

This guide explains how to use tGD with OpenCode in a way that closely mirrors the Claude Code experience (automatic skill selection, lifecycle-driven workflows, and strict process enforcement).

## Overview

OpenCode supports custom `/commands`, but does not have a native plugin system or automatic skill routing like Claude Code.

Instead, we achieve parity through:

- A strong system prompt (`AGENTS.md`)
- The built-in `skill` tool
- Consistent skill discovery from the `/skills` directory

This creates an **agent-driven workflow** where skills are selected and executed automatically.

The setup also installs 7 slash commands for explicit lifecycle control. You
can use either style:

- Skills are selected automatically based on intent
- Workflows are enforced via `AGENTS.md`
- `/tgd-*` commands let you select a lifecycle entry point directly

Natural-language routing remains available when no slash command is used.

---

## Installation

1. Clone the repository:

```bash
git clone https://github.com/openclawyhwang-hub/tGD.git
```

2. Open the project in OpenCode.

3. Install the shared skills, commands, and session plugin:

```bash
cd tGD
bash setup.sh
```

---

## How It Works

### 1. Skill Discovery

All skills live in:

```
skills/<skill-name>/SKILL.md
```

OpenCode agents are instructed (via `AGENTS.md`) to:

- Detect when a skill applies
- Invoke the `skill` tool
- Follow the skill exactly

### 2. Automatic Skill Invocation

The agent evaluates every request and maps it to the appropriate skill.

Examples:

- "build a feature" → `tgd-incremental-implementation` + `tgd-test-driven-development`
- "design a system" → `tgd-spec-driven-development`
- "fix a bug" → `tgd-debugging-and-error-recovery`
- "review this code" → `tgd-code-review-and-quality`

The user does **not** need to explicitly request skills.

### 3. Lifecycle Mapping

The development lifecycle is encoded implicitly:

- DEFINE → `tgd-spec-driven-development`
- PLAN → `tgd-planning-and-task-breakdown`
- BUILD → `tgd-incremental-implementation` + `tgd-test-driven-development`
- VERIFY → `tgd-debugging-and-error-recovery`
- REVIEW → `tgd-code-review-and-quality`
- SHIP → `tgd-shipping-and-launch`

The same mappings are available explicitly as `/tgd-define`, `/tgd-plan`,
`/tgd-develop`, `/tgd-verify`, `/tgd-review`, and `/tgd-release`, with
`/tgd-map` for project initialization.

---

## Usage Examples

### Example 1: Feature Development

User:
```
Add authentication to this app
```

Agent behavior:
- Detects feature work
- Invokes `tgd-spec-driven-development`
- Produces a spec before writing code
- Moves to planning and implementation skills

---

### Example 2: Bug Fix

User:
```
This endpoint is returning 500 errors
```

Agent behavior:
- Invokes `tgd-debugging-and-error-recovery`
- Reproduces → localizes → fixes → adds guards

---

### Example 3: Code Review

User:
```
Review this PR
```

Agent behavior:
- Invokes `tgd-code-review-and-quality`
- Applies structured review (correctness, design, readability, etc.)

---

## Agent Expectations (Critical)

For OpenCode to work correctly, the agent must follow these rules:

- Always check if a skill applies before acting
- If a skill applies, it MUST be used
- Never skip required workflows (spec, plan, test, etc.)
- Do not jump directly to implementation

These rules are enforced via `AGENTS.md`.

---

## Limitations

- Skill invocation depends on model compliance

Use a `/tgd-*` command when you want deterministic lifecycle routing.

---

## Plugins (Hooks)

OpenCode supports lifecycle hooks via TypeScript plugins. tGD ships one plugin in `.opencode/plugins/`:

| Plugin | Hook | Purpose |
|--------|------|---------|
| `session-start.ts` | `session.created` | Injects `tgd-router` meta-skill at session start |

### Installation

```bash
bash setup.sh
```

Setup auto-detects OpenCode and symlinks plugins to `~/.config/opencode/plugins/`.

### Manual Installation

```bash
mkdir -p ~/.config/opencode/plugins
ln -sf "$(pwd)/.opencode/plugins"/* ~/.config/opencode/plugins/
```

### How It Works

**session-start** — Injects the `tgd-router` meta-skill into the agent's context at session start so the router skill is always available.

---

## Recommended Workflow

Just use natural language:

- "Design a feature"
- "Plan this change"
- "Implement this"
- "Fix this bug"
- "Review this"

The agent will automatically select and execute the correct skills.

---

## Summary

OpenCode integration works by combining:

- Structured skills (this repo)
- Strong agent rules (`AGENTS.md`)
- Automatic skill invocation via reasoning

This results in a production-grade workflow with both automatic skill routing
and explicit lifecycle commands.
