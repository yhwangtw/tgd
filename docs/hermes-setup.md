# Hermes Agent Setup

This guide explains how to use tGD with [Hermes Agent](https://github.com/NousResearch/hermes-agent).

## Overview

tGD integrates with Hermes through its native Python plugin and skill systems:

- 7 explicit slash commands (`/tgd-map` through `/tgd-release`)
- Directly discovered tGD skills
- An optional bounded session preamble

Plain `bash setup.sh` installs the commands and skills only. It does not install
a global `AGENTS.md` and does not inject tGD into every session.

## Installation

```bash
git clone https://github.com/openclawyhwang-hub/tGD.git
cd tGD
bash setup.sh
```

Setup links each skill and the tGD command plugin into the default Hermes home
and every existing Hermes profile. Start Hermes and inspect `/plugins`; the
`tgd` plugin should report seven registered commands.

To opt in to a bounded context reminder at the first LLM call of each session:

```bash
bash setup.sh --with-session-preamble
```

Running plain `bash setup.sh` again disables that optional preamble without
removing the commands or skills.

## Lifecycle Commands

| Command | Description |
|---------|-------------|
| `/tgd-map` | Scan and understand the existing project context |
| `/tgd-define` | Create the PRD, conditional design artifacts, and SPEC |
| `/tgd-plan` | Break the approved specification into implementation tasks |
| `/tgd-develop` | Implement incrementally with TDD |
| `/tgd-verify` | Run tests and validate completion claims |
| `/tgd-review` | Run the multi-axis review gate |
| `/tgd-release` | Complete the release workflow |

The plugin reads the canonical command bodies from `.claude/commands/*.md`, so
Hermes does not maintain a second copy of the workflow text. Trailing command
text is appended as additional context:

```text
/tgd-develop add user authentication with OAuth2
```

## Optional Session Preamble

Hermes only uses return values from `pre_llm_call` for context injection.
Accordingly, the tGD plugin registers `pre_llm_call`, not
`on_session_start`. The hook remains dormant unless setup creates the explicit
opt-in marker at `~/.tgd/session-preamble.enabled`.

When enabled, the plugin reads `hooks/session-preamble.md` and returns it once
per session as `{"context": "..."}`. The full `tgd-router` skill is still
loaded on demand rather than being copied into every session.

## Skills

Setup links each `skills/<name>/SKILL.md` directory directly into:

```text
~/.hermes/skills/<name>/
```

The same links are installed under each existing
`~/.hermes/profiles/<profile>/skills/` directory.

## Troubleshooting

Check that the plugin and skills are visible:

```text
/plugins
/reload-skills
```

For CLI diagnostics:

```bash
HERMES_PLUGINS_DEBUG=1 hermes
hermes skills list
hermes logs --level WARNING
```

If commands work but the optional preamble does not, verify that you ran
`bash setup.sh --with-session-preamble`, start a fresh session, and check that
`~/.tgd/session-preamble.enabled` is a tGD-managed symlink.

## File Structure

```text
tGD/
├── .hermes/
│   └── plugins/
│       └── tgd/
│           ├── plugin.yaml
│           └── __init__.py    # 7 commands + optional pre_llm_call hook
├── hooks/
│   └── session-preamble.md
└── skills/
    └── <name>/SKILL.md
```
