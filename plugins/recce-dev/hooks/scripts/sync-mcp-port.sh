#!/bin/bash
# Sync .mcp.json port with the user's configured mcp_port setting.
# Runs on SessionStart so Claude Code connects to the correct port.

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
    PORT=$(echo "$MERGED" | jq -r '.mcp_port // 8081')
else
    PORT=$(grep '"mcp_port"' "$PROJECT_SETTINGS" "$GLOBAL_SETTINGS" "$DEFAULTS" 2>/dev/null | head -1 | sed 's/.*: *\([0-9]*\).*/\1/')
    PORT="${PORT:-8081}"
fi

# Env var override (same precedence as start-mcp.sh)
PORT="${RECCE_MCP_PORT:-$PORT}"

# Read current port from .mcp.json (if it exists)
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
