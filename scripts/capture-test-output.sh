#!/bin/bash
# capture-test-output.sh
#
# Run the project's test suite and write the raw output into TEST-REPORT.md
# as machine-verifiable evidence. Parses pass/fail counts from the output
# so a follow-up "check-test-report.sh" can verify the agent didn't lie
# about results in the summary.
#
# Usage: bash scripts/capture-test-output.sh <test-report-path> [test-cmd] [label]
#   test-report-path: absolute path to the TEST-REPORT.md to update
#   test-cmd: optional override. Default: auto-detect (npm/pytest/go/cargo).
#             Pass "" to auto-detect when you only need the label argument.
#   label:    optional section label — multi-repo features run this script
#             once per worktree with the repo name as label, giving each repo
#             its own "## Raw Test Output (<label>)" section. Runs with the
#             SAME label replace each other; different labels coexist.
#             Without a label the single unlabeled section is replaced
#             (single-repo behavior, unchanged).
#
# What it writes into TEST-REPORT.md:
#   - A new "## Raw Test Output" / "## Raw Test Output (<label>)" section
#     (overwriting any prior section with the same label)
#   - Parsed counts: TOTAL_TESTS, PASSED, FAILED, SKIPPED
#   - A "<!-- test-output-meta: {...} -->" HTML comment with the same
#     numbers (and the label), so a check script can grep them without
#     re-parsing.
#
# Exit codes:
#   0 = test suite passed AND output was captured
#   1 = test suite failed (output still captured; caller decides what to do)
#   2 = usage error (no report path, no test runner detected, etc.)

set -e

REPORT_PATH="${1:?Usage: bash $0 <test-report-path> [test-cmd] [label]}"
TEST_CMD="${2:-}"
LABEL="${3:-}"

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
elif ! grep -qF '## Sign-off' "$REPORT_PATH"; then
    # The agent hand-created the report before this script ran, so the skeleton
    # (and its Sign-off section) never got emitted. /tgd-release's QA gate greps
    # the role line — guarantee it idempotently instead of depending on the
    # agent having run this script first.
    printf '\n## Sign-off\n- [ ] **QA**: (pending)\n' >> "$REPORT_PATH"
    echo "📝 Appended missing ## Sign-off section to existing report"
fi

# Resolve test runner
if [ -z "$TEST_CMD" ]; then
    if [ -f "package.json" ] && grep -q '"test"' package.json; then
        # Run via npm, NOT the extracted script body: npm puts node_modules/.bin
        # on PATH — a script like "jest" executed directly is command-not-found
        # (exit 127) and gets misreported as a test failure.
        TEST_CMD="npm test"
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

# TAP runners (node:test) print exact totals as "# pass N" / "# fail N" /
# "# skipped N" — use them verbatim. The line-grep heuristics above overcount
# here (e.g. the literal summary line "# skipped 0" matches the "skipped"
# pattern and scores 1 even when zero tests were skipped).
TAP_PASS=$(grep -E "^# pass [0-9]+" "$RAW" | tail -1 | grep -oE "[0-9]+" || true)
if [ -n "$TAP_PASS" ]; then
    PASSED=$TAP_PASS
    FAILED=$(grep -E "^# fail [0-9]+" "$RAW" | tail -1 | grep -oE "[0-9]+" || true)
    FAILED=${FAILED:-0}
    SKIPPED=$(grep -E "^# skipped [0-9]+" "$RAW" | tail -1 | grep -oE "[0-9]+" || true)
    SKIPPED=${SKIPPED:-0}
fi

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

# Strip the prior raw-output block WITH THE SAME LABEL (only). Sections with
# other labels are evidence from other repos' runs — they must survive.
python3 - "$REPORT_PATH" "$LABEL" <<'PYEOF'
import sys, pathlib
p = pathlib.Path(sys.argv[1])
label = sys.argv[2]
heading = "## Raw Test Output" + (f" ({label})" if label else "")
out, skipping = [], False
for line in p.read_text().splitlines(keepends=True):
    stripped = line.rstrip("\n")
    if skipping:
        # A section ends at the next level-2 heading (any, including another
        # raw-output section) — the meta comment and fence live inside it.
        if stripped.startswith("## "):
            skipping = False
        else:
            continue
    if stripped == heading:
        skipping = True
        # Drop the blank line that precedes the section we append
        while out and out[-1].strip() == "":
            out.pop()
        continue
    out.append(line)
p.write_text("".join(out))
PYEOF

# Append the new raw output + meta comment
TMP=$(mktemp)
{
    cat "$REPORT_PATH"
    echo ""
    if [ -n "$LABEL" ]; then
        echo "## Raw Test Output ($LABEL)"
    else
        echo "## Raw Test Output"
    fi
    echo ""
    echo "**Captured**: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
    echo "**Command**: \`$TEST_CMD\`"
    echo "**Exit code**: $TEST_EXIT"
    echo ""
    echo "<!-- test-output-meta: {\"label\": \"$LABEL\", \"exit\": $TEST_EXIT, \"passed\": $PASSED, \"failed\": $FAILED, \"skipped\": $SKIPPED} -->"
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
