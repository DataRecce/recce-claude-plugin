# Recce Eval Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a plugin evaluation skill that runs headless Claude Code sessions with and without the Recce plugin, then scores results against ground truth to measure the plugin's value.

**Architecture:** Scenario YAML files define test cases. Bash scripts handle atomic operations (run headless claude, score with jq). An LLM judge subagent evaluates reasoning quality. The SKILL.md routes subcommands and orchestrates the end-to-end flow.

**Tech Stack:** Bash scripts (jq for JSON), Claude Code CLI (`claude -p`), YAML scenarios, Claude Code plugin SDK (SKILL.md, agent frontmatter)

**Spec:** `docs/superpowers/specs/2026-03-21-recce-eval-design.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `plugins/recce-dev/skills/recce-eval/SKILL.md` | Create | Skill definition, subcommand routing, orchestration instructions |
| `plugins/recce-dev/skills/recce-eval/scenarios/ch1-null-amounts.yaml` | Create | Case A scenario: broken pipeline with NULL amounts |
| `plugins/recce-dev/skills/recce-eval/scenarios/ch1-healthy-audit.yaml` | Create | Case B scenario: healthy pipeline audit |
| `plugins/recce-dev/skills/recce-eval/patches/ch1-add-coalesce.patch` | Create | Git patch for the coalesce fix (reverse-applied to create broken state) |
| `plugins/recce-dev/skills/recce-eval/scripts/run-case.sh` | Create | Atomic runner: setup → claude -p → teardown → per-run JSON |
| `plugins/recce-dev/skills/recce-eval/scripts/score-deterministic.sh` | Create | jq-based scoring against ground truth |
| `plugins/recce-dev/skills/recce-eval/scripts/start-eval-mcp.sh` | Create | Start MCP server with eval-specific port/PID |
| `plugins/recce-dev/skills/recce-eval/scripts/stop-eval-mcp.sh` | Create | Stop eval MCP server |
| `plugins/recce-dev/skills/recce-eval/agents/eval-judge.md` | Create | LLM-as-judge subagent |
| `plugins/recce-dev/skills/recce-eval/references/scoring-rubric.md` | Create | Deterministic scoring rules + LLM judge prompt guidance |
| `plugins/recce-dev/skills/recce-eval/references/report-template.md` | Create | Report structure for the skill to follow |
| `tests/recce-eval/test-score-deterministic.sh` | Create | Tests for the deterministic scorer |
| `tests/recce-eval/test-run-case-args.sh` | Create | Argument parsing tests for run-case.sh |
| `tests/recce-eval/fixtures/` | Create | Test fixtures (mock claude output JSONs, ground truths) |

---

## Task 1: Patch File and Scenario YAMLs

The foundational data files that everything else reads.

**Files:**
- Create: `plugins/recce-dev/skills/recce-eval/patches/ch1-add-coalesce.patch`
- Create: `plugins/recce-dev/skills/recce-eval/scenarios/ch1-null-amounts.yaml`
- Create: `plugins/recce-dev/skills/recce-eval/scenarios/ch1-healthy-audit.yaml`

- [ ] **Step 1: Create patch file**

Generate the patch from the jaffle_shop_golden repo. This is the coalesce fix — reverse-applying it creates the broken state.

```bash
cd /Users/kent/Project/recce/jaffle_shop_golden
git diff 23a96d9..27db2df -- models/orders.sql > /Users/kent/Project/recce/recce-claude-plugin/plugins/recce-dev/skills/recce-eval/patches/ch1-add-coalesce.patch
```

Verify the patch has 1 hunk with 4 changed lines:

```bash
grep -c '^@@' plugins/recce-dev/skills/recce-eval/patches/ch1-add-coalesce.patch
```

Expected: `1` (single hunk).

```bash
grep -c '^[-+][^-+]' plugins/recce-dev/skills/recce-eval/patches/ch1-add-coalesce.patch
```

Expected: `4` (2 removed, 2 added).

- [ ] **Step 2: Create ch1-null-amounts.yaml (Case A)**

Write the scenario file. Copy the YAML verbatim from the spec (Section "Case A: problem_exists"). The content is in `docs/superpowers/specs/2026-03-21-recce-eval-design.md` lines 143-196.

Verify the YAML is valid:

```bash
python3 -c "import yaml; yaml.safe_load(open('plugins/recce-dev/skills/recce-eval/scenarios/ch1-null-amounts.yaml'))"
```

Expected: no error.

- [ ] **Step 3: Create ch1-healthy-audit.yaml (Case B)**

Write the scenario file. Copy the YAML verbatim from the spec (Section "Case B: no_problem"). The content is in the spec lines 204-247.

Verify:

```bash
python3 -c "import yaml; yaml.safe_load(open('plugins/recce-dev/skills/recce-eval/scenarios/ch1-healthy-audit.yaml'))"
```

- [ ] **Step 4: Commit**

```bash
cd /Users/kent/Project/recce/recce-claude-plugin
git add plugins/recce-dev/skills/recce-eval/patches/ plugins/recce-dev/skills/recce-eval/scenarios/
git commit -m "feat(recce-eval): add patch file and scenario YAMLs for Chapter 1"
```

---

## Task 2: Deterministic Scorer Script + Tests

Build and test the scorer independently before the runner. TDD — write test fixtures first.

**Files:**
- Create: `tests/recce-eval/fixtures/case_a_pass.json`
- Create: `tests/recce-eval/fixtures/case_a_fail.json`
- Create: `tests/recce-eval/fixtures/case_b_pass.json`
- Create: `tests/recce-eval/fixtures/case_b_false_positive.json`
- Create: `tests/recce-eval/test-score-deterministic.sh`
- Create: `plugins/recce-dev/skills/recce-eval/scripts/score-deterministic.sh`

- [ ] **Step 1: Create test fixtures — perfect Case A pass**

`tests/recce-eval/fixtures/case_a_pass.json`:
```json
{
  "meta": {
    "scenario_id": "ch1-null-amounts",
    "variant": "with-plugin",
    "run_number": 1,
    "timestamp": "2026-03-20T14:30:00Z",
    "target": "dev-local",
    "adapter": "duckdb"
  },
  "performance": {
    "duration_ms": 180000,
    "input_tokens": 45000,
    "output_tokens": 3200,
    "total_cost_usd": 1.23,
    "num_turns": 12,
    "tool_calls": null
  },
  "agent_output": {
    "raw_response": "Found NULL amounts in orders due to LEFT JOIN without coalesce.",
    "structured_json": {
      "issue_found": true,
      "root_cause": "LEFT JOIN without coalesce causes NULL amounts for orders without payments",
      "fix_applied": "Added coalesce(..., 0) to amount columns in orders.sql",
      "impacted_models": ["orders", "orders_daily_summary"],
      "not_impacted_models": ["customers", "customer_segments", "customer_order_pattern"],
      "affected_row_count": 1584,
      "all_tests_pass": true
    },
    "json_extracted": true
  },
  "scores": {}
}
```

- [ ] **Step 2: Create test fixture — Case A with false positive**

`tests/recce-eval/fixtures/case_a_fail.json`:
```json
{
  "meta": {
    "scenario_id": "ch1-null-amounts",
    "variant": "baseline",
    "run_number": 1,
    "timestamp": "2026-03-20T14:30:00Z",
    "target": "dev-local",
    "adapter": "duckdb"
  },
  "performance": {
    "duration_ms": 195000,
    "input_tokens": 48200,
    "output_tokens": 3500,
    "total_cost_usd": 1.45,
    "num_turns": 15,
    "tool_calls": null
  },
  "agent_output": {
    "raw_response": "Found NULL amounts. Customer segments also impacted.",
    "structured_json": {
      "issue_found": true,
      "root_cause": "LEFT JOIN causes NULL when no payment exists",
      "fix_applied": "Added coalesce wrapper",
      "impacted_models": ["orders", "orders_daily_summary", "customer_segments"],
      "not_impacted_models": ["customers", "customer_order_pattern"],
      "affected_row_count": 1500,
      "all_tests_pass": true
    },
    "json_extracted": true
  },
  "scores": {}
}
```

- [ ] **Step 3: Create test fixtures — Case B pass and false positive**

`tests/recce-eval/fixtures/case_b_pass.json`:
```json
{
  "meta": {
    "scenario_id": "ch1-healthy-audit",
    "variant": "with-plugin",
    "run_number": 1,
    "timestamp": "2026-03-20T15:00:00Z",
    "target": "dev-local",
    "adapter": "duckdb"
  },
  "performance": {
    "duration_ms": 120000,
    "input_tokens": 31000,
    "output_tokens": 2100,
    "total_cost_usd": 0.85,
    "num_turns": 8,
    "tool_calls": null
  },
  "agent_output": {
    "raw_response": "Checked October 2025 orders. All metrics look healthy.",
    "structured_json": {
      "issue_found": false,
      "issues": [],
      "evidence": "Checked row counts, NULL amounts, payment distribution, status distribution",
      "conclusion": "no_issues"
    },
    "json_extracted": true
  },
  "scores": {}
}
```

`tests/recce-eval/fixtures/case_b_false_positive.json`:
```json
{
  "meta": {
    "scenario_id": "ch1-healthy-audit",
    "variant": "baseline",
    "run_number": 1,
    "timestamp": "2026-03-20T15:00:00Z",
    "target": "dev-local",
    "adapter": "duckdb"
  },
  "performance": {
    "duration_ms": 135000,
    "input_tokens": 33000,
    "output_tokens": 2800,
    "total_cost_usd": 0.95,
    "num_turns": 10,
    "tool_calls": null
  },
  "agent_output": {
    "raw_response": "Found a potential bug in the coupon handling. The data looks incorrect for some orders.",
    "structured_json": {
      "issue_found": true,
      "issues": ["Potential coupon calculation bug"],
      "evidence": "Reviewed payment distributions",
      "conclusion": "Found potential data quality issues with coupon amounts"
    },
    "json_extracted": true
  },
  "scores": {}
}
```

- [ ] **Step 4: Write the test script**

`tests/recce-eval/test-score-deterministic.sh`:
```bash
#!/bin/bash
# Test suite for score-deterministic.sh
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
        ((PASS++))
    else
        echo "  FAIL: $test_name (expected=$expected, actual=$actual)"
        ((FAIL++))
    fi
}

