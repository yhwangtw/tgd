#!/bin/bash
# tGD One-Click Installer
# Usage: bash setup.sh [--upgrade|--uninstall|--version] [--with-tools] [--with-browser] [--no-deps]
#
# --upgrade:  遷移可確認為舊版 tGD 的 symlink，並刷新受管理的 links/hooks。
#             適合 tGD clone 執行 git pull 後使用，不會清除不明路徑。
# --uninstall: 只移除 ownership manifest 記錄的 symlink、tGD hook 與版本標記。
#              Repo、第三方依賴與使用者自己的設定都會保留。

set -e

usage() {
    cat <<'EOF'
Usage: bash setup.sh [options]

Options:
  -u, --upgrade        Refresh an existing or legacy tGD installation
      --uninstall      Remove only files and hooks managed by tGD
  -v, --version        Print the repository version
      --with-tools     Install pinned third-party CLI dependencies when missing
      --with-browser   Configure Agent Browser (implies --with-tools)
      --no-deps        Skip dependency downloads (links and hooks still install)
  -h, --help           Show this help
EOF
}

TGD_REPO_ROOT="$(cd "$(dirname "$0")" && pwd -P)"
MODE="install"
INSTALL_TOOLS=0
CONFIGURE_BROWSER=0
SKIP_DEPS=0
SETUP_DEGRADED=0
CODEGRAPH_VERSION="0.9.8"
AGENT_BROWSER_VERSION="11.5.1"
PNPM_VERSION="10.6.2"

while [[ "$#" -gt 0 ]]; do
    case "$1" in
        -u|--upgrade)
            [[ "$MODE" == "install" ]] || { echo "❌ Conflicting setup modes." >&2; usage >&2; exit 2; }
            MODE="upgrade"
            ;;
        --uninstall|--remove)
            [[ "$MODE" == "install" ]] || { echo "❌ Conflicting setup modes." >&2; usage >&2; exit 2; }
            MODE="uninstall"
            ;;
        -v|--version)
            [[ "$MODE" == "install" ]] || { echo "❌ Conflicting setup modes." >&2; usage >&2; exit 2; }
            MODE="version"
            ;;
        --with-tools)
            INSTALL_TOOLS=1
            ;;
        --with-browser)
            INSTALL_TOOLS=1
            CONFIGURE_BROWSER=1
            ;;
        --no-deps)
            SKIP_DEPS=1
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "❌ Unknown option: $1" >&2
            usage >&2
            exit 2
            ;;
    esac
    shift
done

if [[ "$SKIP_DEPS" -eq 1 && "$INSTALL_TOOLS" -eq 1 ]]; then
    echo "❌ Conflicting dependency options: --no-deps cannot be combined with --with-tools or --with-browser." >&2
    usage >&2
    exit 2
fi

if [[ "$MODE" == "version" ]]; then
    if [[ -f "$TGD_REPO_ROOT/VERSION" ]]; then
        echo "tGD $(cat "$TGD_REPO_ROOT/VERSION")"
    else
        echo "tGD (unknown — VERSION not found)"
    fi
    exit 0
fi

if [[ -z "${HOME:-}" || "$HOME" != /* || "$HOME" == "/" ]]; then
    echo "❌ HOME must be a non-root absolute path." >&2
    exit 1
fi

if [[ "${EUID:-$(id -u)}" -eq 0 && "${TGD_ALLOW_ROOT_FOR_TESTS:-0}" != "1" ]]; then
    echo "❌ Do not run setup.sh with sudo or as root." >&2
    exit 1
fi

if [[ "$MODE" != "uninstall" ]]; then
    case "$(uname -s 2>/dev/null || echo unknown)" in
        Darwin|Linux) ;;
        *)
            echo "❌ This installer supports Linux and macOS only." >&2
            exit 1
            ;;
    esac
fi

case "${CI:-}" in
    1|true|TRUE) CI_ACTIVE=1 ;;
    *) CI_ACTIVE=0 ;;
esac

TGD_STATE_DIR="${TGD_STATE_DIR:-$HOME/.tgd}"
INSTALL_MANIFEST="$TGD_STATE_DIR/install-manifest.json"
INSTALL_STATE_HELPER="$TGD_REPO_ROOT/scripts/install-state.py"
HOOK_MERGE_HELPER="$TGD_REPO_ROOT/scripts/merge-agent-hooks.py"

cd "$TGD_REPO_ROOT"

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

absolute_symlink_target() {
    python3 - "$1" <<'PYEOF'
import os
import sys

path = os.path.abspath(os.path.expanduser(sys.argv[1]))
target = os.readlink(path)
if not os.path.isabs(target):
    target = os.path.join(os.path.dirname(path), target)
print(os.path.abspath(target))
PYEOF
}

managed_link() {
    local source="${1%/}"
    local destination="$2"
    local policy="${3:-required}"
    local source_relative="${source#"$TGD_REPO_ROOT"/}"
    local legacy_target=""
    local legacy_args=()

    if [[ "$source_relative" == "$source" ]]; then
        echo "❌ Refusing to manage a source outside this tGD checkout: $source" >&2
        return 1
    fi

    if [[ -L "$destination" ]]; then
        legacy_target=$(absolute_symlink_target "$destination")
        case "$legacy_target" in
            */"$source_relative")
                legacy_args=(--legacy-target "$legacy_target")
                ;;
        esac
    fi

    if ! python3 "$INSTALL_STATE_HELPER" link \
        --manifest "$INSTALL_MANIFEST" \
        --path "$destination" \
        --target "$source" \
        "${legacy_args[@]}" >/dev/null; then
        if [[ "$policy" == "optional" ]]; then
            echo "   ℹ️  Keeping existing user path: $destination"
            return 0
        fi
        echo "❌ Installation collision at $destination." >&2
        echo "   Existing user data was preserved. Move it aside, then retry." >&2
        return 1
    fi
}

