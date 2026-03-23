#!/bin/bash
# SessionStart hook: detect dbt environment, check tools, auto-start MCP
# Output: KEY=VALUE lines injected into Claude's context
# Exit: Always 0 (resilient wrapper — never blocks session)

PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/../.." && pwd)}"

# ========== dbt Project Detection ==========

if [ ! -f "dbt_project.yml" ]; then
    echo "DBT_PROJECT=false"
    exit 0
fi

# ========== dbt Project Found ==========

echo "DBT_PROJECT=true"
PROJECT_NAME=$(grep -E "^name:" dbt_project.yml | head -1 | sed 's/name:[[:space:]]*//' | tr -d "'" | tr -d '"')
echo "DBT_PROJECT_NAME=$PROJECT_NAME"

# ========== Tool Availability Checks (informational) ==========

# dbt check (informational only)
if command -v dbt &>/dev/null; then
    echo "DBT_INSTALLED=true"
else
    echo "DBT_INSTALLED=false"
fi

# recce check (gates MCP auto-start)
if command -v recce &>/dev/null; then
    RECCE_INSTALLED=true
    echo "RECCE_INSTALLED=true"
else
    RECCE_INSTALLED=false
    echo "RECCE_INSTALLED=false"
    echo "FIX=Activate your venv or run: pip install 'recce[mcp]'"
fi

# ========== Artifact Checks ==========

# target artifacts (gates MCP auto-start)
if [ -f "target/manifest.json" ]; then
    TARGET_EXISTS=true
    echo "TARGET_EXISTS=true"
else
    TARGET_EXISTS=false
    echo "TARGET_EXISTS=false"
fi

# target-base artifacts (determines single-env warning)
if [ -f "target-base/manifest.json" ]; then
    echo "TARGET_BASE_EXISTS=true"
else
    echo "TARGET_BASE_EXISTS=false"
fi

# ========== Impact Analysis Rule (mandatory) ==========
# Injected into context so the agent uses impact_analysis for all impact determination
echo "IMPACT_RULE=MANDATORY: When determining which dbt models are impacted by a code change, you MUST call the impact_analysis MCP tool BEFORE reporting impacted_models. Do NOT determine impact by reading code, inferring from ref() calls, or guessing from model names — these approaches confuse upstream dependencies with downstream impact and produce false positives. impact_analysis uses the lineage DAG to deterministically classify models as impacted (modified + downstream) or not-impacted. Its impacted_models and not_impacted_models lists are authoritative — copy them directly into your output. When the response includes value_diff.rows_changed for a model, use that number as the affected row count — it is the exact count of rows whose values differ between base and current."

# ========== MCP Auto-Start Decision ==========
# Only attempt if: recce installed AND target/manifest.json exists

if [ "$RECCE_INSTALLED" = "true" ] && [ "$TARGET_EXISTS" = "true" ]; then
    # Delegate to start-mcp.sh — it handles PID, settings, health polling
    MCP_OUTPUT=$(bash "$PLUGIN_ROOT/scripts/start-mcp.sh" 2>/dev/null)
    MCP_EXIT=$?

    # Parse start-mcp.sh output
    MCP_STATUS=$(echo "$MCP_OUTPUT" | grep "^STATUS=" | cut -d= -f2)
    MCP_PORT_VAL=$(echo "$MCP_OUTPUT" | grep "^PORT=" | cut -d= -f2)

    if [ "$MCP_STATUS" = "STARTED" ] || [ "$MCP_STATUS" = "ALREADY_RUNNING" ]; then
        echo "MCP_STARTED=true"
        echo "MCP_PORT=$MCP_PORT_VAL"
    else
        echo "MCP_STARTED=false"
        # Forward error/fix lines from start-mcp.sh
        echo "$MCP_OUTPUT" | grep -E "^(ERROR|FIX|MESSAGE)="
    fi

    # Forward single-env and warning lines from start-mcp.sh
    echo "$MCP_OUTPUT" | grep -E "^(SINGLE_ENV_MODE|WARNING)=" 2>/dev/null
else
    echo "MCP_STARTED=false"
    # Explain why MCP was skipped
    if [ "$RECCE_INSTALLED" != "true" ]; then
        echo "MCP_SKIP_REASON=recce not installed"
    elif [ "$TARGET_EXISTS" != "true" ]; then
        echo "MCP_SKIP_REASON=no target/manifest.json"
        echo "FIX=Run: dbt docs generate"
    fi
fi

exit 0
