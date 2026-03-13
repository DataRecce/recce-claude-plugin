#!/bin/bash
# test-resolve-recce-root.sh — Unit tests for resolve-recce-root.sh
# Validates path resolution across monorepo and cache layouts.
# Run: bash tests/test-resolve-recce-root.sh
# Exit: 0 = all pass, 1 = failures

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
RESOLVE_SCRIPT="$REPO_ROOT/plugins/recce-dev/scripts/resolve-recce-root.sh"

PASS=0
FAIL=0
TOTAL=0

# ── Helpers ──

setup_tmpdir() {
    TMPDIR_TEST=$(mktemp -d)
}

teardown_tmpdir() {
    rm -rf "$TMPDIR_TEST"
}

assert_eq() {
    local label="$1" expected="$2" actual="$3"
    TOTAL=$((TOTAL + 1))
    if [ "$expected" = "$actual" ]; then
        PASS=$((PASS + 1))
        printf "  ✓ %s\n" "$label"
    else
        FAIL=$((FAIL + 1))
        printf "  ✗ %s\n    expected: %s\n    actual:   %s\n" "$label" "$expected" "$actual"
    fi
}

assert_contains() {
    local label="$1" needle="$2" haystack="$3"
    TOTAL=$((TOTAL + 1))
    if echo "$haystack" | grep -qF "$needle"; then
        PASS=$((PASS + 1))
        printf "  ✓ %s\n" "$label"
    else
        FAIL=$((FAIL + 1))
        printf "  ✗ %s\n    expected to contain: %s\n    actual: %s\n" "$label" "$needle" "$haystack"
    fi
}

run_resolve() {
    # Run resolve script with given CLAUDE_PLUGIN_ROOT, capture stdout
    CLAUDE_PLUGIN_ROOT="$1" bash "$RESOLVE_SCRIPT" 2>/dev/null || true
}

# ── Test 1: Monorepo layout ──

test_monorepo_layout() {
    printf "Test 1: Monorepo layout\n"
    setup_tmpdir

    mkdir -p "$TMPDIR_TEST/plugins/recce-dev/scripts"
    mkdir -p "$TMPDIR_TEST/plugins/recce/scripts"
    # Create a dummy start-mcp.sh so scripts/ dir exists
    touch "$TMPDIR_TEST/plugins/recce/scripts/start-mcp.sh"

    OUTPUT=$(run_resolve "$TMPDIR_TEST/plugins/recce-dev")
    RESOLVED_ROOT=$(echo "$OUTPUT" | grep "^RECCE_PLUGIN_ROOT=" | cut -d= -f2-)
    LAYOUT=$(echo "$OUTPUT" | grep "^LAYOUT=" | cut -d= -f2-)

    assert_eq "resolves to recce dir" "$TMPDIR_TEST/plugins/recce" "$RESOLVED_ROOT"
    assert_eq "layout is monorepo" "monorepo" "$LAYOUT"

    teardown_tmpdir
}

# ── Test 2: Cache layout ──

test_cache_layout() {
    printf "Test 2: Cache layout\n"
    setup_tmpdir

    mkdir -p "$TMPDIR_TEST/marketplace/recce-dev/0.1.0/scripts"
    mkdir -p "$TMPDIR_TEST/marketplace/recce/0.2.0/scripts"
    touch "$TMPDIR_TEST/marketplace/recce/0.2.0/scripts/start-mcp.sh"

    OUTPUT=$(run_resolve "$TMPDIR_TEST/marketplace/recce-dev/0.1.0")
    RESOLVED_ROOT=$(echo "$OUTPUT" | grep "^RECCE_PLUGIN_ROOT=" | cut -d= -f2-)
    LAYOUT=$(echo "$OUTPUT" | grep "^LAYOUT=" | cut -d= -f2-)

    assert_eq "resolves to recce/0.2.0" "$TMPDIR_TEST/marketplace/recce/0.2.0" "$RESOLVED_ROOT"
    assert_eq "layout is cache" "cache" "$LAYOUT"

    teardown_tmpdir
}

# ── Test 3: Cache with multiple versions (picks latest) ──

test_cache_multiple_versions() {
    printf "Test 3: Cache with multiple versions\n"
    setup_tmpdir

    mkdir -p "$TMPDIR_TEST/marketplace/recce-dev/0.1.0/scripts"
    mkdir -p "$TMPDIR_TEST/marketplace/recce/0.1.0/scripts"
    mkdir -p "$TMPDIR_TEST/marketplace/recce/0.2.0/scripts"
    mkdir -p "$TMPDIR_TEST/marketplace/recce/0.3.0/scripts"
    touch "$TMPDIR_TEST/marketplace/recce/0.1.0/scripts/start-mcp.sh"
    touch "$TMPDIR_TEST/marketplace/recce/0.2.0/scripts/start-mcp.sh"
    touch "$TMPDIR_TEST/marketplace/recce/0.3.0/scripts/start-mcp.sh"

    OUTPUT=$(run_resolve "$TMPDIR_TEST/marketplace/recce-dev/0.1.0")
    RESOLVED_ROOT=$(echo "$OUTPUT" | grep "^RECCE_PLUGIN_ROOT=" | cut -d= -f2-)

    assert_eq "picks latest version 0.3.0" "$TMPDIR_TEST/marketplace/recce/0.3.0" "$RESOLVED_ROOT"

    teardown_tmpdir
}

# ── Test 4: Neither layout (recce plugin missing) ──