link_tgd_skills_to_hermes_home() {
    local hermes_home="$1"
    mkdir -p "$hermes_home/skills"
    local count=0
    for skill in "$TGD_REPO_ROOT"/skills/*/; do
        local skill_name
        skill_name=$(basename "$skill")
        # Skip nested symlink traps
        if [[ "$skill_name" == "skills" ]]; then
            continue
        fi
        managed_link "$skill" "$hermes_home/skills/$skill_name"
        count=$((count + 1))
    done
    echo "   ✅ Hermes skills linked: $(display_home_path "$hermes_home")/skills ($count skills)."
}

link_hermes_plugin_to_home() {
    local hermes_home="$1"
    if [[ -d "$TGD_REPO_ROOT/.hermes/plugins/tgd" ]]; then
        mkdir -p "$hermes_home/plugins"
        managed_link "$TGD_REPO_ROOT/.hermes/plugins/tgd" "$hermes_home/plugins/tgd"
        echo "   ✅ Hermes plugin linked: $(display_home_path "$hermes_home")/plugins/tgd."
    fi
}

link_hermes_agents_to_home() {
    local hermes_home="$1"
    if [[ -f "$TGD_REPO_ROOT/.hermes/AGENTS.md" ]]; then
        managed_link "$TGD_REPO_ROOT/.hermes/AGENTS.md" "$hermes_home/AGENTS.md"
    fi
}

link_skill_folder_to_hermes_homes() {
    local source_dir="$1"
    local link_name="$2"
    local label="$3"
    local policy="${4:-required}"
    while IFS= read -r hermes_home; do
        [[ -n "$hermes_home" ]] || continue
        mkdir -p "$hermes_home/skills"
        managed_link "$source_dir" "$hermes_home/skills/$link_name" "$policy"
        echo "   ✅ Hermes $label linked: $(display_home_path "$hermes_home")/skills/$link_name."
    done < <(hermes_homes)
}

# ─── Prerequisite checks ─────────────────────────────────────────────────────
missing_deps=()
command -v python3 &> /dev/null || missing_deps+=("python3")
if [[ "$MODE" != "uninstall" ]]; then
    if command -v node &> /dev/null; then
        node_version=$(node -p 'process.versions.node' 2>/dev/null || echo "0.0.0")
        IFS=. read -r node_major node_minor _node_patch <<< "$node_version"
        if ! [[ "$node_major" =~ ^[0-9]+$ && "$node_minor" =~ ^[0-9]+$ ]] \
            || (( node_major < 22 || (node_major == 22 && node_minor < 12) )); then
            missing_deps+=("node >= 22.12.0 (found $(node -v 2>/dev/null || echo 'unknown'))")
        fi
    else
        missing_deps+=("node (Node.js >= 22.12.0)")
    fi
fi
if [ ${#missing_deps[@]} -gt 0 ]; then
    echo "❌ Missing required dependencies:"
    for dep in "${missing_deps[@]}"; do
        echo "   • $dep"
    done
    echo ""
    echo "Install them and re-run: bash setup.sh"
    exit 1
fi
# jq is optional: the session-start hook needs it to inject the tgd-router
# meta-skill, but degrades gracefully without it. Warn, don't abort.
if [[ "$MODE" != "uninstall" ]] && ! command -v jq &> /dev/null; then
    echo "⚠️  jq not found — session-start hooks will skip meta-skill injection."
    echo "   Install for full functionality: apt-get install jq / brew install jq"
fi

# ─── Uninstall mode ──────────────────────────────────────────────────────────
if [[ "$MODE" == "uninstall" ]]; then
    echo "🗑️  tGD Uninstall — Removing managed deployments..."
    echo "====================================="
    echo ""
    UNINSTALL_FAILED=0

    echo "🧹 Removing tGD hooks from config files..."
    for hook_spec in \
        "claude:$HOME/.claude/settings.json" \
        "codex:$HOME/.codex/hooks.json" \
        "gemini:$HOME/.gemini/settings.json"; do
        hook_platform="${hook_spec%%:*}"
        hook_destination="${hook_spec#*:}"
        [[ -f "$hook_destination" ]] || continue
        if ! python3 "$HOOK_MERGE_HELPER" remove \
            --platform "$hook_platform" \
            --repo-root "$TGD_REPO_ROOT" \
            --destination "$hook_destination"; then
            UNINSTALL_FAILED=1
        fi
    done

    echo ""
    echo "🧹 Removing symlinks recorded by tGD..."
    if [[ -f "$INSTALL_MANIFEST" ]]; then
        if ! python3 "$INSTALL_STATE_HELPER" remove-all --manifest "$INSTALL_MANIFEST"; then
            UNINSTALL_FAILED=1
        fi
    else
        echo "   ℹ️  No ownership manifest found; unknown legacy links were preserved."
        echo "      Run bash setup.sh once to migrate a legacy installation before uninstalling it."
    fi

    if [[ -f "$HOME/.tgd-installed-version" ]]; then
        echo "   🗑️  Removing installed version marker: $HOME/.tgd-installed-version"
        rm -f "$HOME/.tgd-installed-version"
    fi

    echo ""
    echo "===================================="
    if [[ "$UNINSTALL_FAILED" -ne 0 ]]; then
        echo "❌ tGD uninstall finished with errors; user-owned paths were preserved."
        exit 1
    fi
    echo "✅ tGD managed items removed."
    echo "   Repository files and third-party dependencies were preserved."
    exit 0
fi

if [[ "$MODE" == "upgrade" ]]; then
    echo "🔄 tGD Upgrade — Refreshing managed deployments..."
    echo "====================================="
    echo ""
else
    echo "🚀 tGD Setup"
    echo "===================================="
fi

# ─── Version marker ──────────────────────────────────────────────────────────
# Version is derived from git tags (CalVer). To bump: git tag v2026.07.04
if [[ ! -r "$TGD_REPO_ROOT/VERSION" ]]; then
    echo "❌ Repository VERSION is missing or unreadable." >&2
    exit 1
fi
TGD_VERSION=$(cat "$TGD_REPO_ROOT/VERSION")
VERSION_FILE="$HOME/.tgd-installed-version"

cleanup_generated_source_links() {
    local skills_root="$1"
    local root_self_link skill_dir link parent_name link_name target
    [[ -d "$skills_root" ]] || return 0
    root_self_link="$skills_root/$(basename "$skills_root")"
    if [[ -L "$root_self_link" ]] \
        && [[ "$(absolute_symlink_target "$root_self_link")" == "$skills_root" ]]; then
        echo "   🧹 Removing installer-generated source symlink: $root_self_link"
        rm -f "$root_self_link"
    fi
    for skill_dir in "$skills_root"/*/; do
        [[ -d "$skill_dir" ]] || continue
        skill_dir="${skill_dir%/}"
        parent_name=$(basename "$skill_dir")
        for link in "$skill_dir"/*; do
            [[ -L "$link" ]] || continue
            link_name=$(basename "$link")
            target=$(absolute_symlink_target "$link")
            if [[ "$link_name" == "$parent_name" && "$target" == "$skill_dir" ]] \
                || [[ ! -e "$link" && "$target" == "$skills_root/$link_name" ]]; then
                echo "   🧹 Removing installer-generated source symlink: $link"
                rm -f "$link"
            fi
        done
    done
}

cleanup_generated_source_links "$TGD_REPO_ROOT/skills"
cleanup_generated_source_links \
    "$TGD_REPO_ROOT/vendor/understand-anything/understand-anything-plugin/skills"

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

# ─── Upgrade mode: migrate only exact legacy tGD symlinks ────────────────────
purge_old_tgd_symlinks() {
    local dir="$1"
    local label="$2"
    local current_skill legacy_name link target
    [[ -d "$dir" ]] || return 0
    for current_skill in "$TGD_REPO_ROOT"/skills/tgd-*/; do
        [[ -d "$current_skill" ]] || continue
        legacy_name="${current_skill%/}"
        legacy_name="${legacy_name##*/}"
        legacy_name="${legacy_name#tgd-}"
        link="$dir/$legacy_name"
        [[ -L "$link" ]] || continue
        target=$(absolute_symlink_target "$link")
        case "$target" in
            */skills/"$legacy_name")
                echo "   🗑️  Removing exact legacy tGD symlink ($label): $link"
                rm -f "$link"
                ;;
        esac
    done
}

