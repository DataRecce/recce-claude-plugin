#!/bin/bash
# Headless eval runner: setup state → invoke claude -p → teardown → write per-run JSON
# Usage: bash run-case.sh --id <id> --case-type <type> --variant <baseline|with-plugin>
#   --prompt-file <path> --setup-strategy <none|git_patch> [--patch-file <path>]
#   [--restore-files <csv>] --target <dbt-target> --max-budget-usd <num>
#   --output-dir <path> [--plugin-dir <path>] [--mcp-config <path>]
#   [--run-number <n>] [--dry-run]
set -euo pipefail

# ========== Argument Parsing ==========
SCENARIO_ID="" CASE_TYPE="" VARIANT="" PROMPT_FILE=""
SETUP_STRATEGY="" PATCH_FILE="" RESTORE_FILES=""
TARGET="" MAX_BUDGET_USD="" OUTPUT_DIR=""
PLUGIN_DIR="" MCP_CONFIG="" RUN_NUMBER="1"
DRY_RUN="false"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --id)               SCENARIO_ID="$2";      shift 2 ;;
        --case-type)        CASE_TYPE="$2";         shift 2 ;;
        --variant)          VARIANT="$2";           shift 2 ;;
        --prompt-file)      PROMPT_FILE="$2";       shift 2 ;;
        --setup-strategy)   SETUP_STRATEGY="$2";    shift 2 ;;
        --patch-file)       PATCH_FILE="$2";        shift 2 ;;
        --restore-files)    RESTORE_FILES="$2";     shift 2 ;;
        --target)           TARGET="$2";            shift 2 ;;
        --max-budget-usd)   MAX_BUDGET_USD="$2";    shift 2 ;;
        --output-dir)       OUTPUT_DIR="$2";        shift 2 ;;
        --plugin-dir)       PLUGIN_DIR="$2";        shift 2 ;;
        --mcp-config)       MCP_CONFIG="$2";        shift 2 ;;
        --run-number)       RUN_NUMBER="$2";        shift 2 ;;
        --dry-run)          DRY_RUN="true";         shift 1 ;;
        *) echo "Unknown argument: $1" >&2; exit 1 ;;
    esac
done

# ========== Required Arg Validation ==========
MISSING=""
[ -z "$SCENARIO_ID" ]     && MISSING="$MISSING --id"
[ -z "$CASE_TYPE" ]       && MISSING="$MISSING --case-type"
[ -z "$VARIANT" ]         && MISSING="$MISSING --variant"
[ -z "$PROMPT_FILE" ]     && MISSING="$MISSING --prompt-file"
[ -z "$SETUP_STRATEGY" ]  && MISSING="$MISSING --setup-strategy"
[ -z "$TARGET" ]          && MISSING="$MISSING --target"
[ -z "$MAX_BUDGET_USD" ]  && MISSING="$MISSING --max-budget-usd"
[ -z "$OUTPUT_DIR" ]      && MISSING="$MISSING --output-dir"

if [ -n "$MISSING" ]; then
    echo "ERROR: Missing required arguments:$MISSING" >&2
    exit 1
fi

if [ ! -f "$PROMPT_FILE" ]; then
    echo "ERROR: Prompt file not found: $PROMPT_FILE" >&2
    exit 1
fi

if [ "$VARIANT" != "baseline" ] && [ "$VARIANT" != "with-plugin" ]; then
    echo "ERROR: --variant must be 'baseline' or 'with-plugin', got: $VARIANT" >&2
    exit 1
fi

# ========== Teardown Trap ==========
cleanup() {
    if [ -n "$RESTORE_FILES" ]; then
        IFS=',' read -ra FILES <<< "$RESTORE_FILES"
        for f in "${FILES[@]}"; do
            f="${f#"${f%%[![:space:]]*}"}"  # trim leading whitespace
            f="${f%"${f##*[![:space:]]}"}"  # trim trailing whitespace
            if [ -n "$f" ] && git rev-parse --is-inside-work-tree &>/dev/null 2>&1; then
                git checkout -- "$f" 2>/dev/null || true
            fi
        done
    fi
}
trap cleanup EXIT

# ========== Setup Strategy ==========
if [ "$DRY_RUN" = "false" ]; then
    case "$SETUP_STRATEGY" in
        git_patch)
            if [ -z "$PATCH_FILE" ]; then
                echo "ERROR: --patch-file required when --setup-strategy=git_patch" >&2
                exit 1
            fi
            if [ ! -f "$PATCH_FILE" ]; then
                echo "ERROR: Patch file not found: $PATCH_FILE" >&2
                exit 1
            fi
            git apply --reverse "$PATCH_FILE"
            dbt run --target "$TARGET" --quiet
            ;;
        none)
            # No setup needed
            ;;
        *)
            echo "ERROR: Unknown setup strategy: $SETUP_STRATEGY" >&2
            exit 1
            ;;
    esac