# --- Test 1: Case A perfect pass ---
echo "Test 1: Case A perfect pass"
cp "$FIXTURES/case_a_pass.json" /tmp/test_score_a_pass.json
bash "$SCORER" \
    --run-file /tmp/test_score_a_pass.json \
    --case-type problem_exists \
    --ground-truth '{"issue_found":true,"root_cause_keywords":["null","left join","coalesce"],"impacted_models":["orders","orders_daily_summary"],"not_impacted_models":["customers","customer_segments","customer_order_pattern"],"affected_row_count":1584,"all_tests_pass":true}'

RESULT=$(jq '.scores.deterministic' /tmp/test_score_a_pass.json)
assert_eq "pass_rate=1.0" "1" "$(echo "$RESULT" | jq '.pass_rate == 1.0')"
assert_eq "fail_count=0" "0" "$(echo "$RESULT" | jq '.fail_count')"

# --- Test 2: Case A with false positive ---
echo "Test 2: Case A with false positive"
cp "$FIXTURES/case_a_fail.json" /tmp/test_score_a_fail.json
bash "$SCORER" \
    --run-file /tmp/test_score_a_fail.json \
    --case-type problem_exists \
    --ground-truth '{"issue_found":true,"root_cause_keywords":["null","left join","coalesce"],"impacted_models":["orders","orders_daily_summary"],"not_impacted_models":["customers","customer_segments","customer_order_pattern"],"affected_row_count":1584,"all_tests_pass":true}'

RESULT=$(jq '.scores.deterministic' /tmp/test_score_a_fail.json)
assert_eq "fail_count>0" "true" "$(echo "$RESULT" | jq '.fail_count > 0')"
# customer_segments false positive should be FAIL
assert_eq "fp_customer_segments" "FAIL" "$(echo "$RESULT" | jq -r '.checks[] | select(.name == "not_impacted: customer_segments") | .result')"

# --- Test 3: Case B pass ---
echo "Test 3: Case B pass (no false positives)"
cp "$FIXTURES/case_b_pass.json" /tmp/test_score_b_pass.json
bash "$SCORER" \
    --run-file /tmp/test_score_b_pass.json \
    --case-type no_problem \
    --ground-truth '{"issue_found":false,"false_positive_keywords":["bug","broken","incorrect","wrong","missing data"]}'

RESULT=$(jq '.scores.deterministic' /tmp/test_score_b_pass.json)
assert_eq "b_pass_rate=1.0" "1" "$(echo "$RESULT" | jq '.pass_rate == 1.0')"

# --- Test 4: Case B false positive ---
echo "Test 4: Case B with hallucinated issues"
cp "$FIXTURES/case_b_false_positive.json" /tmp/test_score_b_fp.json
bash "$SCORER" \
    --run-file /tmp/test_score_b_fp.json \
    --case-type no_problem \
    --ground-truth '{"issue_found":false,"false_positive_keywords":["bug","broken","incorrect","wrong","missing data"]}'

RESULT=$(jq '.scores.deterministic' /tmp/test_score_b_fp.json)
assert_eq "b_fp_issue_found" "FAIL" "$(echo "$RESULT" | jq -r '.checks[] | select(.name == "issue_found") | .result')"

# --- Summary ---
echo ""
echo "Results: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
```

- [ ] **Step 5: Run tests to verify they fail**

```bash
bash tests/recce-eval/test-score-deterministic.sh
```

Expected: Fails because `score-deterministic.sh` doesn't exist yet.

- [ ] **Step 6: Implement score-deterministic.sh**

`plugins/recce-dev/skills/recce-eval/scripts/score-deterministic.sh`:

```bash
#!/bin/bash
# Deterministic scoring: compare per-run JSON against ground truth using jq
# Usage: bash score-deterministic.sh --run-file <path> --case-type <type> --ground-truth '<json>'
# Writes scores.deterministic into the run file in-place.
set -euo pipefail

# ========== Argument Parsing ==========
RUN_FILE=""
CASE_TYPE=""
GROUND_TRUTH=""

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
    echo "ERROR: jq is required for deterministic scoring" >&2
    exit 1
fi

if [ ! -f "$RUN_FILE" ]; then
    echo "ERROR: Run file not found: $RUN_FILE" >&2
    exit 1
fi

# ========== Extract Agent Output ==========
AGENT_JSON=$(jq '.agent_output.structured_json' "$RUN_FILE")
JSON_EXTRACTED=$(jq -r '.agent_output.json_extracted' "$RUN_FILE")

if [ "$JSON_EXTRACTED" != "true" ] || [ "$AGENT_JSON" = "null" ]; then
    # No structured output — all checks FAIL
    if [ "$CASE_TYPE" = "problem_exists" ]; then
        CHECKS='[{"name":"issue_found","expected":true,"actual":null,"result":"FAIL"},{"name":"root_cause_keywords","expected":"match","actual":"no output","result":"FAIL"},{"name":"all_tests_pass","expected":true,"actual":null,"result":"FAIL"}]'
    else
        CHECKS='[{"name":"issue_found","expected":false,"actual":null,"result":"FAIL"}]'
    fi
    TOTAL=$(echo "$CHECKS" | jq 'length')
    jq --argjson checks "$CHECKS" --argjson total "$TOTAL" \
        '.scores.deterministic = {"checks": $checks, "pass_count": 0, "fail_count": $total, "total": $total, "pass_rate": 0.0}' \
        "$RUN_FILE" > "${RUN_FILE}.tmp" && mv "${RUN_FILE}.tmp" "$RUN_FILE"
    exit 0
