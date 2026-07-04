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
for arg in "$@"; do
    case "$arg" in
        --yes|-y) AUTO_YES=true ;;
        --dry-run) DRY_RUN=true ;;
        --help|-h)
            sed -n '2,36p' "$0" | sed 's/^# \{0,1\}//'
            exit 0
            ;;
        *) [ -z "$VERSION" ] && VERSION="$arg" ;;
    esac
done

git fetch --tags --quiet origin 2>/dev/null || echo "⚠️  Could not fetch tags — using local tag list"

# === Compute version ===

tag_exists() { git rev-parse -q --verify "refs/tags/$1" >/dev/null 2>&1; }

if [ -n "$VERSION" ]; then
    [[ "$VERSION" =~ ^v ]] || VERSION="v$VERSION"
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
        feat*:*|feat*)         FEATS="${FEATS}- ${MSG#*: } (\`$HASH\`)\n" ;;
        fix*:*|fix*)           FIXES="${FIXES}- ${MSG#*: } (\`$HASH\`)\n" ;;
        docs*:*|docs*)         DOCS="${DOCS}- ${MSG#*: } (\`$HASH\`)\n" ;;
        refactor*:*|refactor*) REFACTORS="${REFACTORS}- ${MSG#*: } (\`$HASH\`)\n" ;;
        test*:*|test*)         TESTS="${TESTS}- ${MSG#*: } (\`$HASH\`)\n" ;;
        chore*:*|chore*|ci*:*|ci*) CHORES="${CHORES}- ${MSG#*: } (\`$HASH\`)\n" ;;
        Merge\ *)              : ;;  # merge commits carry no release info
        *)                     OTHERS="${OTHERS}- ${MSG} (\`$HASH\`)\n" ;;
    esac
done <<< "$COMMITS"

build_section() {
    [ -n "$2" ] && { echo "### $1"; echo -e "$2"; }
}

NEW_ENTRY="## $VERSION\n\n"
[ -n "$FEATS" ]     && NEW_ENTRY+=$(build_section "✨ Features" "$FEATS")"\n"
[ -n "$FIXES" ]     && NEW_ENTRY+=$(build_section "🐛 Bug Fixes" "$FIXES")"\n"
[ -n "$DOCS" ]      && NEW_ENTRY+=$(build_section "📝 Documentation" "$DOCS")"\n"
[ -n "$REFACTORS" ] && NEW_ENTRY+=$(build_section "♻️ Refactoring" "$REFACTORS")"\n"
[ -n "$TESTS" ]     && NEW_ENTRY+=$(build_section "✅ Tests" "$TESTS")"\n"
[ -n "$CHORES" ]    && NEW_ENTRY+=$(build_section "🔧 Chores" "$CHORES")"\n"
[ -n "$OTHERS" ]    && NEW_ENTRY+=$(build_section "📦 Other Changes" "$OTHERS")"\n"

echo ""
echo "🚀 Preparing release $VERSION (commits: $RANGE)"
echo "---"
echo -e "$NEW_ENTRY"
echo "---"

if [ "$DRY_RUN" = true ]; then
    echo "🔎 Dry run — no files changed, nothing committed."
    exit 0
fi

# === Confirm ===

if [ "$AUTO_YES" != true ]; then
    read -p "Write VERSION + CHANGELOG.md and commit? (Y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Nn]$ ]]; then
        echo "Aborted."
        exit 1
    fi
fi

# === Write VERSION + CHANGELOG (before any commit — CI tags the result) ===

echo "$VERSION" > VERSION

CHANGELOG_HEADER="# Changelog\n\nAll notable changes to tGD will be documented in this file.\n\nFormat based on [Keep a Changelog](https://keepachangelog.com/). Versions follow [CalVer](https://calver.org/) (YYYY.MM.DD).\n\n"
if [ -f "CHANGELOG.md" ]; then
    EXISTING_ENTRIES=$(sed -n '6,$p' CHANGELOG.md)
    echo -e "${CHANGELOG_HEADER}${NEW_ENTRY}\n${EXISTING_ENTRIES}" > CHANGELOG.md
else
    echo -e "${CHANGELOG_HEADER}${NEW_ENTRY}" > CHANGELOG.md
fi
echo "📝 Updated VERSION + CHANGELOG.md"

# === Commit + push (current branch) ===

BRANCH=$(git branch --show-current)
if [ -z "$BRANCH" ]; then
    echo "❌ Detached HEAD — check out a branch first."
    exit 1
fi

git add VERSION CHANGELOG.md
git commit -m "chore: release $VERSION"
git push origin "$BRANCH"

echo ""
echo "✅ Release $VERSION prepared and pushed to '$BRANCH'."
if [ "$BRANCH" = "main" ]; then
    echo "   CI (release.yml) will now tag and publish it."
else
    echo "   Open a PR and merge to main — CI (release.yml) tags and publishes on merge."
fi
echo "   Watch: https://github.com/openclawyhwang-hub/tGD/actions/workflows/release.yml"
