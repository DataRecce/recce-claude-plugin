#!/bin/bash
# run-batch.sh — Batch eval runner: render prompts → interleaved run loop → score
#
# Encapsulates SKILL.md Steps 5-7 into a single background-capable script.
# Caller (SKILL.md) handles Steps 1-4 (parse scenarios, bootstrap project,
# detect adapter, create batch dir) and Steps 8-12 (judge, meta, report).
#
# Usage:
#   bash run-batch.sh \
#     --scenarios scenario1.yaml,scenario2.yaml \
#     --batch-dir /path/to/batch \
#     --eval-id 20260404-1530 \
#     --skill-dir /path/to/recce-eval \
#     --recce-plugin /path/to/recce-plugin \
#     --target dev \
#     --adapter-desc "DuckDB (local file database, target: dev)" \
#     [--mcp-config /tmp/mcp.json] \
#     [-n 3] [--model claude-sonnet-4-20250514] [--mode real-world] \
#     [--no-bare] [--project-dir /path/to/project]
#
# Output:
#   - Per-run JSONs: $BATCH_DIR/<scenario-id>/<variant>_run<N>.json (via run-case.sh)
#   - Deterministic scores merged into per-run JSONs (via score-deterministic.sh)
#   - Batch summary: $BATCH_DIR/batch-summary.json
#   - Progress lines to stdout
set -euo pipefail

# ========== Argument Parsing ==========
SCENARIOS="" BATCH_DIR="" EVAL_ID="" SKILL_DIR="" RECCE_PLUGIN=""
TARGET="" ADAPTER_DESC="" MCP_CONFIG="" RUNS=1 MODEL="" MODE="real-world"
NO_BARE="" PROJECT_DIR=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --scenarios)     SCENARIOS="$2";     shift 2 ;;
        --batch-dir)     BATCH_DIR="$2";     shift 2 ;;
        --eval-id)       EVAL_ID="$2";       shift 2 ;;
        --skill-dir)     SKILL_DIR="$2";     shift 2 ;;
        --recce-plugin)  RECCE_PLUGIN="$2";  shift 2 ;;
        --target)        TARGET="$2";        shift 2 ;;
        --adapter-desc)  ADAPTER_DESC="$2";  shift 2 ;;
        --mcp-config)    MCP_CONFIG="$2";    shift 2 ;;
        -n|--runs)       RUNS="$2";          shift 2 ;;
        --model)         MODEL="$2";         shift 2 ;;
        --mode)          MODE="$2";          shift 2 ;;
        --no-bare)       NO_BARE="true";     shift 1 ;;
        --project-dir)   PROJECT_DIR="$2";   shift 2 ;;
        *) echo "ERROR: Unknown argument: $1" >&2; exit 1 ;;
    esac
done

# ========== Validation ==========
MISSING=""
[ -z "$SCENARIOS" ]    && MISSING="$MISSING --scenarios"
[ -z "$BATCH_DIR" ]    && MISSING="$MISSING --batch-dir"
[ -z "$EVAL_ID" ]      && MISSING="$MISSING --eval-id"
[ -z "$SKILL_DIR" ]    && MISSING="$MISSING --skill-dir"
[ -z "$RECCE_PLUGIN" ] && MISSING="$MISSING --recce-plugin"
[ -z "$TARGET" ]       && MISSING="$MISSING --target"
[ -z "$ADAPTER_DESC" ] && MISSING="$MISSING --adapter-desc"

if [ -n "$MISSING" ]; then
    echo "ERROR: Missing required arguments:$MISSING" >&2
    exit 1
fi

for cmd in yq jq python3; do
    if ! command -v "$cmd" &>/dev/null; then
        echo "ERROR: Required command not found: $cmd" >&2
        exit 1
    fi
done

IFS=',' read -ra SCENARIO_FILES <<< "$SCENARIOS"
for f in "${SCENARIO_FILES[@]}"; do
    if [ ! -f "$f" ]; then
        echo "ERROR: Scenario file not found: $f" >&2
        exit 1
    fi
done

mkdir -p "$BATCH_DIR"

# ========== Phase 1: Render Prompts ==========
echo "=== Phase 1: Rendering prompts for ${#SCENARIO_FILES[@]} scenarios ==="

