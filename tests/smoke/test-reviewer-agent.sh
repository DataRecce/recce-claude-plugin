#!/bin/bash
# Smoke tests for the recce-reviewer sub-agent definition file.
# Validates structural correctness of plugins/recce-dev/agents/recce-reviewer.md
# Tests REVW-01 through REVW-05 requirements.
# Usage: bash tests/smoke/test-reviewer-agent.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
AGENT_FILE="$REPO_ROOT/plugins/recce-dev/agents/recce-reviewer.md"

PASS=0
FAIL=0
TOTAL=0

# ========== Assert helpers ==========

assert_file_exists() {
    local test_name="$1"
    local file="$2"
    TOTAL=$((TOTAL + 1))
    if [ -f "$file" ]; then
        echo "  PASS: $test_name"
        PASS=$((PASS + 1))
    else
        echo "  FAIL: $test_name (file not found: $file)"
        FAIL=$((FAIL + 1))
    fi
}

assert_contains() {
    local test_name="$1"
    local content="$2"
    local expected="$3"
    TOTAL=$((TOTAL + 1))
    if echo "$content" | grep -qF "$expected"; then
        echo "  PASS: $test_name"
        PASS=$((PASS + 1))
    else
        echo "  FAIL: $test_name (expected '$expected' not found)"
        FAIL=$((FAIL + 1))
    fi
}

assert_not_contains() {
    local test_name="$1"
    local content="$2"
    local unexpected="$3"
    TOTAL=$((TOTAL + 1))
    if echo "$content" | grep -qF "$unexpected"; then
        echo "  FAIL: $test_name (unexpected '$unexpected' found)"
        FAIL=$((FAIL + 1))
    else
        echo "  PASS: $test_name"
        PASS=$((PASS + 1))
    fi
}

assert_regex() {
    local test_name="$1"
    local content="$2"
    local pattern="$3"
    TOTAL=$((TOTAL + 1))
    if echo "$content" | grep -qE "$pattern"; then
        echo "  PASS: $test_name"
        PASS=$((PASS + 1))
    else
        echo "  FAIL: $test_name (pattern '$pattern' not matched)"
        FAIL=$((FAIL + 1))
    fi
}

# ========== Abort early if file doesn't exist (all subsequent tests would be meaningless) ==========

echo "--- Checking agent file existence ---"
assert_file_exists "Agent file exists at plugins/recce-dev/agents/recce-reviewer.md" "$AGENT_FILE"

if [ ! -f "$AGENT_FILE" ]; then
    echo ""
    echo "========== RESULTS =========="
    echo "Total: $TOTAL | Passed: $PASS | Failed: $FAIL"
    echo "(Remaining tests skipped — agent file not found)"
    exit 1
fi

# ========== Parse frontmatter and body ==========
# Frontmatter is between the first and second '---' lines
# Body is everything after the second '---' line

FILE_CONTENT=$(cat "$AGENT_FILE")

# Extract frontmatter: lines between first and second '---'
FRONTMATTER=$(awk '/^---$/{if(++c==2) exit; if(c==1) next} c==1' "$AGENT_FILE")

# Extract body: everything after the second '---'
BODY=$(awk '/^---$/{if(++c==2){found=1; next}} found' "$AGENT_FILE")

# ========== Section 1: Frontmatter validation (REVW-02, REVW-05) ==========
echo "--- Section 1: Frontmatter validation (REVW-02, REVW-05) ---"

# 1. File starts with ---
assert_regex "File starts with '---' (YAML frontmatter)" "$FILE_CONTENT" "^---"

# 2. Frontmatter contains name: recce-reviewer
assert_contains "Frontmatter has name: recce-reviewer" "$FRONTMATTER" "name: recce-reviewer"

# 3. Frontmatter contains description: field (non-empty)
assert_regex "Frontmatter has description: field" "$FRONTMATTER" "description:"

# 4. Frontmatter contains tools: field
assert_contains "Frontmatter has tools: field" "$FRONTMATTER" "tools:"

# 5. tools: includes mcp__recce-dev__lineage_diff
assert_contains "tools includes mcp__recce-dev__lineage_diff" "$FRONTMATTER" "mcp__recce-dev__lineage_diff"

# 6. tools: includes mcp__recce-dev__row_count_diff
assert_contains "tools includes mcp__recce-dev__row_count_diff" "$FRONTMATTER" "mcp__recce-dev__row_count_diff"

# 7. tools: includes mcp__recce-dev__schema_diff
assert_contains "tools includes mcp__recce-dev__schema_diff" "$FRONTMATTER" "mcp__recce-dev__schema_diff"

# 8. Frontmatter contains mcpServers: field
assert_contains "Frontmatter has mcpServers: field" "$FRONTMATTER" "mcpServers:"

# 9. mcpServers references recce-dev (correct server name)
assert_contains "mcpServers contains recce-dev" "$FRONTMATTER" "recce-dev"

# 10. mcpServers does NOT reference bare 'recce' as a standalone server name
assert_not_contains "mcpServers does not use bare 'recce' server name" "$FRONTMATTER" "- recce"

# ========== Section 2: System prompt body validation (REVW-01, REVW-03, REVW-04) ==========
echo "--- Section 2: System prompt body validation (REVW-01, REVW-03, REVW-04) ---"

# 11. Body mentions lineage_diff (Step 1)
assert_contains "Body contains lineage_diff (Step 1)" "$BODY" "lineage_diff"

# 12. Body mentions row_count_diff (Step 2)
assert_contains "Body contains row_count_diff (Step 2)" "$BODY" "row_count_diff"

# 13. Body mentions schema_diff (Step 3)
assert_contains "Body contains schema_diff (Step 3)" "$BODY" "schema_diff"

# 14. Body mentions summary (Step 4)
assert_regex "Body mentions summary or Summary (Step 4)" "$BODY" "[Ss]ummary"

# 15. Body mentions view (view edge case handling)
assert_regex "Body mentions view (view edge case)" "$BODY" "[Vv]iew"

# 16. Body mentions single or Single (single-env edge case)
assert_regex "Body mentions single or Single (single-env edge case)" "$BODY" "[Ss]ingle"

# 17. Body mentions permission or error (permission error handling)
assert_regex "Body mentions permission or error (error handling)" "$BODY" "permission|error"

# 18. Body mentions risk or Risk (risk level in summary)
assert_regex "Body mentions risk or Risk (risk level)" "$BODY" "[Rr]isk"

# 19. Body mentions low or medium or high (risk level values)
assert_regex "Body mentions low/medium/high (risk values)" "$BODY" "[Ll]ow|[Mm]edium|[Hh]igh"

# 20. Body mentions recce-changed or changed-models tracking
assert_regex "Body mentions recce-changed or changed models tracking" "$BODY" "recce-changed|changed.*model|model.*changed"

# ========== Summary ==========
echo ""
echo "========== RESULTS =========="
echo "Total: $TOTAL | Passed: $PASS | Failed: $FAIL"

if [ "$FAIL" -gt 0 ]; then
    exit 1
fi
exit 0
