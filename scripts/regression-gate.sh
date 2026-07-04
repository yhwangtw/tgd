#!/bin/bash
# regression-gate.sh
#
# Machine-enforced regression check: run EVERY entry in REGRESSION-CATALOG.md
# explicitly and individually. Fails closed if any catalog entry is missing
# its test file, cannot be executed, or fails.
#
# Usage: bash scripts/regression-gate.sh [client-repo] [artifacts-dir]
#   client-repo:   optional. Defaults to current working directory.
#                  The project that *uses* tGD (e.g. my-app/).
#   artifacts-dir: optional. Where tGD artifacts live (CONTEXT.md, feature
#                  dirs, REGRESSION-CATALOG.md). Resolution order:
#                    1. second argument
#                    2. $TGD_DIR environment variable
#                    3. ../<client-repo-name>-tGD (if it exists)
#
#   NOTE: the artifacts dir is NOT the cloned tGD repo. A previous version
#   of this script looked for the catalog inside the tGD repo itself, where
#   /tgd-release never writes it — so the gate always exited 2 ("no catalog")
#   and silently never gated anything.
#
# Per-entry execution: each catalog entry's test file is run on its own
# (jest/vitest/npm/pytest/go). Full-suite green is NOT accepted as proof —
# a file can exist yet be excluded by runner config. The full suite already
# runs in /tgd-verify's capture-test-output step; this gate's job is the
# catalog entries specifically.
#
# Flaky policy: a failing entry is retried ONCE. Pass-on-retry counts as a
# pass but is reported as FLAKY — record flaky entries in TEST-REPORT.md.
#
# Exit codes:
#   0 = all catalog entries passed (flaky-on-retry counts as pass, reported)
#   1 = one or more catalog entries failed, are stale, or cannot be executed
#   2 = usage error — artifacts dir unresolvable, client repo missing,
#       no test runner detected
#   3 = no catalog file yet (legitimate before the first /tgd-release)
#
#   Callers (/tgd-verify) treat 3 as "first release, nothing to gate yet"
#   and MUST treat 2 as a configuration failure to fix, not a pass.

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TGD_REPO_ROOT="$(dirname "$SCRIPT_DIR")"

CLIENT_REPO="${1:-$(pwd)}"
ARTIFACTS_DIR="${2:-${TGD_DIR:-}}"

if [ ! -d "$CLIENT_REPO" ]; then
    echo "❌ Client repo not found: $CLIENT_REPO"
    exit 2
fi
CLIENT_REPO="$(cd "$CLIENT_REPO" && pwd)"

if [ -z "$ARTIFACTS_DIR" ]; then
    GUESS="$(dirname "$CLIENT_REPO")/$(basename "$CLIENT_REPO")-tGD"
    if [ -d "$GUESS" ]; then
        ARTIFACTS_DIR="$GUESS"
    else
        echo "❌ Cannot resolve the tGD artifacts directory."
        echo "   Tried: \$2 (unset), \$TGD_DIR (unset), $GUESS (missing)"
        echo "   Pass it explicitly: bash $0 $CLIENT_REPO /path/to/<project>-tGD"
        exit 2
    fi
fi

if [ ! -d "$ARTIFACTS_DIR" ]; then
    echo "❌ Artifacts directory not found: $ARTIFACTS_DIR"
    exit 2
fi

CATALOG="$ARTIFACTS_DIR/REGRESSION-CATALOG.md"
if [ ! -f "$CATALOG" ]; then
    echo "ℹ️  No REGRESSION-CATALOG.md at $CATALOG"
    echo "   Legitimate before the first /tgd-release seeds it."
    exit 3
fi

cd "$CLIENT_REPO"

# === Detect per-file test runner ===

RUNNER=""
if [ -f "package.json" ]; then
    if [ -x "node_modules/.bin/jest" ]; then RUNNER="jest";
    elif [ -x "node_modules/.bin/vitest" ]; then RUNNER="vitest";
    elif grep -q '"test"' package.json; then RUNNER="npm";
    fi
elif [ -f "pyproject.toml" ] || [ -f "pytest.ini" ] || [ -f "setup.py" ] || [ -f "conftest.py" ]; then
    command -v pytest &> /dev/null && RUNNER="pytest"
elif [ -f "go.mod" ]; then
    RUNNER="go"
elif [ -f "Cargo.toml" ]; then
    RUNNER="cargo"
fi

if [ -z "$RUNNER" ]; then
    echo "❌ No test runner detected in $CLIENT_REPO"
    echo "   Expected: package.json test script (or jest/vitest installed),"
    echo "             pyproject.toml/pytest.ini/conftest.py, go.mod, or Cargo.toml"
    exit 2
fi

