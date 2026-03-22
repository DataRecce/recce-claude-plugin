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
DRY_RUN="false" BARE_MODE="false"

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
        --bare)             BARE_MODE="true";       shift 1 ;;
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

# ========== Venv Auto-Detection ==========
# Always prefer local venv over global dbt — global dbt may be dbt Cloud CLI
# which requires dbt_cloud.yml and is incompatible with dbt-core projects.
for VENV_DIR in venv .venv; do
    if [ -f "$VENV_DIR/bin/activate" ]; then
        # shellcheck disable=SC1091
        source "$VENV_DIR/bin/activate"
        break
    fi
done

# ========== Claude CLI Resolution ==========
# Prefer ~/.local/bin/claude (standard install) over stale system-wide versions.
# Old versions (0.x) lack --output-format, --max-budget-usd, --mcp-config.
CLAUDE_BIN="claude"
for CLAUDE_PATH in "$HOME/.local/bin/claude" "$HOME/.npm-global/bin/claude"; do
    if [ -x "$CLAUDE_PATH" ]; then
        CLAUDE_BIN="$CLAUDE_PATH"
        break
    fi
done

# ========== Bare Mode Auth ==========
# --bare requires ANTHROPIC_API_KEY (skips OAuth/keychain).
# If not set, try loading from known .env locations.
if [ "$BARE_MODE" = "true" ] && [ -z "${ANTHROPIC_API_KEY:-}" ]; then
    for ENV_FILE in \
        "$HOME/Project/recce/recce-cloud-infra/recce_instance_launcher/recce_agent/.env" \
        "$HOME/.env"; do
        if [ -f "$ENV_FILE" ]; then
            KEY=$(grep "^ANTHROPIC_API_KEY=" "$ENV_FILE" | cut -d= -f2)
            if [ -n "$KEY" ]; then
                export ANTHROPIC_API_KEY="$KEY"
                break
            fi
        fi
    done
    if [ -z "${ANTHROPIC_API_KEY:-}" ]; then
        echo "ERROR: --bare requires ANTHROPIC_API_KEY but none found" >&2
        exit 1
    fi
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

CMD="$CLAUDE_BIN -p"
if [ "$BARE_MODE" = "true" ]; then
    CMD="$CMD --bare"
fi
CMD="$CMD --dangerously-skip-permissions"
CMD="$CMD --output-format json"
CMD="$CMD --max-budget-usd $MAX_BUDGET_USD"

if [ "$VARIANT" = "with-plugin" ]; then
    if [ -n "$PLUGIN_DIR" ]; then
        CMD="$CMD --plugin-dir \"$PLUGIN_DIR\""
    fi
    if [ -n "$MCP_CONFIG" ]; then
        CMD="$CMD --strict-mcp-config --mcp-config \"$MCP_CONFIG\""
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
    echo "CMD: $CMD -- <prompt>"
    exit 0
fi

# ========== Create Output Directory ==========
mkdir -p "$OUTPUT_DIR"

# ========== Invoke Claude ==========
CLAUDE_RAW_FILE="$OUTPUT_DIR/${VARIANT}_run${RUN_NUMBER}_claude_raw.json"
CLAUDE_ERR_FILE="$OUTPUT_DIR/${VARIANT}_run${RUN_NUMBER}_claude_stderr.log"

START_MS=$(python3 -c "import time; print(int(time.time()*1000))")

# Write output directly to file — avoids SIGPIPE from $() capture on large JSON
# Use -- to separate flags from prompt: --mcp-config is variadic and consumes
# subsequent positional arguments without the separator
eval "$CMD" -- '"$PROMPT_CONTENT"' > "$CLAUDE_RAW_FILE" 2>"$CLAUDE_ERR_FILE" || {
    echo '{"result":null,"error":"claude invocation failed","usage":{},"num_turns":0,"total_cost_usd":0,"duration_ms":0}' > "$CLAUDE_RAW_FILE"
}

END_MS=$(python3 -c "import time; print(int(time.time()*1000))")
ELAPSED_MS=$(( END_MS - START_MS ))

