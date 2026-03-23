#!/bin/bash
# Sync .mcp.json port with the user's configured mcp_port setting.
# Runs on SessionStart so Claude Code connects to the correct port.
#
# If the configured port is occupied, scans upward (up to 10 attempts)
# to find a free port and writes it to both .mcp.json and a state file
# so that start-mcp.sh can use the same port later.

PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/../.." && pwd)}"
MCP_JSON="$PLUGIN_ROOT/.mcp.json"

# Resolve sibling recce plugin root for settings paths
RESOLVE_SCRIPT="$PLUGIN_ROOT/scripts/resolve-recce-root.sh"
if [ -f "$RESOLVE_SCRIPT" ]; then
    eval "$(CLAUDE_PLUGIN_ROOT="$PLUGIN_ROOT" bash "$RESOLVE_SCRIPT" 2>/dev/null)"
fi

# Layered settings: recce plugin defaults -> global -> project
DEFAULTS="${RECCE_PLUGIN_ROOT:-}/settings/defaults.json"
GLOBAL_SETTINGS="$HOME/.claude/plugins/recce/settings.json"
PROJECT_SETTINGS=".claude/recce/settings.json"

if command -v jq &>/dev/null; then
    MERGED=$(cat "$DEFAULTS" 2>/dev/null || echo '{}')
    [ -f "$GLOBAL_SETTINGS" ] && MERGED=$(printf '%s\n%s' "$MERGED" "$(cat "$GLOBAL_SETTINGS")" | jq -s '.[0] * .[1]')
    [ -f "$PROJECT_SETTINGS" ] && MERGED=$(printf '%s\n%s' "$MERGED" "$(cat "$PROJECT_SETTINGS")" | jq -s '.[0] * .[1]')
    BASE_PORT=$(echo "$MERGED" | jq -r '.mcp_port // 8081')
else
    BASE_PORT=$(grep '"mcp_port"' "$PROJECT_SETTINGS" "$GLOBAL_SETTINGS" "$DEFAULTS" 2>/dev/null | head -1 | sed 's/.*: *\([0-9]*\).*/\1/')
    BASE_PORT="${BASE_PORT:-8081}"
fi

# Env var override (same precedence as start-mcp.sh)
BASE_PORT="${RECCE_MCP_PORT:-$BASE_PORT}"

# Project-scoped state file
PROJECT_HASH=$(printf '%s' "$PWD" | md5 2>/dev/null | cut -c1-8 || printf '%s' "$PWD" | md5sum | cut -c1-8)
PORT_STATE_FILE="/tmp/recce-mcp-resolved-port-${PROJECT_HASH}.txt"
PID_FILE="/tmp/recce-mcp-${PROJECT_HASH}.pid"

# If a recce MCP server is already running for this project, use its port
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if ps -p "$OLD_PID" > /dev/null 2>&1 && [ -f "$PORT_STATE_FILE" ]; then
        PORT=$(cat "$PORT_STATE_FILE")
        echo "MCP_PORT_ALREADY_RUNNING=$PORT"
        # Ensure .mcp.json matches the running server
        CURRENT_PORT=""
        if [ -f "$MCP_JSON" ] && command -v jq &>/dev/null; then
            CURRENT_PORT=$(jq -r '.mcpServers.recce.url' "$MCP_JSON" 2>/dev/null | grep -oE '[0-9]+' | tail -1)
        fi
        if [ "${CURRENT_PORT:-}" != "$PORT" ]; then
            cat > "$MCP_JSON" <<EOF
{
  "mcpServers": {
    "recce": {
      "type": "sse",
      "url": "http://localhost:${PORT}/sse"
    }
  }
}
EOF
            echo "MCP_JSON_SYNCED=$PORT"
        fi
        exit 0
    fi
fi

# Find a free port starting from BASE_PORT (scan up to 10 ports)
PORT="$BASE_PORT"
MAX_ATTEMPTS=10
for i in $(seq 0 $((MAX_ATTEMPTS - 1))); do
    CANDIDATE=$((BASE_PORT + i))
    if ! lsof -i :"$CANDIDATE" > /dev/null 2>&1; then
        PORT="$CANDIDATE"
        break
    fi
    # If we exhausted all attempts, fall back to BASE_PORT
    # (start-mcp.sh will report the error)
    if [ "$i" -eq $((MAX_ATTEMPTS - 1)) ]; then
        PORT="$BASE_PORT"
    fi
done

# Write resolved port to state file for start-mcp.sh to read
echo "$PORT" > "$PORT_STATE_FILE"

# Read current port from .mcp.json (if it exists)
CURRENT_PORT=""
if [ -f "$MCP_JSON" ] && command -v jq &>/dev/null; then
    CURRENT_PORT=$(jq -r '.mcpServers.recce.url' "$MCP_JSON" 2>/dev/null | grep -oE '[0-9]+' | tail -1)
fi

# Only rewrite if port changed (avoid unnecessary writes)
if [ "${CURRENT_PORT:-}" != "$PORT" ]; then
    cat > "$MCP_JSON" <<EOF
{
  "mcpServers": {
    "recce": {
      "type": "sse",
      "url": "http://localhost:${PORT}/sse"
    }
  }
}
EOF
    echo "MCP_PORT_SYNCED=$PORT"
else
    echo "MCP_PORT_UNCHANGED=$PORT"
fi

if [ "$PORT" != "$BASE_PORT" ]; then
    echo "MCP_PORT_FALLBACK=true"
    echo "MCP_PORT_CONFIGURED=$BASE_PORT"
    echo "MCP_PORT_RESOLVED=$PORT"
fi