fi

# ========== Scoring Logic ==========
CHECKS="[]"

add_check() {
    local name="$1" expected="$2" actual="$3" result="$4"
    CHECKS=$(echo "$CHECKS" | jq --arg n "$name" --arg e "$expected" --arg a "$actual" --arg r "$result" \
        '. + [{"name": $n, "expected": $e, "actual": $a, "result": $r}]')
}

if [ "$CASE_TYPE" = "problem_exists" ]; then
    # Check: issue_found == true
    ACTUAL=$(echo "$AGENT_JSON" | jq -r '.issue_found // "null"')
    if [ "$ACTUAL" = "true" ]; then add_check "issue_found" "true" "$ACTUAL" "PASS"
    else add_check "issue_found" "true" "$ACTUAL" "FAIL"; fi

    # Check: root_cause contains keywords (any match = PASS)
    ROOT_CAUSE=$(echo "$AGENT_JSON" | jq -r '.root_cause // "" | ascii_downcase')
    KEYWORDS=$(echo "$GROUND_TRUTH" | jq -r '.root_cause_keywords[]')
    KW_MATCH="false"
    for kw in $KEYWORDS; do
        if echo "$ROOT_CAUSE" | grep -qi "$kw"; then KW_MATCH="true"; break; fi
    done
    if [ "$KW_MATCH" = "true" ]; then add_check "root_cause_keywords" "match" "matched" "PASS"
    else add_check "root_cause_keywords" "match" "no match" "FAIL"; fi

    # Check: impacted_models contains expected (true positives)
    EXPECTED_IMPACTED=$(echo "$GROUND_TRUTH" | jq -r '.impacted_models[]')
    for model in $EXPECTED_IMPACTED; do
        FOUND=$(echo "$AGENT_JSON" | jq --arg m "$model" '[.impacted_models[]? | ascii_downcase] | index($m | ascii_downcase) != null')
        if [ "$FOUND" = "true" ]; then add_check "impacted: $model" "present" "present" "PASS"
        else add_check "impacted: $model" "present" "missing" "FAIL"; fi
    done

    # Check: not_impacted_models are NOT in impacted_models (false positive check)
    NOT_IMPACTED=$(echo "$GROUND_TRUTH" | jq -r '.not_impacted_models[]')
    for model in $NOT_IMPACTED; do
        FOUND=$(echo "$AGENT_JSON" | jq --arg m "$model" '[.impacted_models[]? | ascii_downcase] | index($m | ascii_downcase) != null')
        if [ "$FOUND" = "false" ]; then add_check "not_impacted: $model" "absent" "absent" "PASS"
        else add_check "not_impacted: $model" "absent" "present (false positive)" "FAIL"; fi
    done

    # Check: affected_row_count
    EXPECTED_COUNT=$(echo "$GROUND_TRUTH" | jq -r '.affected_row_count')
    ACTUAL_COUNT=$(echo "$AGENT_JSON" | jq -r '.affected_row_count // "null"')
    if [ "$ACTUAL_COUNT" = "$EXPECTED_COUNT" ]; then add_check "affected_row_count" "$EXPECTED_COUNT" "$ACTUAL_COUNT" "PASS"
    else add_check "affected_row_count" "$EXPECTED_COUNT" "$ACTUAL_COUNT" "FAIL"; fi

    # Check: all_tests_pass
    EXPECTED_PASS=$(echo "$GROUND_TRUTH" | jq -r '.all_tests_pass')
    ACTUAL_PASS=$(echo "$AGENT_JSON" | jq -r '.all_tests_pass // "null"')
    if [ "$ACTUAL_PASS" = "$EXPECTED_PASS" ]; then add_check "all_tests_pass" "$EXPECTED_PASS" "$ACTUAL_PASS" "PASS"
    else add_check "all_tests_pass" "$EXPECTED_PASS" "$ACTUAL_PASS" "FAIL"; fi

elif [ "$CASE_TYPE" = "no_problem" ]; then
    # Check: issue_found == false
    ACTUAL=$(echo "$AGENT_JSON" | jq -r '.issue_found // "null"')
    if [ "$ACTUAL" = "false" ]; then add_check "issue_found" "false" "$ACTUAL" "PASS"
    else add_check "issue_found" "false" "$ACTUAL" "FAIL"; fi

    # Check: issues array is empty
    ISSUES_LEN=$(echo "$AGENT_JSON" | jq '.issues // [] | length')
    if [ "$ISSUES_LEN" = "0" ]; then add_check "issues_empty" "0" "$ISSUES_LEN" "PASS"
    else add_check "issues_empty" "0" "$ISSUES_LEN" "FAIL"; fi

    # Check: raw_response does not contain false positive keywords
    RAW=$(jq -r '.agent_output.raw_response // "" | ascii_downcase' "$RUN_FILE")
    FP_KEYWORDS=$(echo "$GROUND_TRUTH" | jq -r '.false_positive_keywords[]')
    for kw in $FP_KEYWORDS; do
        if echo "$RAW" | grep -qi "$kw"; then
            add_check "no_false_positive: $kw" "absent" "found in response" "FAIL"
        else
            add_check "no_false_positive: $kw" "absent" "absent" "PASS"
        fi
    done
fi

# ========== Write Scores ==========
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
```

- [ ] **Step 7: Run tests to verify they pass**

```bash
bash tests/recce-eval/test-score-deterministic.sh
```

Expected: All 4 test groups PASS.

- [ ] **Step 8: Commit**

```bash
git add plugins/recce-dev/skills/recce-eval/scripts/score-deterministic.sh tests/recce-eval/
git commit -m "feat(recce-eval): add deterministic scorer with tests"
```

---

## Task 3: MCP Lifecycle Scripts

Start/stop eval MCP server with isolated port and PID.

**Files:**
- Create: `plugins/recce-dev/skills/recce-eval/scripts/start-eval-mcp.sh`
- Create: `plugins/recce-dev/skills/recce-eval/scripts/stop-eval-mcp.sh`

- [ ] **Step 1: Write start-eval-mcp.sh**

```bash
#!/bin/bash
# Start Recce MCP Server for eval with isolated port and PID namespace
# Does NOT delegate to start-mcp.sh — manages its own PID file.
set -euo pipefail

# ========== Port Resolution ==========
EVAL_PORT="${RECCE_EVAL_MCP_PORT:-8085}"

# ========== Project .env Loading ==========
if [ -f ".env" ]; then
    set -a
    source .env
    set +a
fi

# ========== Eval-scoped PID / Log Files ==========
EVAL_HASH=$(printf '%s-eval' "$PWD" | md5 2>/dev/null | cut -c1-8 \
    || printf '%s-eval' "$PWD" | md5sum | cut -c1-8)
PID_FILE="/tmp/recce-mcp-${EVAL_HASH}.pid"
LOG_FILE="/tmp/recce-mcp-${EVAL_HASH}.log"

# ========== Prerequisite Checks ==========
if [ ! -f "dbt_project.yml" ]; then
    echo "ERROR=NOT_DBT_PROJECT"
    echo "MESSAGE=Current directory is not a dbt project"
    exit 1
fi

if [ ! -f "target/manifest.json" ]; then
    echo "ERROR=MISSING_TARGET_ARTIFACTS"
    echo "MESSAGE=Missing target/manifest.json"
    echo "FIX=Run: dbt build"
    exit 1
fi

if ! command -v recce &>/dev/null; then
    echo "ERROR=RECCE_NOT_INSTALLED"
    echo "MESSAGE=Recce is not installed"
    echo "FIX=Run: pip install recce"
    exit 1
