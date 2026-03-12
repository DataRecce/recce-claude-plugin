#!/bin/bash
# Pre-flight checks for MCP E2E validation
# Output: KEY=VALUE lines for each check. EXIT 0 always (informational).

PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/../.." && pwd)}"
RECCE_PLUGIN_ROOT="${PLUGIN_ROOT}/../recce"

# ── dbt project ──
if [ -f "dbt_project.yml" ]; then
    echo "DBT_PROJECT=true"
    PROJECT_NAME=$(grep -E "^name:" dbt_project.yml | head -1 | sed 's/name:[[:space:]]*//' | tr -d "'" | tr -d '"')
    echo "DBT_PROJECT_NAME=$PROJECT_NAME"
else
    echo "DBT_PROJECT=false"
    echo "BLOCK=dbt_project.yml not found"
    exit 0
fi

# ── recce CLI ──
if command -v recce &>/dev/null; then
    echo "RECCE_INSTALLED=true"
    RECCE_VERSION=$(recce --version 2>&1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
    echo "RECCE_VERSION=$RECCE_VERSION"
    # Check --sse support
    if recce mcp-server --help 2>&1 | grep -q "\-\-sse"; then
        echo "SSE_SUPPORT=true"
    else
        echo "SSE_SUPPORT=false"
        echo "WARNING=recce mcp-server --sse not available; editable install may be stale"
    fi
else
    echo "RECCE_INSTALLED=false"
    echo "BLOCK=recce not in PATH"
    exit 0
fi

# ── Artifacts ──
[ -f "target/manifest.json" ] && echo "TARGET_EXISTS=true" || echo "TARGET_EXISTS=false"
[ -f "target-base/manifest.json" ] && echo "TARGET_BASE_EXISTS=true" || echo "TARGET_BASE_EXISTS=false"

# ── Credentials ──
[ -f ".env" ] && echo "ENV_FILE=true" || echo "ENV_FILE=false"

# ── Port availability ──
DEFAULTS="$RECCE_PLUGIN_ROOT/settings/defaults.json"
GLOBAL_SETTINGS="$HOME/.claude/plugins/recce/settings.json"
PROJECT_SETTINGS=".claude/recce/settings.json"

if command -v jq &>/dev/null; then
    MERGED=$(cat "$DEFAULTS" 2>/dev/null || echo '{}')
    [ -f "$GLOBAL_SETTINGS" ] && MERGED=$(printf '%s\n%s' "$MERGED" "$(cat "$GLOBAL_SETTINGS")" | jq -s '.[0] * .[1]')
    [ -f "$PROJECT_SETTINGS" ] && MERGED=$(printf '%s\n%s' "$MERGED" "$(cat "$PROJECT_SETTINGS")" | jq -s '.[0] * .[1]')
    PORT=$(echo "$MERGED" | jq -r '.mcp_port // 8081')
else
    PORT=$(grep '"mcp_port"' "$PROJECT_SETTINGS" "$GLOBAL_SETTINGS" "$DEFAULTS" 2>/dev/null | head -1 | sed 's/.*: *\([0-9]*\).*/\1/')
    PORT="${PORT:-8081}"
fi
echo "PORT=$PORT"

if lsof -i :"$PORT" > /dev/null 2>&1; then
    # Check if it's already a recce MCP server
    PROJECT_HASH=$(printf '%s' "$PWD" | md5 2>/dev/null | cut -c1-8 || printf '%s' "$PWD" | md5sum | cut -c1-8)
    PID_FILE="/tmp/recce-mcp-${PROJECT_HASH}.pid"
    if [ -f "$PID_FILE" ]; then
        OLD_PID=$(cat "$PID_FILE")
        if ps -p "$OLD_PID" > /dev/null 2>&1; then
            echo "PORT_STATUS=recce_running"
            echo "MCP_PID=$OLD_PID"
        else
            echo "PORT_STATUS=stale_pid"
        fi
    else
        echo "PORT_STATUS=occupied_by_other"
    fi
else
    echo "PORT_STATUS=free"
fi

# ── Stale files ──
STALE=0
ls /tmp/recce-mcp-*.pid >/dev/null 2>&1 && STALE=1
ls /tmp/recce-changed-*.txt >/dev/null 2>&1 && STALE=1
[ "$STALE" -eq 0 ] && echo "STALE_FILES=none" || echo "STALE_FILES=found"

exit 0
