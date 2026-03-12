#!/bin/bash
# Check Recce MCP Server status (recce-dev plugin) with KEY=VALUE output

# ========== Settings Loading ==========

PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
DEFAULTS="$PLUGIN_ROOT/settings/defaults.json"
GLOBAL_SETTINGS="$HOME/.claude/plugins/recce-dev/settings.json"
PROJECT_SETTINGS=".claude/recce-dev/settings.json"

# Layered merge: defaults -> global -> project (later wins)
if command -v jq &>/dev/null; then
    MERGED=$(cat "$DEFAULTS" 2>/dev/null || echo '{}')
    [ -f "$GLOBAL_SETTINGS" ] && MERGED=$(printf '%s\n%s' "$MERGED" "$(cat "$GLOBAL_SETTINGS")" | jq -s '.[0] * .[1]')
    [ -f "$PROJECT_SETTINGS" ] && MERGED=$(printf '%s\n%s' "$MERGED" "$(cat "$PROJECT_SETTINGS")" | jq -s '.[0] * .[1]')
    SETTINGS_PORT=$(echo "$MERGED" | jq -r '.mcp_port // 8081')
else
    # Fallback: grep from files in priority order (project > global > defaults), take first match
    SETTINGS_PORT=$(grep '"mcp_port"' "$PROJECT_SETTINGS" "$GLOBAL_SETTINGS" "$DEFAULTS" 2>/dev/null | head -1 | sed 's/.*: *\([0-9]*\).*/\1/')
    SETTINGS_PORT="${SETTINGS_PORT:-8081}"
fi

# ========== Port Resolution ==========
# Env var takes priority over settings-derived port

PORT=${RECCE_MCP_PORT:-$SETTINGS_PORT}

# ========== Project-scoped PID File ==========
# Same derivation as start-mcp.sh — must be identical

PROJECT_HASH=$(printf '%s' "$PWD" | md5 2>/dev/null | cut -c1-8 || printf '%s' "$PWD" | md5sum | cut -c1-8)
PID_FILE="/tmp/recce-mcp-${PROJECT_HASH}.pid"

if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ps -p "$PID" > /dev/null 2>&1; then
        # Check if endpoint responds (use HTTP status code since SSE keeps connection open)
        HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 2 "http://localhost:$PORT/sse" 2>/dev/null)
        if [ "$HTTP_CODE" = "200" ]; then
            echo "RUNNING=true"
            echo "PORT=$PORT"
            echo "PID=$PID"
            echo "URL=http://localhost:$PORT/sse"
            exit 0
        else
            echo "RUNNING=false"
            echo "STATUS=UNHEALTHY"
            echo "MESSAGE=Process running but endpoint not responding"
            echo "PID=$PID"
            exit 1
        fi
    else
        rm -f "$PID_FILE"
        echo "RUNNING=false"
        echo "STATUS=NOT_RUNNING"
        echo "MESSAGE=Stale PID file removed"
        exit 1
    fi
else
    echo "RUNNING=false"
    echo "STATUS=NOT_RUNNING"
    echo "MESSAGE=Recce MCP Server is not running (no PID file for this project)"
    exit 1
fi