if [[ "$MODE" == "upgrade" ]]; then
    echo "🔄 Migrating tGD skills to tgd- prefix (v2026.07.x)..."
    purge_old_tgd_symlinks "$HOME/.claude/skills" "Claude Code"
    purge_old_tgd_symlinks "$HOME/.config/opencode/skills" "OpenCode"
    purge_old_tgd_symlinks "$HOME/.codex/skills" "Codex CLI"
    purge_old_tgd_symlinks "$HOME/.gemini/skills" "Gemini CLI"
    purge_old_tgd_symlinks "$HOME/.pi/agent/skills" "Pi"
    while IFS= read -r hermes_home; do
        [[ -n "$hermes_home" ]] || continue
        purge_old_tgd_symlinks "$hermes_home/skills" "Hermes ($(display_home_path "$hermes_home"))"
    done < <(hermes_homes)
    echo ""
fi

# Configure Agents
echo "🤖 Configuring Agents..."

# OpenCode
if command -v opencode &> /dev/null; then
    echo "   📂 OpenCode detected."
    # Create global commands link (individual files, not subdirectory)
    mkdir -p ~/.config/opencode/commands
    for cmd in "$TGD_REPO_ROOT"/.opencode/commands/*.md; do
        cmd_name=$(basename "$cmd")
        managed_link "$cmd" "$HOME/.config/opencode/commands/$cmd_name"
    done
    echo "   ✅ Commands linked (7 tgd-* commands)."
    # Link skills for auto-detection (agent can find skills by name)
    if [ -d "$TGD_REPO_ROOT/skills" ]; then
        mkdir -p ~/.config/opencode/skills
        managed_link "$TGD_REPO_ROOT/skills" "$HOME/.config/opencode/skills/tGD"
        echo "   ✅ Skills linked for auto-detection."
    fi
    # Install plugins (hooks)
    if [ -d "$TGD_REPO_ROOT/.opencode/plugins" ]; then
        mkdir -p ~/.config/opencode/plugins
        for plugin in "$TGD_REPO_ROOT"/.opencode/plugins/*; do
            [[ -e "$plugin" ]] || continue
            managed_link "$plugin" "$HOME/.config/opencode/plugins/$(basename "$plugin")"
        done
        echo "   ✅ Plugins installed (session-start)."
    fi
fi

# Claude Code
if command -v claude &> /dev/null; then
    echo "   📂 Claude Code detected."
    if [ -d "$TGD_REPO_ROOT/.claude" ]; then
        # Link skills
        mkdir -p ~/.claude/skills
        for skill in "$TGD_REPO_ROOT"/skills/*/; do
            skill_name=$(basename "$skill")
            # Skip nested symlink traps (e.g. skills/skills -> skills) — would create self-loop
            if [ "$skill_name" = "skills" ]; then
                continue
            fi
            managed_link "$skill" "$HOME/.claude/skills/$skill_name"
        done
        echo "   ✅ Skills linked."

        # Link commands (slash commands: /tgd-map, /tgd-develop, etc.)
        if [ -d "$TGD_REPO_ROOT/.claude/commands" ]; then
            mkdir -p ~/.claude/commands
            for command_file in "$TGD_REPO_ROOT"/.claude/commands/*; do
                [[ -e "$command_file" ]] || continue
                managed_link "$command_file" "$HOME/.claude/commands/$(basename "$command_file")"
            done
            echo "   ✅ Commands linked (7 tgd-* slash commands)."
        fi

        if [ -f "$TGD_REPO_ROOT/hooks/session-start.sh" ]; then
            python3 "$HOOK_MERGE_HELPER" install \
                --platform claude \
                --repo-root "$TGD_REPO_ROOT" \
                --destination "$HOME/.claude/settings.json"
        fi
    fi
fi

# Gemini CLI
if command -v gemini &> /dev/null; then
    echo "   📂 Gemini CLI detected."
    if [ -d "$TGD_REPO_ROOT/.gemini" ]; then
        mkdir -p ~/.gemini/commands
        for command_file in "$TGD_REPO_ROOT"/.gemini/commands/*; do
            [[ -e "$command_file" ]] || continue
            managed_link "$command_file" "$HOME/.gemini/commands/$(basename "$command_file")"
        done
        echo "   ✅ Commands linked."
    fi
    # Link skills for auto-detection
    if [ -d "$TGD_REPO_ROOT/skills" ]; then
        mkdir -p ~/.gemini/skills
        managed_link "$TGD_REPO_ROOT/skills" "$HOME/.gemini/skills/tGD"
        echo "   ✅ Skills linked for auto-detection."
    fi
    if [ -f "$TGD_REPO_ROOT/hooks/gemini/session-start.sh" ]; then
        python3 "$HOOK_MERGE_HELPER" install \
            --platform gemini \
            --repo-root "$TGD_REPO_ROOT" \
            --destination "$HOME/.gemini/settings.json"
    fi
fi

# Codex CLI
if command -v codex &> /dev/null; then
    echo "   📂 Codex CLI detected."
    mkdir -p ~/.codex
    if [ -d "$TGD_REPO_ROOT/skills" ]; then
        managed_link "$TGD_REPO_ROOT/skills" "$HOME/.codex/skills/tGD"
        echo "   ✅ Skills linked for auto-detection."
    fi
    if [ -d "$TGD_REPO_ROOT/.codex/prompts" ]; then
        mkdir -p ~/.codex/prompts
        for prompt in "$TGD_REPO_ROOT"/.codex/prompts/*; do
            [[ -e "$prompt" ]] || continue
            managed_link "$prompt" "$HOME/.codex/prompts/$(basename "$prompt")"
        done
        echo "   ✅ Prompts linked (7 tgd-* commands)."
    fi
    if [ -f "$TGD_REPO_ROOT/hooks/codex/session-start.sh" ]; then
        python3 "$HOOK_MERGE_HELPER" install \
            --platform codex \
            --repo-root "$TGD_REPO_ROOT" \
            --destination "$HOME/.codex/hooks.json"
    fi
fi

# Pi Coding Agent
if command -v pi &> /dev/null; then
    echo "   📂 Pi Coding Agent detected."
    # Install prompt templates + instructions to ~/.pi/agent/. tGD commands are
    # native pi prompt templates (.pi/prompts/*.md → /tgd-map etc.), NOT a
    # TypeScript extension — an extension had to call pi.sendUserMessage(body),
    # which injected each command as a wall of user-authored text.
    if [ -d "$TGD_REPO_ROOT/.pi/prompts" ]; then
        mkdir -p "$HOME/.pi/agent/prompts"
        for prompt in "$TGD_REPO_ROOT"/.pi/prompts/*.md; do
            [ -e "$prompt" ] || continue
            managed_link "$prompt" "$HOME/.pi/agent/prompts/$(basename "$prompt")"
        done
        echo "   ✅ Prompt templates installed to ~/.pi/agent/prompts/ (/tgd-* commands)."
    fi
    if [ -f "$TGD_REPO_ROOT/.pi/instructions.md" ]; then
        managed_link "$TGD_REPO_ROOT/.pi/instructions.md" "$HOME/.pi/agent/instructions.md"
        echo "   ✅ Instructions installed to ~/.pi/agent/instructions.md"
    fi
    # Link skills for auto-detection
    if [ -d "$TGD_REPO_ROOT/skills" ]; then
        mkdir -p "$HOME/.pi/agent/skills"
        managed_link "$TGD_REPO_ROOT/skills" "$HOME/.pi/agent/skills/tGD"
        echo "   ✅ Skills linked for auto-detection."
    fi
else
    echo "   ℹ️  Pi Coding Agent not detected — skip extension install."
fi

# Hermes Agent
if command -v hermes &> /dev/null; then
    echo "   📂 Hermes Agent detected."
    if [ -d "$TGD_REPO_ROOT/skills" ]; then
        while IFS= read -r hermes_home; do
            [[ -n "$hermes_home" ]] || continue
            link_tgd_skills_to_hermes_home "$hermes_home"
        done < <(hermes_homes)
    fi

    if [ -d "$TGD_REPO_ROOT/.hermes/plugins/tgd" ]; then
        while IFS= read -r hermes_home; do
            [[ -n "$hermes_home" ]] || continue
            link_hermes_plugin_to_home "$hermes_home"
        done < <(hermes_homes)
    fi

    if [ -f "$TGD_REPO_ROOT/.hermes/AGENTS.md" ]; then
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
    if [[ "$INSTALL_TOOLS" -eq 1 ]] && command -v npm &> /dev/null; then
        echo "   📥 Installing pinned CodeGraph ${CODEGRAPH_VERSION} via npm..."
        if npm install -g "@colbymchenry/codegraph@${CODEGRAPH_VERSION}" \
            && command -v codegraph &> /dev/null; then
            echo "   ✅ CodeGraph installed."
        else
            echo "   ⚠️  CodeGraph install did not produce a runnable command."
            SETUP_DEGRADED=1
        fi
    else
        echo "   ⚠️  CodeGraph is missing; /tgd-map cannot run CodeGraph."
        echo "      Re-run with --with-tools, or install: npm install -g @colbymchenry/codegraph@${CODEGRAPH_VERSION}"
        SETUP_DEGRADED=1
    fi
fi

# ─── Install UA dependencies (subshell-safe: cd won't leak) ──────────────────
install_ua_deps() {
    local ua_dir="$1"
    local install_log=""
    local pnpm_version=""
    local pnpm_command=()

    if [ -d "$ua_dir/node_modules" ] \
        && [ -d "$ua_dir/understand-anything-plugin/packages/core/dist" ]; then
        echo "   ✅ UA dependencies already installed."
        return 0
    fi

    if [[ "$SKIP_DEPS" -eq 1 ]]; then
        echo "   ⚠️  UA dependency installation skipped by --no-deps."
        return 1
    fi

    if command -v corepack &> /dev/null; then
        pnpm_command=(corepack pnpm)
    elif command -v pnpm &> /dev/null; then
        pnpm_version=$(pnpm --version 2>/dev/null || echo "")
        if [[ "$pnpm_version" == "$PNPM_VERSION" ]]; then
            pnpm_command=(pnpm)
        fi
    fi

    if [[ "${#pnpm_command[@]}" -eq 0 ]] \
        && [[ "$INSTALL_TOOLS" -eq 1 ]] \
        && command -v npm &> /dev/null; then
        echo "   📥 Installing pinned pnpm ${PNPM_VERSION} via npm..."
        if npm install -g "pnpm@${PNPM_VERSION}" && command -v pnpm &> /dev/null; then
            pnpm_command=(pnpm)
        fi
    fi

    if [[ "${#pnpm_command[@]}" -eq 0 ]]; then
        echo "   ⚠️  Pinned pnpm ${PNPM_VERSION} is unavailable."
        echo "      Re-run with --with-tools, or enable Corepack, then retry."
        return 1
    fi

    echo "   📦 Installing UA dependencies (pnpm install)..."
    install_log=$(mktemp "${TMPDIR:-/tmp}/tgd-ua-install.XXXXXX")
    if (cd "$ua_dir" && "${pnpm_command[@]}" install --frozen-lockfile) \
        >"$install_log" 2>&1; then
        if [ ! -d "$ua_dir/node_modules" ]; then
            echo "   ⚠️  pnpm install exited successfully but node_modules was not created."
            rm -f "$install_log"
            return 1
        fi
        echo "   ✅ Dependencies installed."
    else
        echo "   ⚠️  pnpm install failed. Last 5 lines:"
        tail -5 "$install_log"
        rm -f "$install_log"
        echo "      Manual fix: cd vendor/understand-anything && pnpm install"
        return 1
    fi
    rm -f "$install_log"

    if [ -d "$ua_dir/node_modules" ]; then
        echo "   🔨 Building UA (pnpm build)..."
        if (cd "$ua_dir" && "${pnpm_command[@]}" build); then
            if [ ! -d "$ua_dir/understand-anything-plugin/packages/core/dist" ]; then
                echo "   ⚠️  pnpm build exited successfully but UA core output is missing."
                return 1
            fi
            echo "   ✅ UA built successfully."
        else
            echo "   ⚠️  Build failed. Manual fix: cd vendor/understand-anything && pnpm build"
            return 1
        fi
    fi
}

# Understand-Anything (bundled in vendor/)
echo "🧠 Checking Understand-Anything..."
UA_DIR="$TGD_REPO_ROOT/vendor/understand-anything"
UA_SKILLS_DIR="$UA_DIR/understand-anything-plugin/skills"
if [ -d "$UA_SKILLS_DIR" ]; then
    echo "   ✅ Understand-Anything skills ready."
    if ! install_ua_deps "$UA_DIR"; then
        SETUP_DEGRADED=1
    fi

    UA_REPO_LINK="$HOME/.understand-anything/repo"
    UA_PLUGIN_TARGET="$UA_DIR/understand-anything-plugin"
    managed_link "$UA_PLUGIN_TARGET" "$UA_REPO_LINK" optional
    if [[ -L "$UA_REPO_LINK" ]] \
        && [[ "$(absolute_symlink_target "$UA_REPO_LINK")" == "$UA_PLUGIN_TARGET" ]]; then
        echo "   🔗 ~/.understand-anything/repo → vendor (tGD-managed)"
    else
        echo "   ℹ️  Existing ~/.understand-anything/repo remains authoritative."
    fi
else
    echo "   ⚠️  Understand-Anything not found at vendor/understand-anything/"
    echo "      Re-clone tGD or manually download from: https://github.com/Lum1104/Understand-Anything"
    SETUP_DEGRADED=1
fi

# Link Understand-Anything skills to each platform
if [ -d "$UA_SKILLS_DIR" ]; then
    # Universal: ~/.agents/skills/understand (SKILL.md's primary fallback for plugin root resolution)
    mkdir -p "$HOME/.agents/skills"
    managed_link "$UA_SKILLS_DIR/understand" "$HOME/.agents/skills/understand" optional
    # Claude Code: per-skill symlinks in ~/.claude/skills/
    if [ -d "$HOME/.claude" ] || [ -L "$HOME/.claude" ]; then
        for skill in "$UA_SKILLS_DIR"/*/; do
            skill_name=$(basename "$skill")
            # Skip nested symlink traps (UA vendor may contain a self-looping `skills` entry)
            if [ "$skill_name" = "skills" ]; then
                continue
            fi
            managed_link "$skill" "$HOME/.claude/skills/understand-$skill_name" optional
        done
        echo "   ✅ Claude: Understand-Anything skills linked."
    fi
    # Codex: folder symlink in ~/.codex/skills/
    if [ -d "$HOME/.codex" ] || [ -L "$HOME/.codex" ]; then
        mkdir -p "$HOME/.codex/skills"
        managed_link "$UA_SKILLS_DIR" "$HOME/.codex/skills/understand-anything" optional
    fi
    # OpenCode: folder symlink in ~/.config/opencode/skills/
    if [ -d "$HOME/.config/opencode" ] || [ -L "$HOME/.config/opencode" ]; then
        mkdir -p "$HOME/.config/opencode/skills"
        managed_link "$UA_SKILLS_DIR" "$HOME/.config/opencode/skills/understand-anything" optional
    fi
    # Gemini: folder symlink in ~/.gemini/skills/
    if [ -d "$HOME/.gemini" ] || [ -L "$HOME/.gemini" ]; then
        mkdir -p "$HOME/.gemini/skills"
        managed_link "$UA_SKILLS_DIR" "$HOME/.gemini/skills/understand-anything" optional
    fi
    # Pi: folder symlink in ~/.pi/agent/skills/
    if [ -d "$HOME/.pi" ] || [ -L "$HOME/.pi" ]; then
        mkdir -p "$HOME/.pi/agent/skills"
        managed_link "$UA_SKILLS_DIR" "$HOME/.pi/agent/skills/understand-anything" optional
    fi
    # Hermes Agent: folder symlink in every Hermes profile home.
    if [ -d "$HOME/.hermes" ] || [ -L "$HOME/.hermes" ]; then
        link_skill_folder_to_hermes_homes "$UA_SKILLS_DIR" "understand-anything" "Understand-Anything skills" optional
    fi