for SCENARIO_FILE in "${SCENARIO_FILES[@]}"; do
    SCENARIO_ID=$(yq -r '.id' "$SCENARIO_FILE")
    TEMPLATE=$(yq -r '.prompt.template // ""' "$SCENARIO_FILE")
    PROMPT_FILE="/tmp/recce-eval-prompt-${EVAL_ID}-${SCENARIO_ID}.txt"

    if [ -n "$TEMPLATE" ]; then
        # v2: template + vars substituted by render-prompt.py
        python3 "${SKILL_DIR}/scripts/render-prompt.py" \
            "${SKILL_DIR}/${TEMPLATE}" "$SCENARIO_FILE" \
            --var "adapter_description=${ADAPTER_DESC}" \
            --var "target=${TARGET}" \
            > "$PROMPT_FILE"
    else
        # v1: inline prompt with runtime variable substitution
        PROMPT_TEXT=$(yq -r '.prompt' "$SCENARIO_FILE")
        PROMPT_TEXT="${PROMPT_TEXT//\{adapter_description\}/$ADAPTER_DESC}"
        PROMPT_TEXT="${PROMPT_TEXT//\{target\}/$TARGET}"
        printf '%s' "$PROMPT_TEXT" > "$PROMPT_FILE"
    fi

    echo "  [ok] $SCENARIO_ID"
done

