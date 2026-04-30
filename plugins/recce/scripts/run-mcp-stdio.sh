#!/bin/bash
# stdio MCP wrapper: detect venv, activate, exec recce mcp-server.
# Called by Claude Code via .mcp.json stdio transport.
# Inherits cwd from Claude Code (the dbt project root).
#
# The launcher always starts in local mode. Cloud-mode flips happen at
# runtime via the MCP `set_backend` tool, called from the /recce-review skill.
set -euo pipefail

# ========== Venv Auto-Detection ==========
# Always prefer local venv over global dbt/recce — global may be dbt Cloud CLI
for VENV_DIR in venv .venv; do
    if [ -f "$VENV_DIR/bin/activate" ]; then
        # shellcheck disable=SC1091
        source "$VENV_DIR/bin/activate"
        break
    fi
done

# ========== Verify recce is available ==========
if ! command -v recce &>/dev/null; then
    echo '{"error": "recce not found in PATH. Activate your venv or run: pip install recce"}' >&2
    exit 1
fi

# ========== Launch MCP server (local mode) ==========
exec recce mcp-server
