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
# Only extract RECCE_PLUGIN_ROOT — do not eval arbitrary output
RESOLVE_SCRIPT="$PLUGIN_ROOT/scripts/resolve-recce-root.sh"
if [ -f "$RESOLVE_SCRIPT" ]; then
    RESOLVE_OUTPUT=$(CLAUDE_PLUGIN_ROOT="$PLUGIN_ROOT" bash "$RESOLVE_SCRIPT" 2>/dev/null || true)
    while IFS= read -r line; do
        case "$line" in
            RECCE_PLUGIN_ROOT=*)
                RECCE_PLUGIN_ROOT="${line#RECCE_PLUGIN_ROOT=}"
                break
                ;;
        esac
    done <<PARSE_EOF
$RESOLVE_OUTPUT
PARSE_EOF
fi

# Layered settings: recce plugin defaults -> global -> project
DEFAULTS="${RECCE_PLUGIN_ROOT:+$RECCE_PLUGIN_ROOT/settings/defaults.json}"
GLOBAL_SETTINGS="$HOME/.claude/plugins/recce/settings.json"
PROJECT_SETTINGS=".claude/recce/settings.json"

if command -v jq &>/dev/null; then
    MERGED=$(cat "$DEFAULTS" 2>/dev/null || echo '{}')
    if [ -f "$GLOBAL_SETTINGS" ]; then
        MERGED=$(printf '%s\n%s' "$MERGED" "$(cat "$GLOBAL_SETTINGS")" | jq -s '.[0] * .[1]' 2>/dev/null) || MERGED='{}'
    fi
    if [ -f "$PROJECT_SETTINGS" ]; then
        MERGED=$(printf '%s\n%s' "$MERGED" "$(cat "$PROJECT_SETTINGS")" | jq -s '.[0] * .[1]' 2>/dev/null) || MERGED='{}'
    fi
    BASE_PORT=$(echo "$MERGED" | jq -r '.mcp_port // 8081' 2>/dev/null)
else
    BASE_PORT=$(grep '"mcp_port"' "$PROJECT_SETTINGS" "$GLOBAL_SETTINGS" "$DEFAULTS" 2>/dev/null | head -1 | sed 's/.*: *\([0-9]*\).*/\1/')
fi

# Validate port is numeric; default to 8081 if not
case "$BASE_PORT" in
    ''|*[!0-9]*) BASE_PORT=8081 ;;
esac

# Env var override (same precedence as start-mcp.sh)
BASE_PORT="${RECCE_MCP_PORT:-$BASE_PORT}"

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
        PORT=$(cat "$PORT_STATE_FILE")
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
