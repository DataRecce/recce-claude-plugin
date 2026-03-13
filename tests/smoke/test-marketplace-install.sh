#!/bin/bash
# Smoke test: marketplace install artifact validation (VALD-03)
# Validates that all plugin filesystem artifacts required for a successful
# /plugin install recce@recce-claude-plugin are present and correct.
#
# This test does NOT require Claude Code or a live install — it validates
# the source tree has everything needed for a successful install.
#
# Usage: bash tests/smoke/test-marketplace-install.sh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
PLUGIN_ROOT="$REPO_ROOT/plugins/recce"

PASS=0
FAIL=0
TOTAL=0

# ---------- Helper functions ----------

assert_file_exists() {
    local test_name="$1"
    local path="$2"
    TOTAL=$((TOTAL + 1))
    if [ -f "$path" ]; then
        echo "  PASS: $test_name"
        PASS=$((PASS + 1))
    else
        echo "  FAIL: $test_name (file not found: $path)"
        FAIL=$((FAIL + 1))
    fi
}

assert_file_contains() {
    local test_name="$1"
    local path="$2"
    local pattern="$3"
    TOTAL=$((TOTAL + 1))
    if [ -f "$path" ] && grep -q "$pattern" "$path" 2>/dev/null; then
        echo "  PASS: $test_name"
        PASS=$((PASS + 1))
    else
        echo "  FAIL: $test_name (pattern '$pattern' not found in $path)"
        FAIL=$((FAIL + 1))
    fi
}

assert_executable() {
    local test_name="$1"
    local path="$2"
    TOTAL=$((TOTAL + 1))
    if [ -x "$path" ]; then
        echo "  PASS: $test_name"
        PASS=$((PASS + 1))
    else
        echo "  FAIL: $test_name (not executable: $path)"
        FAIL=$((FAIL + 1))
    fi
}

assert_valid_json() {
    local test_name="$1"
    local path="$2"
    TOTAL=$((TOTAL + 1))
    if [ ! -f "$path" ]; then
        echo "  FAIL: $test_name (file not found: $path)"
        FAIL=$((FAIL + 1))
        return
    fi
    if command -v jq &>/dev/null; then
        if jq '.' "$path" &>/dev/null; then
            echo "  PASS: $test_name"
            PASS=$((PASS + 1))
        else
            echo "  FAIL: $test_name (invalid JSON: $path)"
            FAIL=$((FAIL + 1))
        fi
    else
        # Fallback: python json check
        if python3 -c "import json, sys; json.load(open('$path'))" &>/dev/null 2>&1; then
            echo "  PASS: $test_name (via python fallback)"
            PASS=$((PASS + 1))
        else
            echo "  FAIL: $test_name (invalid JSON or no jq/python3 available: $path)"
            FAIL=$((FAIL + 1))
        fi
    fi
}

# ========== Test 1: plugin.json exists and is valid JSON ==========
echo "--- Test 1: plugin.json ---"

PLUGIN_JSON="$PLUGIN_ROOT/.claude-plugin/plugin.json"
assert_file_exists "plugin.json exists" "$PLUGIN_JSON"
assert_valid_json "plugin.json is valid JSON" "$PLUGIN_JSON"
assert_file_contains "plugin.json has name field" "$PLUGIN_JSON" '"name"'
assert_file_contains "plugin.json name is recce" "$PLUGIN_JSON" '"recce"'

# ========== Test 2: hooks.json exists and is valid JSON ==========
echo "--- Test 2: hooks.json ---"

HOOKS_JSON="$PLUGIN_ROOT/hooks/hooks.json"
assert_file_exists "hooks.json exists" "$HOOKS_JSON"
assert_valid_json "hooks.json is valid JSON" "$HOOKS_JSON"
assert_file_contains "hooks.json has hooks key" "$HOOKS_JSON" '"hooks"'
assert_file_contains "hooks.json has SessionStart" "$HOOKS_JSON" '"SessionStart"'
assert_file_contains "hooks.json has PostToolUse" "$HOOKS_JSON" '"PostToolUse"'

# ========== Test 3: Scripts are executable ==========
echo "--- Test 3: Script executability ---"

assert_executable "start-mcp.sh is executable" "$PLUGIN_ROOT/scripts/start-mcp.sh"
assert_executable "stop-mcp.sh is executable"  "$PLUGIN_ROOT/scripts/stop-mcp.sh"
assert_executable "check-mcp.sh is executable" "$PLUGIN_ROOT/scripts/check-mcp.sh"

for hook_script in "$PLUGIN_ROOT/hooks/scripts/"*.sh; do
    script_name="$(basename "$hook_script")"
    assert_executable "hooks/scripts/$script_name is executable" "$hook_script"
done

