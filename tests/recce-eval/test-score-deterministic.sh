#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
SCORER="$REPO_ROOT/plugins/recce-dev/skills/recce-eval/scripts/score-deterministic.sh"
FIXTURES="$SCRIPT_DIR/fixtures"

PASS=0
FAIL=0

assert_eq() {
    local test_name="$1" expected="$2" actual="$3"
    if [ "$expected" = "$actual" ]; then
        echo "  PASS: $test_name"
        PASS=$((PASS + 1))
    else
        echo "  FAIL: $test_name (expected=$expected, actual=$actual)"
        FAIL=$((FAIL + 1))
    fi
}

GT_A='{"issue_found":true,"root_cause_keywords":["null","left join","coalesce"],"impacted_models":["orders","orders_daily_summary"],"not_impacted_models":["customers","customer_segments","customer_order_pattern"],"affected_row_count":1584,"all_tests_pass":true}'
GT_B='{"issue_found":false,"false_positive_keywords":["bug","broken","incorrect","wrong","missing data"]}'

# --- Test 1: Case A perfect pass ---
echo "Test 1: Case A perfect pass"
cp "$FIXTURES/case_a_pass.json" /tmp/test_score_a_pass.json
bash "$SCORER" --run-file /tmp/test_score_a_pass.json --case-type problem_exists --ground-truth "$GT_A"
RESULT=$(jq '.scores.deterministic' /tmp/test_score_a_pass.json)
assert_eq "pass_rate=1.0" "true" "$(echo "$RESULT" | jq '.pass_rate == 1.0')"
assert_eq "fail_count=0" "0" "$(echo "$RESULT" | jq '.fail_count')"

# --- Test 2: Case A with false positive ---
echo "Test 2: Case A with false positive"
cp "$FIXTURES/case_a_fail.json" /tmp/test_score_a_fail.json
bash "$SCORER" --run-file /tmp/test_score_a_fail.json --case-type problem_exists --ground-truth "$GT_A"
RESULT=$(jq '.scores.deterministic' /tmp/test_score_a_fail.json)
assert_eq "fail_count>0" "true" "$(echo "$RESULT" | jq '.fail_count > 0')"
assert_eq "fp_customer_segments" "FAIL" "$(echo "$RESULT" | jq -r '.checks[] | select(.name == "not_impacted: customer_segments") | .result')"
assert_eq "wrong_row_count" "FAIL" "$(echo "$RESULT" | jq -r '.checks[] | select(.name == "affected_row_count") | .result')"

# --- Test 3: Case B pass ---
echo "Test 3: Case B pass (no false positives)"
cp "$FIXTURES/case_b_pass.json" /tmp/test_score_b_pass.json
bash "$SCORER" --run-file /tmp/test_score_b_pass.json --case-type no_problem --ground-truth "$GT_B"
RESULT=$(jq '.scores.deterministic' /tmp/test_score_b_pass.json)
assert_eq "b_pass_rate=1.0" "true" "$(echo "$RESULT" | jq '.pass_rate == 1.0')"

# --- Test 4: Case B false positive ---
echo "Test 4: Case B with hallucinated issues"
cp "$FIXTURES/case_b_false_positive.json" /tmp/test_score_b_fp.json
bash "$SCORER" --run-file /tmp/test_score_b_fp.json --case-type no_problem --ground-truth "$GT_B"
RESULT=$(jq '.scores.deterministic' /tmp/test_score_b_fp.json)
assert_eq "b_fp_issue_found" "FAIL" "$(echo "$RESULT" | jq -r '.checks[] | select(.name == "issue_found") | .result')"
assert_eq "b_fp_bug_keyword" "FAIL" "$(echo "$RESULT" | jq -r '.checks[] | select(.name == "no_false_positive: bug") | .result')"
assert_eq "b_fp_incorrect_keyword" "FAIL" "$(echo "$RESULT" | jq -r '.checks[] | select(.name == "no_false_positive: incorrect") | .result')"

echo ""
echo "Results: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
