#!/bin/bash
# stdio MCP wrapper: detect venv, activate, exec recce mcp-server.
# Called by Claude Code via .mcp.json stdio transport.
# Inherits cwd from Claude Code (the dbt project root).
#
# The launcher always starts in local mode. Cloud-mode flips happen at
# runtime via the MCP `set_backend` tool, called from the /recce-dev-review skill.
set -euo pipefail

# ========== Venv Auto-Detection ==========
# Always prefer local venv over global dbt/recce: global may be dbt Cloud CLI
for VENV_DIR in venv .venv; do
    if [ -f "$VENV_DIR/bin/activate" ]; then
        # shellcheck disable=SC1091
        source "$VENV_DIR/bin/activate"
        break
    fi
done

if ! command -v recce &>/dev/null; then
    echo '{"error": "recce not found in PATH. Activate your venv or run: pip install recce"}' >&2
    exit 1
fi

# Without a state file argument, local-mode checks live in process memory and
# go away with the session. `recce server <path>` reads the same file back.
# The state writer opens the path directly and does not create its parent, so
# a missing target/ would fail create_check rather than skip the write.
mkdir -p target

exec recce mcp-server target/recce_state.json