test_recce_missing() {
    printf "Test 4: Recce plugin missing\n"
    setup_tmpdir

    mkdir -p "$TMPDIR_TEST/plugins/recce-dev/scripts"
    # No recce dir at all

    OUTPUT=$(run_resolve "$TMPDIR_TEST/plugins/recce-dev")
    ERROR=$(echo "$OUTPUT" | grep "^ERROR=" | cut -d= -f2-)

    assert_contains "reports error" "not found" "$ERROR"

    teardown_tmpdir
}

# ── Test 5: Recce dir exists but no scripts/ subdir ──

test_recce_no_scripts() {
    printf "Test 5: Recce dir exists but no scripts/\n"
    setup_tmpdir

    mkdir -p "$TMPDIR_TEST/plugins/recce-dev/scripts"
    mkdir -p "$TMPDIR_TEST/plugins/recce"
    # recce dir exists but has no scripts/ subdirectory

    OUTPUT=$(run_resolve "$TMPDIR_TEST/plugins/recce-dev")
    ERROR=$(echo "$OUTPUT" | grep "^ERROR=" | cut -d= -f2-)

    assert_contains "reports error when scripts missing" "not found" "$ERROR"

    teardown_tmpdir
}

# ── Test 6: Monorepo takes priority over cache ──

test_monorepo_priority() {
    printf "Test 6: Monorepo path takes priority when both match\n"
    setup_tmpdir

    # Create a layout where both probes could match:
    # recce-dev/ has a direct ../recce/scripts sibling (monorepo probe)
    mkdir -p "$TMPDIR_TEST/recce-dev/scripts"
    mkdir -p "$TMPDIR_TEST/recce/scripts"
    touch "$TMPDIR_TEST/recce/scripts/start-mcp.sh"

    OUTPUT=$(run_resolve "$TMPDIR_TEST/recce-dev")
    LAYOUT=$(echo "$OUTPUT" | grep "^LAYOUT=" | cut -d= -f2-)

    assert_eq "monorepo probe wins" "monorepo" "$LAYOUT"

    teardown_tmpdir
}

# ── Test 7: Preflight uses resolve script correctly ──

test_preflight_integration() {
    printf "Test 7: Preflight integration (resolve script is sourced)\n"
    setup_tmpdir

    # Simulate monorepo layout with settings
    mkdir -p "$TMPDIR_TEST/plugins/recce-dev/scripts"
    mkdir -p "$TMPDIR_TEST/plugins/recce-dev/skills/mcp-e2e-validate/scripts"
    mkdir -p "$TMPDIR_TEST/plugins/recce/scripts"
    mkdir -p "$TMPDIR_TEST/plugins/recce/settings"

    # Copy actual scripts
    cp "$RESOLVE_SCRIPT" "$TMPDIR_TEST/plugins/recce-dev/scripts/resolve-recce-root.sh"
    cp "$REPO_ROOT/plugins/recce-dev/skills/mcp-e2e-validate/scripts/preflight.sh" \
       "$TMPDIR_TEST/plugins/recce-dev/skills/mcp-e2e-validate/scripts/preflight.sh"

    # Create minimal defaults.json
    echo '{"mcp_port": 9999}' > "$TMPDIR_TEST/plugins/recce/settings/defaults.json"
    touch "$TMPDIR_TEST/plugins/recce/scripts/start-mcp.sh"

    # Create a fake dbt project in a temp working dir
    WORKDIR=$(mktemp -d)
    echo "name: test_project" > "$WORKDIR/dbt_project.yml"
    mkdir -p "$WORKDIR/target" "$WORKDIR/target-base"
    echo '{}' > "$WORKDIR/target/manifest.json"
    echo '{}' > "$WORKDIR/target-base/manifest.json"

    # Run preflight from the fake dbt project dir
    OUTPUT=$(cd "$WORKDIR" && CLAUDE_PLUGIN_ROOT="$TMPDIR_TEST/plugins/recce-dev" \
             bash "$TMPDIR_TEST/plugins/recce-dev/skills/mcp-e2e-validate/scripts/preflight.sh" 2>/dev/null || true)

    # Should NOT contain BLOCK about recce plugin not found
    TOTAL=$((TOTAL + 1))
    if echo "$OUTPUT" | grep -q "BLOCK=recce plugin not found"; then
        FAIL=$((FAIL + 1))
        printf "  ✗ preflight should not block on recce path\n    output: %s\n" "$OUTPUT"
    else
        PASS=$((PASS + 1))
        printf "  ✓ preflight resolves recce path without blocking\n"
    fi

    # Should read port from resolved defaults
    PORT=$(echo "$OUTPUT" | grep "^PORT=" | cut -d= -f2-)
    assert_eq "reads port from recce settings" "9999" "$PORT"

    rm -rf "$WORKDIR"
    teardown_tmpdir
}

# ── Run all tests ──

printf "═══════════════════════════════════════════\n"
printf " resolve-recce-root.sh tests\n"
printf "═══════════════════════════════════════════\n\n"

test_monorepo_layout
echo ""
test_cache_layout
echo ""
test_cache_multiple_versions
echo ""
test_recce_missing
echo ""
test_recce_no_scripts
echo ""
test_monorepo_priority
echo ""
test_preflight_integration

printf "\n═══════════════════════════════════════════\n"
printf " Results: %d/%d passed" "$PASS" "$TOTAL"
if [ "$FAIL" -gt 0 ]; then
    printf " (%d FAILED)" "$FAIL"
fi
printf "\n═══════════════════════════════════════════\n"

exit "$FAIL"
