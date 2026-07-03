#!/bin/bash
# Create a GitHub release for tGD with auto-categorized CHANGELOG
# Usage: bash scripts/release.sh [version] [--yes]
# If version not provided, uses today's date (CalVer)
# --yes: skip interactive confirmation prompts (non-interactive mode)

set -e

# Parse flags
AUTO_YES=false
for arg in "$@"; do
    case "$arg" in
        --yes|-y) AUTO_YES=true ;;
    esac
done

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$REPO_ROOT"

# Check for help flag
if [ "$1" == "--help" ] || [ "$1" == "-h" ]; then
    echo "Usage: $0 [version] [--yes]"
    echo ""
    echo "Create a GitHub release for tGD with categorized changelog."
    echo ""
    echo "If version is not provided, uses today's date (CalVer)."
    echo "Add --yes (or -y) to skip confirmation prompts (non-interactive mode)."
    echo "Syncs VERSION, setup.sh, and CHANGELOG.md."
    echo ""
    echo "Commit message convention (Conventional Commits):"
    echo "  feat:     → ✨ Features"
    echo "  fix:      → 🐛 Bug Fixes"
    echo "  docs:     → 📝 Documentation"
    echo "  refactor: → ♻️  Refactoring"
    echo "  test:     → ✅ Tests"
    echo "  chore:    → 🔧 Chores"
    echo "  (other)   → 📦 Other Changes"
    echo ""
    echo "Examples:"
    echo "  $0          # Release as vYYYY.MM.DD (today)"
    echo "  $0 v2026.06.09   # Release for specific version"
    exit 0
fi

# Check if gh CLI is installed
if ! command -v gh &> /dev/null; then
    echo "❌ GitHub CLI (gh) is required but not installed."
    echo "   Install: https://cli.github.com/"
    exit 1
fi

# Check if authenticated
if ! gh auth status &> /dev/null; then
    echo "❌ Not authenticated with GitHub CLI."
    echo "   Run: gh auth login"
    exit 1
fi

# Get version — default to today's date (CalVer)
# Skip the --yes / -y flag so it doesn't get treated as the version string.
VERSION=""
for arg in "$@"; do
    if [ "$arg" = "--yes" ] || [ "$arg" = "-y" ]; then
        continue
    fi
    if [ -z "$VERSION" ]; then
        VERSION="$arg"
    fi
done
if [ -z "$VERSION" ]; then
    VERSION="v$(date +%Y.%m.%d)"
fi

# Ensure version starts with 'v'
if [[ ! "$VERSION" =~ ^v ]]; then
    VERSION="v$VERSION"
fi

# Derive date format for setup.sh (e.g. v2026.06.09 → 2026-06-09)
SETUP_DATE=$(echo "$VERSION" | sed 's/^v//' | tr '.' '-')

# Sync VERSION
echo "$VERSION" > VERSION
echo "📝 Updated VERSION → $VERSION"

echo "🚀 Creating release for $VERSION"
echo ""

# Check if tag already exists
if git rev-parse "$VERSION" &> /dev/null; then
    echo "⚠️  Tag $VERSION already exists."
    if [ "$AUTO_YES" = true ]; then
        echo "   Auto-deleting and recreating (--yes)"
        git tag -d "$VERSION"
        git push origin ":refs/tags/$VERSION" 2>/dev/null || true
    else
        read -p "   Delete and recreate? (y/N) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            git tag -d "$VERSION"
            git push origin ":refs/tags/$VERSION" 2>/dev/null || true
        else
            echo "   Aborted."
            exit 1
        fi
    fi
fi

# Generate categorized changelog from git log
echo "📝 Generating categorized changelog..."
PREV_TAG=$(git describe --tags --abbrev=0 2>/dev/null || echo "")

if [ -n "$PREV_TAG" ]; then
    COMMITS=$(git log --pretty=format:"%s|||%h" "$PREV_TAG"..HEAD)
    RANGE="$PREV_TAG..HEAD"
else
    COMMITS=$(git log --pretty=format:"%s|||%h" -30)
    RANGE="last 30 commits"
fi

# Categorize commits
FEATS=""
FIXES=""
DOCS=""
REFACTORS=""
TESTS=""
CHORES=""
OTHERS=""

while IFS= read -r line; do
    [ -z "$line" ] && continue
    MSG="${line%%|||*}"
    HASH="${line##*|||}"

    # Strip conventional commit prefix for display
    DISPLAY_MSG="$MSG"

    case "$MSG" in
        feat*:*|feat*)
            FEATS="${FEATS}- ${DISPLAY_MSG#*: } (\`$HASH\`)\n"
            ;;
        fix*:*|fix*)
            FIXES="${FIXES}- ${DISPLAY_MSG#*: } (\`$HASH\`)\n"
            ;;
        docs*:*|docs*)
            DOCS="${DOCS}- ${DISPLAY_MSG#*: } (\`$HASH\`)\n"
            ;;
        refactor*:*|refactor*)
            REFACTORS="${REFACTORS}- ${DISPLAY_MSG#*: } (\`$HASH\`)\n"
            ;;
        test*:*|test*)
            TESTS="${TESTS}- ${DISPLAY_MSG#*: } (\`$HASH\`)\n"
            ;;
        chore*:*|chore*)
            CHORES="${CHORES}- ${DISPLAY_MSG#*: } (\`$HASH\`)\n"
            ;;
        ci*:*|ci*)
            CHORES="${CHORES}- ${DISPLAY_MSG#*: } (\`$HASH\`)\n"
            ;;
        *)
            OTHERS="${OTHERS}- ${DISPLAY_MSG} (\`$HASH\`)\n"
            ;;
    esac
