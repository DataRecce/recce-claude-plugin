#!/bin/bash
# Smoke tests for the recce-review skill definition file.
# Validates structural correctness of plugins/recce-dev/skills/recce-review/SKILL.md
# Tests CMD-01 through CMD-04 requirements.
# Usage: bash tests/smoke/test-recce-review-skill.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
SKILL_FILE="$REPO_ROOT/plugins/recce-dev/skills/recce-review/SKILL.md"

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
    if echo "$content" | grep -qF -- "$unexpected"; then
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

echo "--- Checking skill file existence ---"
assert_file_exists "Skill file exists at plugins/recce-dev/skills/recce-review/SKILL.md" "$SKILL_FILE"

if [ ! -f "$SKILL_FILE" ]; then
    echo ""
    echo "========== RESULTS =========="
    echo "Total: $TOTAL | Passed: $PASS | Failed: $FAIL"
    echo "(Remaining tests skipped — skill file not found)"
    exit 1
fi

# ========== Parse frontmatter and body ==========
# Frontmatter is between the first and second '---' lines
# Body is everything after the second '---' line

FILE_CONTENT=$(cat "$SKILL_FILE")

# Extract frontmatter: lines between first and second '---'
FRONTMATTER=$(awk '/^---$/{if(++c==2) exit; if(c==1) next} c==1' "$SKILL_FILE")

# Extract body: everything after the second '---'
BODY=$(awk '/^---$/{if(++c==2){found=1; next}} found' "$SKILL_FILE")

# ========== Section 1: Frontmatter validation (CMD-01) ==========
echo "--- Section 1: Frontmatter validation (CMD-01) ---"

# 1. File starts with ---
assert_regex "File starts with '---' (YAML frontmatter)" "$FILE_CONTENT" "^---"

# 2. Frontmatter has name: recce-review
assert_contains "Frontmatter has name: recce-review" "$FRONTMATTER" "name: recce-review"

# 3. Frontmatter has description: field
assert_regex "Frontmatter has description: field" "$FRONTMATTER" "description:"

# ========== Section 2: MCP health check (CMD-02) ==========
echo "--- Section 2: MCP health check (CMD-02) ---"

# 4. Body references check-mcp.sh
assert_contains "Body contains check-mcp.sh (health check reference)" "$BODY" "check-mcp.sh"

# 5. Body references start-mcp.sh
assert_contains "Body contains start-mcp.sh (auto-start reference)" "$BODY" "start-mcp.sh"

# 6. Body parses RUNNING= output from check-mcp.sh
assert_regex "Body matches RUNNING= (parses check-mcp output)" "$BODY" "RUNNING="

# ========== Section 3: Agent dispatch (CMD-01) ==========
echo "--- Section 3: Agent dispatch (CMD-01) ---"

# 7. Body references recce-reviewer agent
assert_regex "Body references recce-reviewer or agent dispatch" "$BODY" "recce-reviewer|agent"

# 8. Body references Data Review Summary (success detection for cleanup gating)
assert_contains "Body contains 'Data Review Summary' (success detection)" "$BODY" "Data Review Summary"

# ========== Section 4: Tracked models (CMD-03) ==========
echo "--- Section 4: Tracked models (CMD-03) ---"

# 9. Body references recce-changed temp file
assert_regex "Body references recce-changed (tracked file reference)" "$BODY" "recce-changed"

# 10. Body includes hash derivation (PROJECT_HASH, md5)
assert_regex "Body includes hash derivation (PROJECT_HASH or md5)" "$BODY" "PROJECT_HASH|md5"

# 11. Body includes model name extraction from .sql files
assert_regex "Body includes model name extraction (basename or .sql)" "$BODY" "basename.*\.sql|\.sql"

# ========== Section 5: Manual escape hatch (CMD-04) ==========
echo "--- Section 5: Manual escape hatch (CMD-04) ---"

# 12. Body references state:modified fallback (no tracked file fallback)
assert_regex "Body references state:modified fallback (CMD-04)" "$BODY" "state:modified"

# 13. Body does NOT abort when no tracked changes file exists
assert_not_contains "Body does not abort on missing tracked file" "$BODY" "abort if no tracked"

# 14. Body does NOT gate entirely on tracked file presence
assert_not_contains "Body does not exit if no changes file" "$BODY" "exit if no changes"

# ========== Section 6: Post-review lifecycle ==========
echo "--- Section 6: Post-review lifecycle ---"

# 15. Body includes cleanup instruction (rm -f or cleanup)
assert_regex "Body includes cleanup instruction (rm -f or cleanup)" "$BODY" "rm -f|cleanup|delete.*recce-changed"

# 16. Body includes risk-based next steps
assert_regex "Body mentions Risk level (risk-based next steps)" "$BODY" "[Rr]isk"

# 17. Body mentions HIGH risk level
assert_regex "Body mentions HIGH risk level" "$BODY" "HIGH"

# 18. Body mentions MEDIUM risk level
assert_regex "Body mentions MEDIUM risk level" "$BODY" "MEDIUM"

# 19. Body mentions LOW risk level
assert_regex "Body mentions LOW risk level" "$BODY" "LOW"

# 20. Body uses CLAUDE_PLUGIN_ROOT for script paths
assert_contains "Body uses CLAUDE_PLUGIN_ROOT for script paths" "$BODY" "CLAUDE_PLUGIN_ROOT"

# ========== Summary ==========
echo ""
echo "========== RESULTS =========="
echo "Total: $TOTAL | Passed: $PASS | Failed: $FAIL"

if [ "$FAIL" -gt 0 ]; then
    exit 1
fi
exit 0
