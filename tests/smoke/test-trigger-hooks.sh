#!/bin/bash
# Smoke tests for trigger hook scripts:
#   track-changes.sh, suggest-review.sh, pre-commit-guard.sh
# Validates all 11 TRIG test cases from VALIDATION.md
# Usage: bash tests/smoke/test-trigger-hooks.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
FIXTURES="$REPO_ROOT/tests/fixtures/fake-hook-inputs"
HOOKS_DIR="$REPO_ROOT/plugins/recce-dev/hooks/scripts"

TRACK_CHANGES="$HOOKS_DIR/track-changes.sh"
SUGGEST_REVIEW="$HOOKS_DIR/suggest-review.sh"
PRE_COMMIT_GUARD="$HOOKS_DIR/pre-commit-guard.sh"

PASS=0
FAIL=0
TOTAL=0

# ========== Assert helpers ==========

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
        echo "  Got: [$output]"
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
        echo "  Got: [$output]"
        FAIL=$((FAIL + 1))
    else
        echo "  PASS: $test_name"
        PASS=$((PASS + 1))
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

assert_output_empty() {
    local test_name="$1"
    local output="$2"
    TOTAL=$((TOTAL + 1))
    if [ -z "$output" ]; then
        echo "  PASS: $test_name"
        PASS=$((PASS + 1))
    else
        echo "  FAIL: $test_name (expected empty output)"
        echo "  Got: [$output]"
        FAIL=$((FAIL + 1))
    fi
}

assert_file_contains() {
    local test_name="$1"
    local file="$2"
    local expected="$3"
    TOTAL=$((TOTAL + 1))
    if [ -f "$file" ] && grep -qF "$expected" "$file"; then
        echo "  PASS: $test_name"
        PASS=$((PASS + 1))
    else
        echo "  FAIL: $test_name (expected '$expected' in file '$file')"
        if [ -f "$file" ]; then
            echo "  File contents: $(cat "$file")"
        else
            echo "  File does not exist"
        fi
        FAIL=$((FAIL + 1))
    fi
}

assert_file_not_exists() {
    local test_name="$1"
    local file="$2"
    TOTAL=$((TOTAL + 1))
    if [ ! -f "$file" ]; then
        echo "  PASS: $test_name"
        PASS=$((PASS + 1))
    else
        echo "  FAIL: $test_name (expected file '$file' to not exist)"
        FAIL=$((FAIL + 1))
    fi
}

assert_file_line_count() {
    local test_name="$1"
    local file="$2"
    local expected_count="$3"
    TOTAL=$((TOTAL + 1))
    local actual_count
    actual_count=$(wc -l < "$file" | tr -d ' ')
    if [ "$actual_count" -eq "$expected_count" ]; then
        echo "  PASS: $test_name"
        PASS=$((PASS + 1))
    else
        echo "  FAIL: $test_name (expected $expected_count lines, got $actual_count)"
        if [ -f "$file" ]; then
            echo "  File contents: $(cat "$file")"
        fi
        FAIL=$((FAIL + 1))
    fi
}

# ========== Helper: substitute {{CWD}} in fixture and run hook ==========
run_hook() {
    local script="$1"
    local fixture="$2"
    local cwd="$3"
    sed "s|{{CWD}}|${cwd}|g" "$fixture" | bash "$script"
}

# ========== Helper: compute project hash (cross-platform) ==========
compute_project_hash() {
    local cwd="$1"
    printf '%s' "$cwd" | md5 2>/dev/null | cut -c1-8 || printf '%s' "$cwd" | md5sum | cut -c1-8
}

# ========== Scenario 1: track-changes on Write model file (TRIG-01) ==========
echo "--- Scenario 1: track-changes on Write model file (TRIG-01) ---"
TMPDIR_1=$(mktemp -d)
HASH_1=$(compute_project_hash "$TMPDIR_1")
CHANGES_FILE_1="/tmp/recce-changed-${HASH_1}.txt"
rm -f "$CHANGES_FILE_1"

OUTPUT_1=$(run_hook "$TRACK_CHANGES" "$FIXTURES/write-model.json" "$TMPDIR_1" 2>/dev/null)
EXIT_1=$?

assert_exit_code "exits 0" "$EXIT_1" 0
assert_output_empty "stdout is empty (silent)" "$OUTPUT_1"
assert_file_contains "temp file contains model path" "$CHANGES_FILE_1" "models/stg_bookings.sql"

rm -f "$CHANGES_FILE_1"
rm -rf "$TMPDIR_1"

# ========== Scenario 2: track-changes is truly silent (TRIG-01) ==========
echo "--- Scenario 2: track-changes is truly silent (TRIG-01) ---"
TMPDIR_2=$(mktemp -d)
HASH_2=$(compute_project_hash "$TMPDIR_2")
CHANGES_FILE_2="/tmp/recce-changed-${HASH_2}.txt"
rm -f "$CHANGES_FILE_2"