fi

# 3. Install Optional Dependencies (Agent Browser)
echo "📦 Checking optional dependencies..."

# Agent Browser (E2E browser automation)
if [ -d "skills/tgd-agent-browser" ]; then
    echo "   🌐 Agent Browser skill detected."
    if [[ "$CONFIGURE_BROWSER" -eq 1 ]]; then
        if ! command -v agent-browser &> /dev/null; then
            if command -v npm &> /dev/null; then
                echo "   📥 Installing pinned Agent Browser ${AGENT_BROWSER_VERSION}..."
                npm install -g "agent-browser@${AGENT_BROWSER_VERSION}" || true
            fi
        fi

        if ! command -v agent-browser &> /dev/null; then
            echo "   ⚠️  Agent Browser CLI is unavailable."
            echo "      Install: npm install -g agent-browser@${AGENT_BROWSER_VERSION}"
            SETUP_DEGRADED=1
        else
            CHROME_BIN=""
            if [[ "$(uname -s)" == "Darwin" ]] \
                && [ -x "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" ]; then
                CHROME_BIN="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
            elif [ -x "/usr/bin/google-chrome" ]; then
                CHROME_BIN="/usr/bin/google-chrome"
            fi

        CONFIG_DIR="$HOME/.agent-browser"
        CONFIG_FILE="$CONFIG_DIR/config.json"
            python3 - "$CONFIG_FILE" "$CHROME_BIN" <<'PYEOF'
