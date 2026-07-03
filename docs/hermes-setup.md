# Hermes Agent Setup

This guide explains how to use tGD with [Hermes Agent](https://github.com/NousResearch/hermes-agent) by Nous Research.

## Overview

Hermes Agent is an open-source AI agent framework that runs in your terminal, messaging platforms (Telegram, Discord, Slack, and 15+ others), and IDEs. It supports a full plugin system with custom tools, hooks, and slash commands.

tGD integrates with Hermes via a **Python plugin** that provides:

- **7 slash commands** (`/tgd-map` → `/tgd-release`)
- **Session-start hook** (auto-injects the tgd-router meta-skill)
- **28 skills** (symlinked into `~/.hermes/skills/`)

This gives Hermes the same lifecycle enforcement as Claude Code — skills are auto-discovered, commands are native slash commands, and the meta-skill is injected at session start.

---

## Installation

### Prerequisites

- [Hermes Agent](https://hermes-agent.nousresearch.com/docs/) installed (`hermes` on PATH)

### Setup

1. Clone the repository:

```bash
git clone https://github.com/openclawyhwang-hub/tGD.git && cd tGD
```

2. Run the installer:

```bash
bash setup.sh
```

The installer auto-detects Hermes and configures:
- Skills → `~/.hermes/skills/tgd-*` (individual symlinks)
- Plugin → `~/.hermes/plugins/tgd/` (symlink to `.hermes/plugins/tgd/`)
- AGENTS.md → `~/.hermes/AGENTS.md`

3. Start Hermes:

```bash
hermes
```

4. Verify the plugin is loaded:

```
/plugins
```

You should see `tgd` with 7 commands registered.

---

## How It Works

### 1. Slash Commands

tGD registers 7 slash commands available in both CLI and gateway sessions:

| Command | Description |
|---------|-------------|
| `/tgd-map` | Scan and understand the existing project context |
| `/tgd-define` | Create spec, PRD, and acceptance criteria |
| `/tgd-plan` | Break the spec into ordered implementation tasks |
| `/tgd-develop` | Implement tasks incrementally with TDD |
| `/tgd-verify` | Run tests and validate completion claims |
| `/tgd-review` | Multi-axis code review before merge |
| `/tgd-release` | Create version tag and changelog |

Command prompts are sourced from `.claude/commands/*.md` — single source of truth shared with Claude Code, Codex CLI, and OpenCode.

### 2. Session-Start Hook

The `on_session_start` hook automatically injects the `tgd-router` meta-skill into every new session. This is equivalent to Claude Code's `SessionStart` hook.

The hook uses Hermes's context injection mechanism: the meta-skill content is appended to the first user message (not the system prompt), preserving prompt caching.

### 3. Skills

All 28 tGD skills are symlinked into `~/.hermes/skills/` and auto-discovered by Hermes's skill system. Skills follow the standard SKILL.md format with YAML frontmatter.

---

## Usage

### CLI

```bash
hermes
# In session:
/tgd-map
```

### Messaging Gateway (Telegram, Discord, etc.)

If Hermes is running as a gateway, the same slash commands are available:

```
/tgd-map
```

### Passing Arguments

All commands accept trailing text as additional context:

```
/tgd-develop add user authentication with OAuth2
```

---

## Troubleshooting

### Plugin not showing

```bash
# Check plugin status
/plugins

# Verbose plugin discovery
HERMES_PLUGINS_DEBUG=1 hermes

# Check logs
hermes logs --level WARNING | grep -i plugin
```

### Skills not discovered

```bash
# List installed skills
hermes skills list

# Reload skills
/reload-skills
```

### Session-start hook not firing

The hook fires on new sessions only. Start a fresh session:

```
/new
```

Or restart Hermes:

```bash
hermes gateway restart
```

---

## File Structure

```
tGD/
├── .hermes/
│   ├── AGENTS.md              # Agent instructions (Verification Iron Law)
│   └── plugins/
│       └── tgd/
│           ├── plugin.yaml    # Plugin manifest
│           └── __init__.py    # register(ctx): 7 commands + on_session_start hook
└── ...
```

---

## Differences from Claude Code

| Feature | Claude Code | Hermes Agent |
|---------|-------------|--------------|
| Skills | `~/.claude/skills/` symlinks | `~/.hermes/skills/` symlinks |
| Commands | `.claude/commands/*.md` | Plugin `register_command()` |
| Session hook | `hooks/hooks.json` (JSON) | Plugin `on_session_start` (Python) |
| Hook format | `{priority, message}` JSON | `ctx.register_command()` + `ctx.register_hook()`; session hook returns a `{"context": ...}` dict |
| Prompt source | `.claude/commands/*.md` | Same files, read by plugin |

Both platforms share the exact same command prompt files and skill content — only the delivery mechanism differs.
