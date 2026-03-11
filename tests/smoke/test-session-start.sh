#!/bin/bash
# Smoke tests for session-start.sh
# Validates KEY=VALUE output across multiple environment scenarios
# Usage: bash tests/smoke/test-session-start.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
SESSION_START="$REPO_ROOT/plugins/recce-dev/hooks/scripts/session-start.sh"

PASS=0
FAIL=0
TOTAL=0

assert_output_contains() {
    local test_name="$1"
    local output="$2"
    local expected="$3"
    TOTAL=$((TOTAL + 1))
    if echo "$output" | grep -qF "$expected"; then
        echo "  PASS: $test_name"
        PASS=$((PASS + 1))
    else
        echo "  FAIL: $test_name (expected '$expected' in output)"
        echo "  Got: $output"
        FAIL=$((FAIL + 1))
    fi
}

assert_output_not_contains() {
    local test_name="$1"
    local output="$2"
    local unexpected="$3"
    TOTAL=$((TOTAL + 1))
    if echo "$output" | grep -qF "$unexpected"; then
        echo "  FAIL: $test_name (unexpected '$unexpected' found in output)"
        echo "  Got: $output"
        FAIL=$((FAIL + 1))
    else
        echo "  PASS: $test_name"
        PASS=$((PASS + 1))
    fi
}

assert_line_count() {
    local test_name="$1"
    local output="$2"
    local expected_count="$3"
    TOTAL=$((TOTAL + 1))
    local actual_count
    actual_count=$(echo "$output" | wc -l | tr -d ' ')
    if [ "$actual_count" -eq "$expected_count" ]; then
        echo "  PASS: $test_name"
        PASS=$((PASS + 1))
    else
        echo "  FAIL: $test_name (expected $expected_count lines, got $actual_count)"
        echo "  Got: $output"
        FAIL=$((FAIL + 1))
    fi
}

assert_exit_code() {
    local test_name="$1"
    local actual="$2"
    local expected="$3"
    TOTAL=$((TOTAL + 1))
    if [ "$actual" -eq "$expected" ]; then
        echo "  PASS: $test_name"
        PASS=$((PASS + 1))
    else
        echo "  FAIL: $test_name (expected exit $expected, got $actual)"
        FAIL=$((FAIL + 1))
    fi
}

# ========== Test 1: Non-dbt directory ==========
echo "--- Test 1: Non-dbt directory ---"
TMPDIR_1=$(mktemp -d)
OUTPUT_1=$(cd "$TMPDIR_1" && bash "$SESSION_START" 2>/dev/null)
EXIT_1=$?

assert_exit_code "exits 0" "$EXIT_1" 0
assert_output_contains "outputs DBT_PROJECT=false" "$OUTPUT_1" "DBT_PROJECT=false"
assert_line_count "exactly 1 line" "$OUTPUT_1" 1
assert_output_not_contains "no DBT_PROJECT_NAME" "$OUTPUT_1" "DBT_PROJECT_NAME"
assert_output_not_contains "no MCP keys" "$OUTPUT_1" "MCP_STARTED"

rm -rf "$TMPDIR_1"

# ========== Test 2: dbt directory, recce NOT in PATH ==========
echo "--- Test 2: dbt project, recce not in PATH ---"
TMPDIR_2=$(mktemp -d)
cp "$REPO_ROOT/tests/fixtures/fake-dbt-project/dbt_project.yml" "$TMPDIR_2/"
# Use empty PATH to simulate recce not installed (keep /usr/bin for basic tools)
OUTPUT_2=$(cd "$TMPDIR_2" && PATH="/usr/bin:/bin" bash "$SESSION_START" 2>/dev/null)
EXIT_2=$?

assert_exit_code "exits 0" "$EXIT_2" 0
assert_output_contains "DBT_PROJECT=true" "$OUTPUT_2" "DBT_PROJECT=true"
assert_output_contains "project name extracted" "$OUTPUT_2" "DBT_PROJECT_NAME=fake_dbt_project"
assert_output_contains "RECCE_INSTALLED=false" "$OUTPUT_2" "RECCE_INSTALLED=false"
assert_output_contains "FIX hint present" "$OUTPUT_2" "FIX="
assert_output_contains "FIX mentions venv" "$OUTPUT_2" "venv"
assert_output_contains "MCP_STARTED=false" "$OUTPUT_2" "MCP_STARTED=false"
assert_output_contains "MCP skip reason" "$OUTPUT_2" "MCP_SKIP_REASON=recce not installed"

rm -rf "$TMPDIR_2"

# ========== Test 3: dbt directory, no target artifacts ==========
echo "--- Test 3: dbt project, no target/manifest.json ---"
TMPDIR_3=$(mktemp -d)
cp "$REPO_ROOT/tests/fixtures/fake-dbt-project/dbt_project.yml" "$TMPDIR_3/"
# Simulate recce in PATH by creating a fake recce binary
mkdir -p "$TMPDIR_3/.bin"
echo '#!/bin/bash' > "$TMPDIR_3/.bin/recce"
chmod +x "$TMPDIR_3/.bin/recce"
echo '#!/bin/bash' > "$TMPDIR_3/.bin/dbt"
chmod +x "$TMPDIR_3/.bin/dbt"

OUTPUT_3=$(cd "$TMPDIR_3" && PATH="$TMPDIR_3/.bin:/usr/bin:/bin" bash "$SESSION_START" 2>/dev/null)
EXIT_3=$?

assert_exit_code "exits 0" "$EXIT_3" 0
assert_output_contains "DBT_PROJECT=true" "$OUTPUT_3" "DBT_PROJECT=true"
assert_output_contains "RECCE_INSTALLED=true" "$OUTPUT_3" "RECCE_INSTALLED=true"
assert_output_contains "TARGET_EXISTS=false" "$OUTPUT_3" "TARGET_EXISTS=false"
assert_output_contains "MCP_STARTED=false" "$OUTPUT_3" "MCP_STARTED=false"
assert_output_contains "MCP skip: no manifest" "$OUTPUT_3" "MCP_SKIP_REASON=no target/manifest.json"
assert_output_contains "FIX for missing target" "$OUTPUT_3" "FIX=Run: dbt docs generate"

rm -rf "$TMPDIR_3"

# ========== Test 4: KEY=VALUE format validation ==========
echo "--- Test 4: All output lines are KEY=VALUE format ---"
TMPDIR_4=$(mktemp -d)
cp "$REPO_ROOT/tests/fixtures/fake-dbt-project/dbt_project.yml" "$TMPDIR_4/"
OUTPUT_4=$(cd "$TMPDIR_4" && PATH="/usr/bin:/bin" bash "$SESSION_START" 2>/dev/null)
EXIT_4=$?

TOTAL=$((TOTAL + 1))
BAD_LINES=$(echo "$OUTPUT_4" | grep -v "^[A-Z_]*=" || true)
if [ -z "$BAD_LINES" ]; then
    echo "  PASS: all lines match KEY=VALUE format"
    PASS=$((PASS + 1))
else
    echo "  FAIL: non-KEY=VALUE lines found: $BAD_LINES"
    FAIL=$((FAIL + 1))
fi

rm -rf "$TMPDIR_4"

# ========== Summary ==========
echo ""
echo "========== RESULTS =========="
echo "Total: $TOTAL | Passed: $PASS | Failed: $FAIL"

if [ "$FAIL" -gt 0 ]; then
    exit 1
fi
exit 0