done <<< "$COMMITS"

# Build release notes
build_section() {
    local title="$1"
    local content="$2"
    if [ -n "$content" ]; then
        echo "### $title"
        echo -e "$content"
    fi
}

RELEASE_NOTES="## tGD $VERSION\n\n"
[ -n "$FEATS" ]     && RELEASE_NOTES+=$(build_section "✨ Features" "$FEATS")"\n"
[ -n "$FIXES" ]     && RELEASE_NOTES+=$(build_section "🐛 Bug Fixes" "$FIXES")"\n"
[ -n "$DOCS" ]      && RELEASE_NOTES+=$(build_section "📝 Documentation" "$DOCS")"\n"
[ -n "$REFACTORS" ] && RELEASE_NOTES+=$(build_section "♻️ Refactoring" "$REFACTORS")"\n"
[ -n "$TESTS" ]     && RELEASE_NOTES+=$(build_section "✅ Tests" "$TESTS")"\n"
[ -n "$CHORES" ]    && RELEASE_NOTES+=$(build_section "🔧 Chores" "$CHORES")"\n"
[ -n "$OTHERS" ]    && RELEASE_NOTES+=$(build_section "📦 Other Changes" "$OTHERS")"\n"

if [ -n "$PREV_TAG" ]; then
    COMPARE_URL="https://github.com/openclawyhwang-hub/tGD/compare/${PREV_TAG}...${VERSION}"
else
    COMPARE_URL="https://github.com/openclawyhwang-hub/tGD/commits/${VERSION}"
fi

RELEASE_NOTES+="---\n**Full Changelog**: $COMPARE_URL"

echo ""
echo "📋 Release notes:"
echo "---"
echo -e "$RELEASE_NOTES"
echo "---"
echo ""

# Update CHANGELOG.md
CHANGELOG_HEADER="# Changelog\n\nAll notable changes to tGD will be documented in this file.\n\nFormat based on [Keep a Changelog](https://keepachangelog.com/). Versions follow [CalVer](https://calver.org/) (YYYY.MM.DD).\n\n"
NEW_ENTRY="## $VERSION\n\n"
[ -n "$FEATS" ]     && NEW_ENTRY+=$(build_section "✨ Features" "$FEATS")"\n"
[ -n "$FIXES" ]     && NEW_ENTRY+=$(build_section "🐛 Bug Fixes" "$FIXES")"\n"
[ -n "$DOCS" ]      && NEW_ENTRY+=$(build_section "📝 Documentation" "$DOCS")"\n"
[ -n "$REFACTORS" ] && NEW_ENTRY+=$(build_section "♻️ Refactoring" "$REFACTORS")"\n"
[ -n "$TESTS" ]     && NEW_ENTRY+=$(build_section "✅ Tests" "$TESTS")"\n"
[ -n "$CHORES" ]    && NEW_ENTRY+=$(build_section "🔧 Chores" "$CHORES")"\n"
[ -n "$OTHERS" ]    && NEW_ENTRY+=$(build_section "📦 Other Changes" "$OTHERS")"\n"
NEW_ENTRY+="\n"

if [ -f "CHANGELOG.md" ]; then
    # Extract header (first 5 lines) + insert new entry after header
    EXISTING_ENTRIES=$(sed -n '6,$p' CHANGELOG.md)
    echo -e "${CHANGELOG_HEADER}${NEW_ENTRY}${EXISTING_ENTRIES}" > CHANGELOG.md
else
    echo -e "${CHANGELOG_HEADER}${NEW_ENTRY}" > CHANGELOG.md
fi
echo "📝 Updated CHANGELOG.md"

# Confirm
if [ "$AUTO_YES" = true ]; then
    echo "✅ Auto-confirming (--yes)"
else
    read -p "Create tag and release? (Y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Nn]$ ]]; then
        echo "Aborted."
        exit 1
    fi
fi

# Create and push tag
echo "🏷️  Creating tag $VERSION..."
git tag -a "$VERSION" -m "Release $VERSION" || git tag "$VERSION"
git push origin "$VERSION"

# Commit CHANGELOG.md update
git add CHANGELOG.md VERSION
git commit -m "docs: update CHANGELOG.md for $VERSION" || echo "⚠️  No CHANGELOG changes to commit"
git push origin main

# Create GitHub release
echo "📦 Creating GitHub release..."
gh release create "$VERSION" \
    --title "tGD $VERSION" \
    --notes "$(echo -e "$RELEASE_NOTES")" \
    --latest

echo ""
echo "✅ Release $VERSION created successfully!"
echo "   View: https://github.com/openclawyhwang-hub/tGD/releases/tag/$VERSION"
