#!/bin/bash
# coverage-check.sh
#
# Enforce minimum coverage floors: lines 80%, branches 60%, functions 90%.
# Critical paths (auth, payment, data loss, security) require 100% — those
# are NOT auto-checked here (need file-level analysis); agent must declare.
#
# Usage: bash scripts/coverage-check.sh [test-cmd]
#   test-cmd: optional override. Default: auto-detect npm/pytest/go/cargo
#             and append the appropriate coverage flag.
#
# Exit codes:
#   0 = all floors met
#   1 = at least one floor missed (prints which)
#   2 = no coverage tool detected
#
# Tooling detection:
#   - npm:   nyc / jest --coverage / vitest --coverage (looks for nyc/jest/vitest binary)
#   - py:    coverage.py (pip install coverage)
#   - go:    go test -cover
#   - cargo: cargo tarpaulin (if installed; otherwise warns and skips)
#
# Parsing:
#   - jest/vitest: "All files | 85.7 | 72.3 | 90.5 | ..."  (Lines/Branch/Funcs)
#   - nyc:         "=====" summary table
#   - coverage.py: "TOTAL    1234    567    54%"
#   - go:          "coverage: 78.5% of statements"

set -e

# Floors — THIS SCRIPT is the source of truth (the table in
# skills/tgd-test-driven-development/SKILL.md references these defaults).
# Override per project via env vars, e.g. a legacy codebase ramping up:
#   COVERAGE_LINE_FLOOR=60 bash scripts/coverage-check.sh
LINE_FLOOR="${COVERAGE_LINE_FLOOR:-80}"
BRANCH_FLOOR="${COVERAGE_BRANCH_FLOOR:-60}"
FUNC_FLOOR="${COVERAGE_FUNC_FLOOR:-90}"

TEST_CMD="${1:-}"

# === Detect test runner + coverage tool ===

RUNNER=""
COV_CMD=""

if [ -f "package.json" ]; then
    RUNNER="npm"
    if [ -n "$TEST_CMD" ]; then
        COV_CMD="$TEST_CMD"
    elif [ -x "node_modules/.bin/jest" ]; then
        COV_CMD="npx jest --coverage --silent"
    elif [ -x "node_modules/.bin/vitest" ]; then
        COV_CMD="npx vitest run --coverage"
    elif [ -x "node_modules/.bin/nyc" ]; then
        # nyc wraps whatever test script
        BASE=$(node -e "try { console.log(require('./package.json').scripts.test || 'echo') } catch(e) { console.log('echo') }" 2>/dev/null)
        COV_CMD="npx nyc --reporter=text-summary $BASE"
    else
        echo "❌ npm project but no coverage tool found"
        echo "   Install one: npm i -D @vitest/coverage-v8 || npm i -D nyc"
        exit 2
    fi
elif [ -f "pyproject.toml" ] || [ -f "pytest.ini" ] || [ -f "setup.py" ]; then
    if command -v pytest &> /dev/null && (python3 -c "import pytest_cov" 2>/dev/null || python3 -c "import coverage" 2>/dev/null); then
        RUNNER="pytest"
        if [ -n "$TEST_CMD" ]; then
            COV_CMD="$TEST_CMD --cov --cov-report=term"
        else
            COV_CMD="pytest --cov --cov-report=term -q"
        fi
    else
        echo "❌ Python project but no coverage tool found"
        echo "   Install one: pip install coverage pytest-cov"
        exit 2
    fi
elif [ -f "go.mod" ]; then
    RUNNER="go"
    COV_CMD="go test -cover ./..."
elif [ -f "Cargo.toml" ]; then
    if command -v cargo-tarpaulin &> /dev/null; then
        RUNNER="cargo"
        COV_CMD="cargo tarpaulin --skip-clean --out Stdout"
    else
        echo "⚠️  Cargo project but cargo-tarpaulin not installed"
        echo "   Install: cargo install cargo-tarpaulin"
        echo "   Skipping coverage check (manual review required)"
        exit 0
    fi
else
    echo "❌ No package manager or test runner detected"
    exit 2
fi

echo "🛡️  Coverage gate"
echo "   Runner:   $RUNNER"
echo "   Command:  $COV_CMD"
echo "   Floors:   lines ≥ $LINE_FLOOR%, branches ≥ $BRANCH_FLOOR%, functions ≥ $FUNC_FLOOR%"
echo ""

# === Run coverage ===

RAW=$(mktemp)
TEST_EXIT=0
$COV_CMD > "$RAW" 2>&1 || TEST_EXIT=$?

if [ $TEST_EXIT -ne 0 ]; then
    echo "❌ Test/coverage run failed (exit $TEST_EXIT)"
    tail -20 "$RAW" | sed 's/^/   | /'
    rm -f "$RAW"
    exit 1
