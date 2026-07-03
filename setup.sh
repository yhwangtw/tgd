#!/bin/bash
# tGD One-Click Installer
# Usage: bash setup.sh [--upgrade|--uninstall|--version]
#
# --upgrade:  先掃描並清除舊版殘留的 stale symlink / hooks，再重新部署。
#             適合 tGD-clone git pull 後執行，確保乾淨無殘留。
# --uninstall: 徹底移除所有 tGD 部署（symlinks、hooks、版本標記）。
#             適合不想再用 tGD 或要乾淨重裝的使用者。

set -e

MODE="install"
if [[ "$1" == "--upgrade" || "$1" == "-u" ]]; then
    MODE="upgrade"
elif [[ "$1" == "--uninstall" || "$1" == "--remove" ]]; then
    MODE="uninstall"
elif [[ "$1" == "--version" || "$1" == "-v" ]]; then
    TGD_DIR="$(cd "$(dirname "$0")" && pwd)"
    if [[ -f "$TGD_DIR/VERSION" ]]; then
        echo "tGD $(cat "$TGD_DIR/VERSION")"
    else
        echo "tGD (unknown — VERSION not found)"
    fi
    exit 0
fi

TGD_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$TGD_DIR"

# Hermes profiles are isolated homes.  A profile-scoped Hermes session resolves
# skills/plugins from ~/.hermes/profiles/<name>/, not from the default
# ~/.hermes/ tree, so install tGD into default plus every existing profile.
hermes_homes() {
    # Always include the default home — link functions mkdir -p as needed.
    echo "$HOME/.hermes"
    if [[ -d "$HOME/.hermes/profiles" ]]; then
        for profile_home in "$HOME/.hermes/profiles"/*; do
            [[ -d "$profile_home" ]] || continue
            echo "$profile_home"
        done
    fi
}

display_home_path() {
    local path="$1"
    echo "${path/#$HOME/~}"
}

link_tgd_skills_to_hermes_home() {
    local hermes_home="$1"
    mkdir -p "$hermes_home/skills"
    local count=0
    for skill in "$TGD_DIR"/skills/*/; do
        local skill_name
        skill_name=$(basename "$skill")
        # Skip nested symlink traps
        if [[ "$skill_name" == "skills" ]]; then
            continue
        fi
        if [[ -d "$hermes_home/skills/$skill_name" && ! -L "$hermes_home/skills/$skill_name" ]]; then
            rm -rf "$hermes_home/skills/$skill_name"
        fi
        ln -sf "$skill" "$hermes_home/skills/$skill_name" 2>/dev/null || true
        count=$((count + 1))
    done
    echo "   ✅ Hermes skills linked: $(display_home_path "$hermes_home")/skills ($count skills)."
}

link_hermes_plugin_to_home() {
    local hermes_home="$1"
    if [[ -d "$TGD_DIR/.hermes/plugins/tgd" ]]; then
        mkdir -p "$hermes_home/plugins"
        if [[ -d "$hermes_home/plugins/tgd" && ! -L "$hermes_home/plugins/tgd" ]]; then
            rm -rf "$hermes_home/plugins/tgd"
        fi
        ln -sf "$TGD_DIR/.hermes/plugins/tgd" "$hermes_home/plugins/tgd" 2>/dev/null || true
        echo "   ✅ Hermes plugin linked: $(display_home_path "$hermes_home")/plugins/tgd."
    fi
}

link_hermes_agents_to_home() {
    local hermes_home="$1"
    if [[ -f "$TGD_DIR/.hermes/AGENTS.md" ]]; then
        ln -sf "$TGD_DIR/.hermes/AGENTS.md" "$hermes_home/AGENTS.md" 2>/dev/null || true
    fi
}

link_skill_folder_to_hermes_homes() {
    local source_dir="$1"
    local link_name="$2"
    local label="$3"
    while IFS= read -r hermes_home; do
        [[ -n "$hermes_home" ]] || continue
        mkdir -p "$hermes_home/skills"
        if [[ -d "$hermes_home/skills/$link_name" && ! -L "$hermes_home/skills/$link_name" ]]; then
            rm -rf "$hermes_home/skills/$link_name"
        fi
        ln -sf "$source_dir" "$hermes_home/skills/$link_name" 2>/dev/null || true
        echo "   ✅ Hermes $label linked: $(display_home_path "$hermes_home")/skills/$link_name."
    done < <(hermes_homes)
}

