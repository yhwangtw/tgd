#!/usr/bin/env bash
# tGD One-Click Installer
# Usage: bash setup.sh [--upgrade|--uninstall|--version] [--with-session-preamble] [--with-tools] [--with-browser] [--no-deps]
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
      --with-session-preamble
                       Opt in to bounded tGD context at session start
      --no-deps        Skip dependency downloads
  -h, --help           Show this help
EOF
}

TGD_REPO_ROOT="$(cd "$(dirname "$0")" && pwd -P)"
MODE="install"
INSTALL_TOOLS=0
CONFIGURE_BROWSER=0
SKIP_DEPS=0
WITH_SESSION_PREAMBLE=0
SETUP_DEGRADED=0
CODEGRAPH_VERSION="0.9.8"
AGENT_BROWSER_VERSION="11.5.1"
PNPM_VERSION="10.6.2"
LEGACY_RULES_HEADER="<!-- tGD rules — https://github.com/openclawyhwang-hub/tGD -->"

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
        --with-session-preamble)
            WITH_SESSION_PREAMBLE=1
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

if [[ "$MODE" == "uninstall" || "$MODE" == "version" ]] \
    && [[ "$INSTALL_TOOLS" -eq 1 || "$CONFIGURE_BROWSER" -eq 1 || "$SKIP_DEPS" -eq 1 || "$WITH_SESSION_PREAMBLE" -eq 1 ]]; then
    echo "❌ Install options are only valid for install or upgrade." >&2
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
HOOK_STATE_FILE="$TGD_STATE_DIR/hook-ownership.json"
VERSION_FILE="$HOME/.tgd-installed-version"
INSTALL_STATE_HELPER="$TGD_REPO_ROOT/scripts/install-state.py"
HOOK_MERGE_HELPER="$TGD_REPO_ROOT/scripts/merge-agent-hooks.py"
UA_BUILD_STATE_HELPER="$TGD_REPO_ROOT/scripts/ua-build-state.py"
UA_BUILD_STAMP="$TGD_STATE_DIR/ua-build-state.json"

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

canonical_path_for_compare() {
    python3 - "$1" <<'PYEOF'
import os
import sys

print(os.path.realpath(os.path.abspath(os.path.expanduser(sys.argv[1]))))
PYEOF
}

is_recognized_tgd_checkout() {
    local checkout_root="$1"
    [[ -f "$checkout_root/setup.sh" ]] \
        && [[ -f "$checkout_root/VERSION" ]] \
        && {
            [[ -f "$checkout_root/skills/tgd-core-rules/SKILL.md" ]] \
                || [[ -f "$checkout_root/skills/tgd-rules/SKILL.md" ]] \
                || [[ -f "$checkout_root/skills/rules/SKILL.md" ]]
        }
}

is_recognized_legacy_target() {
    local target="$1"
    local relative="$2"
    local checkout_root

    [[ "$target" == */"$relative" ]] || return 1
    checkout_root="${target%"/$relative"}"
    [[ -n "$checkout_root" && "$checkout_root" != "$target" ]] || return 1
    is_recognized_tgd_checkout "$checkout_root"
}

managed_link() {
    local source="${1%/}"
    local destination="$2"
    local policy="${3:-required}"
    local legacy_file_sha256="${4:-}"
    local source_relative="${source#"$TGD_REPO_ROOT"/}"
    local legacy_target=""
    local legacy_args=()
    local legacy_file_args=()

    if [[ "$source_relative" == "$source" ]]; then
        echo "❌ Refusing to manage a source outside this tGD checkout: $source" >&2
        return 1
    fi

    if [[ -L "$destination" ]]; then
        legacy_target=$(absolute_symlink_target "$destination")
        if is_recognized_legacy_target "$legacy_target" "$source_relative"; then
            legacy_args=(--legacy-target "$legacy_target")
        fi
    fi
    if [[ -n "$legacy_file_sha256" ]]; then
        legacy_file_args=(--legacy-file-sha256 "$legacy_file_sha256")
    fi

    if ! python3 "$INSTALL_STATE_HELPER" link \
        --manifest "$INSTALL_MANIFEST" \
        --path "$destination" \
        --target "$source" \
        "${legacy_args[@]}" \
        "${legacy_file_args[@]}" >/dev/null; then
        if [[ "$policy" == "optional" ]]; then
            echo "   ℹ️  Keeping existing user path: $destination"
            return 0
        fi
        echo "❌ Installation collision at $destination." >&2
        echo "   Existing user data was preserved. Move it aside, then retry." >&2
        return 1
    fi
}

remove_exact_symlink_safely() {
    python3 "$INSTALL_STATE_HELPER" remove-exact-symlink \
        --manifest "$INSTALL_MANIFEST" \
        --path "$1" \
        --target "$2" >/dev/null
}

retire_one_legacy_global_rule() {
    local destination="$1"
    local suffix_size="$2"
    local suffix_sha256="$3"
    local label="$4"
    local result=""

    [[ -f "$destination" && ! -L "$destination" ]] || return 0
    grep -qF "$LEGACY_RULES_HEADER" "$destination" 2>/dev/null || return 0
    if ! result=$(python3 "$INSTALL_STATE_HELPER" remove-legacy-suffix \
        --manifest "$INSTALL_MANIFEST" \
        --path "$destination" \
        --size "$suffix_size" \
        --sha256 "$suffix_sha256"); then
        echo "   ❌ Failed to inspect historical tGD block: $destination" >&2
        return 1
    fi
    if [[ "$result" == removed* ]]; then
        echo "   🧹 Removed exact historical tGD block: $label"
    else
        echo "   ⚠️  Preserved modified historical-looking file: $destination"
    fi
}

