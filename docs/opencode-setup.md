# OpenCode Setup

This guide explains how to use tGD skills and lifecycle commands with OpenCode.

## Overview

OpenCode supports native TypeScript plugins, custom `/commands`, and skill
discovery through its built-in `skill` tool. tGD setup installs skills and
commands; it does not install a session plugin and does not install a global `AGENTS.md`.

tGD routing comes from:

- Skills discovered by OpenCode and exposed through the built-in `skill` tool
- Model compliance with each skill's trigger instructions
- Explicit `/tgd-*` commands

Repository-local instructions such as `AGENTS.md` may still apply when they are
part of the project opened in OpenCode, but setup does not install them
globally or rely on them for routing.

Setup installs 7 slash commands. It does not inject model context. You can use
either routing style:

- Ask naturally and let the model select a discovered skill based on intent
- `/tgd-*` commands let you select a lifecycle entry point directly

Natural-language routing remains available when no slash command is used, but
its automatic skill selection depends on model compliance.

---

## Installation

1. Clone the repository:

```bash
git clone https://github.com/openclawyhwang-hub/tGD.git
```

2. Open the project in OpenCode.

3. Install the shared skills and commands:

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

Setup links the repository skills into OpenCode's skill-discovery directory.
Each discovered skill describes when it applies and how the agent should use
it. A compliant model should:

- Detect when a skill applies
- Invoke the `skill` tool
- Follow the skill exactly

### 2. Automatic Skill Invocation

When the model follows the discovered skill instructions, it evaluates each
request and maps it to the appropriate skill.

Examples:

- "build a feature" → `tgd-develop-incremental` + `tgd-develop-tdd`
- "design a system" → `tgd-define-spec`
- "fix a bug" → `tgd-verify-debug`
- "review this code" → `tgd-review-quality`

The user does **not** need to explicitly request skills, although automatic
selection depends on model compliance. Use a `/tgd-*` command when you want to
choose the lifecycle entry point explicitly.

### 3. Lifecycle Mapping

The development lifecycle is encoded implicitly:

- DEFINE → `tgd-define-spec`
- PLAN → `tgd-plan-breakdown`
- BUILD → `tgd-develop-incremental` + `tgd-develop-tdd`
- VERIFY → `tgd-verify-debug`
- REVIEW → `tgd-review-quality`
- SHIP → `tgd-release-ship`

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
- Invokes `tgd-define-spec`
- Produces a spec before writing code
- Moves to planning and implementation skills

---

### Example 2: Bug Fix

User:
```
This endpoint is returning 500 errors
```

Agent behavior:
- Invokes `tgd-verify-debug`
- Reproduces → localizes → fixes → adds guards

---

### Example 3: Code Review

User:
```
Review this PR
```

Agent behavior:
- Invokes `tgd-review-quality`
- Applies structured review (correctness, design, readability, etc.)

---

## Agent Expectations (Critical)

For OpenCode to work correctly, the agent must follow these rules:

- Always check if a skill applies before acting
- If a skill applies, it MUST be used
- Never skip required workflows (spec, plan, test, etc.)
- Do not jump directly to implementation

These expectations come from the discovered skill instructions. Setup does not
add a global instruction file, so natural-language enforcement depends on model
compliance. Explicit `/tgd-*` commands remain available when you want to select
the workflow directly.

---

## Limitations

- Skill invocation depends on model compliance

Use a `/tgd-*` command when you want deterministic lifecycle routing.

---

## Session Context

Although OpenCode supports native TypeScript plugins, tGD deliberately does
not install a session plugin. Plain setup and `--with-session-preamble` both
leave OpenCode context unchanged; routing comes from direct skill discovery
and the explicit `/tgd-*` commands.

---

## Recommended Workflow

Just use natural language:

- "Design a feature"
- "Plan this change"
- "Implement this"
- "Fix this bug"
- "Review this"

With a compliant model, the agent can automatically select and execute the
applicable skills. Use a `/tgd-*` command whenever you prefer an explicit
lifecycle entry point.

---

## Summary

OpenCode integration works by combining:

- Structured skills (this repo)
- Model-driven skill selection from OpenCode's discovered skills
- Explicit lifecycle commands

This provides both natural-language skill routing (subject to model compliance)
and explicit lifecycle commands, without installing global agent instructions
or injecting session context.
