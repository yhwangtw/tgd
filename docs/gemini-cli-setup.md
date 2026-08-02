# Using tGD with Gemini CLI

## Setup

### Option 1: Install as Skills (Recommended)

Gemini CLI has a native skills system that auto-discovers `SKILL.md` files in
`.gemini/skills/` or `.agents/skills/` directories. A `SKILL.md` is discovered
at the skills root or one directory deep; deeper nesting is ignored. tGD
therefore links every `skills/<skill-name>/` directory directly into
`~/.gemini/skills/<skill-name>/`. Each skill activates on demand when it
matches your task.

For bundled Understand-Anything, setup links every skill at the shared
`~/.agents/skills/<canonical-name>` path and links the plugin root at
`~/.understand-anything-plugin`. Gemini uses those universal links directly.
Only when a universal canonical path has a collision with an existing user
path does setup add that one skill as a direct fallback under
`~/.gemini/skills/<canonical-name>`. This keeps normal installs deduplicated
without overwriting a user-owned collision.

**Install all tGD integration assets from a local clone:**

```bash
git clone https://github.com/openclawyhwang-hub/tGD.git
cd tGD
bash setup.sh
```

**Or link only the skills from an existing local clone:**

```bash
cd /path/to/tGD
mkdir -p "$HOME/.gemini/skills"
for skill_dir in "$(pwd)"/skills/*/; do
  ln -sf "$skill_dir" "$HOME/.gemini/skills/$(basename "$skill_dir")"
done
```

**Link the skills for a specific workspace only:**

```bash
cd /path/to/workspace
for skill_dir in /path/to/tGD/skills/*/; do
  gemini skills link "$skill_dir" --scope workspace
done
```

Skills installed at workspace scope go into `.gemini/skills/` (or `.agents/skills/`). User-level skills go into `~/.gemini/skills/`.

Once installed, verify with:

```
/skills list
```

Gemini CLI injects skill names and descriptions into the prompt automatically. When it recognizes a matching task, it asks permission to activate the skill before loading its full instructions.

### Option 2: GEMINI.md (Persistent Context)

For skills you want always loaded as persistent project context (rather than on-demand activation), add them to your project's `GEMINI.md`:

```bash
# Create GEMINI.md with core skills as persistent context
cat /path/to/tGD/skills/tgd-develop-incremental/SKILL.md > GEMINI.md
echo -e "\n---\n" >> GEMINI.md
cat /path/to/tGD/skills/tgd-review-quality/SKILL.md >> GEMINI.md
```

You can also modularize by importing from separate files:

```markdown
# Project Instructions

@skills/tgd-develop-tdd/SKILL.md
@skills/tgd-develop-incremental/SKILL.md
```

Use `/memory show` to verify loaded context, and `/memory reload` to refresh after changes.

> **Skills vs GEMINI.md:** Skills are on-demand expertise that activate only when relevant, keeping your context window clean. GEMINI.md provides persistent context loaded for every prompt. Use skills for phase-specific workflows and GEMINI.md for always-on project conventions.

## Recommended Configuration

### Always-On (GEMINI.md)

Add these as persistent context for every session:

- `tgd-develop-incremental` — Build in small verifiable slices
- `tgd-review-quality` — Five-axis review

### On-Demand (Skills)

Install these as skills so they activate only when relevant:

- `tgd-develop-tdd` — Activates when implementing logic or fixing bugs
- `tgd-define-spec` — Activates when starting a new project or feature
- `tgd-develop-ui` — Activates when building UI
- `tgd-review-security` — Activates during security reviews
- `tgd-review-performance` — Activates during performance work

## Advanced Configuration

### MCP Integration

Many skills in this pack leverage [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) tools to interact with the environment. For example:

- `tgd-verify-browser` uses CDP-based browser automation via Rust CLI.
- `tgd-review-performance` can benefit from performance-related MCP tools.

To enable these, configure the relevant MCP servers with the `gemini mcp`
command (use `gemini mcp list` to verify them). Gemini CLI stores user-level
MCP settings in `~/.gemini/settings.json`.

### Session Hooks

Gemini CLI supports session lifecycle hooks. tGD can install one `SessionStart`
hook as an explicit opt-in and preserves unrelated hooks already present in
your settings:

| Hook | Event | Purpose |
|------|-------|---------|
| `session-start.sh` | `SessionStart` | Injects a bounded tGD session preamble |

#### Installation

```bash
bash setup.sh --with-session-preamble
```

The opt-in setup atomically merges the canonical tGD hook into
`~/.gemini/settings.json`. Plain `bash setup.sh` removes only a managed or
verified legacy tGD hook; it does not replace the settings file or remove
foreign hooks.

#### Manual Installation

```bash
python3 scripts/merge-agent-hooks.py install \
  --platform gemini \
  --repo-root "$(pwd)" \
  --destination "$HOME/.gemini/settings.json" \
  --state "$HOME/.tgd/hook-ownership.json"
```

#### How It Works

**session-start** — Injects the bounded `hooks/session-preamble.md` content at
session start. The preamble carries the core verification rule and tells
Gemini to load `tgd-core-router` on demand when it needs skill routing. The full
router skill is not injected into every session.

### Explicit Context Loading

You can explicitly load any skill into your current session by referencing it with the `@` symbol in your prompt:

```markdown
Use the @skills/tgd-develop-tdd/SKILL.md skill to implement this fix.
```

This is useful when you want to ensure a specific workflow is followed without waiting for auto-discovery.

## Slash Commands

The repo ships 7 slash commands under `.gemini/commands/` that map to the development lifecycle. `bash setup.sh` links them into the user-level Gemini commands directory.

| Command | What it does |
|---------|--------------|
| `/tgd-map` | Scan and understand the existing project context |
| `/tgd-define` | Write a structured spec before writing code |
| `/tgd-plan` | Break work into small, verifiable tasks |
| `/tgd-develop` | Implement the next task incrementally |
| `/tgd-verify` | Run TDD workflow — red, green, refactor |
| `/tgd-review` | Five-axis code review |
| `/tgd-release` | Pre-launch checklist via parallel persona fan-out |

Each command invokes the corresponding skill automatically — no manual skill loading required.

> **Note:** Commands now use the `/tgd-*` namespace to avoid conflicts with built-in CLI commands.

## Usage Tips

1. **Prefer skills over GEMINI.md** — Skills activate on demand and keep your context window focused. Only put skills in GEMINI.md if you want them always loaded.
2. **Skill descriptions matter** — Each SKILL.md has a `description` field in its frontmatter that tells agents when to activate it. The descriptions in this repo are optimized for auto-discovery across all supported tools (Claude Code, Gemini CLI, etc.) by clearly stating both *what* the skill does and *when* it should be triggered.
3. **Use agents for review** — Copy `agents/code-reviewer.md` content when requesting structured code reviews.
4. **Combine with references** — Reference checklists from `references/` when working on specific quality areas like testing or performance.