# ========== Extract Fields from claude -p JSON Output ==========
# All reads from file, not shell variable
INPUT_TOKENS=$(jq -r '.usage.input_tokens // 0' "$CLAUDE_RAW_FILE")
OUTPUT_TOKENS=$(jq -r '.usage.output_tokens // 0' "$CLAUDE_RAW_FILE")
NUM_TURNS=$(jq -r '.num_turns // 0' "$CLAUDE_RAW_FILE")
TOTAL_COST=$(jq -r '.total_cost_usd // 0' "$CLAUDE_RAW_FILE")
DURATION_MS=$(jq -r ".duration_ms // $ELAPSED_MS" "$CLAUDE_RAW_FILE")

# ========== Extract Structured JSON from Fenced Block ==========
# Use Python for reliable multi-line extraction from .result field
python3 - "$CLAUDE_RAW_FILE" "$OUTPUT_DIR/${VARIANT}_run${RUN_NUMBER}_structured.json" <<'PYEOF'
import sys, re, json

raw_file, out_file = sys.argv[1], sys.argv[2]
try:
    with open(raw_file) as f:
        data = json.load(f)
    result_text = data.get("result") or ""
    match = re.search(r'```json\s*\n([\s\S]*?)\n```', result_text)
    if match:
        obj = json.loads(match.group(1))
        with open(out_file, "w") as f:
            json.dump(obj, f)
        sys.exit(0)
except Exception:
    pass
# Write null marker if extraction failed
with open(out_file, "w") as f:
    f.write("null")
sys.exit(1)
PYEOF

JSON_EXTRACTED="false"
STRUCTURED_JSON_FILE="$OUTPUT_DIR/${VARIANT}_run${RUN_NUMBER}_structured.json"
if [ -f "$STRUCTURED_JSON_FILE" ] && [ "$(cat "$STRUCTURED_JSON_FILE")" != "null" ]; then
    if jq empty "$STRUCTURED_JSON_FILE" 2>/dev/null; then
        JSON_EXTRACTED="true"
    fi
fi

# Extract raw_response text for the per-run JSON
RAW_RESPONSE=$(jq -r '.result // ""' "$CLAUDE_RAW_FILE")

# ========== Write Per-Run JSON ==========
OUTPUT_FILE="$OUTPUT_DIR/${VARIANT}_run${RUN_NUMBER}.json"

# Use Python to assemble per-run JSON from files — avoids shell variable size limits
python3 - "$CLAUDE_RAW_FILE" "$STRUCTURED_JSON_FILE" "$OUTPUT_FILE" \
    "$SCENARIO_ID" "$VARIANT" "$RUN_NUMBER" "$TARGET" "$JSON_EXTRACTED" <<'PYEOF'
import sys, json

claude_raw_file, structured_file, output_file = sys.argv[1], sys.argv[2], sys.argv[3]
scenario_id, variant, run_number, target, json_extracted = sys.argv[4], sys.argv[5], sys.argv[6], sys.argv[7], sys.argv[8]

# Read claude raw output
try:
    with open(claude_raw_file) as f:
        claude_data = json.load(f)
except Exception:
    claude_data = {}

# Read structured JSON
structured_json = None
if json_extracted == "true":
    try:
        with open(structured_file) as f:
            structured_json = json.load(f)
    except Exception:
        json_extracted = "false"

raw_response = claude_data.get("result") or ""
usage = claude_data.get("usage", {})

per_run = {
    "meta": {
        "scenario_id": scenario_id,
        "variant": variant,
        "run_number": int(run_number),
        "timestamp": __import__("datetime").datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "target": target,
        "adapter": "unknown"
    },
    "performance": {
        "duration_ms": claude_data.get("duration_ms", 0),
        "input_tokens": usage.get("input_tokens", 0),
        "output_tokens": usage.get("output_tokens", 0),
        "total_cost_usd": claude_data.get("total_cost_usd", 0),
        "num_turns": claude_data.get("num_turns", 0),
        "tool_calls": None
    },
    "agent_output": {
        "raw_response": raw_response,
        "structured_json": structured_json,
        "json_extracted": json_extracted == "true"
    },
    "scores": {}
}

with open(output_file, "w") as f:
    json.dump(per_run, f, indent=2)
PYEOF

echo "OUTPUT_FILE=$OUTPUT_FILE"
echo "JSON_EXTRACTED=$JSON_EXTRACTED"
echo "INPUT_TOKENS=$INPUT_TOKENS"
echo "OUTPUT_TOKENS=$OUTPUT_TOKENS"
echo "NUM_TURNS=$NUM_TURNS"
echo "TOTAL_COST_USD=$TOTAL_COST"
echo "DURATION_MS=$DURATION_MS"
