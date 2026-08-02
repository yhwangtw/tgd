#!/bin/bash
# release.sh — PREPARE a tGD release. Publishing happens in CI.
#
# Division of labor (single-copy by design):
#   - This script:  compute the version, generate the categorized CHANGELOG
#                   entry, bump VERSION, commit, push. Nothing else.
#   - CI (release.yml): when the VERSION change lands on main, create the tag
#                   and the GitHub release, with notes extracted from the
#                   CHANGELOG entry this script wrote.
#
# Why prepare-only:
#   - The old script tagged BEFORE committing VERSION/CHANGELOG, so every
#     historical tag carried the previous release's VERSION file
#     (verify: `git show v2026.07.04:VERSION` → v2026.07.02). Letting CI tag
#     the commit that contains the bump makes that bug structurally
#     impossible.
#   - The old script duplicated ~90 lines of release-notes generation with
#     release.yml, and the two had already diverged. The categorization
#     logic now lives here only; CI reads the result from CHANGELOG.md.
#   - No gh CLI or auth needed locally.
#
# Versioning (CalVer, immutable tags):
#   - Default: vYYYY.MM.DD (today). If that tag exists, auto-bump a micro
#     segment: vYYYY.MM.DD.1, .2, ... Published tags are NEVER deleted or
#     moved — re-releasing a version someone may have fetched changes its
#     content under them.
#   - Explicit version argument is honored but refused if the tag exists.
#
# Usage: bash scripts/release.sh [version] [--yes] [--dry-run]
#   version:   vYYYY.MM.DD or vYYYY.MM.DD.N (leading v optional; N starts at 1)
#   --yes:     skip the confirmation prompt (non-interactive)
#   --dry-run: print the computed version and CHANGELOG entry, change nothing
#
# Exit codes: 0 ok · 1 refused (existing tag, no commits, user abort) · 2 usage

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$REPO_ROOT"

AUTO_YES=false
DRY_RUN=false
VERSION=""

usage() {
    echo "Usage: bash scripts/release.sh [version] [--yes] [--dry-run]"
}

usage_error() {
    printf '❌ %s\n' "$1" >&2
    usage >&2
    exit 2
}

for arg in "$@"; do
    case "$arg" in
        --yes|-y) AUTO_YES=true ;;
        --dry-run) DRY_RUN=true ;;
        --help|-h)
            sed -n '2,34p' "$0" | sed 's/^# \{0,1\}//'
            exit 0
            ;;
        -*) usage_error "Unknown option: $arg" ;;
        *)
            if [ -n "$VERSION" ]; then
                usage_error "Unexpected extra argument: $arg"
            fi
            VERSION="$arg"
            ;;
    esac
done

if [ -n "$VERSION" ]; then
    RAW_VERSION="$VERSION"
    [[ "$VERSION" =~ ^v ]] || VERSION="v$VERSION"
    if ! [[ "$VERSION" =~ ^v[0-9]{4}\.[0-9]{2}\.[0-9]{2}(\.[1-9][0-9]*)?$ ]]; then
        usage_error "Invalid version: $RAW_VERSION (expected vYYYY.MM.DD or vYYYY.MM.DD.N with N >= 1)"
    fi
    if ! command -v python3 >/dev/null 2>&1; then
        usage_error "python3 is required to validate release dates"
    fi
    if ! python3 -c \
        'import datetime, sys; year, month, day = map(int, sys.argv[1][1:].split(".")[:3]); datetime.date(year, month, day)' \
        "$VERSION" >/dev/null 2>&1; then
        usage_error "Invalid calendar date: $RAW_VERSION"
    fi
fi

START_BRANCH=""
START_HEAD=""
if [ "$DRY_RUN" != true ]; then
    START_BRANCH=$(git branch --show-current)
    if [ -z "$START_BRANCH" ]; then
        echo "❌ Detached HEAD — check out a branch first."
        exit 1
    fi
    START_HEAD=$(git rev-parse --verify HEAD)
fi