# ========== Phase 2: Interleaved Run Loop ==========
# Order: for each run_num → for each scenario → baseline then with-plugin.
# Interleaving reduces systematic bias from cache warming or temporal effects.
TOTAL_RUNS=$(( ${#SCENARIO_FILES[@]} * RUNS * 2 ))
echo ""
echo "=== Phase 2: Running $TOTAL_RUNS cases (${#SCENARIO_FILES[@]} scenarios x $RUNS runs x 2 variants) ==="
echo ""

RUN_INDEX=0
SUCCEEDED=0
FAILED=0
BATCH_START=$(date +%s)

for (( run_num=1; run_num<=RUNS; run_num++ )); do
    for SCENARIO_FILE in "${SCENARIO_FILES[@]}"; do
        # Parse scenario metadata once per scenario per run_num
        SCENARIO_ID=$(yq -r '.id' "$SCENARIO_FILE")
        CASE_TYPE=$(yq -r '.case_type' "$SCENARIO_FILE")
        SETUP_STRATEGY=$(yq -r '.setup.strategy' "$SCENARIO_FILE")
        PATCH_REL=$(yq -r '.setup.patch_reverse_file // ""' "$SCENARIO_FILE")
        SKIP_CTX=$(yq -r '.setup.skip_context // "false"' "$SCENARIO_FILE")
        RESTORE=$(yq -r '.teardown.restore_files // [] | join(",")' "$SCENARIO_FILE")
        MAX_BUDGET=$(yq -r '.headless.max_budget_usd' "$SCENARIO_FILE")
        GT_JSON=$(yq -o=json '.ground_truth' "$SCENARIO_FILE" | jq -c .)
        PROMPT_FILE="/tmp/recce-eval-prompt-${EVAL_ID}-${SCENARIO_ID}.txt"

        mkdir -p "$BATCH_DIR/$SCENARIO_ID"

        for VARIANT in baseline with-plugin; do
            RUN_INDEX=$(( RUN_INDEX + 1 ))
            CASE_START=$(date +%s)
            echo "[${RUN_INDEX}/${TOTAL_RUNS}] ${SCENARIO_ID} ${VARIANT} run${run_num} — starting"

            # Build run-case.sh argument list
            RUN_ARGS=(
                --id "$SCENARIO_ID"
                --case-type "$CASE_TYPE"
                --variant "$VARIANT"
                --prompt-file "$PROMPT_FILE"
                --setup-strategy "$SETUP_STRATEGY"
                --target "$TARGET"
                --max-budget-usd "$MAX_BUDGET"
                --output-dir "$BATCH_DIR/$SCENARIO_ID"
                --run-number "$run_num"
            )

            # Isolation mode: --bare (default) or --no-bare
            if [ -z "$NO_BARE" ]; then
                RUN_ARGS+=(--bare)
            else
                RUN_ARGS+=(--no-bare --no-clean-profile)
            fi

            # Patch file (only for git_patch strategy)
            if [ "$SETUP_STRATEGY" = "git_patch" ] && [ -n "$PATCH_REL" ] && [ "$PATCH_REL" != "null" ]; then
                RUN_ARGS+=(--patch-file "${SKILL_DIR}/${PATCH_REL}")
            fi
            [ -n "$RESTORE" ] && RUN_ARGS+=(--restore-files "$RESTORE")

            # With-plugin variant: inject plugin + MCP
            if [ "$VARIANT" = "with-plugin" ]; then
                RUN_ARGS+=(--plugin-dir "$RECCE_PLUGIN")
                [ -n "$MCP_CONFIG" ] && RUN_ARGS+=(--mcp-config "$MCP_CONFIG")
            fi

            # Optional flags
            [ -n "$MODEL" ] && RUN_ARGS+=(--model "$MODEL")
            RUN_ARGS+=(--mode "$MODE")
            [ -n "$PROJECT_DIR" ] && RUN_ARGS+=(--project-dir "$PROJECT_DIR")
            [ "$SKIP_CTX" = "true" ] && RUN_ARGS+=(--skip-setup-context)

            # Execute run-case.sh
            RUN_FILE="$BATCH_DIR/$SCENARIO_ID/${VARIANT}_run${run_num}.json"
            RUN_OUTPUT=""
            if RUN_OUTPUT=$(bash "${SKILL_DIR}/scripts/run-case.sh" "${RUN_ARGS[@]}" 2>&1); then
                # Parse KEY=VALUE output from run-case.sh
                COST=$(echo "$RUN_OUTPUT" | grep "^TOTAL_COST_USD=" | cut -d= -f2 || echo "?")
                DURATION=$(echo "$RUN_OUTPUT" | grep "^DURATION_MS=" | cut -d= -f2 || echo "0")
                JSON_OK=$(echo "$RUN_OUTPUT" | grep "^JSON_EXTRACTED=" | cut -d= -f2 || echo "?")

                # Score immediately after each run
                SCORE_OUTPUT=""
                if SCORE_OUTPUT=$(bash "${SKILL_DIR}/scripts/score-deterministic.sh" \
                    --run-file "$RUN_FILE" \
                    --case-type "$CASE_TYPE" \
                    --ground-truth "$GT_JSON" 2>&1); then
                    PASS_RATE=$(echo "$SCORE_OUTPUT" | grep "^PASS_RATE=" | cut -d= -f2 || echo "?")
                else
                    PASS_RATE="score-error"
                fi

                DURATION_SEC=$(( ${DURATION:-0} / 1000 ))
                echo "[${RUN_INDEX}/${TOTAL_RUNS}] ${SCENARIO_ID} ${VARIANT} run${run_num} — DONE cost=\$${COST} duration=${DURATION_SEC}s json=${JSON_OK} pass_rate=${PASS_RATE}"
                SUCCEEDED=$(( SUCCEEDED + 1 ))
            else
                CASE_END=$(date +%s)
                WALL_SEC=$(( CASE_END - CASE_START ))
                echo "[${RUN_INDEX}/${TOTAL_RUNS}] ${SCENARIO_ID} ${VARIANT} run${run_num} — FAILED after ${WALL_SEC}s"
                echo "$RUN_OUTPUT" | tail -3 | sed 's/^/  > /'
                FAILED=$(( FAILED + 1 ))
            fi
        done
    done
done

# ========== Phase 3: Summary ==========
BATCH_END=$(date +%s)
BATCH_DURATION=$(( BATCH_END - BATCH_START ))
BATCH_MINUTES=$(( BATCH_DURATION / 60 ))
BATCH_SECONDS=$(( BATCH_DURATION % 60 ))

echo ""
echo "=== BATCH COMPLETE ==="
echo "Eval ID:    $EVAL_ID"
echo "Succeeded:  $SUCCEEDED / $TOTAL_RUNS"
echo "Failed:     $FAILED / $TOTAL_RUNS"
echo "Duration:   ${BATCH_MINUTES}m ${BATCH_SECONDS}s"
echo "Output:     $BATCH_DIR"

# Write machine-readable summary for SKILL.md Steps 8-12
SCENARIO_IDS="[]"
for SCENARIO_FILE in "${SCENARIO_FILES[@]}"; do
    SID=$(yq -r '.id' "$SCENARIO_FILE")
    SCENARIO_IDS=$(echo "$SCENARIO_IDS" | jq --arg id "$SID" '. + [$id]')
done

jq -n \
    --arg eval_id "$EVAL_ID" \
    --argjson total "$TOTAL_RUNS" \
    --argjson succeeded "$SUCCEEDED" \
    --argjson failed "$FAILED" \
    --argjson runs "$RUNS" \
    --argjson scenarios "$SCENARIO_IDS" \
    --arg batch_dir "$BATCH_DIR" \
    --arg completed_at "$(date -u +"%Y-%m-%dT%H:%M:%SZ")" \
    --argjson duration_sec "$BATCH_DURATION" \
    '{
        eval_id: $eval_id,
        total_runs: $total,
        succeeded: $succeeded,
        failed: $failed,
        runs_per_scenario: $runs,
        scenarios: $scenarios,
        batch_dir: $batch_dir,
        completed_at: $completed_at,
        duration_sec: $duration_sec
    }' > "$BATCH_DIR/batch-summary.json"

echo "Summary:    $BATCH_DIR/batch-summary.json"