# ─── Prerequisite checks ─────────────────────────────────────────────────────
missing_deps=()
command -v git &> /dev/null || missing_deps+=("git")
command -v node &> /dev/null || missing_deps+=("node (Node.js >= 22)")
command -v python3 &> /dev/null || missing_deps+=("python3")
if [ ${#missing_deps[@]} -gt 0 ]; then
    echo "❌ Missing required dependencies:"
    for dep in "${missing_deps[@]}"; do
        echo "   • $dep"
    done
    echo ""
    echo "Install them and re-run: bash setup.sh"
    exit 1
fi

# ─── Uninstall mode ──────────────────────────────────────────────────────────
if [[ "$MODE" == "uninstall" ]]; then
    echo "🗑️  tGD Uninstall — Removing all deployments..."
    echo "====================================="
    echo ""

    # Helper: remove tGD-prefixed symlinks/files from a directory
    remove_tgd_items() {
        local dir="$1"
        local label="$2"
        local pattern="${3:-tgd}"
        if [[ -d "$dir" ]]; then
            for item in "$dir"/*; do
                local base=$(basename "$item")
                if [[ "$base" == *"$pattern"* ]] && [[ -L "$item" || -f "$item" ]]; then
                    echo "   🗑️  Removing $label: $item"
                    rm -f "$item"
                fi
            done
        fi
    }

    # 1. Remove all tGD symlinks
    echo "🧹 Removing tGD symlinks..."
    remove_tgd_items "$HOME/.claude/skills" "Claude skill" "tgd"
    remove_tgd_items "$HOME/.claude/commands" "Claude command" "tgd"
    remove_tgd_items "$HOME/.gemini/commands" "Gemini command" "tgd"
    remove_tgd_items "$HOME/.config/opencode/commands" "OpenCode command" "tgd"
    remove_tgd_items "$HOME/.codex/prompts" "Codex prompt" "tgd"
    remove_tgd_items "$HOME/.codex/skills" "Codex skill" "tgd"
    remove_tgd_items "$HOME/.config/opencode/skills" "OpenCode skill" "tgd"
    remove_tgd_items "$HOME/.gemini/skills" "Gemini skill" "tgd"
    remove_tgd_items "$HOME/.pi/agent/skills" "Pi skill" "tgd"
    remove_tgd_items "$HOME/.pi/agent/extensions" "Pi extension" "tgd"
    remove_tgd_items "$HOME/.claude/rules" "Claude rule" "tgd"
    while IFS= read -r hermes_home; do
        [[ -n "$hermes_home" ]] || continue
        remove_tgd_items "$hermes_home/skills" "Hermes skill" "tgd"
        # Remove Hermes plugin
        if [[ -L "$hermes_home/plugins/tgd" ]]; then
            echo "   🗑️  Removing Hermes plugin: $(display_home_path "$hermes_home")/plugins/tgd"
            rm -f "$hermes_home/plugins/tgd"
        fi
        if [[ -L "$hermes_home/AGENTS.md" ]] && readlink "$hermes_home/AGENTS.md" 2>/dev/null | grep -q "/tGD/.hermes/AGENTS.md"; then
            echo "   🗑️  Removing Hermes AGENTS.md: $(display_home_path "$hermes_home")/AGENTS.md"
            rm -f "$hermes_home/AGENTS.md"
        fi
    done < <(hermes_homes)

    # Remove Codex top-level skills/tGD symlink
    if [[ -L "$HOME/.codex/skills/tGD" ]]; then
        echo "   🗑️  Removing Codex skills/tGD: $HOME/.codex/skills/tGD"
        rm -f "$HOME/.codex/skills/tGD"
    fi
    # Remove OpenCode/Gemini/Pi top-level skills/tGD symlinks
    for dir in "$HOME/.config/opencode/skills" "$HOME/.gemini/skills" "$HOME/.pi/agent/skills"; do
        if [[ -L "$dir/tGD" ]]; then
            echo "   🗑️  Removing $dir/tGD"
            rm -f "$dir/tGD"
        fi
    done

    # Remove Pi instructions
    if [[ -L "$HOME/.pi/agent/instructions.md" ]]; then
        echo "   🗑️  Removing Pi instructions: $HOME/.pi/agent/instructions.md"
        rm -f "$HOME/.pi/agent/instructions.md"
    fi

    # 2. Remove tGD hooks from settings files
    echo ""
    echo "🧹 Removing tGD hooks from config files..."

    # Claude Code: ~/.claude/settings.json
    if [[ -f "$HOME/.claude/settings.json" ]]; then
        python3 << 'PYEOF'
import json, os

path = os.path.expanduser("~/.claude/settings.json")
with open(path) as f:
    data = json.load(f)

def is_tgd_hook(obj):
    """Check if a hook object is a tGD hook (contains /hooks/ or /tGD in command path)."""
    cmd = obj.get("command", "")
    return "/hooks/" in cmd or "/tGD" in cmd

def filter_hooks_deep(items):
    """Recursively filter hooks at any nesting depth. Returns (kept, removed_count)."""
    kept = []
    removed = 0
    for item in items:
        sub = item.get("hooks", [])
        if sub and all(isinstance(s, dict) and "command" in s for s in sub):
            # Flat hooks array (Claude format)
            non_tgd = [s for s in sub if not is_tgd_hook(s)]
            removed += len(sub) - len(non_tgd)
            if non_tgd:
                item["hooks"] = non_tgd
                kept.append(item)
        elif sub:
            # Nested hooks (Gemini format) - recurse
            kept_sub, r = filter_hooks_deep(sub)
            removed += r
            if kept_sub:
                item["hooks"] = kept_sub
                kept.append(item)
        else:
            # No hooks array, check this item itself
            if not is_tgd_hook(item):
                kept.append(item)
            else:
                removed += 1
    return kept, removed

hooks = data.get("hooks", {})
total_removed = 0

for event in list(hooks.keys()):
    entries = hooks[event]
    kept, r = filter_hooks_deep(entries)
    total_removed += r
    if kept:
        hooks[event] = kept
    else:
        hooks.pop(event, None)

with open(path, "w") as f:
    json.dump(data, f, indent=2)
print(f"   ✅ Removed {total_removed} tGD hooks from ~/.claude/settings.json (user hooks preserved)")
PYEOF
    fi

    # Codex CLI: ~/.codex/hooks.json (tGD owns this file entirely)
    if [[ -f "$HOME/.codex/hooks.json" ]]; then
        echo "   🗑️  Removing ~/.codex/hooks.json"
        rm -f "$HOME/.codex/hooks.json"
    fi

    # Gemini CLI: ~/.gemini/settings.json
    if [[ -f "$HOME/.gemini/settings.json" ]]; then
        python3 << 'PYEOF'
import json, os

path = os.path.expanduser("~/.gemini/settings.json")
with open(path) as f:
    data = json.load(f)

def is_tgd_hook(obj):
    cmd = obj.get("command", "")
    return "/hooks/" in cmd or "/tGD" in cmd

def filter_hooks_deep(items):
    kept = []
    removed = 0
    for item in items:
        sub = item.get("hooks", [])
        if sub and all(isinstance(s, dict) and "command" in s for s in sub):
            non_tgd = [s for s in sub if not is_tgd_hook(s)]
            removed += len(sub) - len(non_tgd)
            if non_tgd:
                item["hooks"] = non_tgd
                kept.append(item)
        elif sub:
            kept_sub, r = filter_hooks_deep(sub)
            removed += r
            if kept_sub:
                item["hooks"] = kept_sub
                kept.append(item)
        else:
            if not is_tgd_hook(item):
                kept.append(item)
            else:
                removed += 1
    return kept, removed

hooks = data.get("hooks", {})
total_removed = 0

for event in list(hooks.keys()):
    entries = hooks[event]
    kept, r = filter_hooks_deep(entries)
    total_removed += r
    if kept:
        hooks[event] = kept
    else:
        hooks.pop(event, None)

with open(path, "w") as f:
    json.dump(data, f, indent=2)
print(f"   ✅ Removed {total_removed} tGD hooks from ~/.gemini/settings.json (user hooks preserved)")
PYEOF
    fi

    # 3. Remove Understand-Anything links
    for dir in "$HOME/.claude/skills" "$HOME/.agents/skills" "$HOME/.codex/skills" "$HOME/.config/opencode/skills" "$HOME/.gemini/skills" "$HOME/.pi/agent/skills" "$HOME/.hermes/skills" "$HOME/.hermes/profiles"/*/skills; do
        if [[ -d "$dir" ]]; then
            for link in "$dir"/understand*; do
                if [[ -L "$link" ]] && readlink "$link" 2>/dev/null | grep -q "understand-anything"; then
                    echo "   🗑️  Removing UA link: $link"
                    rm -f "$link"
                fi
            done
        fi
    done

    # 4. Remove tgd CLI
    for bin_path in "/usr/local/bin/tgd" "$HOME/.local/bin/tgd"; do
        if [[ -L "$bin_path" ]] && readlink "$bin_path" 2>/dev/null | grep -q "tGD"; then
            echo "   🗑️  Removing tgd CLI: $bin_path"
            rm -f "$bin_path"
        fi
    done

    # 5. Remove version marker
    if [[ -f "$TGD_DIR/VERSION" ]]; then
        echo "   🗑️  Removing version marker: $TGD_DIR/VERSION"
        rm -f "$TGD_DIR/VERSION"
    fi
    if [[ -f "$HOME/.tgd-installed-version" ]]; then
        echo "   🗑️  Removing installed version marker: $HOME/.tgd-installed-version"
        rm -f "$HOME/.tgd-installed-version"
    fi

    # 6. Clean UA build artifacts (node_modules)
    if [[ -d "$TGD_DIR/vendor/understand-anything/node_modules" ]]; then
        echo "   🗑️  Removing UA build artifacts (vendor/understand-anything/node_modules)..."
        rm -rf "$TGD_DIR/vendor/understand-anything/node_modules"
    fi

    echo ""
    echo "===================================="
    echo "✅ tGD Uninstalled!"
    echo ""
    echo "The following were removed:"
    echo "  • All tGD symlinks (skills, commands, prompts, rules, extensions)"
    echo "  • All tGD hooks from config files"
    echo "  • tgd CLI binary"
    echo "  • Version marker (VERSION)"
    echo ""
    echo "Your ~/.claude/skills/ (and other dirs) are untouched — only tGD items were removed."
    exit 0
fi

if [[ "$MODE" == "upgrade" ]]; then
    echo "🔄 tGD Upgrade — Cleaning stale deployments..."
    echo "====================================="
    echo ""
else
    echo "🚀 tGD Setup"
    echo "===================================="
fi

# ─── Version marker ──────────────────────────────────────────────────────────
# Version is derived from git tags (CalVer). To bump: git tag v2026.07.04
TGD_VERSION=$(cat "$TGD_DIR/VERSION" 2>/dev/null || echo "unknown")
VERSION_FILE="$HOME/.tgd-installed-version"

# Guard: remove any pre-existing self-loop symlink at $TGD_DIR/skills/skills
# (historical artifact — was never created by setup.sh, but recurs somehow).
# Self-loops break Claude's individual symlink scan if a future setup.sh change
# ever iterates skills/*/ without filtering.
if [[ -L "$TGD_DIR/skills/skills" ]]; then
    rm -f "$TGD_DIR/skills/skills"
fi

if [[ "$MODE" == "install" ]] && [[ -f "$VERSION_FILE" ]]; then
    INSTALLED_VERSION=$(cat "$VERSION_FILE" 2>/dev/null || echo "unknown")
    if [[ "$INSTALLED_VERSION" == "$TGD_VERSION" ]]; then
        echo "ℹ️  tGD ${TGD_VERSION} already installed — refreshing..."
        MODE="upgrade"
    else
        echo "🔄 New version available: ${INSTALLED_VERSION} → ${TGD_VERSION}"
        MODE="upgrade"
    fi
fi

# Write current version marker
echo "$TGD_VERSION" > "$VERSION_FILE"

# ─── Upgrade mode: purge stale symlinks ──────────────────────────────────────
purge_stale_symlinks() {
    local dir="$1"
    local prefix="$2"
    echo "   🧹 Cleaning stale $prefix symlinks in $dir..."
    if [[ -d "$dir" ]]; then
        for link in "$dir"/*; do
            if [[ -L "$link" ]] && [[ ! -e "$link" ]]; then
                echo "      🗑️  Removing broken symlink: $link"
                rm -f "$link"
            fi
        done
    fi
}

purge_stale_skills() {
    local target_dir="$1"
    local label="$2"
    if [[ -d "$target_dir" ]]; then
        for link in "$target_dir"/*/; do
            link="${link%/}"
            if [[ -L "$link" ]]; then
                local resolved=$(readlink -f "$link" 2>/dev/null || python3 -c "import os,sys; print(os.path.realpath(sys.argv[1]))" "$link" 2>/dev/null || echo "")
                if [[ -z "$resolved" ]] || [[ ! -e "$resolved" ]]; then
                    echo "      🗑️  Removing stale skill: $link → $resolved"
                    rm -f "$link"
                fi
            fi
        done
    fi
}

# Remove pre-v2026.07 tGD symlinks (no tgd- prefix) that point into ~/tGD/skills/
# Migration: every tGD skill was renamed to tgd-<name> in v2026.07.x.
# Old symlinks (e.g. `spec-driven-development`) are dead references; new symlinks
# (`tgd-spec-driven-development`) are created by the install sections below.
# Safety: only remove if BOTH (a) symlink name lacks tgd- prefix AND
# (b) target path segment after /tGD/skills/ also lacks tgd- prefix.
# This protects third-party symlinks like `understand-anything`.
purge_old_tgd_symlinks() {
    local dir="$1"
    local label="$2"
    if [[ -d "$dir" ]]; then
        for link in "$dir"/*; do
            [[ -L "$link" ]] || continue
            local base=$(basename "$link")
            local target=$(readlink "$link" 2>/dev/null)
            # Extract the path segment after /tGD/skills/ (e.g. .../tGD/skills/tgd-spec-driven-development/)
            local seg=$(echo "$target" | sed -nE 's#.*/tGD/skills/([^/]+)/?.*#\1#p')
            # Match only if BOTH symlink name AND target segment are pre-prefix
            if [[ -n "$seg" ]] && [[ ! "$base" =~ ^tgd- ]] && [[ ! "$seg" =~ ^tgd- ]]; then
                echo "   🗑️  Removing legacy tGD symlink ($label): $link → $target"
                rm -f "$link"
            fi
        done
    fi
}

if [[ "$MODE" == "upgrade" ]]; then
    echo "🧹 Purging stale symlinks from previous version..."
    purge_stale_symlinks "$HOME/.claude/skills" "Claude Code skills"
    purge_stale_symlinks "$HOME/.claude/commands" "Claude Code commands"
    purge_stale_symlinks "$HOME/.gemini/commands" "Gemini CLI commands"
    purge_stale_symlinks "$HOME/.config/opencode/commands" "OpenCode commands"
    purge_stale_symlinks "$HOME/.codex/prompts" "Codex CLI prompts"
    purge_stale_symlinks "$HOME/.codex/skills" "Codex CLI skills"
    purge_stale_symlinks "$HOME/.config/opencode/skills" "OpenCode skills"
    purge_stale_symlinks "$HOME/.gemini/skills" "Gemini CLI skills"
    purge_stale_symlinks "$HOME/.pi/agent/skills" "Pi skills"
    purge_stale_symlinks "$HOME/.pi/agent/extensions" "Pi extensions"
    purge_stale_skills "$HOME/.claude/rules" "Claude Code rules"
    # v2026.07.x migration: remove pre-prefix tGD symlinks (now tgd-<name>)
    echo "🔄 Migrating tGD skills to tgd- prefix (v2026.07.x)..."
    purge_old_tgd_symlinks "$HOME/.claude/skills" "Claude Code"
    purge_old_tgd_symlinks "$HOME/.config/opencode/skills" "OpenCode"
    purge_old_tgd_symlinks "$HOME/.codex/skills" "Codex CLI"
    purge_old_tgd_symlinks "$HOME/.gemini/skills" "Gemini CLI"
    purge_old_tgd_symlinks "$HOME/.pi/agent/skills" "Pi"
    while IFS= read -r hermes_home; do
        [[ -n "$hermes_home" ]] || continue
        purge_stale_symlinks "$hermes_home/skills" "Hermes skills ($(display_home_path "$hermes_home"))"
        purge_old_tgd_symlinks "$hermes_home/skills" "Hermes ($(display_home_path "$hermes_home"))"
    done < <(hermes_homes)
    echo ""
fi

# 1. Verify Environment
if [[ "$OSTYPE" != "linux-gnu"* && "$OSTYPE" != "darwin"* ]]; then
    echo "❌ Warning: This installer supports Linux and macOS only."
fi

# 2. Configure Agents
echo "🤖 Configuring Agents..."

# OpenCode
if command -v opencode &> /dev/null; then
    echo "   📂 OpenCode detected."
    # Create global commands link (individual files, not subdirectory)
    mkdir -p ~/.config/opencode/commands
    for cmd in "$TGD_DIR"/.opencode/commands/*.md; do
        cmd_name=$(basename "$cmd")
        ln -sf "$cmd" ~/.config/opencode/commands/$cmd_name 2>/dev/null || true
    done
    echo "   ✅ Commands linked (7 tgd-* commands)."
    # Link skills for auto-detection (agent can find skills by name)
    if [ -d "$TGD_DIR/skills" ]; then
        mkdir -p ~/.config/opencode/skills
        if [ -d "$HOME/.config/opencode/skills/tGD" ] && [ ! -L "$HOME/.config/opencode/skills/tGD" ]; then
            rm -rf "$HOME/.config/opencode/skills/tGD"
        fi
        ln -sf "$TGD_DIR/skills" ~/.config/opencode/skills/tGD 2>/dev/null || true
        echo "   ✅ Skills linked for auto-detection."
    fi
    # Install plugins (hooks)
    if [ -d "$TGD_DIR/.opencode/plugins" ]; then
        mkdir -p ~/.config/opencode/plugins
        ln -sf "$TGD_DIR/.opencode/plugins"/* ~/.config/opencode/plugins/ 2>/dev/null || true
        echo "   ✅ Plugins installed (session-start)."
    fi
fi

# Claude Code
if command -v claude &> /dev/null; then
    echo "   📂 Claude Code detected."
    if [ -d "$TGD_DIR/.claude" ]; then
        # Link skills
        mkdir -p ~/.claude/skills
        for skill in "$TGD_DIR"/skills/*/; do
            skill_name=$(basename "$skill")
            # Skip nested symlink traps (e.g. skills/skills -> skills) — would create self-loop
            if [ "$skill_name" = "skills" ]; then
                continue
            fi
            # Remove real directories (from old copy-installs) before re-linking
            if [ -d "$HOME/.claude/skills/$skill_name" ] && [ ! -L "$HOME/.claude/skills/$skill_name" ]; then
                rm -rf "$HOME/.claude/skills/$skill_name"
            fi
            ln -sf "$skill" ~/.claude/skills/$skill_name 2>/dev/null || true
        done
        echo "   ✅ Skills linked."

        # Link commands (slash commands: /tgd-map, /tgd-develop, etc.)
        if [ -d "$TGD_DIR/.claude/commands" ]; then
            mkdir -p ~/.claude/commands
            ln -sf "$TGD_DIR/.claude/commands"/* ~/.claude/commands/ 2>/dev/null || true
            echo "   ✅ Commands linked (7 tgd-* slash commands)."
        fi

        # Install hooks into settings.json (resolve paths to absolute)
        if [ -d "$TGD_DIR/hooks" ] && [ -f "$TGD_DIR/hooks/hooks.json" ]; then
            mkdir -p ~/.claude
            TGD_ABS="$TGD_DIR"
            SETTINGS="$HOME/.claude/settings.json"
            # Create default settings.json if it doesn't exist
            if [ ! -f "$SETTINGS" ]; then
                echo '{}' > "$SETTINGS"
            fi
            python3 -c "
import json
TGD_ABS = '$TGD_ABS'
SETTINGS = '$SETTINGS'
# Load existing user settings
with open(SETTINGS) as f:
    user = json.load(f)
# Load tGD hooks
with open('hooks/hooks.json') as f:
    tgd = json.load(f)
# Resolve ${CLAUDE_PLUGIN_ROOT} to absolute path
def resolve(obj, key='command'):
    if isinstance(obj, dict):
        for k, v in list(obj.items()):
            if k == key and isinstance(v, str) and '$' + '{CLAUDE_PLUGIN_ROOT}' in v:
                obj[k] = v.replace('$' + '{CLAUDE_PLUGIN_ROOT}', TGD_ABS)
            else:
                resolve(v, key)
    elif isinstance(obj, list):
        for item in obj:
            resolve(item, key)
resolve(tgd)
# Merge hooks by event name (deduplicate by command string)
user_hooks = user.setdefault('hooks', {})
for event, hook_list in tgd.get('hooks', {}).items():
    existing = user_hooks.get(event, [])
    existing_cmds = set()
    for h in existing:
        for sub in h.get('hooks', []):
            existing_cmds.add(sub.get('command', ''))
    for entry in hook_list:
        for sub in entry.get('hooks', []):
            if sub.get('command', '') not in existing_cmds:
                existing.append(entry)
                break
    user_hooks[event] = existing
with open(SETTINGS, 'w') as f:
    json.dump(user, f, indent=2)
print('   ✅ Hooks merged into ~/.claude/settings.json.')
" 2>/dev/null || echo "   ⚠️  Hooks install failed. Check hooks/hooks.json exists."
        fi
    fi
fi

# Gemini CLI
if command -v gemini &> /dev/null; then
    echo "   📂 Gemini CLI detected."
    if [ -d "$TGD_DIR/.gemini" ]; then
        mkdir -p ~/.gemini/commands
        ln -sf "$TGD_DIR/.gemini/commands"/* ~/.gemini/commands/ 2>/dev/null || true
        echo "   ✅ Commands linked."
    fi
    # Link skills for auto-detection
    if [ -d "$TGD_DIR/skills" ]; then
        mkdir -p ~/.gemini/skills
        if [ -d "$HOME/.gemini/skills/tGD" ] && [ ! -L "$HOME/.gemini/skills/tGD" ]; then
            rm -rf "$HOME/.gemini/skills/tGD"
        fi
        ln -sf "$TGD_DIR/skills" ~/.gemini/skills/tGD 2>/dev/null || true
        echo "   ✅ Skills linked for auto-detection."
    fi
    # Install hooks (Gemini uses flat format, different from Claude Code/Codex nested format)
    if [ -f "$TGD_DIR/.gemini/settings.json" ]; then
        mkdir -p ~/.gemini
        TGD_ABS="$TGD_DIR"
        # Resolve relative paths in .gemini/settings.json to absolute
        if [ -f ~/.gemini/settings.json ]; then
            echo "   ⚠️  ~/.gemini/settings.json exists. Merging tGD hooks..."
            python3 -c "
import json
TGD_ABS = '$TGD_ABS'
with open('$HOME/.gemini/settings.json') as f:
    user = json.load(f)
with open('.gemini/settings.json') as f:
    tgd = json.load(f)
# Resolve relative paths, ensure type: 'command',
# and convert ALL hooks to nested format (matcher + hooks array)
for event, hook_list in tgd.get('hooks', {}).items():
    if event in ('BeforeTool', 'AfterTool'):
        by_matcher = {}
        for h in hook_list:
            if 'type' not in h:
                h['type'] = 'command'
            cmd = h.get('command', '')
            if cmd.startswith('bash hooks/'):
                h['command'] = cmd.replace('bash hooks/', 'bash ' + TGD_ABS + '/hooks/', 1)
            matcher = h.get('matcher', '*')
            if matcher not in by_matcher:
                by_matcher[matcher] = []
            h.pop('matcher', None)
            by_matcher[matcher].append(h)
        tgd['hooks'][event] = [
            {'matcher': m, 'hooks': hooks}
            for m, hooks in by_matcher.items()
        ]
    else:
        # Lifecycle events (SessionStart, SessionEnd) also need nested format
        # Source may already be nested (has 'hooks' key in items) or flat
        for h in hook_list:
            if 'hooks' in h and isinstance(h['hooks'], list):
                # Already nested — resolve paths in sub-hooks
                for sub in h['hooks']:
                    if 'type' not in sub:
                        sub['type'] = 'command'
                    cmd = sub.get('command', '')
                    if cmd.startswith('bash hooks/'):
                        sub['command'] = cmd.replace('bash hooks/', 'bash ' + TGD_ABS + '/hooks/', 1)
            else:
                # Flat format — wrap and resolve
                if 'type' not in h:
                    h['type'] = 'command'
                cmd = h.get('command', '')
                if cmd.startswith('bash hooks/'):
                    h['command'] = cmd.replace('bash hooks/', 'bash ' + TGD_ABS + '/hooks/', 1)
                h = {'matcher': '*', 'hooks': [h]}
        # Normalize: ensure top-level is list of {matcher, hooks} objects
        normalized = []
        for h in hook_list:
            if 'hooks' in h and isinstance(h['hooks'], list):
                normalized.append(h)
            else:
                normalized.append({'matcher': '*', 'hooks': [h]})
        tgd['hooks'][event] = normalized
user_hooks = user.setdefault('hooks', {})
for event, hook_list in tgd.get('hooks', {}).items():
    existing = user_hooks.get(event, [])
    # All events use nested format: [{matcher, hooks: [...]}]
    existing_by_matcher = {}
    for i, entry in enumerate(existing):
        m = entry.get('matcher', '*')
        existing_by_matcher[m] = i
    for entry in hook_list:
        matcher = entry.get('matcher', '*')
        if matcher in existing_by_matcher:
            # Replace existing entry
            existing[existing_by_matcher[matcher]] = entry
        else:
            existing.append(entry)
    user_hooks[event] = existing
with open('$HOME/.gemini/settings.json', 'w') as f:
    json.dump(user, f, indent=2)
print('   ✅ tGD hooks merged into ~/.gemini/settings.json.')
" 2>&1 || echo "   ⚠️  Merge failed — please manually merge hooks from .gemini/settings.json"
        else
            python3 -c "
import json
TGD_ABS = '$TGD_ABS'
with open('.gemini/settings.json') as f:
    cfg = json.load(f)
for event, hook_list in cfg.get('hooks', {}).items():
    for h in hook_list:
        cmd = h.get('command', '')
        if cmd.startswith('bash hooks/'):
            h['command'] = cmd.replace('bash hooks/', f'bash {TGD_ABS}/hooks/', 1)
with open('$HOME/.gemini/settings.json', 'w') as f:
    json.dump(cfg, f, indent=2)
print('   ✅ Hooks installed to ~/.gemini/settings.json.')
" 2>/dev/null || echo "   ⚠️  Hooks install failed. Check .gemini/settings.json exists."
        fi
    fi
fi

# Codex CLI
if command -v codex &> /dev/null; then
    echo "   📂 Codex CLI detected."
    mkdir -p ~/.codex
    if [ -d "$TGD_DIR/skills" ]; then
        # Remove real directory (from old copy-installs) before re-linking
        if [ -d "$HOME/.codex/skills/tGD" ] && [ ! -L "$HOME/.codex/skills/tGD" ]; then
            rm -rf "$HOME/.codex/skills/tGD"
        fi
        ln -sf "$TGD_DIR/skills" ~/.codex/skills/tGD 2>/dev/null || true
        echo "   ✅ Skills linked for auto-detection."
    fi
    if [ -d "$TGD_DIR/.codex/prompts" ]; then
        mkdir -p ~/.codex/prompts
        ln -sf "$TGD_DIR/.codex/prompts"/* ~/.codex/prompts/ 2>/dev/null || true
        echo "   ✅ Prompts linked (7 tgd-* commands)."
    fi
    # Install hooks (Codex only reads ~/.codex/hooks.json — plugin-local hooks don't work)
    # We merge TWO sources: hooks/hooks.json (Claude-style) and hooks/codex/hooks.json
    # (Codex-style). The merge is idempotent and dedups by command string.
    # See scripts/merge-codex-hooks.py for details and the Codex contract ref.
    if [ -f "$TGD_DIR/hooks/hooks.json" ] || [ -f "$TGD_DIR/hooks/codex/hooks.json" ]; then
        HOOKS_DST="$HOME/.codex/hooks.json"
        TGD_ABS="$TGD_DIR"
        export TGD_ABS HOOKS_DST
        python3 "$TGD_DIR/scripts/merge-codex-hooks.py" 2>/dev/null || echo "   ⚠️  Hooks install/merge failed. Check scripts/merge-codex-hooks.py."
    fi
fi

# Pi Coding Agent
if command -v pi &> /dev/null; then
    echo "   📂 Pi Coding Agent detected."
    # Install extension and instructions to ~/.pi/agent/
    mkdir -p "$HOME/.pi/agent/extensions"
    if [ -f "$TGD_DIR/.pi/extensions/tgd-commands.ts" ]; then
        ln -sf "$TGD_DIR/.pi/extensions/tgd-commands.ts" "$HOME/.pi/agent/extensions/tgd-commands.ts" 2>/dev/null || true
        echo "   ✅ Extension installed to ~/.pi/agent/extensions/tgd-commands.ts"
    fi
    if [ -f "$TGD_DIR/.pi/instructions.md" ]; then
        ln -sf "$TGD_DIR/.pi/instructions.md" "$HOME/.pi/agent/instructions.md" 2>/dev/null || true
        echo "   ✅ Instructions installed to ~/.pi/agent/instructions.md"
    fi
    # Link skills for auto-detection
    if [ -d "$TGD_DIR/skills" ]; then
        mkdir -p "$HOME/.pi/agent/skills"
        if [ -d "$HOME/.pi/agent/skills/tGD" ] && [ ! -L "$HOME/.pi/agent/skills/tGD" ]; then
            rm -rf "$HOME/.pi/agent/skills/tGD"
        fi
        ln -sf "$TGD_DIR/skills" "$HOME/.pi/agent/skills/tGD" 2>/dev/null || true
        echo "   ✅ Skills linked for auto-detection."
    fi
else
    echo "   ℹ️  Pi Coding Agent not detected — skip extension install."
fi

# Hermes Agent
if command -v hermes &> /dev/null; then
    echo "   📂 Hermes Agent detected."
    if [ -d "$TGD_DIR/skills" ]; then
        while IFS= read -r hermes_home; do
            [[ -n "$hermes_home" ]] || continue
            link_tgd_skills_to_hermes_home "$hermes_home"
        done < <(hermes_homes)
    fi

    if [ -d "$TGD_DIR/.hermes/plugins/tgd" ]; then
        while IFS= read -r hermes_home; do
            [[ -n "$hermes_home" ]] || continue
            link_hermes_plugin_to_home "$hermes_home"
        done < <(hermes_homes)
    fi

    if [ -f "$TGD_DIR/.hermes/AGENTS.md" ]; then
        while IFS= read -r hermes_home; do
            [[ -n "$hermes_home" ]] || continue
            link_hermes_agents_to_home "$hermes_home"
        done < <(hermes_homes)
        echo "   ✅ Hermes AGENTS.md linked across profiles."
    fi
else
    echo "   ℹ️  Hermes Agent not detected — skip plugin install."
fi

# CodeGraph (required for /tgd-map)
echo "📊 Checking CodeGraph..."
if command -v codegraph &> /dev/null; then
    echo "   ✅ CodeGraph already installed."
else
    if command -v npm &> /dev/null; then
        echo "   📥 Installing CodeGraph via npm..."
        npm install -g @colbymchenry/codegraph 2>/dev/null && echo "   ✅ CodeGraph installed." || echo "   ⚠️  Install manually: npm install -g @colbymchenry/codegraph"
    else
        echo "   ⚠️  npm not found. Install CodeGraph manually:"
        echo "      npm install -g @colbymchenry/codegraph"
    fi
fi

# tGD Wiki (Docusaurus 3) — powered by the tgd-wiki-generation skill
# No install needed here: /tgd-map Step 6 will run `npm install` inside $TGD_DIR
# on first use. Node.js 22+ is already required above (see prerequisite checks).
echo "📖 tGD Wiki: Docusaurus 3 site is generated by /tgd-map Step 6."
echo "   Node.js 22+ is already required for tGD. Nothing to install here."

# ─── Install UA dependencies (subshell-safe: cd won't leak) ──────────────────
install_ua_deps() {
    local ua_dir="$1"
    if [ -d "$ua_dir/node_modules" ]; then
        echo "   ✅ UA dependencies already installed."
        return 0
    fi
    if ! command -v pnpm &> /dev/null && ! command -v npm &> /dev/null; then
        echo "   ⚠️  pnpm/npm not found. Skills work but scanning scripts won't run."
        echo "      Install pnpm, then: cd vendor/understand-anything && pnpm install && pnpm build"
        return 1
    fi
    # Install pnpm if missing
    if ! command -v pnpm &> /dev/null; then
        echo "   📥 pnpm not found. Installing via npm..."
        # Check npm registry — refuse to use default registry.npmjs.org
        NPM_REGISTRY=$(npm config get registry 2>/dev/null || echo "")
        if [[ -z "$CI" ]] && { [[ "$NPM_REGISTRY" == *"registry.npmjs.org"* ]] || [[ -z "$NPM_REGISTRY" ]]; }; then
            echo "   ⚠️  npm registry is set to registry.npmjs.org (or not configured)."
            echo "      Set your registry first: npm config set registry <your internal registry URL>"
            echo "      Then re-run setup.sh, or install pnpm manually."
            return 1
        fi
        npm install -g pnpm 2>/dev/null && echo "   ✅ pnpm installed." || { echo "   ⚠️  npm install -g pnpm failed. Install manually."; return 1; }
    fi
    echo "   📦 Installing UA dependencies (pnpm install)..."
    # Check pnpm registry — refuse to use default registry.npmjs.org
    PNPM_REGISTRY=$(pnpm config get registry 2>/dev/null || echo "")
    if [[ -z "$CI" ]] && { [[ "$PNPM_REGISTRY" == *"registry.npmjs.org"* ]] || [[ -z "$PNPM_REGISTRY" ]]; }; then
        echo "   ⚠️  pnpm registry is set to registry.npmjs.org (or not configured)."
        echo "      Set your registry first: pnpm config set registry <your internal registry URL>"
        return 1
    fi
    # Subshell: cd won't affect the parent shell's cwd
    (cd "$ua_dir" && pnpm install --frozen-lockfile) && echo "   ✅ Dependencies installed." || {
        echo "   ⚠️  pnpm install failed. Last 5 lines:"
        (cd "$ua_dir" && pnpm install --frozen-lockfile 2>&1 | tail -5)
        echo "      Manual fix: cd vendor/understand-anything && pnpm install"
        return 1
    }
    if [ -d "$ua_dir/node_modules" ]; then
        echo "   🔨 Building UA (pnpm build)..."
        (cd "$ua_dir" && pnpm build) && echo "   ✅ UA built successfully." || {
            echo "   ⚠️  Build failed. Manual fix: cd vendor/understand-anything && pnpm build"
            return 1
        }
    fi
}

# Understand-Anything (bundled in vendor/)
echo "🧠 Checking Understand-Anything..."
UA_DIR="$TGD_DIR/vendor/understand-anything"
UA_SKILLS_DIR="$UA_DIR/understand-anything-plugin/skills"
if [ -d "$UA_SKILLS_DIR" ]; then
    echo "   ✅ Understand-Anything skills ready."
    install_ua_deps "$UA_DIR"

    # Make ~/.understand-anything/repo a symlink to vendor — single source of truth.
    # Only act when the target does NOT exist yet. If a real directory is already
    # there (e.g. user installed the official UA first), leave it alone.
    UA_REPO_LINK="$HOME/.understand-anything/repo"
    UA_PLUGIN_TARGET="$UA_DIR/understand-anything-plugin"
    if [[ -L "$UA_REPO_LINK" && ! -e "$UA_REPO_LINK" ]]; then
        # Broken symlink — fix it
        rm "$UA_REPO_LINK"
    fi
    if [[ ! -e "$UA_REPO_LINK" ]] && [[ ! -L "$UA_REPO_LINK" ]]; then
        mkdir -p "$(dirname "$UA_REPO_LINK")"
        ln -sf "$UA_PLUGIN_TARGET" "$UA_REPO_LINK"
        echo "   🔗 ~/.understand-anything/repo → vendor (tGD-managed)"
    elif [[ -L "$UA_REPO_LINK" ]]; then
        echo "   🔗 ~/.understand-anything/repo already symlinks to vendor."
    else
        echo "   ℹ️  ~/.understand-anything/repo exists (not a symlink) — keeping existing UA install."
    fi
else
    echo "   ⚠️  Understand-Anything not found at vendor/understand-anything/"
    echo "      Re-clone tGD or manually download from: https://github.com/Lum1104/Understand-Anything"
fi

# Link Understand-Anything skills to each platform
if [ -d "$UA_SKILLS_DIR" ]; then
    # Universal: ~/.agents/skills/understand (SKILL.md's primary fallback for plugin root resolution)
    mkdir -p "$HOME/.agents/skills"
    ln -sf "$UA_SKILLS_DIR/understand" "$HOME/.agents/skills/understand" 2>/dev/null && echo "   ✅ Universal: ~/.agents/skills/understand → symlink"
    # Claude Code: per-skill symlinks in ~/.claude/skills/
    if [ -d "$HOME/.claude" ] || [ -L "$HOME/.claude" ]; then
        for skill in "$UA_SKILLS_DIR"/*/; do
            skill_name=$(basename "$skill")
            # Skip nested symlink traps (UA vendor may contain a self-looping `skills` entry)
            if [ "$skill_name" = "skills" ]; then
                continue
            fi
            ln -sf "$skill" "$HOME/.claude/skills/understand-$skill_name" 2>/dev/null || true
        done
        echo "   ✅ Claude: Understand-Anything skills linked."
    fi
    # Codex: folder symlink in ~/.codex/skills/
    if [ -d "$HOME/.codex" ] || [ -L "$HOME/.codex" ]; then
        mkdir -p "$HOME/.codex/skills"
        if [ -d "$HOME/.codex/skills/understand-anything" ] && [ ! -L "$HOME/.codex/skills/understand-anything" ]; then
            rm -rf "$HOME/.codex/skills/understand-anything"
        fi
        ln -sf "$UA_SKILLS_DIR" "$HOME/.codex/skills/understand-anything" 2>/dev/null && echo "   ✅ Codex: Understand-Anything skills linked."
    fi
    # OpenCode: folder symlink in ~/.config/opencode/skills/
    if [ -d "$HOME/.config/opencode" ] || [ -L "$HOME/.config/opencode" ]; then
        mkdir -p "$HOME/.config/opencode/skills"
        if [ -d "$HOME/.config/opencode/skills/understand-anything" ] && [ ! -L "$HOME/.config/opencode/skills/understand-anything" ]; then
            rm -rf "$HOME/.config/opencode/skills/understand-anything"
        fi
        ln -sf "$UA_SKILLS_DIR" "$HOME/.config/opencode/skills/understand-anything" 2>/dev/null && echo "   ✅ OpenCode: Understand-Anything skills linked."
    fi
    # Gemini: folder symlink in ~/.gemini/skills/
    if [ -d "$HOME/.gemini" ] || [ -L "$HOME/.gemini" ]; then
        mkdir -p "$HOME/.gemini/skills"
        if [ -d "$HOME/.gemini/skills/understand-anything" ] && [ ! -L "$HOME/.gemini/skills/understand-anything" ]; then
            rm -rf "$HOME/.gemini/skills/understand-anything"
        fi
        ln -sf "$UA_SKILLS_DIR" "$HOME/.gemini/skills/understand-anything" 2>/dev/null && echo "   ✅ Gemini: Understand-Anything skills linked."
    fi
    # Pi: folder symlink in ~/.pi/agent/skills/
    if [ -d "$HOME/.pi" ] || [ -L "$HOME/.pi" ]; then
        mkdir -p "$HOME/.pi/agent/skills"
        if [ -d "$HOME/.pi/agent/skills/understand-anything" ] && [ ! -L "$HOME/.pi/agent/skills/understand-anything" ]; then
            rm -rf "$HOME/.pi/agent/skills/understand-anything"
        fi
        ln -sf "$UA_SKILLS_DIR" "$HOME/.pi/agent/skills/understand-anything" 2>/dev/null && echo "   ✅ Pi: Understand-Anything skills linked."
    fi
    # Hermes Agent: folder symlink in every Hermes profile home.
    if [ -d "$HOME/.hermes" ] || [ -L "$HOME/.hermes" ]; then
        link_skill_folder_to_hermes_homes "$UA_SKILLS_DIR" "understand-anything" "Understand-Anything skills"
    fi
fi

# 3. Install Optional Dependencies (Agent Browser)
echo "📦 Checking optional dependencies..."

# Agent Browser (E2E browser automation)
if [ -d "skills/tgd-agent-browser" ]; then
    echo "   🌐 Agent Browser skill detected."
    if command -v npm &> /dev/null || command -v npx &> /dev/null; then
        NPM_CMD=$(command -v npm || command -v npx)
        
        # Check if agent-browser is already installed
        if ! command -v agent-browser &> /dev/null; then
            echo "   📥 Installing Agent Browser CLI..."
            $NPM_CMD install -g agent-browser 2>/dev/null || echo "   ⚠️  npm install failed. Run manually: npm i -g agent-browser"
        fi
        
        # Configure system Chrome and auto-connect
        CONFIG_DIR="$HOME/.agent-browser"
        CONFIG_FILE="$CONFIG_DIR/config.json"
        
        if [[ "$OSTYPE" == "darwin"* ]] && [ -d "/Applications/Google Chrome.app" ]; then
            CHROME_BIN="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        elif [ -x "/usr/bin/google-chrome" ]; then
            CHROME_BIN="/usr/bin/google-chrome"
        fi
        
        mkdir -p "$CONFIG_DIR"
        
        # Create or update config.json
        if [ -f "$CONFIG_FILE" ]; then
            # Check if autoConnect is already set
            if ! grep -q "autoConnect" "$CONFIG_FILE" 2>/dev/null; then
                # Add autoConnect and executablePath
                echo "   🔧 Updating $CONFIG_FILE with auto-connect..."
                python3 -c "
import json
with open('$CONFIG_FILE', 'r') as f:
    config = json.load(f)
config['autoConnect'] = True
if '$CHROME_BIN':
    config['executablePath'] = '$CHROME_BIN'
with open('$CONFIG_FILE', 'w') as f:
    json.dump(config, f, indent=2)
"
            else
                echo "   ✅ auto-connect already configured in $CONFIG_FILE"
            fi
        else
            echo "   📝 Creating $CONFIG_FILE with auto-connect..."
            if [ -n "$CHROME_BIN" ]; then
                echo "{\"autoConnect\": true, \"executablePath\": \"$CHROME_BIN\"}" > "$CONFIG_FILE"
            else
                echo "{\"autoConnect\": true}" > "$CONFIG_FILE"
            fi
        fi
        
        echo "   ✅ Agent Browser ready! Uses your system Google Chrome with auto-connect."
    else
        echo "   ⚠️  npm/npx not found. Install Node.js first."
    fi
fi

echo ""
echo "📋 Installing tGD rules (project-local only, no global pollution)..."
echo ""

# Claude Code: NO global rules symlink — tgd-rules stays as a project-local skill.
# Previously: ln -sf ... "$HOME/.claude/rules/tgd.md" (loaded in ALL conversations)
# Now: rules are loaded via skill system only when in a tGD project context.
# If you need rules in a specific project, add to .claude/CLAUDE.md:
#   "Load tgd-rules skill for tGD workflow enforcement."

# Codex CLI: ~/.codex/skills/tgd-rules (auto-discovered)
if command -v codex &> /dev/null || [ -n "$CI" ]; then
    mkdir -p "$HOME/.codex/skills"
    if [ -d "$HOME/.codex/skills/tgd-rules" ] && [ ! -L "$HOME/.codex/skills/tgd-rules" ]; then
        rm -rf "$HOME/.codex/skills/tgd-rules"
    fi
    ln -sf "$TGD_DIR/skills/tgd-rules" "$HOME/.codex/skills/tgd-rules" 2>/dev/null && echo "   ✅ Codex CLI: ~/.codex/skills/tgd-rules → symlink"
fi

# OpenCode: ~/.config/opencode/skills/tgd-rules
if command -v opencode &> /dev/null || [ -n "$CI" ]; then
    mkdir -p "$HOME/.config/opencode/skills"
    if [ -d "$HOME/.config/opencode/skills/tgd-rules" ] && [ ! -L "$HOME/.config/opencode/skills/tgd-rules" ]; then
        rm -rf "$HOME/.config/opencode/skills/tgd-rules"
    fi
    ln -sf "$TGD_DIR/skills/tgd-rules" "$HOME/.config/opencode/skills/tgd-rules" 2>/dev/null && echo "   ✅ OpenCode: ~/.config/opencode/skills/tgd-rules → symlink"
fi

# Gemini CLI: ~/.gemini/skills/tgd-rules
if command -v gemini &> /dev/null || [ -n "$CI" ]; then
    mkdir -p "$HOME/.gemini/skills"
    if [ -d "$HOME/.gemini/skills/tgd-rules" ] && [ ! -L "$HOME/.gemini/skills/tgd-rules" ]; then
        rm -rf "$HOME/.gemini/skills/tgd-rules"
    fi
    ln -sf "$TGD_DIR/skills/tgd-rules" "$HOME/.gemini/skills/tgd-rules" 2>/dev/null && echo "   ✅ Gemini CLI: ~/.gemini/skills/tgd-rules → symlink"
fi

# Pi: ~/.pi/agent/skills/tgd-rules
if command -v pi &> /dev/null || [ -n "$CI" ]; then
    mkdir -p "$HOME/.pi/agent/skills"
    if [ -d "$HOME/.pi/agent/skills/tgd-rules" ] && [ ! -L "$HOME/.pi/agent/skills/tgd-rules" ]; then
        rm -rf "$HOME/.pi/agent/skills/tgd-rules"
    fi
    ln -sf "$TGD_DIR/skills/tgd-rules" "$HOME/.pi/agent/skills/tgd-rules" 2>/dev/null && echo "   ✅ Pi: ~/.pi/agent/skills/tgd-rules → symlink"
fi

# Hermes Agent: ~/.hermes/skills/tgd-rules plus every existing profile.
if command -v hermes &> /dev/null || [ -n "$CI" ]; then
    link_skill_folder_to_hermes_homes "$TGD_DIR/skills/tgd-rules" "tgd-rules" "tgd-rules"
fi

echo ""
echo "===================================="

# ─── Install tgd CLI ────────────────────────────────────────────────────────
TGD_BIN="$TGD_DIR/bin/tgd"
chmod +x "$TGD_BIN"

# Try /usr/local/bin first, fall back to ~/.local/bin
if [[ -w "/usr/local/bin" ]] 2>/dev/null; then
    ln -sf "$TGD_BIN" "/usr/local/bin/tgd" 2>/dev/null && echo "   🔧 tgd CLI → /usr/local/bin/tgd"
else
    mkdir -p "$HOME/.local/bin"
    ln -sf "$TGD_BIN" "$HOME/.local/bin/tgd" && echo "   🔧 tgd CLI → ~/.local/bin/tgd"
    # Ensure ~/.local/bin is in PATH hint
    if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
        echo "   ⚠️  Add ~/.local/bin to PATH: export PATH=\"\$HOME/.local/bin:\$PATH\""
    fi
fi

# ─── Final guard: remove any self-loop symlinks left in tGD skill dirs ──────
# A self-loop is a symlink whose target, when resolved, points back into its
# own path (e.g. skills/skills → skills). These confuse `find -L` and some
# platform skill discovery scanners. We detect by realpath comparison: if the
# symlink's realpath equals its own parent dir, it's a self-loop.
for dir in "$TGD_DIR/skills" "$TGD_DIR/vendor/understand-anything/understand-anything-plugin/skills"; do
    if [[ -d "$dir" ]]; then
        for entry in "$dir"/*; do
            [[ -L "$entry" ]] || continue
            sl_target=$(readlink "$entry" 2>/dev/null)
            [[ -z "$sl_target" ]] && continue
            # Resolve target to absolute path (handles relative targets)
            if [[ "$sl_target" != /* ]]; then
                sl_abs="$(cd "$(dirname "$entry")" && cd "$sl_target" 2>/dev/null && pwd -P)" || continue
            else
                sl_abs="$(cd "$sl_target" 2>/dev/null && pwd -P)" || continue
            fi
            entry_abs="$(cd "$(dirname "$entry")" && pwd -P)/$(basename "$entry")"
            # Self-loop: symlink target equals its own parent directory
            if [[ "$sl_abs" == "$(dirname "$entry_abs")" ]]; then
                echo "   🧹 Removing self-loop symlink: $entry → $sl_target"
                rm -f "$entry"
            fi
        done
    fi
done

echo "✅ Setup Complete!"
echo ""
echo "tGD is now active in ALL projects."
echo "Just start your agent in any project:"
echo "  claude | codex | opencode | gemini | pi | hermes"
echo "Then type '/tgd-map' to initialize."
echo ""