validate_release_state() {
    local phase="$1"
    local current_branch current_head worktree_status

    current_branch=$(git branch --show-current)
    current_head=$(git rev-parse --verify HEAD)
    if [ "$current_branch" != "$START_BRANCH" ] || [ "$current_head" != "$START_HEAD" ]; then
        echo "❌ Repository branch or HEAD changed $phase; refusing to modify release files." >&2
        return 1
    fi

    worktree_status=$(git status --porcelain --untracked-files=normal)
    if [ -n "$worktree_status" ]; then
        echo "❌ Release requires a clean worktree $phase; commit or stash changes first." >&2
        printf '%s\n' "$worktree_status" >&2
        return 1
    fi
}

if ! git fetch --tags --quiet origin 2>/dev/null; then
    if [ "$DRY_RUN" = true ]; then
        echo "⚠️  Could not fetch tags — dry run is using the local tag list"
    else
        echo "❌ Could not fetch tags from origin; refusing to prepare a release with an unverified tag list." >&2
        exit 1
    fi
fi

# === Compute version ===

tag_exists() { git rev-parse -q --verify "refs/tags/$1" >/dev/null 2>&1; }

if [ -n "$VERSION" ]; then
    if tag_exists "$VERSION"; then
        echo "❌ Tag $VERSION already exists. Published tags are immutable —"
        echo "   pick a new version (same-day releases take a micro segment, e.g. ${VERSION}.1)."
        exit 1
    fi
else
    VERSION="v$(date +%Y.%m.%d)"
    if tag_exists "$VERSION"; then
        N=1
        while tag_exists "$VERSION.$N"; do N=$((N + 1)); done
        VERSION="$VERSION.$N"
        echo "ℹ️  Today's base tag exists — auto-bumped to $VERSION"
    fi
fi

# === Collect commits since the last tag ===

PREV_TAG=$(git describe --tags --abbrev=0 2>/dev/null || echo "")
if [ -n "$PREV_TAG" ]; then
    COMMITS=$(git log --pretty=format:"%s|||%h" "$PREV_TAG"..HEAD)
    RANGE="$PREV_TAG..HEAD"
else
    COMMITS=$(git log --pretty=format:"%s|||%h" -30)
    RANGE="last 30 commits"
fi

if [ -z "$COMMITS" ]; then
    echo "❌ No commits since $PREV_TAG — nothing to release."
    exit 1
fi

# === Categorize (Conventional Commits) — the ONLY copy of this logic ===

FEATS=""; FIXES=""; DOCS=""; REFACTORS=""; TESTS=""; CHORES=""; OTHERS=""
while IFS= read -r line; do
    [ -z "$line" ] && continue
    MSG="${line%%|||*}"
    HASH="${line##*|||}"
    case "$MSG" in
        feat*:*|feat*)         FEATS="${FEATS}- ${MSG#*: } (\`$HASH\`)"$'\n' ;;
        fix*:*|fix*)           FIXES="${FIXES}- ${MSG#*: } (\`$HASH\`)"$'\n' ;;
        docs*:*|docs*)         DOCS="${DOCS}- ${MSG#*: } (\`$HASH\`)"$'\n' ;;
        refactor*:*|refactor*) REFACTORS="${REFACTORS}- ${MSG#*: } (\`$HASH\`)"$'\n' ;;
        test*:*|test*)         TESTS="${TESTS}- ${MSG#*: } (\`$HASH\`)"$'\n' ;;
        chore*:*|chore*|ci*:*|ci*) CHORES="${CHORES}- ${MSG#*: } (\`$HASH\`)"$'\n' ;;
        Merge\ *)              : ;;  # merge commits carry no release info
        *)                     OTHERS="${OTHERS}- ${MSG} (\`$HASH\`)"$'\n' ;;
    esac
done <<< "$COMMITS"

NEW_ENTRY="## $VERSION"$'\n\n'
append_section() {
    if [ -n "$2" ]; then
        NEW_ENTRY="${NEW_ENTRY}### $1"$'\n'"$2"$'\n'
    fi
}