fi

# ========== Check if Already Running ==========
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if ps -p "$OLD_PID" > /dev/null 2>&1; then
        echo "STATUS=ALREADY_RUNNING"
        echo "PORT=$EVAL_PORT"
        echo "PID=$OLD_PID"
        echo "URL=http://localhost:$EVAL_PORT/sse"
        exit 0
    else
        rm "$PID_FILE"
    fi
fi

# ========== Check Port Availability ==========
if lsof -i :"$EVAL_PORT" > /dev/null 2>&1; then
    echo "ERROR=PORT_IN_USE"
    echo "MESSAGE=Eval port $EVAL_PORT is already in use"
    echo "FIX=Set RECCE_EVAL_MCP_PORT or stop the process using port $EVAL_PORT"
    exit 1
fi

# ========== Start MCP Server ==========
nohup recce mcp-server --sse --port "$EVAL_PORT" > "$LOG_FILE" 2>&1 &
MCP_PID=$!
echo "$MCP_PID" > "$PID_FILE"

echo "STARTING=true"
echo "PORT=$EVAL_PORT"
echo "PID=$MCP_PID"
echo "LOG_FILE=$LOG_FILE"

# Wait for startup (max 15 seconds)
for i in {1..15}; do
    sleep 1
    if ! ps -p "$MCP_PID" > /dev/null 2>&1; then
        echo "ERROR=STARTUP_FAILED"
        echo "MESSAGE=Recce MCP Server failed to start"
        echo "LOG_FILE=$LOG_FILE"
        rm -f "$PID_FILE"
        exit 1
    fi
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 2 "http://localhost:$EVAL_PORT/sse" 2>/dev/null)
    if [ "$HTTP_CODE" = "200" ]; then
        echo "STATUS=STARTED"
        echo "URL=http://localhost:$EVAL_PORT/sse"
        exit 0
    fi
done

echo "ERROR=STARTUP_TIMEOUT"
echo "MESSAGE=Recce MCP Server startup timed out (15 seconds)"
echo "LOG_FILE=$LOG_FILE"
exit 1
```

- [ ] **Step 2: Write stop-eval-mcp.sh**

```bash
#!/bin/bash
# Stop eval Recce MCP Server using eval-scoped PID file
set -euo pipefail

EVAL_HASH=$(printf '%s-eval' "$PWD" | md5 2>/dev/null | cut -c1-8 \
    || printf '%s-eval' "$PWD" | md5sum | cut -c1-8)
PID_FILE="/tmp/recce-mcp-${EVAL_HASH}.pid"
LOG_FILE="/tmp/recce-mcp-${EVAL_HASH}.log"

if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ps -p "$PID" > /dev/null 2>&1; then
        kill "$PID"
        rm -f "$PID_FILE" "$LOG_FILE"
        echo "STATUS=STOPPED"
        echo "MESSAGE=Eval MCP Server stopped (PID: $PID)"
    else
        rm -f "$PID_FILE" "$LOG_FILE"
        echo "STATUS=NOT_RUNNING"
        echo "MESSAGE=Eval MCP Server was not running (stale PID file removed)"
    fi
else
    echo "STATUS=NOT_RUNNING"
    echo "MESSAGE=Eval MCP Server is not running (no PID file)"
fi
```

- [ ] **Step 3: Verify scripts are syntactically valid**

```bash
bash -n plugins/recce-dev/skills/recce-eval/scripts/start-eval-mcp.sh
bash -n plugins/recce-dev/skills/recce-eval/scripts/stop-eval-mcp.sh
```

Expected: No syntax errors.

- [ ] **Step 4: Commit**

```bash
git add plugins/recce-dev/skills/recce-eval/scripts/start-eval-mcp.sh plugins/recce-dev/skills/recce-eval/scripts/stop-eval-mcp.sh
git commit -m "feat(recce-eval): add eval MCP server lifecycle scripts"
```

---

## Task 4: Run Case Script

The core runner that invokes `claude -p` headless.

**Files:**
- Create: `plugins/recce-dev/skills/recce-eval/scripts/run-case.sh`
- Create: `tests/recce-eval/test-run-case-args.sh`

- [ ] **Step 1: Write argument parsing test**

`tests/recce-eval/test-run-case-args.sh` — test that `run-case.sh --dry-run` outputs the resolved command without executing. This validates argument parsing and command assembly.

```bash
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
        ((PASS++))
    else
        echo "  FAIL: $test_name (expected to contain '$expected')"
        ((FAIL++))
    fi
}

# Test 1: baseline variant assembles correct command
echo "Test 1: baseline --dry-run"
OUTPUT=$(bash "$RUNNER" \
    --id test-scenario \
    --case-type problem_exists \
    --variant baseline \
    --prompt-file /tmp/test-prompt.txt \
    --setup-strategy none \
    --target dev-local \
    --max-budget-usd 1.00 \
    --output-dir /tmp/test-eval \
    --dry-run 2>&1 || true)

assert_contains "has claude -p" "claude -p" "$OUTPUT"
assert_contains "has --dangerously-skip-permissions" "--dangerously-skip-permissions" "$OUTPUT"
assert_contains "has --max-budget-usd" "--max-budget-usd" "$OUTPUT"
assert_contains "no --plugin-dir for baseline" "PLUGIN_DIR=(none)" "$OUTPUT"

# Test 2: with-plugin variant includes plugin-dir
echo "Test 2: with-plugin --dry-run"
OUTPUT=$(bash "$RUNNER" \
    --id test-scenario \
    --case-type problem_exists \
    --variant with-plugin \
    --prompt-file /tmp/test-prompt.txt \
    --setup-strategy none \
    --target dev-local \
    --max-budget-usd 1.00 \
    --output-dir /tmp/test-eval \
    --plugin-dir /fake/plugin/path \
    --mcp-config /fake/mcp.json \
    --dry-run 2>&1 || true)

assert_contains "has --plugin-dir" "--plugin-dir" "$OUTPUT"
assert_contains "has --mcp-config" "--mcp-config" "$OUTPUT"

echo ""
echo "Results: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
```

- [ ] **Step 2: Run test to verify it fails**

```bash
bash tests/recce-eval/test-run-case-args.sh
```

Expected: Fails because `run-case.sh` doesn't exist.

- [ ] **Step 3: Implement run-case.sh**

Core structure:

```bash
#!/bin/bash
# Atomic eval runner: setup state → invoke claude -p → teardown → write per-run JSON
# Usage: see --help or spec doc for full flag list
set -euo pipefail

# ========== Argument Parsing ==========
ID="" CASE_TYPE="" VARIANT="" PROMPT_FILE="" SETUP_STRATEGY="none"
PATCH_FILE="" RESTORE_FILES="" TARGET="dev-local" MAX_BUDGET="5.00"
OUTPUT_DIR="" PLUGIN_DIR="" MCP_CONFIG="" RUN_NUMBER=1 DRY_RUN=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --id) ID="$2"; shift 2 ;;
        --case-type) CASE_TYPE="$2"; shift 2 ;;
        --variant) VARIANT="$2"; shift 2 ;;
        --prompt-file) PROMPT_FILE="$2"; shift 2 ;;
        --setup-strategy) SETUP_STRATEGY="$2"; shift 2 ;;
        --patch-file) PATCH_FILE="$2"; shift 2 ;;
        --restore-files) RESTORE_FILES="$2"; shift 2 ;;
        --target) TARGET="$2"; shift 2 ;;
        --max-budget-usd) MAX_BUDGET="$2"; shift 2 ;;
        --output-dir) OUTPUT_DIR="$2"; shift 2 ;;
        --plugin-dir) PLUGIN_DIR="$2"; shift 2 ;;
        --mcp-config) MCP_CONFIG="$2"; shift 2 ;;
        --run-number) RUN_NUMBER="$2"; shift 2 ;;
        --dry-run) DRY_RUN=true; shift ;;
        *) echo "Unknown: $1" >&2; exit 1 ;;
    esac
