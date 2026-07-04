#!/bin/bash
# capture-test-output.sh
#
# Run the project's test suite and write the raw output into TEST-REPORT.md
# as machine-verifiable evidence. Parses pass/fail counts from the output
# so a follow-up "check-test-report.sh" can verify the agent didn't lie
# about results in the summary.
#
# Usage: bash scripts/capture-test-output.sh <test-report-path> [test-cmd]
#   test-report-path: absolute path to the TEST-REPORT.md to update
#   test-cmd: optional override. Default: auto-detect (npm/pytest/go/cargo)
#
# What it writes into TEST-REPORT.md:
#   - A new "## Raw Test Output" section (overwriting any prior one)
#   - Parsed counts: TOTAL_TESTS, PASSED, FAILED, SKIPPED
#   - A "<!-- test-output-meta: {...} -->" HTML comment with the same
#     numbers, so a check script can grep them without re-parsing.
#
# Exit codes:
#   0 = test suite passed AND output was captured
#   1 = test suite failed (output still captured; caller decides what to do)
#   2 = usage error (no report path, no test runner detected, etc.)

set -e

REPORT_PATH="${1:?Usage: bash $0 <test-report-path> [test-cmd]}"
TEST_CMD="${2:-}"

if [ ! -f "$REPORT_PATH" ]; then
    # Create the skeleton so /tgd-verify's "creates the report if needed"
    # is literally true. The agent fills the tables from the meta-comment
    # this script appends — numbers come from the machine, not memory.
    mkdir -p "$(dirname "$REPORT_PATH")"
    cat > "$REPORT_PATH" <<'SKELETON'
# TEST-REPORT: [Feature Name]

> **Date**: YYYY-MM-DD

## 1. Test Summary
| Suite | Passed | Failed | Skipped |
|-------|--------|--------|---------|
| Unit | | | |
| Integration | | | |
| E2E | | | |

Exit code: `0` (PASS) / `1` (FAIL)

## 2. Coverage
| Metric | Value |
|--------|-------|
| Lines | |
| Branches | |
| Functions | |

## 3. Failures & Root Causes
| Test | Error | Root Cause | Fix Applied |
|------|-------|------------|-------------|

## 4. Flaky Tests
| Test | Behavior | Follow-up |
|------|----------|-----------|

## 5. Regression Status
- [ ] regression-gate.sh exits 0 (or 3 = no catalog yet)
- [ ] No cross-feature regressions introduced

## Sign-off
- [ ] **QA**: (pending)
SKELETON
    echo "📝 Created TEST-REPORT skeleton: $REPORT_PATH"
fi

# Resolve test runner
if [ -z "$TEST_CMD" ]; then
    if [ -f "package.json" ] && grep -q '"test"' package.json; then
        TEST_CMD=$(node -e "try { console.log(require('./package.json').scripts.test || '') } catch(e) {}" 2>/dev/null || echo "")
    elif [ -f "pyproject.toml" ] || [ -f "pytest.ini" ] || [ -f "setup.py" ]; then
        if command -v pytest &> /dev/null; then
            TEST_CMD="pytest -v --tb=short"
        fi
    elif [ -f "go.mod" ]; then
        TEST_CMD="go test -v ./..."
    elif [ -f "Cargo.toml" ]; then
        TEST_CMD="cargo test"
    fi
fi

if [ -z "$TEST_CMD" ]; then
    echo "❌ No test runner detected and no command provided"
    echo "   Pass test command explicitly: bash $0 <report> 'npm test'"
    exit 2
fi

echo "🧪 Capturing test output"
echo "   Report:  $REPORT_PATH"
echo "   Command: $TEST_CMD"
echo ""

# Run the suite, capture output
RAW=$(mktemp)
TEST_EXIT=0
$TEST_CMD > "$RAW" 2>&1 || TEST_EXIT=$?

# Parse counts — these patterns are tuned for common runners but not exhaustive.
# The check script is conservative: missing counts default to "unknown", not "passed".
PASSED=$(grep -cE "passed|✓|ok |PASS\b" "$RAW" 2>/dev/null || true)
PASSED=${PASSED:-0}
FAILED=$(grep -cE "failed|✗|FAIL\b|ERROR\b" "$RAW" 2>/dev/null || true)
FAILED=${FAILED:-0}
SKIPPED=$(grep -cE "skipped|⊘|SKIP\b" "$RAW" 2>/dev/null || true)
SKIPPED=${SKIPPED:-0}

# Some runners (jest, vitest) report a "Tests: X passed, Y failed" summary
JEST_SUMMARY=$(grep -E "^Tests:.*(passed|failed)" "$RAW" | tail -1)
PYTEST_SUMMARY=$(grep -E "=+ .* (passed|failed) in" "$RAW" | tail -1)
GO_SUMMARY=$(grep -E "^(ok|FAIL|---)" "$RAW" | tail -1)

if [ -n "$JEST_SUMMARY" ]; then
    PASSED=$(echo "$JEST_SUMMARY" | grep -oE "[0-9]+ passed" | grep -oE "[0-9]+" | head -1)
    PASSED=${PASSED:-0}
    FAILED=$(echo "$JEST_SUMMARY" | grep -oE "[0-9]+ failed" | grep -oE "[0-9]+" | head -1)
    FAILED=${FAILED:-0}
fi
if [ -n "$PYTEST_SUMMARY" ]; then
    PASSED=$(echo "$PYTEST_SUMMARY" | grep -oE "[0-9]+ passed" | grep -oE "[0-9]+" | head -1)
    PASSED=${PASSED:-0}
    FAILED=$(echo "$PYTEST_SUMMARY" | grep -oE "[0-9]+ failed" | grep -oE "[0-9]+" | head -1)
    FAILED=${FAILED:-0}
fi

# Strip any prior raw-output block
python3 - "$REPORT_PATH" <<'PYEOF'
import sys, re, pathlib
p = pathlib.Path(sys.argv[1])
text = p.read_text()
# Remove prior "## Raw Test Output" block (if any)
text = re.sub(r"\n## Raw Test Output.*?(?=\n## |\Z)", "\n", text, flags=re.DOTALL)
# Remove prior meta comment
text = re.sub(r"\n<!-- test-output-meta:.*?-->\n", "\n", text)
p.write_text(text)
PYEOF

# Append the new raw output + meta comment
TMP=$(mktemp)
{
    cat "$REPORT_PATH"
    echo ""
    echo "## Raw Test Output"
    echo ""
    echo "**Captured**: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
    echo "**Command**: \`$TEST_CMD\`"
    echo "**Exit code**: $TEST_EXIT"
    echo ""
    echo "<!-- test-output-meta: {\"exit\": $TEST_EXIT, \"passed\": $PASSED, \"failed\": $FAILED, \"skipped\": $SKIPPED} -->"
    echo ""
    echo '```'
    cat "$RAW"
    echo '```'
    echo ""
} > "$TMP"
mv "$TMP" "$REPORT_PATH"

# Clean up
rm -f "$RAW"

echo ""
echo "📊 Captured: exit=$TEST_EXIT, passed=~$PASSED, failed=~$FAILED, skipped=~$SKIPPED"
echo "   Written to: $REPORT_PATH"

if [ $TEST_EXIT -ne 0 ]; then
    echo ""
    echo "❌ Test suite FAILED. Output captured for evidence."
    echo "   Do NOT claim tests passed. Fix and re-run."
    exit 1
fi

echo ""
echo "✅ Test suite passed. Raw output captured in TEST-REPORT.md"
exit 0
