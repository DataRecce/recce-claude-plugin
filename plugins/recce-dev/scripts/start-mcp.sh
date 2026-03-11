#!/bin/bash
# Start Recce MCP Server (recce-dev plugin) with settings loading and project-scoped PID

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

# Determine which settings layer provided the port
SETTINGS_SOURCE="defaults"
if [ -f "$PROJECT_SETTINGS" ] && grep -q '"mcp_port"' "$PROJECT_SETTINGS" 2>/dev/null; then
    SETTINGS_SOURCE="project"
elif [ -f "$GLOBAL_SETTINGS" ] && grep -q '"mcp_port"' "$GLOBAL_SETTINGS" 2>/dev/null; then
    SETTINGS_SOURCE="global"
fi

# ========== Port Resolution ==========
# Env var takes priority over settings-derived port

PORT=${RECCE_MCP_PORT:-$SETTINGS_PORT}

# ========== Project-scoped PID / Log Files ==========
# Use PWD hash so two different dbt projects get independent PID files

PROJECT_HASH=$(printf '%s' "$PWD" | md5 2>/dev/null | cut -c1-8 || printf '%s' "$PWD" | md5sum | cut -c1-8)
PID_FILE="/tmp/recce-mcp-${PROJECT_HASH}.pid"
LOG_FILE="/tmp/recce-mcp-${PROJECT_HASH}.log"

# ========== Prerequisite Checks ==========

# 1. Check if in dbt project directory
if [ ! -f "dbt_project.yml" ]; then
    echo "ERROR=NOT_DBT_PROJECT"
    echo "MESSAGE=Current directory is not a dbt project (dbt_project.yml not found)"
    echo "FIX=Please switch to a dbt project directory"
    exit 1
fi

# 2. Check base artifacts
if [ ! -f "target-base/manifest.json" ]; then
    echo "ERROR=MISSING_BASE_ARTIFACTS"
    echo "MESSAGE=Missing base artifacts (target-base/manifest.json)"
    echo "FIX=Run: git checkout <base-branch> && dbt build --target-path target-base"
    exit 1
fi

# 3. Check current artifacts
if [ ! -f "target/manifest.json" ]; then
    echo "ERROR=MISSING_TARGET_ARTIFACTS"
    echo "MESSAGE=Missing current artifacts (target/manifest.json)"
    echo "FIX=Run: dbt build"
    exit 1
fi

# 4. Check Recce installation
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
        echo "PORT=$PORT"
        echo "PID=$OLD_PID"
        echo "URL=http://localhost:$PORT/sse"
        echo "SETTINGS_SOURCE=$SETTINGS_SOURCE"
        exit 0
    else
        rm "$PID_FILE"
    fi
fi

# ========== Check Port Availability ==========

if lsof -i :"$PORT" > /dev/null 2>&1; then
    echo "ERROR=PORT_IN_USE"
    echo "MESSAGE=Port $PORT is already in use"
    echo "FIX=Set RECCE_MCP_PORT env var or update mcp_port in .claude/recce-dev/settings.json to use a different port"
    exit 1
fi

# ========== Start MCP Server ==========

nohup recce mcp-server --sse --port "$PORT" > "$LOG_FILE" 2>&1 &
MCP_PID=$!
echo "$MCP_PID" > "$PID_FILE"

echo "STARTING=true"
echo "PORT=$PORT"
echo "PID=$MCP_PID"
echo "SETTINGS_SOURCE=$SETTINGS_SOURCE"
echo "LOG_FILE=$LOG_FILE"

# Wait for startup (max 15 seconds)
for i in {1..15}; do
    sleep 1

    # Check if process is still running
    if ! ps -p "$MCP_PID" > /dev/null 2>&1; then
        echo "ERROR=STARTUP_FAILED"
        echo "MESSAGE=Recce MCP Server failed to start"
        echo "LOG_FILE=$LOG_FILE"
        rm -f "$PID_FILE"
        exit 1
    fi

    # Check if SSE endpoint is available (use HTTP status code since SSE keeps connection open)
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 2 "http://localhost:$PORT/sse" 2>/dev/null)
    if [ "$HTTP_CODE" = "200" ]; then
        echo "STATUS=STARTED"
        echo "URL=http://localhost:$PORT/sse"
        exit 0
    fi
done

# Timeout
echo "ERROR=STARTUP_TIMEOUT"
echo "MESSAGE=Recce MCP Server startup timed out (15 seconds)"
echo "LOG_FILE=$LOG_FILE"
exit 1