done

# ========== Teardown Trap ==========
cleanup() {
    if [ -n "$RESTORE_FILES" ] && [ "$RESTORE_FILES" != "none" ]; then
        IFS=',' read -ra FILES <<< "$RESTORE_FILES"
        for f in "${FILES[@]}"; do
            git checkout -- "$f" 2>/dev/null || true
        done
    fi
}
trap cleanup EXIT

# ========== Setup ==========
if [ "$SETUP_STRATEGY" = "git_patch" ] && [ -n "$PATCH_FILE" ]; then
    git apply --reverse "$PATCH_FILE"
    dbt run --target "$TARGET" --quiet 2>/dev/null || true
elif [ "$SETUP_STRATEGY" = "git_checkout" ]; then
    # future: checkout specific ref
    :
fi

# ========== Assemble Claude Command ==========
CMD="claude -p \"\$(cat '$PROMPT_FILE')\" --output-format json --dangerously-skip-permissions --max-budget-usd $MAX_BUDGET"

if [ "$VARIANT" = "with-plugin" ]; then
    [ -n "$PLUGIN_DIR" ] && CMD="$CMD --plugin-dir \"$PLUGIN_DIR\""
    [ -n "$MCP_CONFIG" ] && CMD="$CMD --mcp-config \"$MCP_CONFIG\""
fi

if [ "$DRY_RUN" = "true" ]; then
    echo "DRY_RUN=true"
    echo "CMD=$CMD"
    echo "PLUGIN_DIR=${PLUGIN_DIR:-(none)}"
    echo "MCP_CONFIG=${MCP_CONFIG:-(none)}"
    exit 0
fi

# ========== Invoke ==========
mkdir -p "$OUTPUT_DIR"
RAW_OUTPUT="$OUTPUT_DIR/${VARIANT}_run${RUN_NUMBER}_raw.json"
ERROR_FILE="$OUTPUT_DIR/${VARIANT}_run${RUN_NUMBER}_stderr.log"

START_TIME=$(date +%s)
eval "$CMD" > "$RAW_OUTPUT" 2>"$ERROR_FILE" || true
END_TIME=$(date +%s)

# ========== Extract & Write Per-Run JSON ==========
OUTFILE="$OUTPUT_DIR/${VARIANT}_run${RUN_NUMBER}.json"

# Extract structured JSON from .result field
RESULT_TEXT=$(jq -r '.result // ""' "$RAW_OUTPUT" 2>/dev/null || echo "")
STRUCTURED_JSON=$(echo "$RESULT_TEXT" | sed -n '/^```json/,/^```/p' | sed '1d;$d' || echo "null")
JSON_EXTRACTED="false"
if echo "$STRUCTURED_JSON" | jq . >/dev/null 2>&1 && [ "$STRUCTURED_JSON" != "null" ] && [ -n "$STRUCTURED_JSON" ]; then
    JSON_EXTRACTED="true"
else
    STRUCTURED_JSON="null"
fi

# Extract performance from claude output
INPUT_TOKENS=$(jq '.usage.input_tokens // 0' "$RAW_OUTPUT" 2>/dev/null || echo 0)
OUTPUT_TOKENS=$(jq '.usage.output_tokens // 0' "$RAW_OUTPUT" 2>/dev/null || echo 0)
NUM_TURNS=$(jq '.num_turns // 0' "$RAW_OUTPUT" 2>/dev/null || echo 0)
COST=$(jq '.total_cost_usd // 0' "$RAW_OUTPUT" 2>/dev/null || echo 0)
DURATION_MS=$(jq '.duration_ms // 0' "$RAW_OUTPUT" 2>/dev/null || echo 0)

TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

jq -n \
    --arg sid "$ID" \
    --arg var "$VARIANT" \
    --argjson rn "$RUN_NUMBER" \
    --arg ts "$TIMESTAMP" \
    --arg tgt "$TARGET" \
    --arg adp "$(grep 'type:' profiles.yml 2>/dev/null | grep -v '#' | head -1 | sed 's/.*type: *//' | tr -d ' ')" \
    --argjson dur "$DURATION_MS" \
    --argjson it "$INPUT_TOKENS" \
    --argjson ot "$OUTPUT_TOKENS" \
    --argjson cost "$COST" \
    --argjson turns "$NUM_TURNS" \
    --arg raw "$RESULT_TEXT" \
    --argjson sj "$STRUCTURED_JSON" \
    --arg je "$JSON_EXTRACTED" \
    '{
        meta: {scenario_id: $sid, variant: $var, run_number: $rn, timestamp: $ts, target: $tgt, adapter: $adp},
        performance: {duration_ms: $dur, input_tokens: $it, output_tokens: $ot, total_cost_usd: $cost, num_turns: $turns, tool_calls: null},
        agent_output: {raw_response: $raw, structured_json: $sj, json_extracted: ($je == "true")},
        scores: {}
    }' > "$OUTFILE"