fi

# ========== Detect Adapter (for prompt interpolation) ==========
detect_adapter() {
    if [ -f "profiles.yml" ]; then
        python3 - "$TARGET" <<'PYEOF'
import sys, yaml, os
target = sys.argv[1]
try:
    with open("profiles.yml") as f:
        profiles = yaml.safe_load(f)
    for profile_name, profile in profiles.items():
        outputs = profile.get("outputs", {})
        if target in outputs:
            t = outputs[target].get("type", "unknown")
            print(t)
            sys.exit(0)
    print("unknown")
except Exception:
    print("unknown")
PYEOF
    else
        echo "unknown"
    fi
}

ADAPTER_TYPE=$(detect_adapter 2>/dev/null || echo "unknown")
case "$ADAPTER_TYPE" in
    snowflake) ADAPTER_DESC="Snowflake" ;;
    bigquery)  ADAPTER_DESC="BigQuery" ;;
    redshift)  ADAPTER_DESC="Redshift" ;;
    postgres)  ADAPTER_DESC="PostgreSQL" ;;
    duckdb)    ADAPTER_DESC="DuckDB" ;;
    *)         ADAPTER_DESC="$ADAPTER_TYPE" ;;
esac

# ========== Assemble claude -p Command ==========
PROMPT_CONTENT=$(cat "$PROMPT_FILE")

CMD="claude -p"
CMD="$CMD --dangerously-skip-permissions"
CMD="$CMD --output-format json"
CMD="$CMD --max-turns 30"
CMD="$CMD --max-budget-usd $MAX_BUDGET_USD"

if [ "$VARIANT" = "with-plugin" ]; then
    if [ -n "$PLUGIN_DIR" ]; then
        CMD="$CMD --plugin-dir \"$PLUGIN_DIR\""
    fi
    if [ -n "$MCP_CONFIG" ]; then
        CMD="$CMD --mcp-config \"$MCP_CONFIG\""
    fi
fi

# ========== Dry Run Mode ==========
if [ "$DRY_RUN" = "true" ]; then
    if [ "$VARIANT" = "baseline" ]; then
        echo "PLUGIN_DIR=(none)"
    else
        echo "PLUGIN_DIR=$PLUGIN_DIR"
    fi
    echo "ADAPTER_TYPE=$ADAPTER_TYPE"
    echo "ADAPTER_DESC=$ADAPTER_DESC"
    echo "CMD: $CMD <prompt>"
    exit 0
fi

# ========== Create Output Directory ==========
mkdir -p "$OUTPUT_DIR"

# ========== Invoke Claude ==========
START_MS=$(date +%s%3N 2>/dev/null || python3 -c "import time; print(int(time.time()*1000))")

CLAUDE_JSON=$(echo "$PROMPT_CONTENT" | eval "$CMD" 2>/dev/null) || {
    CLAUDE_JSON='{"result":null,"error":"claude invocation failed","usage":{},"num_turns":0,"total_cost_usd":0,"duration_ms":0}'
}

END_MS=$(date +%s%3N 2>/dev/null || python3 -c "import time; print(int(time.time()*1000))")
ELAPSED_MS=$(( END_MS - START_MS ))

# ========== Extract Fields from claude -p JSON Output ==========
RAW_RESPONSE=$(echo "$CLAUDE_JSON" | jq -r '.result // ""')
INPUT_TOKENS=$(echo "$CLAUDE_JSON" | jq -r '.usage.input_tokens // 0')
OUTPUT_TOKENS=$(echo "$CLAUDE_JSON" | jq -r '.usage.output_tokens // 0')
NUM_TURNS=$(echo "$CLAUDE_JSON" | jq -r '.num_turns // 0')
TOTAL_COST=$(echo "$CLAUDE_JSON" | jq -r '.total_cost_usd // 0')
DURATION_MS=$(echo "$CLAUDE_JSON" | jq -r '.duration_ms // '"$ELAPSED_MS")