run_one() {
    # $1 = repo-relative test file. Returns the runner's exit code.
    local file="$1"
    case "$RUNNER" in
        jest)   npx jest "$file" ;;
        vitest) npx vitest run "$file" ;;
        npm)    npm test -- "$file" ;;
        pytest) pytest -q "$file" ;;
        go)     go test "./$(dirname "$file")/" ;;
        cargo)
            # Cargo has no reliable per-file invocation for unit tests.
            # Best effort: integration tests under tests/<name>.rs.
            local stem
            stem="$(basename "$file" .rs)"
            cargo test --test "$stem" ;;
    esac
}

# === Parse catalog entries ===

ENTRY_TSV=$(python3 - "$CATALOG" <<'PYEOF'
import re, sys, pathlib
text = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8")
# Entries: "### [feature] Title" followed by "- **Test:** `path`" (or "Test: path")
blocks = re.split(r"(?m)^### ", text)[1:]
for b in blocks:
    title = b.splitlines()[0].strip()
    # Tolerate both markdown stylings: "**Test:** `x`" and "**Test**: `x`"
    m = re.search(r"Test\*{0,2}:\*{0,2}\s*`?([^`\n]+)`?", b)
    test = m.group(1).strip() if m else ""
    print(f"{title}\t{test}")
PYEOF
)

if [ -z "$ENTRY_TSV" ]; then
    echo "⚠️  Catalog exists but has 0 entries. Nothing to verify."
    echo "   Unusual — every release should add at least one [R] entry."
    exit 0
fi

TOTAL=0; PASSED=0; FAILED=0; STALE=0; FLAKY=0
FAILED_LIST=""; STALE_LIST=""; FLAKY_LIST=""

echo "🔍 Regression gate (per-entry execution)"
echo "   Client repo:   $CLIENT_REPO"
echo "   Artifacts dir: $ARTIFACTS_DIR"
echo "   Runner:        $RUNNER"
echo ""

while IFS=$'\t' read -r title testref; do
    TOTAL=$((TOTAL + 1))
    if [ -z "$testref" ]; then
        echo "❌ [$title] — no 'Test:' reference in catalog entry"
        STALE=$((STALE + 1)); STALE_LIST="$STALE_LIST\n   - $title (no Test: reference)"
        continue
    fi
    # testref may be "tests/foo.test.ts" or "pytest tests/test_foo.py" — take last token
    TESTFILE=$(echo "$testref" | awk '{print $NF}')
    if [ ! -f "$CLIENT_REPO/$TESTFILE" ]; then
        echo "❌ [$title] — test file missing: $TESTFILE"
        STALE=$((STALE + 1)); STALE_LIST="$STALE_LIST\n   - $title ($TESTFILE)"
        continue
    fi

    set +e
    run_one "$TESTFILE" > /dev/null 2>&1
    RC=$?
    set -e
    if [ $RC -ne 0 ]; then
        # Flaky policy: retry once. Pass-on-retry = pass, reported as FLAKY.
        set +e
        run_one "$TESTFILE" > /dev/null 2>&1
        RC2=$?
        set -e
        if [ $RC2 -eq 0 ]; then
            echo "⚠️  [$title] — FLAKY (failed once, passed on retry): $TESTFILE"
            FLAKY=$((FLAKY + 1)); FLAKY_LIST="$FLAKY_LIST\n   - $title ($TESTFILE)"
            PASSED=$((PASSED + 1))
        else
            echo "❌ [$title] — FAILED (twice): $TESTFILE"
            FAILED=$((FAILED + 1)); FAILED_LIST="$FAILED_LIST\n   - $title ($TESTFILE)"
        fi
    else
        echo "✅ [$title] — $TESTFILE"
        PASSED=$((PASSED + 1))
    fi
done <<< "$ENTRY_TSV"

echo ""
echo "📊 Catalog entries: $TOTAL total, $PASSED passed, $FAILED failed, $STALE stale, $FLAKY flaky"

if [ $FLAKY -ne 0 ]; then
    echo ""
    echo "⚠️  Flaky entries (record these in TEST-REPORT.md and fix them):"
    echo -e "$FLAKY_LIST"
fi

if [ $FAILED -ne 0 ] || [ $STALE -ne 0 ]; then
    echo ""
    echo "❌ REGRESSION GATE FAILED"
    [ $FAILED -ne 0 ] && echo -e "   Failing entries (a previously shipped critical path broke):$FAILED_LIST"
    [ $STALE -ne 0 ] && echo -e "   Stale entries (fix the catalog or restore the tests):$STALE_LIST"
    exit 1
fi

echo ""
echo "✅ REGRESSION GATE PASSED: $TOTAL entries executed individually, all green"
exit 0