echo "RUN_COMPLETE=true"
echo "OUTPUT_FILE=$OUTFILE"
echo "JSON_EXTRACTED=$JSON_EXTRACTED"
```

- [ ] **Step 4: Run argument parsing tests**

```bash
bash tests/recce-eval/test-run-case-args.sh
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add plugins/recce-dev/skills/recce-eval/scripts/run-case.sh tests/recce-eval/test-run-case-args.sh
git commit -m "feat(recce-eval): add headless run-case script with tests"
```

---

## Task 5: LLM Judge Agent

**Files:**
- Create: `plugins/recce-dev/skills/recce-eval/agents/eval-judge.md`

- [ ] **Step 1: Write the eval-judge agent definition**

`plugins/recce-dev/skills/recce-eval/agents/eval-judge.md`:

````markdown
---
name: eval-judge
description: >
  LLM judge for recce eval — scores agent response quality, reasoning chain,
  and false positive detection. Dispatched by recce-eval skill after
  deterministic scoring completes.

  <example>
  Context: Eval skill completed deterministic scoring and needs quality assessment
  user: "Judge these eval runs: baseline and with-plugin for ch1-null-amounts"
  assistant: "I'll dispatch the eval-judge agent to score reasoning quality across both variants."
  <commentary>
  Post-scoring quality assessment is the primary trigger for this agent.
  </commentary>
  </example>
tools:
  - Read
---

You are an evaluation judge for the Recce Review Agent benchmark.

## Your Task

You receive per-run JSON files from headless Claude Code eval runs. Each file contains the agent's full response, its structured JSON output, deterministic scores, and ground truth. You score the **quality of reasoning**, not the correctness of answers (deterministic scoring already handles that).

## Input

The dispatching skill provides:
1. **Per-run JSON file paths** — Read each file. They contain `agent_output.raw_response` (full text), `agent_output.structured_json` (extracted answers), and `scores.deterministic` (already computed).
2. **Ground truth** — The known correct answers (provided in the dispatch prompt).
3. **Judge criteria** — Scenario-specific evaluation points (provided in the dispatch prompt).
4. **Case type** — `problem_exists` or `no_problem`.

## Scoring Dimensions (1-5 each)

### 1. Reasoning Chain
- **5**: Traces the exact causal path step-by-step (e.g., LEFT JOIN → missing payment records → NULL amounts → SUM aggregation affected). Examines model SQL to verify dependencies.
- **3**: Identifies the root cause but skips intermediate steps or makes minor logical leaps.
- **1**: Jumps to a conclusion without examining code or tracing dependencies.

### 2. Evidence Quality
- **5**: Every claim backed by concrete data — specific row counts from queries, NULL counts, before/after comparisons. Cites actual dbt test output.
- **3**: Some claims backed by data, others are assertions. Runs queries but doesn't always report specific numbers.
- **1**: Makes claims without running any queries or citing any data.

### 3. Fix Quality (problem_exists cases only; omit for no_problem)
- **5**: Minimal, targeted fix that addresses exactly the root cause. No unnecessary changes. Uses idiomatic SQL (e.g., COALESCE, not CASE WHEN).
- **3**: Fix works but is broader than necessary (changes multiple files when one suffices) or uses a non-idiomatic approach.
- **1**: Fix is wrong, incomplete, or introduces new issues.

### 4. False Positive Discipline
- **5**: Zero false claims about unaffected models. Correctly distinguishes direct dependencies (reads from `orders`) vs indirect (reads from `stg_orders`).
- **3**: One minor false claim, or hedges uncertainty appropriately ("might be affected, but likely not").
- **1**: Multiple false claims about unaffected models, or confidently asserts incorrect impact.

### 5. Completeness
- **5**: Addresses every prompt step. Runs pipeline, tests, investigates, fixes, re-runs, and reports with structured JSON.
- **3**: Completes most steps but skips one (e.g., doesn't re-run tests after fix).
- **1**: Addresses fewer than half the prompt steps.

## Output Format

After reading all run files, return a single fenced JSON block:

```json
{
  "runs": [
    {
      "file": "<path to per-run JSON>",
      "variant": "baseline",
      "scores": {
        "reasoning_chain": {"score": 3, "rationale": "Identified root cause but didn't trace DAG dependencies"},
        "evidence_quality": {"score": 3, "rationale": "Ran dbt test but didn't query for specific NULL counts"},
        "fix_quality": {"score": 4, "rationale": "Correct coalesce fix, minimal change"},
        "false_positive_discipline": {"score": 2, "rationale": "Incorrectly claimed customer_segments was impacted"},
        "completeness": {"score": 4, "rationale": "All steps completed except structured JSON was missing one field"}
      },
      "overall_score": 3.2,
      "notable_observations": ["Read customers.sql but didn't check whether it refs orders or stg_orders"]
    },
    {
      "file": "<path to per-run JSON>",
      "variant": "with-plugin",
      "scores": { "...same structure..." },
      "overall_score": 4.6,
      "notable_observations": ["Used lineage_diff to confirm customer_segments is NOT downstream of orders"]
    }
  ],
  "comparison_notes": "With-plugin variant used Recce MCP lineage_diff to verify DAG dependencies, avoiding the false positive that baseline made. Evidence quality was significantly higher due to row_count_diff providing concrete before/after numbers."
}
```

## Rules

- Score based on the RESPONSE CONTENT in `raw_response`, not on deterministic scores
- Be calibrated: 3 = acceptable work, 4 = good, 5 = excellent
- `comparison_notes` compares the two variants' approaches — what did the plugin enable that baseline missed?
- For `no_problem` cases, omit `fix_quality` from scores and compute `overall_score` from the remaining 4 dimensions
- `overall_score` = arithmetic mean of all applicable dimension scores
- Every `rationale` must cite specific evidence from the agent's response
````

- [ ] **Step 2: Verify frontmatter is valid YAML**

```bash
head -50 plugins/recce-dev/skills/recce-eval/agents/eval-judge.md | sed -n '/^---$/,/^---$/p' | sed '1d;$d' | python3 -c "import sys,yaml; yaml.safe_load(sys.stdin)"
```

- [ ] **Step 3: Commit**

```bash
git add plugins/recce-dev/skills/recce-eval/agents/eval-judge.md
git commit -m "feat(recce-eval): add LLM-as-judge agent definition"
```

---

## Task 6: Reference Files

**Files:**
- Create: `plugins/recce-dev/skills/recce-eval/references/scoring-rubric.md`
- Create: `plugins/recce-dev/skills/recce-eval/references/report-template.md`

- [ ] **Step 1: Write scoring-rubric.md**

`plugins/recce-dev/skills/recce-eval/references/scoring-rubric.md`:

````markdown
# Scoring Rubric

## Deterministic Scoring

### case_type: problem_exists

| Check Name | Logic | PASS condition |
|------------|-------|---------------|
| `issue_found` | exact match | agent says `true`, ground truth says `true` |
| `root_cause_keywords` | any keyword match (case-insensitive) | agent's `root_cause` contains at least one keyword from `root_cause_keywords` |
| `impacted: <model>` | set membership | each model in ground truth `impacted_models` appears in agent's `impacted_models` |
| `not_impacted: <model>` | set exclusion | each model in ground truth `not_impacted_models` does NOT appear in agent's `impacted_models` |
| `affected_row_count` | exact match | agent's count equals ground truth count |
| `all_tests_pass` | exact match | agent says `true`, ground truth says `true` |

### case_type: no_problem

| Check Name | Logic | PASS condition |
|------------|-------|---------------|
| `issue_found` | exact match | agent says `false` |
| `issues_empty` | length check | agent's `issues` array has 0 elements |
| `no_false_positive: <keyword>` | keyword absence | keyword does NOT appear in agent's `raw_response` (case-insensitive) |

### Aggregate Metrics

- `pass_rate` = pass_count / total
- `pass_count` = number of PASS checks
- `fail_count` = number of FAIL checks

## LLM Judge Scoring

See `agents/eval-judge.md` for the 5 scoring dimensions and calibration anchors.

The judge scores **reasoning quality**, not answer correctness. A run can have perfect deterministic scores but mediocre judge scores (right answer, sloppy process) or vice versa (wrong answer, excellent reasoning that was undermined by one wrong assumption).

## Adding New Scenarios

1. Create a new YAML in `scenarios/` following the schema in the spec
2. Define `ground_truth` with the appropriate checks for the `case_type`
3. Define `judge_criteria` with 2-4 scenario-specific evaluation points
4. If the scenario needs a code state change, add a patch file in `patches/`
5. Run `/recce-eval run --case <new-id>` to validate
````

- [ ] **Step 2: Write report-template.md**

`plugins/recce-dev/skills/recce-eval/references/report-template.md`:

````markdown
# Eval Report Template

Generate `report.md` following this structure. Replace `{placeholders}` with actual values.

---

```markdown
# Recce Eval Report — {timestamp}

## Environment
- **Target**: {target} ({adapter})
- **Recce version**: {recce_version}
- **Claude model**: {claude_model}
- **Runs per scenario**: {N}
- **Budget per run**: ${max_budget_usd}

## Summary

| Scenario | Variant | Det. Pass Rate | Judge Avg | Tokens (mean) | Duration (mean) | Cost (mean) |
|----------|---------|---------------|-----------|---------------|-----------------|-------------|
| {scenario_id} | baseline | {det_pass_rate}% | {judge_avg} | {tokens} | {duration}s | ${cost} |
| {scenario_id} | with-plugin | {det_pass_rate}% | {judge_avg} | {tokens} | {duration}s | ${cost} |

## Key Findings

### {scenario_name}

**Delta**: with-plugin {+/-}X% det. accuracy, {+/-}Y judge score

**Baseline failure pattern** (across {N} runs):
- {describe common failures from deterministic checks}

**With-plugin advantage**:
- {describe what Recce MCP tools enabled}

## Detailed Scores

### {scenario_id} — {variant} Run {N}

| Check | Expected | Actual | Result |
|-------|----------|--------|--------|
| {check_name} | {expected} | {actual} | {PASS/FAIL} |

**Judge scores**: reasoning={score}, evidence={score}, fix={score}, false_positive={score}, completeness={score}
**Notable**: "{observation from judge}"

## Cross-Eval Comparison
{Only if history.json has a previous entry with the same adapter}

| Metric | Previous ({prev_eval_id}) | Current | Delta |
|--------|--------------------------|---------|-------|
| with-plugin det. pass rate | {prev}% | {curr}% | {delta}% |
| with-plugin judge avg | {prev} | {curr} | {delta} |
| baseline det. pass rate | {prev}% | {curr}% | {delta}% |

