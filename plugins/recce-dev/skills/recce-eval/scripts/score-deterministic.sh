#!/bin/bash
# Deterministic scoring: compare per-run JSON against ground truth using jq
# Usage: bash score-deterministic.sh --run-file <path> --case-type <type> --ground-truth '<json>'
# Writes scores.deterministic into the run file in-place.
set -euo pipefail

RUN_FILE="" CASE_TYPE="" GROUND_TRUTH=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --run-file) RUN_FILE="$2"; shift 2 ;;
        --case-type) CASE_TYPE="$2"; shift 2 ;;
        --ground-truth) GROUND_TRUTH="$2"; shift 2 ;;
        *) echo "Unknown argument: $1" >&2; exit 1 ;;
    esac
done

if [ -z "$RUN_FILE" ] || [ -z "$CASE_TYPE" ] || [ -z "$GROUND_TRUTH" ]; then
    echo "Usage: score-deterministic.sh --run-file <path> --case-type <type> --ground-truth '<json>'" >&2
    exit 1
fi

if ! command -v jq &>/dev/null; then
    echo "ERROR: jq is required" >&2; exit 1
fi

if [ ! -f "$RUN_FILE" ]; then
    echo "ERROR: Run file not found: $RUN_FILE" >&2; exit 1
fi

AGENT_JSON=$(jq '.agent_output.structured_json' "$RUN_FILE")
JSON_EXTRACTED=$(jq -r '.agent_output.json_extracted' "$RUN_FILE")

if [ "$JSON_EXTRACTED" != "true" ] || [ "$AGENT_JSON" = "null" ]; then
    if [ "$CASE_TYPE" = "problem_exists" ]; then
        CHECKS='[{"name":"issue_found","expected":"true","actual":"null","result":"FAIL"},{"name":"root_cause_keywords","expected":"match","actual":"no output","result":"FAIL"},{"name":"all_tests_pass","expected":"true","actual":"null","result":"FAIL"}]'
    else
        CHECKS='[{"name":"issue_found","expected":"false","actual":"null","result":"FAIL"}]'
    fi
    TOTAL=$(echo "$CHECKS" | jq 'length')
    jq --argjson checks "$CHECKS" --argjson total "$TOTAL" \
        '.scores.deterministic = {"checks": $checks, "pass_count": 0, "fail_count": $total, "total": $total, "pass_rate": 0.0}' \
        "$RUN_FILE" > "${RUN_FILE}.tmp" && mv "${RUN_FILE}.tmp" "$RUN_FILE"
    echo "SCORED=true"; echo "PASS_COUNT=0"; echo "FAIL_COUNT=$TOTAL"; echo "TOTAL=$TOTAL"; echo "PASS_RATE=0.0"
    exit 0
fi

CHECKS="[]"

add_check() {
    local name="$1" expected="$2" actual="$3" result="$4"
    CHECKS=$(echo "$CHECKS" | jq --arg n "$name" --arg e "$expected" --arg a "$actual" --arg r "$result" \
        '. + [{"name": $n, "expected": $e, "actual": $a, "result": $r}]')
}