fi

# === Parse results ===

# Default to 0; only assigned if regex matches
LINES=0
BRANCHES=0
FUNCS=0

if [ "$RUNNER" = "npm" ]; then
    # jest/vitest: "All files | 85.7  | 72.3  | 90.5  | ..."
    # nyc:        "All files | 85.7  | 72.3  | 90.5  | ..."
    SUMMARY=$(grep -E "All files" "$RAW" | tail -1 || echo "")
    if [ -n "$SUMMARY" ]; then
        # Try to read 3 numbers: line, branch, func
        # Columns vary: nyc may have only 2-3
        read -r _ L B F <<< $(echo "$SUMMARY" | awk -F'|' '{print $2, $3, $4, $5}' | tr -d ' ' | tr '|' ' ')
        LINES=${L:-0}
        BRANCHES=${B:-0}
        FUNCS=${F:-0}
    fi
elif [ "$RUNNER" = "pytest" ]; then
    # coverage.py: "TOTAL    1234    567    54%"  (statements, missing, percent)
    # OR with branch: "TOTAL    1234    567    234    65%   70%"
    LINE_LINE=$(grep -E "^TOTAL" "$RAW" | tail -1 || echo "")
    if [ -n "$LINE_LINE" ]; then
        LINES=$(echo "$LINE_LINE" | awk '{print $NF}' | tr -d '%')
    fi
    # Branch coverage (if pytest-cov --cov-branch)
    BRANCH_LINE=$(grep -E "^TOTAL.*branch" "$RAW" | tail -1 || echo "")
    if [ -n "$BRANCH_LINE" ]; then
        BRANCHES=$(echo "$BRANCH_LINE" | grep -oE "[0-9]+%" | tail -1 | tr -d '%')
    fi
elif [ "$RUNNER" = "go" ]; then
    # "coverage: 78.5% of statements"
    GOLINE=$(grep -oE "coverage: [0-9.]+% of statements" "$RAW" | tail -1 || echo "")
    if [ -n "$GOLINE" ]; then
        LINES=$(echo "$GOLINE" | grep -oE "[0-9.]+" | head -1)
    fi
elif [ "$RUNNER" = "cargo" ]; then
    # cargo tarpaulin output varies; assume 1 line near end with "XX.XX% coverage"
    LINES=$(grep -oE "[0-9.]+% coverage" "$RAW" | tail -1 | grep -oE "[0-9.]+" | head -1)
fi

# === Evaluate floors ===

echo "📊 Coverage:"
printf "   Lines:    %s%%  (floor %s%%)\n" "${LINES}" "$LINE_FLOOR"
printf "   Branches: %s%%  (floor %s%%)\n" "${BRANCHES}" "$BRANCH_FLOOR"
printf "   Functions: %s%%  (floor %s%%)\n" "${FUNCS}" "$FUNC_FLOOR"
echo ""

PASS=1
FAIL_MSG=""

# Use awk for float comparison (POSIX sh doesn't do floats)
check() {
    local val=$1
    local floor=$2
    local name=$3
    awk -v v="$val" -v f="$floor" 'BEGIN { if (v+0 < f+0) exit 1; exit 0 }'
}

if [ "${LINES%.*}" -lt 0 ] 2>/dev/null || ! check "$LINES" "$LINE_FLOOR" "lines"; then
    PASS=0
    FAIL_MSG="${FAIL_MSG}   - lines: ${LINES}% < ${LINE_FLOOR}%\n"
fi
if [ "${BRANCHES%.*}" -lt 0 ] 2>/dev/null || ! check "$BRANCHES" "$BRANCH_FLOOR" "branches"; then
    PASS=0
    FAIL_MSG="${FAIL_MSG}   - branches: ${BRANCHES}% < ${BRANCH_FLOOR}%\n"
fi
if [ "${FUNCS%.*}" -lt 0 ] 2>/dev/null || ! check "$FUNCS" "$FUNC_FLOOR" "funcs"; then
    PASS=0
    FAIL_MSG="${FAIL_MSG}   - funcs: ${FUNCS}% < ${FUNC_FLOOR}%\n"
fi

rm -f "$RAW"

if [ $PASS -eq 0 ]; then
    echo "❌ Coverage gate FAILED:"
    printf "$FAIL_MSG"
    echo ""
    echo "   Add tests or document an exception in TEST-REPORT.md '## Coverage Exceptions'."
    exit 1
fi

echo "✅ Coverage gate PASSED"
echo ""
echo "   Note: critical paths (auth, payment, data loss, security) require"
echo "   100% line + branch coverage. This script does NOT auto-check those —"
echo "   the agent must declare them and verify manually."
exit 0
