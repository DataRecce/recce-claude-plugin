#!/bin/bash
# save-benchmark.sh — Persist E2E benchmark result as JSON
#
# Usage:
#   bash save-benchmark.sh \
#     --flow-version 1.0.0 \
#     --recce-version 1.40.0.dev0 \
#     --adapter snowflake \
#     --project jaffle_shop \
#     --model stg_payments \
#     --results '{"preflight":"PASS","mcp_startup":"PASS","tier1_tracking":"PASS","tier2_suggestion":"PASS","review_agent":"PASS","cleanup":"PASS"}' \
#     --performance '{"tool_uses":29,"total_tokens":23821,"duration_s":3862}' \
#     --risk-level HIGH \
#     --verdict PASS
#
# Output: KEY=VALUE lines
#   SAVED=true
#   BENCHMARK_FILE=/path/to/.claude/recce/benchmarks/2026-03-13T041957.json
#   LATEST_FILE=/path/to/.claude/recce/benchmarks/latest.json

set -euo pipefail

# ── Parse arguments ──
FLOW_VERSION=""
RECCE_VERSION=""
ADAPTER=""
PROJECT=""
MODEL=""
RESULTS=""
PERFORMANCE=""
RISK_LEVEL=""
VERDICT=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --flow-version|--recce-version|--adapter|--project|--model|--results|--performance|--risk-level|--verdict)
            [[ $# -lt 2 ]] && { echo "ERROR=Missing value for $1"; exit 1; }
            ;;&
        --flow-version)   FLOW_VERSION="$2"; shift 2 ;;
        --recce-version)  RECCE_VERSION="$2"; shift 2 ;;
        --adapter)        ADAPTER="$2"; shift 2 ;;
        --project)        PROJECT="$2"; shift 2 ;;
        --model)          MODEL="$2"; shift 2 ;;
        --results)        RESULTS="$2"; shift 2 ;;
        --performance)    PERFORMANCE="$2"; shift 2 ;;
        --risk-level)     RISK_LEVEL="$2"; shift 2 ;;
        --verdict)        VERDICT="$2"; shift 2 ;;
        *) echo "ERROR=Unknown argument: $1"; exit 1 ;;
    esac
done

# ── Validate required fields ──
for field in FLOW_VERSION RECCE_VERSION PROJECT MODEL RESULTS PERFORMANCE VERDICT; do
    if [ -z "${!field}" ]; then
        echo "ERROR=Missing required argument: --$(echo "$field" | tr '_' '-' | tr '[:upper:]' '[:lower:]')"
        exit 1
    fi
done

# ── Ensure benchmarks directory ──
BENCHMARKS_DIR=".claude/recce/benchmarks"
mkdir -p "$BENCHMARKS_DIR"

# ── Generate timestamp ──
TIMESTAMP=$(date -u +"%Y-%m-%dT%H%M%S")
TIMESTAMP_ISO=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
FILENAME="${TIMESTAMP}.json"
FILEPATH="${BENCHMARKS_DIR}/${FILENAME}"

# ── Build JSON ──
if command -v jq &>/dev/null; then
    jq -n \
        --arg ts "$TIMESTAMP_ISO" \
        --arg fv "$FLOW_VERSION" \
        --arg rv "$RECCE_VERSION" \
        --arg adapter "${ADAPTER:-unknown}" \
        --arg project "$PROJECT" \
        --arg model "$MODEL" \
        --argjson results "$RESULTS" \
        --argjson perf "$PERFORMANCE" \
        --arg risk "${RISK_LEVEL:-unknown}" \
        --arg verdict "$VERDICT" \
        '{
            timestamp: $ts,
            flow_version: $fv,
            recce_version: $rv,
            dbt_adapter: $adapter,
            project: $project,
            test_model: $model,
            results: $results,
            performance: $perf,
            risk_level: $risk,
            verdict: $verdict
        }' > "$FILEPATH"
else
    # Fallback: manual JSON (no jq)
    cat > "$FILEPATH" <<ENDJSON
{
  "timestamp": "${TIMESTAMP_ISO}",
  "flow_version": "${FLOW_VERSION}",
  "recce_version": "${RECCE_VERSION}",
  "dbt_adapter": "${ADAPTER:-unknown}",
  "project": "${PROJECT}",
  "test_model": "${MODEL}",
  "results": ${RESULTS},
  "performance": ${PERFORMANCE},
  "risk_level": "${RISK_LEVEL:-unknown}",
  "verdict": "${VERDICT}"
}
ENDJSON
fi

# ── Update latest.json (copy, not symlink — more portable) ──
cp "$FILEPATH" "${BENCHMARKS_DIR}/latest.json"

echo "SAVED=true"
echo "BENCHMARK_FILE=${FILEPATH}"
echo "LATEST_FILE=${BENCHMARKS_DIR}/latest.json"