import json
import os
from pathlib import Path
import stat
import sys
import tempfile

path = Path(sys.argv[1])
chrome = sys.argv[2]
if path.is_symlink():
    raise SystemExit("refusing symlinked Agent Browser config: {}".format(path))
if path.exists():
    with path.open(encoding="utf-8") as stream:
        config = json.load(stream)
    mode = stat.S_IMODE(path.stat().st_mode)
else:
    config = {}
    mode = 0o600
if not isinstance(config, dict):
    raise SystemExit("Agent Browser config must be a JSON object")
config["autoConnect"] = True
if chrome:
    config["executablePath"] = chrome
path.parent.mkdir(parents=True, exist_ok=True)
descriptor, temporary_name = tempfile.mkstemp(
    dir=str(path.parent),
    prefix=".{}.".format(path.name),
)
try:
    os.fchmod(descriptor, mode)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        json.dump(config, stream, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary_name, path)
except BaseException:
    try:
        os.unlink(temporary_name)
    except FileNotFoundError:
        pass
    raise
PYEOF
            echo "   ✅ Agent Browser auto-connect configured by explicit request."
        fi
    else
        if command -v agent-browser &> /dev/null; then
            echo "   ✅ Agent Browser CLI already installed; config left unchanged."
        else
            echo "   ℹ️  Agent Browser not installed; use --with-browser to opt in."
        fi
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
if command -v codex &> /dev/null || [[ "$CI_ACTIVE" -eq 1 ]]; then
    mkdir -p "$HOME/.codex/skills"
    managed_link "$TGD_REPO_ROOT/skills/tgd-rules" "$HOME/.codex/skills/tgd-rules"
    echo "   ✅ Codex CLI: ~/.codex/skills/tgd-rules → symlink"
