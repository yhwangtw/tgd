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
#   - npm:   nyc / jest --coverage / vitest --coverage (looks for nyc/jest/vitest
#            binary); falls back to Node >= 20 native test-runner coverage
#            (node --experimental-test-coverage --test) when none is installed
#   - py:    coverage.py (pip install coverage)
#   - go:    go test -cover
#   - cargo: cargo tarpaulin (if installed; otherwise warns and skips)
#
# Parsing:
#   - jest/vitest: "All files | 85.7 | 72.3 | 90.5 | ..."  (Lines/Branch/Funcs)
#   - nyc:         "=====" summary table
#   - node:test:   "# all files | 100.00 | 100.00 | 100.00 |" (line/branch/funcs)
#   - coverage.py: "TOTAL    1234    567    54%"
#   - go:          "coverage: 78.5% of statements"

set -e

# Floors — THIS SCRIPT is the source of truth (the table in
# skills/tgd-develop-tdd/SKILL.md references these defaults).
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
    elif node -e 'process.exit(parseInt(process.versions.node) >= 20 ? 0 : 1)' 2>/dev/null; then
        # No coverage package installed, but Node >= 20 ships a native
        # test-runner coverage reporter — zero extra dependencies. Projects
        # using node:test (`"test": "node --test"`) land here.
        COV_CMD="node --experimental-test-coverage --test"
    else
        echo "❌ npm project but no coverage tool found"
        echo "   Install one: npm i -D @vitest/coverage-v8 || npm i -D nyc (or use Node >= 20 native coverage)"
        exit 2
    fi
elif [ -f "pyproject.toml" ] || [ -f "pytest.ini" ] || [ -f "setup.py" ]; then
    RUNNER="pytest"
    if [ -n "$TEST_CMD" ]; then
        # Explicit command — trust it verbatim (the caller knows their tooling)
        COV_CMD="$TEST_CMD"
    elif command -v pytest &> /dev/null && (python3 -c "import pytest_cov" 2>/dev/null || python3 -c "import coverage" 2>/dev/null); then
        COV_CMD="pytest --cov --cov-report=term -q"
    else
        echo "❌ Python project but no coverage tool found"
        echo "   Install one: pip install coverage pytest-cov"
        exit 2
    fi
elif [ -f "go.mod" ]; then
    RUNNER="go"
    COV_CMD="${TEST_CMD:-go test -cover ./...}"
elif [ -f "Cargo.toml" ]; then
    RUNNER="cargo"
    if [ -n "$TEST_CMD" ]; then
        COV_CMD="$TEST_CMD"
    elif command -v cargo-tarpaulin &> /dev/null; then
        COV_CMD="cargo tarpaulin --skip-clean --out Stdout"
    else
        echo "❌ Cargo project but cargo-tarpaulin not installed"
        echo "   Install: cargo install cargo-tarpaulin"
        # exit 2 like the npm/python branches — a missing tool is a
        # configuration problem to fix, never a silent pass
        exit 2
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

# "N/A" means the coverage tool does not report that metric. An N/A metric's
# floor is NOT enforced (announced instead) — scoring missing data as 0 would
# make the gate fail on every runner regardless of real coverage, which is
# exactly what the previous version of this parser did.
LINES="N/A"
BRANCHES="N/A"
FUNCS="N/A"

num_or_na() {
    # Echo $1 if it is a number, else "N/A"
    case "$1" in
        ''|*[!0-9.]*) echo "N/A" ;;
        *) echo "$1" ;;
    esac
}

