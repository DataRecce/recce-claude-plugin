#!/bin/bash
# SessionStart hook: detect the dbt environment and report what is present.
# The MCP server is stdio-based (.mcp.json), so nothing here starts it.
# Output: KEY=VALUE lines injected into Claude's context -- observations
#         only, no fixes and no readiness verdict (see the note below).
# Exit: Always 0 (resilient wrapper — never blocks session)

# ========== Binary Resolution ==========
# dbt and recce normally live in the project's virtualenv, not on PATH. This
# hook runs in Claude Code's shell, which has no venv activated, so a bare
# `command -v` reports "not installed" for a correctly set up project — and
# then contradicts run-mcp-stdio.sh, which activates the venv and starts the
# server fine. Same lookup order as run-mcp-stdio.sh.
#
# Stdout: the path if found, nothing if not. Exit 1 when not found.
#
# Kept local on purpose. skills/recce-dev-review/scripts/_resolve-bin.sh has
# the same order; sourcing it from here would couple this hook to a path
# outside hooks/ and reintroduce the CLAUDE_PLUGIN_ROOT fallback. Change both
# together. plugins/recce keeps its own pair for the same reason -- separate
# plugins, no shared file.
find_bin() {
    local name="$1" dir
    for dir in venv .venv; do
        if [ -x "$dir/bin/$name" ]; then
            printf '%s\n' "$dir/bin/$name"
            return 0
        fi
    done
    command -v "$name" 2>/dev/null
}

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
if find_bin dbt >/dev/null; then
    echo "DBT_INSTALLED=true"
else
    echo "DBT_INSTALLED=false"
fi

# recce check
if find_bin recce >/dev/null; then
    echo "RECCE_INSTALLED=true"
else
    echo "RECCE_INSTALLED=false"
fi

# ========== Artifact Checks ==========

if [ -f "target/manifest.json" ]; then
    echo "TARGET_EXISTS=true"
else
    echo "TARGET_EXISTS=false"
fi

# Observations only. No FIX line, no MCP_READY verdict, no TARGET_BASE_EXISTS:
# skills/recce-dev-review/scripts/check-preflight.sh owns what the user must
# do, and a second weaker answer in the model's context gets acted on.
# MCP_READY was also a false positive by construction -- a hook cannot see
# whether the session bound the tools.

exit 0