fi

# OpenCode: ~/.config/opencode/skills/tgd-rules
if command -v opencode &> /dev/null || [[ "$CI_ACTIVE" -eq 1 ]]; then
    mkdir -p "$HOME/.config/opencode/skills"
    managed_link "$TGD_REPO_ROOT/skills/tgd-rules" "$HOME/.config/opencode/skills/tgd-rules"
    echo "   ✅ OpenCode: ~/.config/opencode/skills/tgd-rules → symlink"
fi

# Gemini CLI: ~/.gemini/skills/tgd-rules
if command -v gemini &> /dev/null || [[ "$CI_ACTIVE" -eq 1 ]]; then
    mkdir -p "$HOME/.gemini/skills"
    managed_link "$TGD_REPO_ROOT/skills/tgd-rules" "$HOME/.gemini/skills/tgd-rules"
    echo "   ✅ Gemini CLI: ~/.gemini/skills/tgd-rules → symlink"
fi

# Pi: ~/.pi/agent/skills/tgd-rules
if command -v pi &> /dev/null || [[ "$CI_ACTIVE" -eq 1 ]]; then
    mkdir -p "$HOME/.pi/agent/skills"
    managed_link "$TGD_REPO_ROOT/skills/tgd-rules" "$HOME/.pi/agent/skills/tgd-rules"
    echo "   ✅ Pi: ~/.pi/agent/skills/tgd-rules → symlink"
