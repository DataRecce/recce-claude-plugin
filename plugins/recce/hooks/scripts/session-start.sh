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

# ========== MCP Readiness Check ==========
# MCP server is now stdio-based (.mcp.json) — Claude Code spawns it on demand.
# No external server to start. Just report whether prerequisites are met.

if [ "$RECCE_INSTALLED" = "true" ] && [ "$TARGET_EXISTS" = "true" ]; then
    echo "MCP_READY=true"
else
    echo "MCP_READY=false"
    if [ "$RECCE_INSTALLED" != "true" ]; then
        echo "MCP_SKIP_REASON=recce not installed"
        echo "FIX=Activate your venv or run: pip install recce"
    elif [ "$TARGET_EXISTS" != "true" ]; then
        echo "MCP_SKIP_REASON=no target/manifest.json"
        echo "FIX=Run: dbt docs generate"
    fi
fi

exit 0