if [ "$CASE_TYPE" = "problem_exists" ]; then
    # issue_found == true
    ACTUAL=$(echo "$AGENT_JSON" | jq -r 'if .issue_found == null then "null" else (.issue_found | tostring) end')
    if [ "$ACTUAL" = "true" ]; then add_check "issue_found" "true" "$ACTUAL" "PASS"
    else add_check "issue_found" "true" "$ACTUAL" "FAIL"; fi

    # root_cause contains keywords
    ROOT_CAUSE=$(echo "$AGENT_JSON" | jq -r '.root_cause // "" | ascii_downcase')
    KEYWORDS=$(echo "$GROUND_TRUTH" | jq -r '.root_cause_keywords[]')
    KW_MATCH="false"
    for kw in $KEYWORDS; do
        if echo "$ROOT_CAUSE" | grep -qi "$kw"; then KW_MATCH="true"; break; fi
    done
    if [ "$KW_MATCH" = "true" ]; then add_check "root_cause_keywords" "match" "matched" "PASS"
    else add_check "root_cause_keywords" "match" "no match" "FAIL"; fi

    # impacted_models contains expected
    EXPECTED_IMPACTED=$(echo "$GROUND_TRUTH" | jq -r '.impacted_models[]')
    for model in $EXPECTED_IMPACTED; do
        FOUND=$(echo "$AGENT_JSON" | jq --arg m "$model" '[.impacted_models[]? | ascii_downcase] | index($m | ascii_downcase) != null')
        if [ "$FOUND" = "true" ]; then add_check "impacted: $model" "present" "present" "PASS"
        else add_check "impacted: $model" "present" "missing" "FAIL"; fi
    done

    # not_impacted_models NOT in impacted_models
    NOT_IMPACTED=$(echo "$GROUND_TRUTH" | jq -r '.not_impacted_models[]')
    for model in $NOT_IMPACTED; do
        FOUND=$(echo "$AGENT_JSON" | jq --arg m "$model" '[.impacted_models[]? | ascii_downcase] | index($m | ascii_downcase) != null')
        if [ "$FOUND" = "false" ]; then add_check "not_impacted: $model" "absent" "absent" "PASS"
        else add_check "not_impacted: $model" "absent" "present (false positive)" "FAIL"; fi
    done

    # affected_row_count (±20% tolerance — agents interpret "affected rows" differently)
    EXPECTED_COUNT=$(echo "$GROUND_TRUTH" | jq -r '.affected_row_count')
    ACTUAL_COUNT=$(echo "$AGENT_JSON" | jq -r '.affected_row_count // "null"')
    if [ "$ACTUAL_COUNT" = "null" ] || [ "$ACTUAL_COUNT" = "0" ]; then
        add_check "affected_row_count" "$EXPECTED_COUNT (±20%)" "$ACTUAL_COUNT" "FAIL"
    else
        WITHIN_TOLERANCE=$(jq -n --argjson e "$EXPECTED_COUNT" --argjson a "$ACTUAL_COUNT" \
            '(($a - $e) | fabs) / $e < 0.2')
        if [ "$WITHIN_TOLERANCE" = "true" ]; then
            add_check "affected_row_count" "$EXPECTED_COUNT (±20%)" "$ACTUAL_COUNT" "PASS"
        else
            add_check "affected_row_count" "$EXPECTED_COUNT (±20%)" "$ACTUAL_COUNT" "FAIL"
        fi
    fi

    # all_tests_pass
    EXPECTED_PASS=$(echo "$GROUND_TRUTH" | jq -r '.all_tests_pass | tostring')
    ACTUAL_PASS=$(echo "$AGENT_JSON" | jq -r 'if .all_tests_pass == null then "null" else (.all_tests_pass | tostring) end')
    if [ "$ACTUAL_PASS" = "$EXPECTED_PASS" ]; then add_check "all_tests_pass" "$EXPECTED_PASS" "$ACTUAL_PASS" "PASS"
    else add_check "all_tests_pass" "$EXPECTED_PASS" "$ACTUAL_PASS" "FAIL"; fi

elif [ "$CASE_TYPE" = "no_problem" ]; then
    # issue_found == false
    ACTUAL=$(echo "$AGENT_JSON" | jq -r 'if .issue_found == null then "null" else (.issue_found | tostring) end')
    if [ "$ACTUAL" = "false" ]; then add_check "issue_found" "false" "$ACTUAL" "PASS"
    else add_check "issue_found" "false" "$ACTUAL" "FAIL"; fi

    # issues array is empty
    ISSUES_LEN=$(echo "$AGENT_JSON" | jq '.issues // [] | length')
    if [ "$ISSUES_LEN" = "0" ]; then add_check "issues_empty" "0" "$ISSUES_LEN" "PASS"
    else add_check "issues_empty" "0" "$ISSUES_LEN" "FAIL"; fi

    # raw_response does not contain false positive keywords
    # Use jq index-based loop to handle multi-word keywords safely
    RAW=$(jq -r '.agent_output.raw_response // "" | ascii_downcase' "$RUN_FILE")
    FP_COUNT=$(echo "$GROUND_TRUTH" | jq '.false_positive_keywords | length')
    for i in $(seq 0 $((FP_COUNT - 1))); do
        kw=$(echo "$GROUND_TRUTH" | jq -r ".false_positive_keywords[$i]")
        if echo "$RAW" | grep -qi "$kw"; then
            add_check "no_false_positive: $kw" "absent" "found in response" "FAIL"
        else
            add_check "no_false_positive: $kw" "absent" "absent" "PASS"
        fi
    done
fi

PASS_COUNT=$(echo "$CHECKS" | jq '[.[] | select(.result == "PASS")] | length')
FAIL_COUNT=$(echo "$CHECKS" | jq '[.[] | select(.result == "FAIL")] | length')
TOTAL=$(echo "$CHECKS" | jq 'length')
if [ "$TOTAL" -gt 0 ]; then
    PASS_RATE=$(jq -n "$PASS_COUNT / $TOTAL")
else
    PASS_RATE="0.0"
fi

jq --argjson checks "$CHECKS" \
   --argjson pc "$PASS_COUNT" \
   --argjson fc "$FAIL_COUNT" \
   --argjson total "$TOTAL" \
   --arg pr "$PASS_RATE" \
    '.scores.deterministic = {"checks": $checks, "pass_count": $pc, "fail_count": $fc, "total": $total, "pass_rate": ($pr | tonumber)}' \
    "$RUN_FILE" > "${RUN_FILE}.tmp" && mv "${RUN_FILE}.tmp" "$RUN_FILE"

echo "SCORED=true"
echo "PASS_COUNT=$PASS_COUNT"
echo "FAIL_COUNT=$FAIL_COUNT"
echo "TOTAL=$TOTAL"
echo "PASS_RATE=$PASS_RATE"