# ========== Extract Structured JSON from Fenced Block ==========
# Looks for ```json ... ``` in the raw response
STRUCTURED_JSON=$(echo "$RAW_RESPONSE" | sed -n '/^```json$/,/^```$/p' | sed '1d;$d' | head -1 | tr -d '\n')
# If single-line extraction got nothing, try multi-line extraction
if [ -z "$STRUCTURED_JSON" ]; then
    STRUCTURED_JSON=$(echo "$RAW_RESPONSE" | python3 - <<'PYEOF'
import sys, re, json
text = sys.stdin.read()
match = re.search(r'```json\s*\n([\s\S]*?)\n```', text)
if match:
    try:
        obj = json.loads(match.group(1))
        print(json.dumps(obj))
    except Exception:
        pass
PYEOF
)
fi

JSON_EXTRACTED="false"
STRUCTURED_JSON_FIELD="null"
if [ -n "$STRUCTURED_JSON" ]; then
    # Validate it's actually parseable JSON
    if echo "$STRUCTURED_JSON" | jq empty 2>/dev/null; then
        JSON_EXTRACTED="true"
        STRUCTURED_JSON_FIELD="$STRUCTURED_JSON"
    fi
fi

# ========== Write Per-Run JSON ==========
OUTPUT_FILE="$OUTPUT_DIR/${VARIANT}_run${RUN_NUMBER}.json"

if [ "$JSON_EXTRACTED" = "true" ]; then
    jq -n \
        --arg scenario_id "$SCENARIO_ID" \
        --arg case_type "$CASE_TYPE" \
        --arg variant "$VARIANT" \
        --arg target "$TARGET" \
        --argjson run_number "$RUN_NUMBER" \
        --arg raw_response "$RAW_RESPONSE" \
        --argjson structured_json "$STRUCTURED_JSON_FIELD" \
        --arg json_extracted "$JSON_EXTRACTED" \
        --argjson input_tokens "$INPUT_TOKENS" \
        --argjson output_tokens "$OUTPUT_TOKENS" \
        --argjson num_turns "$NUM_TURNS" \
        --argjson total_cost_usd "$TOTAL_COST" \
        --argjson duration_ms "$DURATION_MS" \
        '{
            scenario_id: $scenario_id,
            case_type: $case_type,
            variant: $variant,
            target: $target,
            run_number: $run_number,
            agent_output: {
                raw_response: $raw_response,
                structured_json: $structured_json,
                json_extracted: ($json_extracted == "true")
            },
            performance: {
                input_tokens: $input_tokens,
                output_tokens: $output_tokens,
                num_turns: $num_turns,
                total_cost_usd: $total_cost_usd,
                duration_ms: $duration_ms
            },
            scores: {}
        }' > "$OUTPUT_FILE"
else
    jq -n \
        --arg scenario_id "$SCENARIO_ID" \
        --arg case_type "$CASE_TYPE" \
        --arg variant "$VARIANT" \
        --arg target "$TARGET" \
        --argjson run_number "$RUN_NUMBER" \
        --arg raw_response "$RAW_RESPONSE" \
        --arg json_extracted "$JSON_EXTRACTED" \
        --argjson input_tokens "$INPUT_TOKENS" \
        --argjson output_tokens "$OUTPUT_TOKENS" \
        --argjson num_turns "$NUM_TURNS" \
        --argjson total_cost_usd "$TOTAL_COST" \
        --argjson duration_ms "$DURATION_MS" \
        '{
            scenario_id: $scenario_id,
            case_type: $case_type,
            variant: $variant,
            target: $target,
            run_number: $run_number,
            agent_output: {
                raw_response: $raw_response,
                structured_json: null,
                json_extracted: ($json_extracted == "true")
            },
            performance: {
                input_tokens: $input_tokens,
                output_tokens: $output_tokens,
                num_turns: $num_turns,
                total_cost_usd: $total_cost_usd,
                duration_ms: $duration_ms
            },
            scores: {}
        }' > "$OUTPUT_FILE"
fi

echo "OUTPUT_FILE=$OUTPUT_FILE"
echo "JSON_EXTRACTED=$JSON_EXTRACTED"
echo "INPUT_TOKENS=$INPUT_TOKENS"
echo "OUTPUT_TOKENS=$OUTPUT_TOKENS"
echo "NUM_TURNS=$NUM_TURNS"
echo "TOTAL_COST_USD=$TOTAL_COST"
echo "DURATION_MS=$DURATION_MS"