retire_legacy_global_rules() {
    retire_one_legacy_global_rule \
        "$HOME/.claude/CLAUDE.md" \
        1135 \
        "43172b04edbf5cdf95c2301a39c28652f94e23da21587f1f659c9c71f8599c98" \
        "Claude global rules" || return 1
    retire_one_legacy_global_rule \
        "$HOME/.codex/AGENTS.md" \
        10651 \
        "16a4ae9d30e746291edb4aec50cef4de0c459d491f24b105b92ef648e16154f9" \
        "Codex global rules" || return 1
    retire_one_legacy_global_rule \
        "$HOME/.config/opencode/AGENTS.md" \
        10651 \
        "16a4ae9d30e746291edb4aec50cef4de0c459d491f24b105b92ef648e16154f9" \
        "OpenCode global rules" || return 1
    retire_one_legacy_global_rule \
        "$HOME/.gemini/GEMINI.md" \
        1041 \
        "4f9be9f0faa5371b95fb5062a00c11b4b9ee22ee8e243fdd7cedc840eb0af689" \
        "Gemini global rules" || return 1
    retire_one_legacy_global_rule \
        "$HOME/.pi/agent/instructions.md" \
        1041 \
        "4f9be9f0faa5371b95fb5062a00c11b4b9ee22ee8e243fdd7cedc840eb0af689" \
        "Pi global rules" || return 1
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
if command -v python3 &> /dev/null; then
    if ! python3 -c 'import sys; raise SystemExit(sys.version_info < (3, 9))' \
        >/dev/null 2>&1; then
        missing_deps+=("python3 >= 3.9 (found $(python3 --version 2>&1 || echo 'unknown'))")
    fi
else
    missing_deps+=("python3 >= 3.9")
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
# ─── Uninstall mode ──────────────────────────────────────────────────────────
if [[ "$MODE" == "uninstall" ]]; then
    echo "🗑️  tGD Uninstall — Removing managed deployments..."
    echo "====================================="
    echo ""
    UNINSTALL_FAILED=0

    echo "🧹 Removing exact historical global rule blocks..."
    if ! retire_legacy_global_rules; then
        UNINSTALL_FAILED=1
    fi

    echo "🧹 Removing tGD hooks from config files..."
    for hook_spec in \
        "claude:$HOME/.claude/settings.json" \
        "codex:$HOME/.codex/hooks.json" \
        "gemini:$HOME/.gemini/settings.json"; do
        hook_platform="${hook_spec%%:*}"
        hook_destination="${hook_spec#*:}"
        if [[ ! -f "$hook_destination" && ! -f "$HOOK_STATE_FILE" ]]; then
            continue
        fi
        if ! python3 "$HOOK_MERGE_HELPER" remove \
            --platform "$hook_platform" \
            --repo-root "$TGD_REPO_ROOT" \
            --destination "$hook_destination" \
            --state "$HOOK_STATE_FILE"; then
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

    if [[ -e "$VERSION_FILE" || -L "$VERSION_FILE" ]]; then
        echo "   ℹ️  Preserving unowned or changed version marker: $VERSION_FILE"
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
# Release preparation writes the tracked CalVer value (including .N micro tags).
if [[ ! -r "$TGD_REPO_ROOT/VERSION" ]]; then
    echo "❌ Repository VERSION is missing or unreadable." >&2
    exit 1
fi
TGD_VERSION=$(cat "$TGD_REPO_ROOT/VERSION")
MARKER_LEGACY_ARGS=()
if [[ -f "$VERSION_FILE" && ! -L "$VERSION_FILE" ]]; then
    LEGACY_VERSION=$(cat "$VERSION_FILE" 2>/dev/null || echo "")
    if [[ "$LEGACY_VERSION" =~ ^v[0-9]{4}\.[0-9]{2}\.[0-9]{2}(\.[1-9][0-9]*)?$ ]]; then
        MARKER_LEGACY_ARGS=(--legacy-version "$LEGACY_VERSION")
    fi
fi
if ! python3 "$INSTALL_STATE_HELPER" check-marker \
    --manifest "$INSTALL_MANIFEST" \
    --path "$VERSION_FILE" \
    --recovery-version "$TGD_VERSION" \
    "${MARKER_LEGACY_ARGS[@]}" >/dev/null; then
    echo "❌ Installation collision at $VERSION_FILE." >&2
    echo "   Existing user data was preserved. Move it aside, then retry." >&2
    exit 1
fi

cleanup_generated_source_links() {
    local skills_root="$1"
    local root_self_link skill_dir link parent_name link_name target legacy_name
    local canonical_target canonical_alias_target
    [[ ! -L "$skills_root" && -d "$skills_root" ]] || return 0
    root_self_link="$skills_root/$(basename "$skills_root")"
    if [[ -L "$root_self_link" ]] \
        && [[ "$(absolute_symlink_target "$root_self_link")" == "$skills_root" ]]; then
        echo "   🧹 Removing installer-generated source symlink: $root_self_link"
        remove_exact_symlink_safely "$root_self_link" "$skills_root"
    fi
    for skill_dir in "$skills_root"/*/; do
        skill_dir="${skill_dir%/}"
        [[ ! -L "$skill_dir" && -d "$skill_dir" ]] || continue
        parent_name=$(basename "$skill_dir")
        legacy_name="${parent_name#tgd-}"
        for link in "$skill_dir"/*; do
            [[ -L "$link" ]] || continue
            link_name=$(basename "$link")
            target=$(absolute_symlink_target "$link")
            canonical_target=$(canonical_path_for_compare "$target")
            canonical_alias_target=$(
                canonical_path_for_compare "$skills_root/$link_name"
            )
            if [[ "$link_name" == "$parent_name" && "$target" == "$skill_dir" ]] \
                || [[ "$parent_name" == tgd-* \
                    && "$link_name" == "$legacy_name" \
                    && ! -e "$link" \
                    && "$target" == "$skills_root/$legacy_name" ]] \
                || [[ "$parent_name" == "tgd-core-rules" \
                    && "$link_name" == "rules" \
                    && ! -e "$link" \
                    && "$target" == "$skills_root/rules" ]] \
                || [[ "$parent_name" == "tgd-core-router" \
                    && ! -e "$link" \
                    && "$canonical_target" == "$canonical_alias_target" \
                    && ( "$link_name" == "using-tgd" \
                        || "$link_name" == "tgd-using-tgd" ) ]]; then
                echo "   🧹 Removing installer-generated source symlink: $link"
                remove_exact_symlink_safely "$link" "$target"
            fi
        done
    done
}

cleanup_generated_source_links "$TGD_REPO_ROOT/skills"
cleanup_generated_source_links \
    "$TGD_REPO_ROOT/vendor/understand-anything/understand-anything-plugin/skills"
hermes_plugin_self_link="$TGD_REPO_ROOT/.hermes/plugins/tgd/tgd"
if [[ -L "$hermes_plugin_self_link" ]] \
    && [[ "$(absolute_symlink_target "$hermes_plugin_self_link")" \
        == "$TGD_REPO_ROOT/.hermes/plugins/tgd" ]]; then
    echo "   🧹 Removing installer-generated source symlink: $hermes_plugin_self_link"
    remove_exact_symlink_safely \
        "$hermes_plugin_self_link" \
        "$TGD_REPO_ROOT/.hermes/plugins/tgd"
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
        if is_recognized_legacy_target "$target" "skills/$legacy_name"; then
            echo "   🗑️  Removing verified legacy tGD symlink ($label): $link"
            remove_exact_symlink_safely "$link" "$target"
        fi
    done
}

# Skill IDs were reorganized under lifecycle-oriented names in the first
# release after v2026.08.02.1. Remove only symlinks that can still be proven to
# point at an older tGD checkout; foreign user skills are never touched.
LEGACY_SKILL_RENAMES=(
    "tgd-agent-browser:tgd-verify-browser"
    "tgd-api-and-interface-design:tgd-define-api"
    "tgd-ci-cd-and-automation:tgd-release-ci"
    "tgd-code-review-and-quality:tgd-review-quality"
    "tgd-code-simplification:tgd-review-simplify"
    "tgd-context-engineering:tgd-core-context"
    "tgd-debugging-and-error-recovery:tgd-verify-debug"
    "tgd-deprecation-and-migration:tgd-release-migration"
    "tgd-documentation-and-adrs:tgd-review-adr"
    "tgd-doubt-driven-development:tgd-core-doubt"
    "tgd-frontend-ui-engineering:tgd-develop-ui"
    "tgd-git-workflow-and-versioning:tgd-core-git"
    "tgd-idea-refine:tgd-define-ideate"
    "tgd-incremental-implementation:tgd-develop-incremental"
    "tgd-interview-me:tgd-define-interview"
    "tgd-jira-auto-sync:tgd-plan-jira"
    "tgd-performance-optimization:tgd-review-performance"
    "tgd-planning-and-task-breakdown:tgd-plan-breakdown"
    "tgd-router:tgd-core-router"
    "tgd-rules:tgd-core-rules"
    "tgd-security-and-hardening:tgd-review-security"
    "tgd-shipping-and-launch:tgd-release-ship"
    "tgd-sketch:tgd-define-sketch"
    "tgd-source-driven-development:tgd-develop-source"
    "tgd-spec-driven-development:tgd-define-spec"
    "tgd-subagent-driven-development:tgd-develop-subagents"
    "tgd-test-driven-development:tgd-develop-tdd"
    "tgd-verification-before-completion:tgd-verify-completion"
    "tgd-wiki-generation:tgd-support-wiki"
)

purge_renamed_tgd_symlinks() {
    local dir="$1"
    local label="$2"
    local pair old_name new_name link target
    [[ -d "$dir" ]] || return 0
    for pair in "${LEGACY_SKILL_RENAMES[@]}"; do
        old_name="${pair%%:*}"
        new_name="${pair#*:}"
        link="$dir/$old_name"
        [[ -L "$link" ]] || continue
        target=$(absolute_symlink_target "$link")
        if is_recognized_legacy_target "$target" "skills/$old_name"; then
            echo "   🗑️  Removing verified renamed skill ($label): $link → $new_name"
            remove_exact_symlink_safely "$link" "$target"
        fi
    done
}

echo "🔄 Migrating renamed tGD skills to lifecycle IDs..."
purge_renamed_tgd_symlinks "$HOME/.claude/skills" "Claude Code"
purge_renamed_tgd_symlinks "$HOME/.config/opencode/skills" "OpenCode"
purge_renamed_tgd_symlinks "$HOME/.codex/skills" "Codex CLI"
purge_renamed_tgd_symlinks "$HOME/.gemini/skills" "Gemini CLI"
purge_renamed_tgd_symlinks "$HOME/.pi/agent/skills" "Pi"
while IFS= read -r hermes_home; do
    [[ -n "$hermes_home" ]] || continue
    purge_renamed_tgd_symlinks "$hermes_home/skills" "Hermes ($(display_home_path "$hermes_home"))"
done < <(hermes_homes)

if [[ "$MODE" == "upgrade" ]]; then
    echo "🔄 Removing verified pre-lifecycle skill aliases..."
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

remove_verified_legacy_link() {
    local destination="$1"
    local source_relative="$2"
    local label="$3"
    local target result

    [[ -L "$destination" ]] || return 0
    target=$(absolute_symlink_target "$destination")
    if is_recognized_legacy_target "$target" "$source_relative"; then
        result=$(python3 "$INSTALL_STATE_HELPER" retire-owned-link \
            --manifest "$INSTALL_MANIFEST" \
            --path "$destination" \
            --target "$target")
        if [[ "$result" == removed* ]]; then
            echo "   🗑️  Retired managed legacy $label: $destination"
        else
            echo "   🗑️  Removing verified unowned legacy $label: $destination"
            remove_exact_symlink_safely "$destination" "$target"
        fi
    fi
}

retire_verified_legacy_bundle() {
    local destination="$1"
    local source="$2"
    local source_relative="$3"
    local label="$4"
    local target

    [[ -L "$destination" ]] || return 0
    target=$(absolute_symlink_target "$destination")
    if ! is_recognized_legacy_target "$target" "$source_relative"; then
        return 0
    fi

    # Adopt the exact verified legacy link before removing it so the
    # ownership manifest remains authoritative throughout the migration.
    managed_link "$source" "$destination"
    python3 "$INSTALL_STATE_HELPER" remove \
        --manifest "$INSTALL_MANIFEST" \
        --path "$destination" >/dev/null
    echo "   🗑️  Retired verified legacy $label: $destination"
}

retire_exact_managed_link() {
    local source="$1"
    local destination="$2"
    local label="$3"

    local result=""
    result=$(python3 "$INSTALL_STATE_HELPER" retire-owned-link \
        --manifest "$INSTALL_MANIFEST" \
        --path "$destination" \
        --target "$source")
    if [[ "$result" == removed* ]]; then
        echo "   🗑️  Retired managed $label: $destination"
    fi
}

# These integrations were intentionally retired. Remove them only when their
# exact source can still be proven to belong to a tGD checkout.
retire_legacy_global_rules
remove_verified_legacy_link \
    "$HOME/.claude/rules/tgd.md" \
    "skills/tgd-core-rules/SKILL.md" \
    "Claude global rule"
# The previous release used tgd-rules; keep this exact legacy target check so
# the rename does not strand an old global rule symlink.
remove_verified_legacy_link \
    "$HOME/.claude/rules/tgd.md" \
    "skills/tgd-rules/SKILL.md" \
    "Claude legacy global rule"
remove_verified_legacy_link \
    "$HOME/.pi/agent/extensions/tgd-commands.ts" \
    ".pi/extensions/tgd-commands.ts" \
    "Pi command extension"

# Retire integrations that older tGD releases treated as global context.
# Exact managed/verified tGD links are removed; foreign files are preserved.
remove_verified_legacy_link \
    "$HOME/.pi/agent/instructions.md" \
    ".pi/instructions.md" \
    "Pi instructions link"
retire_exact_managed_link \
    "$TGD_REPO_ROOT/.pi/instructions.md" \
    "$HOME/.pi/agent/instructions.md" \
    "Pi instructions link"
remove_verified_legacy_link \
    "$HOME/.config/opencode/plugins/session-start.ts" \
    ".opencode/plugins/session-start.ts" \
    "OpenCode session plugin"
retire_exact_managed_link \
    "$TGD_REPO_ROOT/.opencode/plugins/session-start.ts" \
    "$HOME/.config/opencode/plugins/session-start.ts" \
    "OpenCode session plugin"
while IFS= read -r hermes_home; do
    [[ -n "$hermes_home" ]] || continue
    remove_verified_legacy_link \
        "$hermes_home/AGENTS.md" \
        ".hermes/AGENTS.md" \
        "Hermes AGENTS.md"
    retire_exact_managed_link \
        "$TGD_REPO_ROOT/.hermes/AGENTS.md" \
        "$hermes_home/AGENTS.md" \
        "Hermes AGENTS.md"
done < <(hermes_homes)

if [[ "$WITH_SESSION_PREAMBLE" -eq 1 ]]; then
    managed_link \
        "$TGD_REPO_ROOT/hooks/session-preamble.enabled" \
        "$TGD_STATE_DIR/session-preamble.enabled"
    echo "   ✅ Optional session preamble enabled."
else
    retire_exact_managed_link \
        "$TGD_REPO_ROOT/hooks/session-preamble.enabled" \
        "$TGD_STATE_DIR/session-preamble.enabled" \
        "session preamble marker"
    echo "   ℹ️  Session preamble disabled; skills and commands load on demand."
fi

# Configure Agents
echo "🤖 Configuring Agents..."

# OpenCode
if command -v opencode &> /dev/null || [[ -d "$HOME/.config/opencode" ]]; then
    echo "   📂 OpenCode detected or existing config found."
    # Create global commands link (individual files, not subdirectory)
    mkdir -p ~/.config/opencode/commands
    for cmd in "$TGD_REPO_ROOT"/.opencode/commands/*.md; do
        [[ -e "$cmd" ]] || continue
        cmd_name=$(basename "$cmd")
        managed_link "$cmd" "$HOME/.config/opencode/commands/$cmd_name"
    done
    echo "   ✅ Commands linked (7 tgd-* commands)."
    # OpenCode discovers one skill per direct child directory.
    if [ -d "$TGD_REPO_ROOT/skills" ]; then
        mkdir -p ~/.config/opencode/skills
        retire_verified_legacy_bundle \
            "$HOME/.config/opencode/skills/tGD" \
            "$TGD_REPO_ROOT/skills" \
            "skills" \
            "OpenCode aggregate skill link"
        for skill in "$TGD_REPO_ROOT"/skills/*/; do
            skill="${skill%/}"
            [[ ! -L "$skill" && -d "$skill" ]] || continue
            skill_name=$(basename "$skill")
            [[ "$skill_name" != "skills" ]] || continue
            managed_link "$skill" "$HOME/.config/opencode/skills/$skill_name"
        done
        echo "   ✅ Skills linked directly for on-demand loading."
    fi
fi

# Claude Code
if command -v claude &> /dev/null || [[ -d "$HOME/.claude" ]]; then
    echo "   📂 Claude Code detected or existing config found."
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

        if [[ "$WITH_SESSION_PREAMBLE" -eq 1 ]] \
            && [ -f "$TGD_REPO_ROOT/hooks/session-start.sh" ]; then
            python3 "$HOOK_MERGE_HELPER" install \
                --platform claude \
                --repo-root "$TGD_REPO_ROOT" \
                --destination "$HOME/.claude/settings.json" \
                --state "$HOOK_STATE_FILE"
        else
            python3 "$HOOK_MERGE_HELPER" remove \
                --platform claude \
                --repo-root "$TGD_REPO_ROOT" \
                --destination "$HOME/.claude/settings.json" \
                --state "$HOOK_STATE_FILE"
        fi
    fi
fi

# Gemini CLI
if command -v gemini &> /dev/null || [[ -d "$HOME/.gemini" ]]; then
    echo "   📂 Gemini CLI detected or existing config found."
    if [ -d "$TGD_REPO_ROOT/.gemini" ]; then
        mkdir -p ~/.gemini/commands
        for command_file in "$TGD_REPO_ROOT"/.gemini/commands/*; do
            [[ -e "$command_file" ]] || continue
            managed_link "$command_file" "$HOME/.gemini/commands/$(basename "$command_file")"
        done
        echo "   ✅ Commands linked."
    fi
    # Gemini discovers skills only one directory below ~/.gemini/skills.
    # Retire the historical aggregate link, then link each skill directly.
    if [ -d "$TGD_REPO_ROOT/skills" ]; then
        mkdir -p ~/.gemini/skills
        retire_verified_legacy_bundle \
            "$HOME/.gemini/skills/tGD" \
            "$TGD_REPO_ROOT/skills" \
            "skills" \
            "Gemini aggregate skill link"
        gemini_skill_count=0
        for skill in "$TGD_REPO_ROOT"/skills/*/; do
            skill="${skill%/}"
            [[ ! -L "$skill" && -d "$skill" ]] || continue
            skill_name=$(basename "$skill")
            [[ "$skill_name" != "skills" ]] || continue
            managed_link "$skill" "$HOME/.gemini/skills/$skill_name"
            gemini_skill_count=$((gemini_skill_count + 1))
        done
        echo "   ✅ Gemini skills linked directly ($gemini_skill_count skills)."
    fi
    if [[ "$WITH_SESSION_PREAMBLE" -eq 1 ]] \
        && [ -f "$TGD_REPO_ROOT/hooks/gemini/session-start.sh" ]; then
        python3 "$HOOK_MERGE_HELPER" install \
            --platform gemini \
            --repo-root "$TGD_REPO_ROOT" \
            --destination "$HOME/.gemini/settings.json" \
            --state "$HOOK_STATE_FILE"
    else
        python3 "$HOOK_MERGE_HELPER" remove \
            --platform gemini \
            --repo-root "$TGD_REPO_ROOT" \
            --destination "$HOME/.gemini/settings.json" \
            --state "$HOOK_STATE_FILE"
    fi
fi

# Codex CLI
if command -v codex &> /dev/null || [[ -d "$HOME/.codex" ]]; then
    echo "   📂 Codex CLI detected or existing config found."
    mkdir -p "$HOME/.codex" "$HOME/.agents/skills"
    if [ -d "$TGD_REPO_ROOT/skills" ]; then
        mkdir -p "$HOME/.codex/skills"
        retire_verified_legacy_bundle \
            "$HOME/.codex/skills/tGD" \
            "$TGD_REPO_ROOT/skills" \
            "skills" \
            "Codex legacy aggregate skill link"
        for skill in "$TGD_REPO_ROOT"/skills/*/; do
            skill="${skill%/}"
            [[ ! -L "$skill" && -d "$skill" ]] || continue
            skill_name=$(basename "$skill")
            [[ "$skill_name" != "skills" ]] || continue
            managed_link "$skill" "$HOME/.agents/skills/$skill_name"
        done
        echo "   ✅ Codex skills linked to ~/.agents/skills for on-demand loading."
    fi
    if [ -d "$TGD_REPO_ROOT/.codex/skills" ]; then
        for lifecycle_skill in "$TGD_REPO_ROOT"/.codex/skills/*/; do
            lifecycle_skill="${lifecycle_skill%/}"
            [[ -d "$lifecycle_skill" ]] || continue
            managed_link \
                "$lifecycle_skill" \
                "$HOME/.agents/skills/$(basename "$lifecycle_skill")"
        done
        echo "   ✅ Lifecycle skills linked (use \$tgd-map … \$tgd-release)."
    fi
    for command_name in tgd-map tgd-define tgd-plan tgd-develop tgd-verify tgd-review tgd-release; do
        remove_verified_legacy_link \
            "$HOME/.codex/prompts/$command_name.md" \
            ".codex/prompts/$command_name.md" \
            "Codex deprecated prompt"
        retire_exact_managed_link \
            "$TGD_REPO_ROOT/.codex/prompts/$command_name.md" \
            "$HOME/.codex/prompts/$command_name.md" \
            "Codex deprecated prompt"
    done
    if [[ "$WITH_SESSION_PREAMBLE" -eq 1 ]] \
        && [ -f "$TGD_REPO_ROOT/hooks/codex/session-start.sh" ]; then
        python3 "$HOOK_MERGE_HELPER" install \
            --platform codex \
            --repo-root "$TGD_REPO_ROOT" \
            --destination "$HOME/.codex/hooks.json" \
            --state "$HOOK_STATE_FILE"
        echo "   ℹ️  Codex reviews user hooks by exact definition. If Codex warns, open /hooks and trust this hook."
    else
        python3 "$HOOK_MERGE_HELPER" remove \
            --platform codex \
            --repo-root "$TGD_REPO_ROOT" \
            --destination "$HOME/.codex/hooks.json" \
            --state "$HOOK_STATE_FILE"
    fi
fi

# Pi Coding Agent
if command -v pi &> /dev/null || [[ -d "$HOME/.pi/agent" ]]; then
    echo "   📂 Pi Coding Agent detected or existing config found."
    # Install prompt templates to ~/.pi/agent/. tGD commands are
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
    if [[ "$WITH_SESSION_PREAMBLE" -eq 1 ]] \
        && [ -f "$TGD_REPO_ROOT/.pi/APPEND_SYSTEM.md" ]; then
        managed_link \
            "$TGD_REPO_ROOT/.pi/APPEND_SYSTEM.md" \
            "$HOME/.pi/agent/APPEND_SYSTEM.md" \
            optional
        if [[ -L "$HOME/.pi/agent/APPEND_SYSTEM.md" ]] \
            && [[ "$(absolute_symlink_target "$HOME/.pi/agent/APPEND_SYSTEM.md")" \
                == "$TGD_REPO_ROOT/.pi/APPEND_SYSTEM.md" ]]; then
            echo "   ✅ Optional preamble installed to ~/.pi/agent/APPEND_SYSTEM.md"
        else
            echo "   ℹ️  Existing Pi APPEND_SYSTEM.md remains authoritative."
        fi
    else
        retire_exact_managed_link \
            "$TGD_REPO_ROOT/.pi/APPEND_SYSTEM.md" \
            "$HOME/.pi/agent/APPEND_SYSTEM.md" \
            "Pi APPEND_SYSTEM preamble"
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
if command -v hermes &> /dev/null || [[ -d "$HOME/.hermes" ]]; then
    echo "   📂 Hermes Agent detected or existing config found."
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

    echo "   ✅ Hermes commands and skills installed; optional preamble follows the setup flag."
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
    local build_state_status=0
    local install_log=""
    local node_version=""
    local node_major=""
    local node_minor=""
    local pnpm_version=""
    local pnpm_command=()

    if python3 "$UA_BUILD_STATE_HELPER" is-current \
        --ua-root "$ua_dir" \
        --stamp "$UA_BUILD_STAMP" >/dev/null 2>&1; then
        echo "   ✅ UA dependencies already installed."
        return 0
    else
        build_state_status=$?
    fi
    if [[ "$build_state_status" -gt 1 ]]; then
        echo "   ⚠️  Could not verify UA build freshness."
        return 1
    fi
    if [ -f "$ua_dir/node_modules/.modules.yaml" ] \
        && [ -f "$ua_dir/understand-anything-plugin/packages/core/dist/index.js" ]; then
        echo "   🔄 UA build inputs changed or the build stamp is missing; rebuilding."
    fi

    if [[ "$SKIP_DEPS" -eq 1 ]]; then
        echo "   ⚠️  UA dependency installation skipped by --no-deps."
        return 1
    fi

    if ! command -v node &> /dev/null; then
        echo "   ⚠️  UA requires Node.js >= 22.12.0; Node.js was not found."
        echo "      Core tGD links and hooks will still be installed."
        return 1
    fi
    node_version=$(node -p 'process.versions.node' 2>/dev/null || echo "0.0.0")
    IFS=. read -r node_major node_minor _node_patch <<< "$node_version"
    if ! [[ "$node_major" =~ ^[0-9]+$ && "$node_minor" =~ ^[0-9]+$ ]] \
        || (( node_major < 22 || (node_major == 22 && node_minor < 12) )); then
        echo "   ⚠️  UA requires Node.js >= 22.12.0; found $(node -v 2>/dev/null || echo 'unknown')."
        echo "      Core tGD links and hooks will still be installed."
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
        if [ ! -f "$ua_dir/node_modules/.modules.yaml" ]; then
            echo "   ⚠️  pnpm install exited successfully but its module manifest is missing."
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

    if [ -f "$ua_dir/node_modules/.modules.yaml" ]; then
        echo "   🔨 Building UA (pnpm build)..."
        if (cd "$ua_dir" && "${pnpm_command[@]}" build); then
            if [ ! -f "$ua_dir/understand-anything-plugin/packages/core/dist/index.js" ]; then
                echo "   ⚠️  pnpm build exited successfully but UA core output is missing."
                return 1
            fi
            if ! python3 "$UA_BUILD_STATE_HELPER" write \
                --ua-root "$ua_dir" \
                --stamp "$UA_BUILD_STAMP" >/dev/null; then
                echo "   ⚠️  UA built, but its build freshness stamp could not be recorded."
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

    UA_PLUGIN_TARGET="$UA_DIR/understand-anything-plugin"
    UA_PLUGIN_LINK="$HOME/.understand-anything-plugin"
    managed_link "$UA_PLUGIN_TARGET" "$UA_PLUGIN_LINK" optional
    if [[ -L "$UA_PLUGIN_LINK" ]] \
        && [[ "$(absolute_symlink_target "$UA_PLUGIN_LINK")" == "$UA_PLUGIN_TARGET" ]]; then
        echo "   🔗 ~/.understand-anything-plugin → vendor (tGD-managed)"
    else
        echo "   ℹ️  Existing ~/.understand-anything-plugin remains authoritative."
    fi
    retire_verified_legacy_bundle \
        "$HOME/.understand-anything/repo" \
        "$UA_PLUGIN_TARGET" \
        "vendor/understand-anything/understand-anything-plugin" \
        "Understand-Anything legacy repo link"
else
    echo "   ⚠️  Understand-Anything not found at vendor/understand-anything/"
    echo "      Re-clone tGD or manually download from: https://github.com/Lum1104/Understand-Anything"
    SETUP_DEGRADED=1
fi

# Link Understand-Anything skills to each platform
if [ -d "$UA_SKILLS_DIR" ]; then
    # Universal canonical links shared by Gemini, Codex, OpenCode, and Pi.
    mkdir -p "$HOME/.agents/skills"
    GEMINI_UA_ACTIVE=0
    if [ -d "$HOME/.gemini" ] || [ -L "$HOME/.gemini" ]; then
        GEMINI_UA_ACTIVE=1
        mkdir -p "$HOME/.gemini/skills"
        retire_verified_legacy_bundle \
            "$HOME/.gemini/skills/understand-anything" \
            "$UA_SKILLS_DIR" \
            "vendor/understand-anything/understand-anything-plugin/skills" \
            "Gemini Understand-Anything aggregate skill link"
    fi
    for skill in "$UA_SKILLS_DIR"/*/; do
        skill="${skill%/}"
        [[ ! -L "$skill" && -d "$skill" ]] || continue
        skill_name=$(basename "$skill")
        universal_skill_link="$HOME/.agents/skills/$skill_name"
        managed_link "$skill" "$universal_skill_link" optional

        if [[ "$GEMINI_UA_ACTIVE" -eq 1 ]]; then
            retire_exact_managed_link \
                "$skill" \
                "$HOME/.gemini/skills/understand-$skill_name" \
                "Gemini Understand-Anything prefixed skill link"
            if [[ -L "$universal_skill_link" ]] \
                && [[ "$(absolute_symlink_target "$universal_skill_link")" == "$skill" ]]; then
                retire_exact_managed_link \
                    "$skill" \
                    "$HOME/.gemini/skills/$skill_name" \
                    "Gemini Understand-Anything direct fallback"
            else
                managed_link \
                    "$skill" \
                    "$HOME/.gemini/skills/$skill_name" \
                    optional
            fi
        fi
    done
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
    # Gemini uses the universal links above. A direct child fallback is created
    # only for a canonical name blocked by an existing ~/.agents path.
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
if [ -d "skills/tgd-verify-browser" ]; then
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
            CONFIG_LOCK="$TGD_STATE_DIR/agent-browser-config.lock"
            python3 - "$CONFIG_FILE" "$CHROME_BIN" "$CONFIG_LOCK" <<'PYEOF'
import fcntl
import json
import os
from pathlib import Path
import stat
import sys
import tempfile

path = Path(sys.argv[1])
chrome = sys.argv[2]
lock_path = Path(sys.argv[3])


def fsync_directory(directory):
    flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    try:
        descriptor = os.open(str(directory), flags)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def update_config():
    if path.is_symlink():
        raise SystemExit("refusing symlinked Agent Browser config: {}".format(path))
    if path.exists():
        original = path.read_bytes()
        config = json.loads(original.decode("utf-8"))
        mode = stat.S_IMODE(path.stat().st_mode)
    else:
        original = None
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
            descriptor = -1
            json.dump(config, stream, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        if path.is_symlink():
            raise SystemExit(
                "Agent Browser config changed to a symlink during update"
            )
        if original is None:
            if os.path.lexists(str(path)):
                raise SystemExit("Agent Browser config changed during update")
        elif not path.is_file() or path.read_bytes() != original:
            raise SystemExit("Agent Browser config changed during update")
        os.replace(temporary_name, path)
        fsync_directory(path.parent)
    except BaseException:
        if descriptor >= 0:
            os.close(descriptor)
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


lock_path.parent.mkdir(parents=True, exist_ok=True)
lock_flags = os.O_CREAT | os.O_RDWR
if hasattr(os, "O_NOFOLLOW"):
    lock_flags |= os.O_NOFOLLOW
try:
    lock_descriptor = os.open(str(lock_path), lock_flags, 0o600)
except OSError as error:
    raise SystemExit(
        "cannot safely open Agent Browser config lock: {}".format(error)
    )
try:
    if not stat.S_ISREG(os.fstat(lock_descriptor).st_mode):
        raise SystemExit("Agent Browser config lock is not a regular file")
    fcntl.flock(lock_descriptor, fcntl.LOCK_EX)
    update_config()
finally:
    os.close(lock_descriptor)
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

# Claude Code: NO global rules symlink — tgd-core-rules stays as a project-local skill.
# Previously: ln -sf ... "$HOME/.claude/rules/tgd.md" (loaded in ALL conversations)
# Now: rules are loaded via skill system only when in a tGD project context.
# If you need rules in a specific project, add to .claude/CLAUDE.md:
#   "Load tgd-core-rules skill for tGD workflow enforcement."

# Codex CLI: official shared user-skill path
if command -v codex &> /dev/null || [[ "$CI_ACTIVE" -eq 1 ]]; then
    mkdir -p "$HOME/.agents/skills"
    managed_link "$TGD_REPO_ROOT/skills/tgd-core-rules" "$HOME/.agents/skills/tgd-core-rules"
    echo "   ✅ Codex CLI: ~/.agents/skills/tgd-core-rules → symlink"
fi

# OpenCode: ~/.config/opencode/skills/tgd-core-rules
if command -v opencode &> /dev/null || [[ "$CI_ACTIVE" -eq 1 ]]; then
    mkdir -p "$HOME/.config/opencode/skills"
    managed_link "$TGD_REPO_ROOT/skills/tgd-core-rules" "$HOME/.config/opencode/skills/tgd-core-rules"
    echo "   ✅ OpenCode: ~/.config/opencode/skills/tgd-core-rules → symlink"
fi

# Gemini CLI: ~/.gemini/skills/tgd-core-rules
if command -v gemini &> /dev/null || [[ "$CI_ACTIVE" -eq 1 ]]; then
    mkdir -p "$HOME/.gemini/skills"
    managed_link "$TGD_REPO_ROOT/skills/tgd-core-rules" "$HOME/.gemini/skills/tgd-core-rules"
    echo "   ✅ Gemini CLI: ~/.gemini/skills/tgd-core-rules → symlink"
fi

# Pi: ~/.pi/agent/skills/tgd-core-rules
if command -v pi &> /dev/null || [[ "$CI_ACTIVE" -eq 1 ]]; then
    mkdir -p "$HOME/.pi/agent/skills"
    managed_link "$TGD_REPO_ROOT/skills/tgd-core-rules" "$HOME/.pi/agent/skills/tgd-core-rules"
    echo "   ✅ Pi: ~/.pi/agent/skills/tgd-core-rules → symlink"
fi

# Hermes Agent: ~/.hermes/skills/tgd-core-rules plus every existing profile.
if command -v hermes &> /dev/null || [[ "$CI_ACTIVE" -eq 1 ]]; then
    link_skill_folder_to_hermes_homes "$TGD_REPO_ROOT/skills/tgd-core-rules" "tgd-core-rules" "tgd-core-rules"
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
LEGACY_GLOBAL_TGD="/usr/local/bin/tgd"
if [[ "$CI_ACTIVE" -eq 0 ]] \
    && [[ "${TGD_DISABLE_GLOBAL_MIGRATION_FOR_TESTS:-0}" != "1" ]] \
    && [[ -L "$LEGACY_GLOBAL_TGD" ]] \
    && is_recognized_legacy_target \
        "$(absolute_symlink_target "$LEGACY_GLOBAL_TGD")" \
        "bin/tgd"; then
    managed_link "$TGD_BIN" "$LEGACY_GLOBAL_TGD" optional
    if [[ -L "$LEGACY_GLOBAL_TGD" ]] \
        && [[ "$(absolute_symlink_target "$LEGACY_GLOBAL_TGD")" == "$TGD_BIN" ]]; then
        echo "   🔄 Adopted existing legacy CLI link: $LEGACY_GLOBAL_TGD"
    else
        echo "   ⚠️  Existing legacy CLI remains at $LEGACY_GLOBAL_TGD; it may shadow ~/.local/bin/tgd."
    fi
fi
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
    local label="$1" destination_dir="$2" source_dir="$3" pattern="$4"
    local source_count=0 verified_count=0 source destination
    for source in "$source_dir"/$pattern; do
        [[ -e "$source" ]] || continue
        source_count=$((source_count + 1))
        destination="$destination_dir/$(basename "$source")"
        if python3 "$INSTALL_STATE_HELPER" verify \
            --manifest "$INSTALL_MANIFEST" \
            --path "$destination" \
            --target "$source" >/dev/null 2>&1; then
            verified_count=$((verified_count + 1))
        fi
    done
    if [[ "$source_count" -eq 7 && "$verified_count" -eq 7 ]]; then
        echo "   ✅ $label: 7/7 canonical commands verified ($destination_dir)"
    else
        echo "   ❌ $label: $verified_count/7 canonical commands verified in $destination_dir (source has $source_count)"
        SETUP_FAILED=1
    fi
}

command -v claude &> /dev/null \
    && verify_cmd_links "Claude Code" "$HOME/.claude/commands" "$TGD_REPO_ROOT/.claude/commands" "tgd-*.md" \
    || echo "   ⏭️  Claude Code not detected — skipped"
command -v opencode &> /dev/null \
    && verify_cmd_links "OpenCode" "$HOME/.config/opencode/commands" "$TGD_REPO_ROOT/.opencode/commands" "tgd-*.md" \
    || echo "   ⏭️  OpenCode not detected — skipped"
command -v gemini &> /dev/null \
    && verify_cmd_links "Gemini CLI" "$HOME/.gemini/commands" "$TGD_REPO_ROOT/.gemini/commands" "tgd-*.toml" \
    || echo "   ⏭️  Gemini CLI not detected — skipped"
command -v codex &> /dev/null \
    && verify_cmd_links "Codex CLI" "$HOME/.agents/skills" "$TGD_REPO_ROOT/.codex/skills" "tgd-*" \
    || echo "   ⏭️  Codex CLI not detected — skipped"
command -v pi &> /dev/null \
    && verify_cmd_links "Pi" "$HOME/.pi/agent/prompts" "$TGD_REPO_ROOT/.pi/prompts" "tgd-*.md" \
    || echo "   ⏭️  Pi not detected — skipped"

# Understand-Anything runtime state (needed by /tgd-map Steps 4-5)
if [ -d "$UA_SKILLS_DIR" ]; then
    if [ -f "$UA_DIR/node_modules/.modules.yaml" ]; then
        echo "   ✅ UA dependencies installed (pnpm module manifest present)"
    else
        echo "   ⚠️  UA dependencies NOT installed — /understand scans and the dashboard will not run."
        echo "      (pnpm missing or registry policy deferred the install — see messages above)"
    fi
    if [ -f "$UA_DIR/understand-anything-plugin/packages/core/dist/index.js" ]; then
        echo "   ✅ UA core built (packages/core/dist/index.js present)"
    else
        echo "   ⚠️  UA core NOT built — run: cd vendor/understand-anything && pnpm install && pnpm build"
    fi
    if python3 "$UA_BUILD_STATE_HELPER" is-current \
        --ua-root "$UA_DIR" \
        --stamp "$UA_BUILD_STAMP" >/dev/null 2>&1; then
        echo "   ✅ UA build fingerprint matches the current vendored inputs"
    else
        echo "   ⚠️  UA build fingerprint is missing or stale — a supported Node runtime must rebuild it."
        SETUP_DEGRADED=1
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

python3 "$INSTALL_STATE_HELPER" write-marker \
    --manifest "$INSTALL_MANIFEST" \
    --path "$VERSION_FILE" \
    --version "$TGD_VERSION" \
    "${MARKER_LEGACY_ARGS[@]}" >/dev/null

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
echo "Then initialize with the platform-native entry point:"
echo "  Codex: \$tgd-map"
echo "  Claude/Gemini/OpenCode/Pi/Hermes: /tgd-map"
echo ""