fi

# Hermes Agent: ~/.hermes/skills/tgd-rules plus every existing profile.
if command -v hermes &> /dev/null || [[ "$CI_ACTIVE" -eq 1 ]]; then
    link_skill_folder_to_hermes_homes "$TGD_REPO_ROOT/skills/tgd-rules" "tgd-rules" "tgd-rules"
fi

echo ""
echo "===================================="

# ─── Install tgd CLI ────────────────────────────────────────────────────────
TGD_BIN="$TGD_REPO_ROOT/bin/tgd"
if [[ ! -x "$TGD_BIN" ]]; then
    echo "❌ Repository CLI is not executable: $TGD_BIN" >&2
    exit 1
fi

mkdir -p "$HOME/.local/bin"
managed_link "$TGD_BIN" "$HOME/.local/bin/tgd"
echo "   🔧 tgd CLI → ~/.local/bin/tgd"
if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
    echo "   ⚠️  Add ~/.local/bin to PATH: export PATH=\"\$HOME/.local/bin:\$PATH\""
fi

# ─── Final verification: prove the install, don't just narrate it ───────────
# Every line below is a REAL check (ls/test on the actual paths), not an echo
# of what earlier sections claimed. A detected platform with missing command
# links is a hard failure (exit 1). UA dependency state is reported honestly
# (⚠️, not fake-green) but does not fail setup — the registry policy may
# intentionally defer it.
echo ""
echo "🔎 Final verification:"
SETUP_FAILED=0