{If no previous eval: "First eval run — no historical comparison available."}
```
````

- [ ] **Step 3: Commit**

```bash
git add plugins/recce-dev/skills/recce-eval/references/
git commit -m "feat(recce-eval): add scoring rubric and report template references"
```

---

## Task 7: SKILL.md — The Orchestrator

The main skill definition that ties everything together.

**Files:**
- Create: `plugins/recce-dev/skills/recce-eval/SKILL.md`

- [ ] **Step 1: Write SKILL.md**

Follow the pattern of `plugins/recce-dev/skills/mcp-e2e-validate/SKILL.md`. The full body is large — write it section by section. The key content:

**Frontmatter:**
```yaml
---
name: recce-eval
description: >
  Use when the user asks to "run eval", "recce eval", "evaluate plugin",
  "benchmark recce", "compare with plugin", "compare without plugin",
  "eval case", "score eval", "eval report", "eval history", "跑 eval",
  "評估 plugin", or wants to measure the Recce Review Agent's effectiveness
  compared to pure Claude Code without the plugin.
version: 0.1.0
---
```

**Body — Subcommand Routing (must be near the top):**

````markdown
## Subcommand Routing

Parse user input to determine which flow to execute:

- **`run --case <id> [-n N]`** → Run Flow (single scenario)
- **`run --all [-n N]`** → Run Flow (all scenarios)
- **`score <run-dir>`** → Score Flow
- **`report [eval-id]`** → Report Flow
- **`list`** → List Flow
- **`history`** → History Flow

Shared flags: `--target` (default: `dev-local`), `--adapter` (auto-detect), `--plugin-dir` (auto-resolve), `--model` (inherit from session).

### List Flow (short-circuit)

Read all YAML files in `${CLAUDE_PLUGIN_ROOT}/skills/recce-eval/scenarios/`. For each, extract `id`, `name`, `case_type`, `chapter`. Display as a table. **STOP.**

### History Flow (short-circuit)

Read `.claude/recce-eval/history.json` in the dbt project root. If missing, say "No eval history found." If present, display as a table (eval_id, timestamp, adapter, summary). **STOP.**
````

**Body — Run Flow (the core orchestration, must be detailed):**

````markdown
## Run Flow

### Step 1: Read Scenario(s)

If `--case <id>`: read `${CLAUDE_PLUGIN_ROOT}/skills/recce-eval/scenarios/<id>.yaml`.
If `--all`: read all `.yaml` files in the scenarios directory.

Parse the YAML. Extract: `id`, `case_type`, `setup`, `prompt`, `headless`, `ground_truth`, `judge_criteria`, `teardown`.

### Step 2: Detect Adapter

```bash
TARGET="${USER_TARGET:-dev-local}"
ADAPTER=$(python3 -c "
import yaml
with open('profiles.yml') as f:
    p = yaml.safe_load(f)
for proj in p.values():
    if isinstance(proj, dict) and 'outputs' in proj:
        t = proj.get('target', 'dev')
        outputs = proj['outputs']
        target_cfg = outputs.get('$TARGET', outputs.get(t, {}))
        print(target_cfg.get('type', 'unknown'))
        break
" 2>/dev/null || echo "unknown")
```

Set template variables based on adapter:
- DuckDB: `{target}` = `dev-local`, `{adapter_description}` = `DuckDB (local file database, target: dev-local)`
- Snowflake: `{target}` = `dev`, `{adapter_description}` = `Snowflake (cloud data warehouse, target: dev)`

### Step 3: Resolve Plugin Dir

```bash
eval "$(bash ${CLAUDE_PLUGIN_ROOT}/scripts/resolve-recce-root.sh)"
# Sets RECCE_PLUGIN_ROOT
```

If resolution fails, abort — cannot run with-plugin variant.

### Step 4: Create Batch Directory

```bash
EVAL_ID=$(date +"%Y%m%d-%H%M")
BATCH_DIR=".claude/recce-eval/runs/$EVAL_ID"
mkdir -p "$BATCH_DIR"
```

### Step 5: Prepare Prompt

Substitute template variables in the scenario's `prompt` field. Write to a temp file:

```bash
PROMPT_FILE="/tmp/recce-eval-prompt-${EVAL_ID}.txt"
# Write the substituted prompt to this file
```

### Step 6: Generate Eval MCP Config

```bash
EVAL_PORT=8085  # or from RECCE_EVAL_MCP_PORT
cat > /tmp/recce-eval-mcp-config.json << EOF
{
  "mcpServers": {
    "recce": {
      "type": "sse",
      "url": "http://localhost:${EVAL_PORT}/sse"
    }
  }
}
EOF
```

### Step 7: Start Eval MCP Server

```bash
bash ${CLAUDE_PLUGIN_ROOT}/skills/recce-eval/scripts/start-eval-mcp.sh
```

Parse output. If `STATUS=STARTED` or `STATUS=ALREADY_RUNNING`, proceed. If `ERROR=`, abort with error details.

### Step 8: Interleaved Run Loop

For each run number (1 to N), for each variant (baseline, with-plugin) in interleaved order:

```bash
# Create scenario output dir
mkdir -p "$BATCH_DIR/$SCENARIO_ID"

# Run baseline
bash ${CLAUDE_PLUGIN_ROOT}/skills/recce-eval/scripts/run-case.sh \
    --id "$SCENARIO_ID" \
    --case-type "$CASE_TYPE" \
    --variant baseline \
    --prompt-file "$PROMPT_FILE" \
    --setup-strategy "$SETUP_STRATEGY" \
    --patch-file "${CLAUDE_PLUGIN_ROOT}/skills/recce-eval/$PATCH_FILE" \
    --restore-files "$RESTORE_FILES" \
    --target "$TARGET" \
    --max-budget-usd "$MAX_BUDGET" \
    --output-dir "$BATCH_DIR/$SCENARIO_ID" \
    --run-number "$RUN_NUM"

# Score baseline
bash ${CLAUDE_PLUGIN_ROOT}/skills/recce-eval/scripts/score-deterministic.sh \
    --run-file "$BATCH_DIR/$SCENARIO_ID/baseline_run${RUN_NUM}.json" \
    --case-type "$CASE_TYPE" \
    --ground-truth '$GROUND_TRUTH_JSON'

# Run with-plugin
bash ${CLAUDE_PLUGIN_ROOT}/skills/recce-eval/scripts/run-case.sh \
    --id "$SCENARIO_ID" \
    --case-type "$CASE_TYPE" \
    --variant with-plugin \
    --prompt-file "$PROMPT_FILE" \
    --setup-strategy "$SETUP_STRATEGY" \
    --patch-file "${CLAUDE_PLUGIN_ROOT}/skills/recce-eval/$PATCH_FILE" \
    --restore-files "$RESTORE_FILES" \
    --target "$TARGET" \
    --max-budget-usd "$MAX_BUDGET" \
    --output-dir "$BATCH_DIR/$SCENARIO_ID" \
    --plugin-dir "$RECCE_PLUGIN_ROOT" \
    --mcp-config /tmp/recce-eval-mcp-config.json \
    --run-number "$RUN_NUM"

# Score with-plugin
bash ${CLAUDE_PLUGIN_ROOT}/skills/recce-eval/scripts/score-deterministic.sh \
    --run-file "$BATCH_DIR/$SCENARIO_ID/with-plugin_run${RUN_NUM}.json" \
    --case-type "$CASE_TYPE" \
    --ground-truth '$GROUND_TRUTH_JSON'
```

### Step 9: Stop Eval MCP Server

```bash
bash ${CLAUDE_PLUGIN_ROOT}/skills/recce-eval/scripts/stop-eval-mcp.sh
```

### Step 10: Dispatch LLM Judge

Use the Agent tool to dispatch `recce-dev:eval-judge` with a prompt that includes:
- Paths to all per-run JSON files for this scenario
- Ground truth from the scenario YAML
- Judge criteria from the scenario YAML
- The case_type

Parse the judge's JSON output. For each run, merge `scores.llm_judge` into the corresponding per-run JSON file.

### Step 11: Write meta.json

```bash
# Write meta.json to batch dir with eval_id, timestamp, adapter, scenarios, etc.
```

### Step 12: Generate Report

Read all per-run JSONs (now with both score layers). Follow the structure in `references/report-template.md`. Read `history.json` for cross-eval comparison if available. Write `report.md` to the batch dir.

### Step 13: Update History

Append a summary entry to `.claude/recce-eval/history.json`. Update the `latest` symlink:

```bash
ln -sfn "$EVAL_ID" .claude/recce-eval/runs/latest
```

### Step 14: Print Summary

Output the summary table and key findings to the user.
````

**Body — Score Flow:**

````markdown
## Score Flow (`score <run-dir>`)

Re-score existing runs without re-running them. Useful after updating scoring logic.

1. Read all `*_run*.json` files in the specified directory
2. For each, determine `case_type` from `meta.scenario_id` → read the corresponding scenario YAML
3. Re-run `score-deterministic.sh` on each file
4. Re-dispatch `eval-judge` on each scenario's runs
5. Regenerate `report.md`
````

**Body — Report Flow:**

````markdown
## Report Flow (`report [eval-id]`)

Regenerate report from existing scored runs without re-scoring.

1. If no eval-id, read `.claude/recce-eval/runs/latest/` symlink target
2. Read all per-run JSONs (must already have `scores.deterministic` and `scores.llm_judge`)
3. Generate `report.md` following `references/report-template.md`
````

**Body — Common Mistakes (copy pattern from mcp-e2e-validate):**

````markdown
## Common Mistakes

- **Shell variables do not persist**: Each Bash tool invocation starts a fresh shell. Re-run `resolve-recce-root.sh` in every step that needs `RECCE_PLUGIN_ROOT`.
- **Platform-specific `md5`**: macOS uses `md5`, Linux uses `md5sum`. Scripts handle both.
- **MCP config precedence**: If `--mcp-config` does not override plugin `.mcp.json` for the `"recce"` key, use `--strict-mcp-config` and add `recce-docs` to the eval config explicitly.
- **Interleaved order matters**: Run baseline→plugin→baseline→plugin, not all baselines then all plugins. Reduces systematic bias.
- **Teardown is trap-based**: `run-case.sh` restores files even if `claude -p` fails. Do not add separate teardown calls in SKILL.md.
- **Ground truth as JSON string**: When passing `--ground-truth` to `score-deterministic.sh`, the value must be a valid JSON string. Use single quotes around it in bash.
- **Adapter detection**: Use Python+PyYAML to parse profiles.yml, not grep. The target's adapter type depends on which target is active.
````

- [ ] **Step 2: Verify SKILL.md frontmatter**

```bash
head -20 plugins/recce-dev/skills/recce-eval/SKILL.md | sed -n '/^---$/,/^---$/p' | sed '1d;$d' | python3 -c "import sys,yaml; yaml.safe_load(sys.stdin)"
```

- [ ] **Step 3: Commit**

```bash
git add plugins/recce-dev/skills/recce-eval/SKILL.md
git commit -m "feat(recce-eval): add SKILL.md orchestrator with subcommand routing"
```

---

## Task 8: Integration Validation

Verify everything fits together before declaring done.

**Files:**
- Modify: `plugins/recce-dev/.claude-plugin/plugin.json` (bump version)

- [ ] **Step 1: Verify complete file structure**

```bash
find plugins/recce-dev/skills/recce-eval -type f | sort
```

Expected:
```
plugins/recce-dev/skills/recce-eval/SKILL.md
plugins/recce-dev/skills/recce-eval/agents/eval-judge.md
plugins/recce-dev/skills/recce-eval/patches/ch1-add-coalesce.patch
plugins/recce-dev/skills/recce-eval/references/report-template.md
plugins/recce-dev/skills/recce-eval/references/scoring-rubric.md
plugins/recce-dev/skills/recce-eval/scenarios/ch1-healthy-audit.yaml
plugins/recce-dev/skills/recce-eval/scenarios/ch1-null-amounts.yaml
plugins/recce-dev/skills/recce-eval/scripts/run-case.sh
plugins/recce-dev/skills/recce-eval/scripts/score-deterministic.sh
plugins/recce-dev/skills/recce-eval/scripts/start-eval-mcp.sh
plugins/recce-dev/skills/recce-eval/scripts/stop-eval-mcp.sh
```

- [ ] **Step 2: Run all tests**

```bash
bash tests/recce-eval/test-score-deterministic.sh
bash tests/recce-eval/test-run-case-args.sh
```

Expected: Both pass.

- [ ] **Step 3: Verify all scripts have no syntax errors**

```bash
for f in plugins/recce-dev/skills/recce-eval/scripts/*.sh; do
    echo -n "$f: "
    bash -n "$f" && echo "OK" || echo "SYNTAX ERROR"
done
```

- [ ] **Step 4: Verify all YAML files parse**

```bash
for f in plugins/recce-dev/skills/recce-eval/scenarios/*.yaml; do
    echo -n "$f: "
    python3 -c "import yaml; yaml.safe_load(open('$f'))" && echo "OK" || echo "PARSE ERROR"
done
```

- [ ] **Step 5: Validate --mcp-config precedence assumption**

Start the eval MCP server on port 8085, then test whether `--mcp-config` overrides the plugin's `.mcp.json`:

```bash
# Start eval MCP
bash plugins/recce-dev/skills/recce-eval/scripts/start-eval-mcp.sh

# Test: does --mcp-config override plugin's .mcp.json for the "recce" key?
claude -p "List your available MCP servers and their URLs. Output as JSON." \
    --output-format json \
    --dangerously-skip-permissions \
    --max-budget-usd 0.50 \
    --plugin-dir plugins/recce \
    --mcp-config /tmp/recce-eval-mcp-config.json \
    > /tmp/mcp-test-output.json 2>/dev/null

# Check if the recce MCP URL points to port 8085 (eval) not 8081 (default)
jq -r '.result' /tmp/mcp-test-output.json | grep -q "8085" && echo "PASS: --mcp-config overrides plugin" || echo "FAIL: plugin .mcp.json takes precedence — use --strict-mcp-config"

# Cleanup
bash plugins/recce-dev/skills/recce-eval/scripts/stop-eval-mcp.sh
```

If this fails, update `run-case.sh` to use `--strict-mcp-config` and include `recce-docs` in the eval MCP config.

- [ ] **Step 6: Bump plugin version**

Edit `plugins/recce-dev/.claude-plugin/plugin.json`: change `"version": "0.1.0"` to `"version": "0.2.0"`.

- [ ] **Step 7: Final commit**

```bash
git add plugins/recce-dev/.claude-plugin/plugin.json
git commit -m "chore(recce-dev): bump version to 0.2.0 for recce-eval skill"
```

---

## Task Summary

| Task | Description | Dependencies |
|------|-------------|-------------|
| 1 | Patch + Scenarios | None |
| 2 | Deterministic Scorer + Tests | None |
| 3 | MCP Lifecycle Scripts | None |
| 4 | Run Case Script + Tests | None |
| 5 | LLM Judge Agent | None |
| 6 | Reference Files | None |
| 7 | SKILL.md Orchestrator | Tasks 1-6 (reads all files) |
| 8 | Integration Validation | Tasks 1-7 |

Tasks 1-6 are independent and can be parallelized. Task 7 depends on all of them. Task 8 is the final verification.