# ========== Test 4: Agent file exists ==========
echo "--- Test 4: Agent file ---"

AGENT_FILE="$PLUGIN_ROOT/agents/recce-reviewer.md"
assert_file_exists "recce-reviewer.md exists" "$AGENT_FILE"
assert_file_contains "agent has YAML frontmatter" "$AGENT_FILE" '^---'
assert_file_contains "agent has name field" "$AGENT_FILE" 'name:'

# ========== Test 5: Skill file exists ==========
echo "--- Test 5: Skill file ---"

SKILL_FILE="$PLUGIN_ROOT/skills/recce-review/SKILL.md"
assert_file_exists "SKILL.md exists" "$SKILL_FILE"
assert_file_contains "skill has YAML frontmatter" "$SKILL_FILE" '^---'
assert_file_contains "skill has name field" "$SKILL_FILE" 'name:'

# ========== Test 6: marketplace.json references plugin correctly ==========
echo "--- Test 6: marketplace.json ---"

MARKETPLACE_JSON="$REPO_ROOT/.claude-plugin/marketplace.json"
assert_file_exists "marketplace.json exists" "$MARKETPLACE_JSON"
assert_valid_json "marketplace.json is valid JSON" "$MARKETPLACE_JSON"
assert_file_contains "marketplace.json references recce" "$MARKETPLACE_JSON" '"recce"'
assert_file_contains "marketplace.json has correct source path" "$MARKETPLACE_JSON" '"./plugins/recce"'
assert_file_contains "marketplace.json has plugins array" "$MARKETPLACE_JSON" '"plugins"'

# ========== Test 7: No broken symlinks in plugin tree ==========
echo "--- Test 7: No broken symlinks ---"

TOTAL=$((TOTAL + 1))
BROKEN_SYMLINKS=""

# Walk the full plugin tree — symlinks replaced by real bundles (MKTD-02)
# (removed -not -path "*/servers/*" exclusion — symlinks replaced by real bundles)
while IFS= read -r -d '' symlink; do
    if ! [ -e "$symlink" ]; then
        BROKEN_SYMLINKS="${BROKEN_SYMLINKS}${symlink}\n"
    fi
done < <(find "$PLUGIN_ROOT" -type l -print0 2>/dev/null)

if [ -z "$BROKEN_SYMLINKS" ]; then
    echo "  PASS: no broken symlinks in plugin tree"
    PASS=$((PASS + 1))
else
    echo "  FAIL: broken symlinks found:"
    # shellcheck disable=SC2059
    printf "  $BROKEN_SYMLINKS"
    FAIL=$((FAIL + 1))
fi

# ========== Test 8: Bundle distribution (MKTD-02, MKTD-03) ==========
echo "--- Test 8: Bundle distribution ---"

# dist/cli.js exists and is a real file (not symlink)
assert_file_exists "dist/cli.js exists" "$PLUGIN_ROOT/servers/recce-docs-mcp/dist/cli.js"

TOTAL=$((TOTAL + 1))
if [ -L "$PLUGIN_ROOT/servers/recce-docs-mcp" ]; then
    echo "  FAIL: servers/recce-docs-mcp is a symlink (should be real directory)"
    FAIL=$((FAIL + 1))
else
    echo "  PASS: servers/recce-docs-mcp is a real directory"
    PASS=$((PASS + 1))
fi

# dist/cli.js is non-empty
TOTAL=$((TOTAL + 1))
if [ -s "$PLUGIN_ROOT/servers/recce-docs-mcp/dist/cli.js" ]; then
    echo "  PASS: dist/cli.js is non-empty"
    PASS=$((PASS + 1))
else
    echo "  FAIL: dist/cli.js is empty or missing"
    FAIL=$((FAIL + 1))
fi

# MCP handshake returns valid JSON-RPC
TOTAL=$((TOTAL + 1))
MCP_RESPONSE=$(echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"0"}}}' \
  | node "$PLUGIN_ROOT/servers/recce-docs-mcp/dist/cli.js" 2>/dev/null \
  | head -1)
if [ "${MCP_RESPONSE:0:1}" = "{" ] && echo "$MCP_RESPONSE" | python3 -c "import json,sys; d=json.load(sys.stdin); assert 'result' in d" 2>/dev/null; then
    echo "  PASS: MCP handshake returns valid JSON-RPC"
    PASS=$((PASS + 1))
else
    echo "  FAIL: MCP handshake did not return valid JSON-RPC"
    FAIL=$((FAIL + 1))
fi

# ========== Summary ==========
echo ""
echo "========== RESULTS =========="
echo "Total: $TOTAL | Passed: $PASS | Failed: $FAIL"

if [ "$FAIL" -gt 0 ]; then
    exit 1
fi
exit 0