append_section "✨ Features" "$FEATS"
append_section "🐛 Bug Fixes" "$FIXES"
append_section "📝 Documentation" "$DOCS"
append_section "♻️ Refactoring" "$REFACTORS"
append_section "✅ Tests" "$TESTS"
append_section "🔧 Chores" "$CHORES"
append_section "📦 Other Changes" "$OTHERS"

echo ""
echo "🚀 Preparing release $VERSION (commits: $RANGE)"
echo "---"
printf '%s' "$NEW_ENTRY"
echo "---"

if [ "$DRY_RUN" = true ]; then
    echo "🔎 Dry run — no files changed, nothing committed."
    exit 0
fi

# === Confirm ===

validate_release_state "before confirmation"

if [ "$AUTO_YES" != true ]; then
    read -p "Write VERSION + CHANGELOG.md and commit? (Y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Nn]$ ]]; then
        echo "Aborted."
        exit 1
    fi
fi

validate_release_state "after confirmation"

# === Write VERSION + CHANGELOG (before any commit — CI tags the result) ===

CHANGELOG_HEADER="# Changelog"$'\n\n'
CHANGELOG_HEADER="${CHANGELOG_HEADER}All notable changes to tGD will be documented in this file."$'\n\n'
CHANGELOG_HEADER="${CHANGELOG_HEADER}Format based on [Keep a Changelog](https://keepachangelog.com/). Versions follow [CalVer](https://calver.org/) (YYYY.MM.DD)."$'\n\n'
EXISTING_ENTRIES_FILE=""
cleanup_release_temp() {
    if [ -n "$EXISTING_ENTRIES_FILE" ]; then
        rm -f "$EXISTING_ENTRIES_FILE"
    fi
}
trap cleanup_release_temp EXIT

if [ -f "CHANGELOG.md" ]; then
    EXISTING_ENTRIES_FILE=$(mktemp "${TMPDIR:-/tmp}/tgd-release-changelog.XXXXXX")
    tail -n +7 CHANGELOG.md > "$EXISTING_ENTRIES_FILE"
fi

echo "$VERSION" > VERSION
{
    printf '%s' "$CHANGELOG_HEADER"
    printf '%s' "$NEW_ENTRY"
    if [ -n "$EXISTING_ENTRIES_FILE" ]; then
        cat "$EXISTING_ENTRIES_FILE"
    fi
} > CHANGELOG.md
cleanup_release_temp
trap - EXIT
echo "📝 Updated VERSION + CHANGELOG.md"

# === Commit + push the exact release commit ===

git commit --only -m "chore: release $VERSION" -- VERSION CHANGELOG.md
RELEASE_COMMIT=$(git rev-parse HEAD)
RELEASE_PARENT=$(git rev-parse "$RELEASE_COMMIT^")
if [ "$RELEASE_PARENT" != "$START_HEAD" ]; then
    echo "❌ Release commit was not created from the starting HEAD; refusing to push." >&2
    exit 1
fi

CURRENT_BRANCH=$(git branch --show-current)
CURRENT_BRANCH_HEAD=$(git rev-parse "refs/heads/$START_BRANCH")
if [ "$CURRENT_BRANCH" != "$START_BRANCH" ] \
    || [ "$CURRENT_BRANCH_HEAD" != "$RELEASE_COMMIT" ]; then
    echo "❌ Local branch moved while creating the release commit; refusing to push." >&2
    exit 1
fi

git push origin "$RELEASE_COMMIT:refs/heads/$START_BRANCH"

echo ""
echo "✅ Release $VERSION prepared and pushed to '$START_BRANCH'."
if [ "$START_BRANCH" = "main" ]; then
    echo "   CI (release.yml) will now tag and publish it."
else
    echo "   Open a PR and merge to main — CI (release.yml) tags and publishes on merge."
fi
echo "   Watch: https://github.com/yhwangtw/tgd/actions/workflows/release.yml"