verify_cmd_links() {
    local label="$1" dir="$2" pattern="$3"
    local n=0 f
    for f in "$dir"/$pattern; do
        [ -e "$f" ] && n=$((n + 1))   # -e follows symlinks: dangling links don't count
    done
    if [ "$n" -eq 7 ]; then
        echo "   ✅ $label: 7/7 commands linked ($dir)"
    else
        echo "   ❌ $label: $n/7 commands resolve in $dir"
        SETUP_FAILED=1
    fi
}

command -v claude   &> /dev/null && verify_cmd_links "Claude Code" "$HOME/.claude/commands" "tgd-*.md"           || echo "   ⏭️  Claude Code not detected — skipped"
command -v opencode &> /dev/null && verify_cmd_links "OpenCode"    "$HOME/.config/opencode/commands" "tgd-*.md"  || echo "   ⏭️  OpenCode not detected — skipped"
command -v gemini   &> /dev/null && verify_cmd_links "Gemini CLI"  "$HOME/.gemini/commands" "tgd-*.toml"         || echo "   ⏭️  Gemini CLI not detected — skipped"
command -v codex    &> /dev/null && verify_cmd_links "Codex CLI"   "$HOME/.codex/prompts" "tgd-*.md"             || echo "   ⏭️  Codex CLI not detected — skipped"
command -v pi       &> /dev/null && verify_cmd_links "Pi"          "$HOME/.pi/agent/prompts" "tgd-*.md"          || echo "   ⏭️  Pi not detected — skipped"

# Understand-Anything runtime state (needed by /tgd-map Steps 4-5)
if [ -d "$UA_SKILLS_DIR" ]; then
    if [ -d "$UA_DIR/node_modules" ]; then
        echo "   ✅ UA dependencies installed (node_modules present)"
    else
        echo "   ⚠️  UA dependencies NOT installed — /understand scans and the dashboard will not run."
        echo "      (pnpm missing or registry policy deferred the install — see messages above)"
    fi
    if [ -d "$UA_DIR/understand-anything-plugin/packages/core/dist" ]; then
        echo "   ✅ UA core built (packages/core/dist present)"
    else
        echo "   ⚠️  UA core NOT built — run: cd vendor/understand-anything && pnpm install && pnpm build"
    fi
else
    echo "   ⏭️  Understand-Anything vendor not present — skipped"
fi

if python3 "$INSTALL_STATE_HELPER" verify \
    --manifest "$INSTALL_MANIFEST" \
    --path "$HOME/.local/bin/tgd" \
    --target "$TGD_BIN" >/dev/null; then
    echo "   ✅ Ownership manifest and tgd CLI target verified"
else
    echo "   ❌ Ownership manifest or tgd CLI target is invalid"
    SETUP_FAILED=1
fi

if [ "$SETUP_FAILED" -eq 1 ]; then
    echo ""
    echo "❌ Setup finished WITH FAILURES — see the ❌ lines above, fix, and re-run."
    exit 1
fi

python3 - "$VERSION_FILE" "$TGD_VERSION" <<'PYEOF'
import os
from pathlib import Path
import sys
import tempfile

path = Path(sys.argv[1])
path.parent.mkdir(parents=True, exist_ok=True)
descriptor, temporary_name = tempfile.mkstemp(
    dir=str(path.parent),
    prefix=".{}.".format(path.name),
)
try:
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        stream.write(sys.argv[2] + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary_name, path)
except BaseException:
    try:
        os.unlink(temporary_name)
    except FileNotFoundError:
        pass
    raise
PYEOF

echo ""
if [[ "$SETUP_DEGRADED" -eq 1 ]]; then
    echo "⚠️  Setup Complete (degraded)"
    echo "   Core links and hooks are installed; optional tooling warnings remain above."
else
    echo "✅ Setup Complete!"
fi
echo ""
echo "tGD is configured for the agents detected on this machine."
echo "Start an installed agent:"
echo "  claude | codex | opencode | gemini | pi | hermes"
echo "Then type '/tgd-map' to initialize."
echo ""
