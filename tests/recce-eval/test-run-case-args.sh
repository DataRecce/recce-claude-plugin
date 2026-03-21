#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
RUNNER="$REPO_ROOT/plugins/recce-dev/skills/recce-eval/scripts/run-case.sh"

PASS=0
FAIL=0

assert_contains() {
    local test_name="$1" expected="$2" actual="$3"
    if echo "$actual" | grep -q "$expected"; then
        echo "  PASS: $test_name"
        PASS=$((PASS + 1))
    else
        echo "  FAIL: $test_name (expected to contain '$expected')"
        FAIL=$((FAIL + 1))
    fi
}

# Create a dummy prompt file
echo "Test prompt" > /tmp/test-eval-prompt.txt

# Test 1: baseline variant
echo "Test 1: baseline --dry-run"
OUTPUT=$(bash "$RUNNER" \
    --id test-scenario \
    --case-type problem_exists \
    --variant baseline \
    --prompt-file /tmp/test-eval-prompt.txt \
    --setup-strategy none \
    --target dev-local \
    --max-budget-usd 1.00 \
    --output-dir /tmp/test-eval \
    --dry-run 2>&1 || true)

assert_contains "has claude" "claude" "$OUTPUT"
assert_contains "has --dangerously-skip-permissions" "dangerously-skip-permissions" "$OUTPUT"
assert_contains "has --max-budget-usd" "max-budget-usd" "$OUTPUT"
assert_contains "no plugin-dir for baseline" "PLUGIN_DIR=(none)" "$OUTPUT"

# Test 2: with-plugin variant
echo "Test 2: with-plugin --dry-run"
OUTPUT=$(bash "$RUNNER" \
    --id test-scenario \
    --case-type problem_exists \
    --variant with-plugin \
    --prompt-file /tmp/test-eval-prompt.txt \
    --setup-strategy none \
    --target dev-local \
    --max-budget-usd 1.00 \
    --output-dir /tmp/test-eval \
    --plugin-dir /fake/plugin/path \
    --mcp-config /fake/mcp.json \
    --dry-run 2>&1 || true)

assert_contains "has --plugin-dir" "plugin-dir" "$OUTPUT"
assert_contains "has --mcp-config" "mcp-config" "$OUTPUT"

# Cleanup
rm -f /tmp/test-eval-prompt.txt

echo ""
echo "Results: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
