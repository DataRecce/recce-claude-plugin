#!/bin/bash
# Sync .mcp.json port with the resolved MCP port.
# Runs on SessionStart so Claude Code connects to the correct port.
#
# Uses default port 8081 (or RECCE_MCP_PORT env var override).
# If the port is occupied, scans upward (up to 10 attempts) to find
# a free port and writes it to both .mcp.json and a state file
# so that start-mcp.sh can use the same port later.

PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/../.." && pwd)}"
MCP_JSON="$PLUGIN_ROOT/.mcp.json"

# Default port; env var override takes precedence
BASE_PORT="${RECCE_MCP_PORT:-8081}"

# Project-scoped state file
PROJECT_HASH=$(printf '%s' "$PWD" | md5 2>/dev/null | cut -c1-8 || printf '%s' "$PWD" | md5sum | cut -c1-8)
PORT_STATE_FILE="/tmp/recce-mcp-resolved-port-${PROJECT_HASH}.txt"
PID_FILE="/tmp/recce-mcp-${PROJECT_HASH}.pid"

# Helper: read current port from .mcp.json (works with or without jq)
read_mcp_json_port() {
    if [ ! -f "$MCP_JSON" ]; then
        return
    fi
    if command -v jq &>/dev/null; then
        jq -r '.mcpServers.recce.url' "$MCP_JSON" 2>/dev/null | grep -oE '[0-9]+' | tail -1
    else
        grep -oE '"url"[[:space:]]*:[[:space:]]*"http://localhost:[0-9]+/sse"' "$MCP_JSON" 2>/dev/null | grep -oE '[0-9]+' | tail -1
    fi
}

# Helper: write .mcp.json and check success
write_mcp_json() {
    local port="$1"
    cat > "$MCP_JSON" <<EOF
{
  "mcpServers": {
    "recce": {
      "type": "sse",
      "url": "http://localhost:${port}/sse"
    }
  }
}
EOF
    if [ $? -ne 0 ]; then
        echo "ERROR=Failed to write $MCP_JSON (directory may be read-only)"
        return 1
    fi
    return 0
}

# If a recce MCP server is already running for this project, use its port
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if ps -p "$OLD_PID" > /dev/null 2>&1 && [ -f "$PORT_STATE_FILE" ]; then
        PORT=$(cat "$PORT_STATE_FILE" 2>/dev/null | tr -d '[:space:]')
        # Validate port is numeric and in range
        if [ -z "$PORT" ] || ! [ "$PORT" -ge 1 ] 2>/dev/null || ! [ "$PORT" -le 65535 ] 2>/dev/null; then
            rm -f "$PORT_STATE_FILE"
            PORT="$BASE_PORT"
        fi
        echo "MCP_PORT_ALREADY_RUNNING=$PORT"
        # Ensure .mcp.json matches the running server
        CURRENT_PORT=$(read_mcp_json_port)
        if [ "${CURRENT_PORT:-}" != "$PORT" ]; then
            if write_mcp_json "$PORT"; then
                echo "MCP_JSON_SYNCED=$PORT"
            fi
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

# Read current port from .mcp.json
CURRENT_PORT=$(read_mcp_json_port)

# Only rewrite if port changed (avoid unnecessary writes)
if [ "${CURRENT_PORT:-}" != "$PORT" ]; then
    if write_mcp_json "$PORT"; then
        echo "MCP_PORT_SYNCED=$PORT"
    fi
else
    echo "MCP_PORT_UNCHANGED=$PORT"
fi

if [ "$PORT" != "$BASE_PORT" ]; then
    echo "MCP_PORT_FALLBACK=true"
    echo "MCP_PORT_CONFIGURED=$BASE_PORT"
    echo "MCP_PORT_RESOLVED=$PORT"
fi
