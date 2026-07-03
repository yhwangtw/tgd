# OpenCode Setup

This guide explains how to use tGD with OpenCode in a way that closely mirrors the Claude Code experience (automatic skill selection, lifecycle-driven workflows, and strict process enforcement).

## Overview

OpenCode supports custom `/commands`, but does not have a native plugin system or automatic skill routing like Claude Code.

Instead, we achieve parity through:

- A strong system prompt (`AGENTS.md`)
- The built-in `skill` tool
- Consistent skill discovery from the `/skills` directory

This creates an **agent-driven workflow** where skills are selected and executed automatically.

While it is possible to recreate `/spec`, `/plan`, and other commands in OpenCode, this integration intentionally uses an agent-driven approach instead:

- Skills are selected automatically based on intent
- Workflows are enforced via `AGENTS.md`
- No manual command invocation is required

This more closely matches how Claude Code behaves in practice, where skills are triggered automatically rather than manually.

---

## Installation

1. Clone the repository:

```bash
git clone https://github.com/openclawyhwang-hub/tGD.git
```

2. Open the project in OpenCode.

3. Ensure the following files are present in your workspace:

- `AGENTS.md` (root)
- `skills/` directory

No additional installation is required.

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

### 3. Lifecycle Mapping (Implicit Commands)

The development lifecycle is encoded implicitly:

- DEFINE → `tgd-spec-driven-development`
- PLAN → `tgd-planning-and-task-breakdown`
- BUILD → `tgd-incremental-implementation` + `tgd-test-driven-development`
- VERIFY → `tgd-debugging-and-error-recovery`
- REVIEW → `tgd-code-review-and-quality`
- SHIP → `tgd-shipping-and-launch`

This replaces slash commands like `/spec`, `/plan`, etc.

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

- No native slash commands (handled via intent mapping instead)
- Skill invocation depends on model compliance

Despite these, the workflow closely matches Claude Code in practice.

---

## Plugins (Hooks)

OpenCode supports lifecycle hooks via TypeScript plugins. tGD ships three plugins in `.opencode/plugins/`:

| Plugin | Hook | Purpose |
|--------|------|---------|
| `session-start.ts` | `session.created` | Injects `tgd-router` meta-skill at session start |
| `sdd-cache.ts` | `tool.execute.before/after` | HTTP cache for `tgd-source-driven-development` doc fetching |

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

**safe-edit** — Protects code regions marked with `@safe-edit begin/end` markers in long files.

**sdd-cache** — Caches WebFetch responses with HTTP validator revalidation. Same behavior as the Claude Code hook: only serves from cache when the origin responds `304 Not Modified`.

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

This results in a **fully agent-driven, production-grade engineering workflow** without requiring plugins or manual commands.