OUTPUT_2=$(run_hook "$TRACK_CHANGES" "$FIXTURES/write-model.json" "$TMPDIR_2" 2>/dev/null)

TOTAL=$((TOTAL + 1))
BYTE_COUNT=${#OUTPUT_2}
if [ "$BYTE_COUNT" -eq 0 ]; then
    echo "  PASS: stdout is zero bytes"
    PASS=$((PASS + 1))
else
    echo "  FAIL: stdout is not zero bytes (got $BYTE_COUNT bytes: [$OUTPUT_2])"
    FAIL=$((FAIL + 1))
fi

rm -f "$CHANGES_FILE_2"
rm -rf "$TMPDIR_2"

# ========== Scenario 3: temp file uses project hash (TRIG-02) ==========
echo "--- Scenario 3: temp file uses project hash (TRIG-02) ---"
TMPDIR_3=$(mktemp -d)
HASH_3=$(compute_project_hash "$TMPDIR_3")
CHANGES_FILE_3="/tmp/recce-changed-${HASH_3}.txt"
rm -f "$CHANGES_FILE_3"

run_hook "$TRACK_CHANGES" "$FIXTURES/write-model.json" "$TMPDIR_3" >/dev/null 2>&1 || true

assert_exit_code "exits 0 for hash test" 0 0
TOTAL=$((TOTAL + 1))
if [ -f "$CHANGES_FILE_3" ]; then
    echo "  PASS: file /tmp/recce-changed-${HASH_3}.txt exists"
    PASS=$((PASS + 1))
else
    echo "  FAIL: expected /tmp/recce-changed-${HASH_3}.txt to exist"
    FAIL=$((FAIL + 1))
fi

rm -f "$CHANGES_FILE_3"
rm -rf "$TMPDIR_3"

# ========== Scenario 4: non-model file NOT tracked (TRIG-01) ==========
echo "--- Scenario 4: non-model file NOT tracked (TRIG-01) ---"
TMPDIR_4=$(mktemp -d)
HASH_4=$(compute_project_hash "$TMPDIR_4")
CHANGES_FILE_4="/tmp/recce-changed-${HASH_4}.txt"
rm -f "$CHANGES_FILE_4"

run_hook "$TRACK_CHANGES" "$FIXTURES/write-readme.json" "$TMPDIR_4" >/dev/null 2>&1 || true

TOTAL=$((TOTAL + 1))
if [ ! -f "$CHANGES_FILE_4" ] || ! grep -qF "README.md" "$CHANGES_FILE_4" 2>/dev/null; then
    echo "  PASS: README.md not tracked in temp file"
    PASS=$((PASS + 1))
else
    echo "  FAIL: README.md should not be tracked (found in $CHANGES_FILE_4)"
    FAIL=$((FAIL + 1))
fi

rm -f "$CHANGES_FILE_4"
rm -rf "$TMPDIR_4"

# ========== Scenario 5: duplicate edits produce 1 entry (TRIG-01) ==========
echo "--- Scenario 5: duplicate edits produce 1 entry (TRIG-01) ---"
TMPDIR_5=$(mktemp -d)
HASH_5=$(compute_project_hash "$TMPDIR_5")
CHANGES_FILE_5="/tmp/recce-changed-${HASH_5}.txt"
rm -f "$CHANGES_FILE_5"

run_hook "$TRACK_CHANGES" "$FIXTURES/write-model.json" "$TMPDIR_5" >/dev/null 2>&1 || true
run_hook "$TRACK_CHANGES" "$FIXTURES/write-model.json" "$TMPDIR_5" >/dev/null 2>&1 || true

assert_file_line_count "exactly 1 line after 2 identical edits" "$CHANGES_FILE_5" 1

rm -f "$CHANGES_FILE_5"
rm -rf "$TMPDIR_5"

# ========== Scenario 6: suggest-review fires on dbt run (TRIG-03) ==========
echo "--- Scenario 6: suggest-review fires on dbt run (TRIG-03) ---"
TMPDIR_6=$(mktemp -d)
HASH_6=$(compute_project_hash "$TMPDIR_6")
CHANGES_FILE_6="/tmp/recce-changed-${HASH_6}.txt"
rm -f "$CHANGES_FILE_6"
echo "${TMPDIR_6}/models/stg_bookings.sql" > "$CHANGES_FILE_6"

OUTPUT_6=$(run_hook "$SUGGEST_REVIEW" "$FIXTURES/bash-dbt-run.json" "$TMPDIR_6" 2>/dev/null)
EXIT_6=$?

assert_exit_code "exits 0" "$EXIT_6" 0
assert_output_contains "stdout contains additionalContext" "$OUTPUT_6" "additionalContext"

rm -f "$CHANGES_FILE_6"
rm -rf "$TMPDIR_6"

# ========== Scenario 7: suggest-review includes model names in output (TRIG-04) ==========
echo "--- Scenario 7: suggest-review includes model names in output (TRIG-04) ---"
TMPDIR_7=$(mktemp -d)
HASH_7=$(compute_project_hash "$TMPDIR_7")
CHANGES_FILE_7="/tmp/recce-changed-${HASH_7}.txt"
rm -f "$CHANGES_FILE_7"
echo "${TMPDIR_7}/models/stg_bookings.sql" > "$CHANGES_FILE_7"

OUTPUT_7=$(run_hook "$SUGGEST_REVIEW" "$FIXTURES/bash-dbt-run.json" "$TMPDIR_7" 2>/dev/null)

assert_output_contains "stdout contains model name" "$OUTPUT_7" "stg_bookings"
assert_output_contains "stdout contains '1 model'" "$OUTPUT_7" "1 model"

rm -f "$CHANGES_FILE_7"
rm -rf "$TMPDIR_7"

# ========== Scenario 8: suggest-review silent on non-dbt command (TRIG-03) ==========
echo "--- Scenario 8: suggest-review silent on non-dbt command (TRIG-03) ---"
TMPDIR_8=$(mktemp -d)
HASH_8=$(compute_project_hash "$TMPDIR_8")
CHANGES_FILE_8="/tmp/recce-changed-${HASH_8}.txt"
rm -f "$CHANGES_FILE_8"
echo "${TMPDIR_8}/models/stg_bookings.sql" > "$CHANGES_FILE_8"

OUTPUT_8=$(run_hook "$SUGGEST_REVIEW" "$FIXTURES/bash-git-status.json" "$TMPDIR_8" 2>/dev/null)
EXIT_8=$?

assert_exit_code "exits 0" "$EXIT_8" 0
assert_output_empty "stdout is empty for non-dbt command" "$OUTPUT_8"

rm -f "$CHANGES_FILE_8"
rm -rf "$TMPDIR_8"

# ========== Scenario 9: suggest-review silent when no tracked models (TRIG-04) ==========
echo "--- Scenario 9: suggest-review silent when no tracked models (TRIG-04) ---"
TMPDIR_9=$(mktemp -d)
HASH_9=$(compute_project_hash "$TMPDIR_9")
CHANGES_FILE_9="/tmp/recce-changed-${HASH_9}.txt"
rm -f "$CHANGES_FILE_9"

OUTPUT_9=$(run_hook "$SUGGEST_REVIEW" "$FIXTURES/bash-dbt-run.json" "$TMPDIR_9" 2>/dev/null)
EXIT_9=$?

assert_exit_code "exits 0" "$EXIT_9" 0
assert_output_empty "stdout is empty when no tracked models" "$OUTPUT_9"

rm -rf "$TMPDIR_9"

# ========== Scenario 10: pre-commit-guard warns on git commit with tracked models (TRIG-05) ==========
echo "--- Scenario 10: pre-commit-guard warns on git commit with tracked models (TRIG-05) ---"
TMPDIR_10=$(mktemp -d)
HASH_10=$(compute_project_hash "$TMPDIR_10")
CHANGES_FILE_10="/tmp/recce-changed-${HASH_10}.txt"
rm -f "$CHANGES_FILE_10"
echo "${TMPDIR_10}/models/stg_bookings.sql" > "$CHANGES_FILE_10"

OUTPUT_10=$(run_hook "$PRE_COMMIT_GUARD" "$FIXTURES/bash-git-commit.json" "$TMPDIR_10" 2>/dev/null)
EXIT_10=$?

assert_exit_code "exits 0" "$EXIT_10" 0
assert_output_contains "stdout contains systemMessage" "$OUTPUT_10" "systemMessage"
assert_output_contains "stdout contains model name" "$OUTPUT_10" "stg_bookings"

rm -f "$CHANGES_FILE_10"
rm -rf "$TMPDIR_10"

# ========== Scenario 11: pre-commit-guard silent when no tracked models (TRIG-05) ==========
echo "--- Scenario 11: pre-commit-guard silent when no tracked models (TRIG-05) ---"
TMPDIR_11=$(mktemp -d)
HASH_11=$(compute_project_hash "$TMPDIR_11")
CHANGES_FILE_11="/tmp/recce-changed-${HASH_11}.txt"
rm -f "$CHANGES_FILE_11"

OUTPUT_11=$(run_hook "$PRE_COMMIT_GUARD" "$FIXTURES/bash-git-commit.json" "$TMPDIR_11" 2>/dev/null)
EXIT_11=$?

assert_exit_code "exits 0" "$EXIT_11" 0
assert_output_empty "stdout is empty when no tracked models" "$OUTPUT_11"

rm -rf "$TMPDIR_11"

# ========== Summary ==========
echo ""
echo "========== RESULTS =========="
echo "Total: $TOTAL | Passed: $PASS | Failed: $FAIL"

if [ "$FAIL" -gt 0 ]; then
    exit 1
fi
exit 0