if [ "$RUNNER" = "npm" ]; then
    # istanbul-style table (jest/vitest/nyc), column order:
    # "All files | % Stmts | % Branch | % Funcs | % Lines | Uncovered ..."
    SUMMARY=$(grep -E "All files" "$RAW" | tail -1 || echo "")
    if [ -n "$SUMMARY" ]; then
        STMTS=$(echo "$SUMMARY"   | awk -F'|' '{gsub(/ /,"",$2); print $2}')
        BRANCHES=$(num_or_na "$(echo "$SUMMARY" | awk -F'|' '{gsub(/ /,"",$3); print $3}')")
        FUNCS=$(num_or_na "$(echo "$SUMMARY"    | awk -F'|' '{gsub(/ /,"",$4); print $4}')")
        LINES=$(num_or_na "$(echo "$SUMMARY"    | awk -F'|' '{gsub(/ /,"",$5); print $5}')")
        # nyc text-summary variants can have fewer columns — fall back to Stmts
        [ "$LINES" = "N/A" ] && LINES=$(num_or_na "$STMTS")
    else
        # node:test native coverage — TAP comment table, column order:
        # "# all files | <line %> | <branch %> | <funcs %> |"
        SUMMARY=$(grep -E "^# all files" "$RAW" | tail -1 || echo "")
        if [ -n "$SUMMARY" ]; then
            LINES=$(num_or_na "$(echo "$SUMMARY"    | awk -F'|' '{gsub(/ /,"",$2); print $2}')")
            BRANCHES=$(num_or_na "$(echo "$SUMMARY" | awk -F'|' '{gsub(/ /,"",$3); print $3}')")
            FUNCS=$(num_or_na "$(echo "$SUMMARY"    | awk -F'|' '{gsub(/ /,"",$4); print $4}')")
        fi
    fi
elif [ "$RUNNER" = "pytest" ]; then
    # coverage.py: "TOTAL    1234    567    54%" — last field is line coverage.
    # Its terminal report has no separate branch/function percentages, so
    # those stay N/A (honest) rather than being scored as 0.
    LINE_LINE=$(grep -E "^TOTAL" "$RAW" | tail -1 || echo "")
    if [ -n "$LINE_LINE" ]; then
        LINES=$(num_or_na "$(echo "$LINE_LINE" | awk '{print $NF}' | tr -d '%')")
    fi
elif [ "$RUNNER" = "go" ]; then
    # "coverage: 78.5% of statements" — statement coverage only
    GOLINE=$(grep -oE "coverage: [0-9.]+% of statements" "$RAW" | tail -1 || echo "")
    if [ -n "$GOLINE" ]; then
        LINES=$(num_or_na "$(echo "$GOLINE" | grep -oE "[0-9.]+" | head -1)")
    fi
elif [ "$RUNNER" = "cargo" ]; then
    # cargo tarpaulin: "XX.XX% coverage" — line coverage only
    LINES=$(num_or_na "$(grep -oE "[0-9.]+% coverage" "$RAW" | tail -1 | grep -oE "[0-9.]+" | head -1)")
fi

if [ "$LINES" = "N/A" ]; then
    echo "❌ Could not parse a line-coverage number from the tool output."
    echo "   Last 15 lines of output:"
    tail -15 "$RAW" | sed 's/^/   | /'
    echo "   Fix the parser or pass an explicit coverage command. Do NOT treat this as a pass."
    rm -f "$RAW"
    exit 2
fi

# === Evaluate floors ===

echo "📊 Coverage:"
printf "   Lines:    %s%%  (floor %s%%)\n" "${LINES}" "$LINE_FLOOR"
printf "   Branches: %s%%  (floor %s%%)\n" "${BRANCHES}" "$BRANCH_FLOOR"
printf "   Functions: %s%%  (floor %s%%)\n" "${FUNCS}" "$FUNC_FLOOR"
echo ""

PASS=1
FAIL_MSG=""

# Use awk for float comparison (POSIX sh doesn't do floats).
# N/A metrics are announced and skipped — the tool doesn't report them.
check_floor() {
    local name=$1 val=$2 floor=$3
    if [ "$val" = "N/A" ]; then
        echo "   ℹ️  $name: no data from this coverage tool — floor not enforced"
        return 0
    fi
    if ! awk -v v="$val" -v f="$floor" 'BEGIN { if (v+0 < f+0) exit 1; exit 0 }'; then
        PASS=0
        FAIL_MSG="${FAIL_MSG}   - $name: ${val}% < ${floor}%\n"
    fi
}

check_floor "lines"     "$LINES"    "$LINE_FLOOR"
check_floor "branches"  "$BRANCHES" "$BRANCH_FLOOR"
check_floor "functions" "$FUNCS"    "$FUNC_FLOOR"

rm -f "$RAW"

if [ $PASS -eq 0 ]; then
    echo "❌ Coverage gate FAILED:"
    # '%b' expands the \n escapes; passing FAIL_MSG as the format string would
    # let its '%' characters (e.g. "55.0% < 60%") be eaten as format specifiers
    printf '%b' "$FAIL_MSG"
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
