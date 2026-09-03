#!/bin/bash
# session-start.sh -- Report what the dbt environment has, at session start.
#
# Run by hooks.json on SessionStart (startup|resume). Nothing calls it by hand.
# The MCP server is stdio-based (.mcp.json), so this does not start it.
#
# Args:    none (the project is the cwd Claude Code passes in)
# Stdout:  DBT_PROJECT=true|false      (false and nothing else when
#                                       dbt_project.yml is absent)
#          DBT_PROJECT_NAME=<name>
#          DBT_INSTALLED=true|false
#          RECCE_INSTALLED=true|false
#          TARGET_EXISTS=true|false
# Exit:    0 always. A hook failure must never block the session.
#
# No FIX line and no readiness verdict: a hook cannot see whether the session
# bound the MCP tools, and check-preflight.sh owns what the user must do.

# ========== Binary Resolution ==========
# dbt and recce normally live in the project's virtualenv, not on PATH. This
# hook runs in Claude Code's shell, which has no venv activated, so a bare
# `command -v` reports "not installed" for a correctly set up project, and
# then contradicts run-mcp-stdio.sh, which activates the venv and starts the
# server fine. Same order of places as run-mcp-stdio.sh.
#
# Stdout: the path if found, nothing if not. Exit 1 when not found.
#
# Kept local on purpose. skills/recce-dev-review/scripts/_resolve-bin.sh has
# the same order; sourcing it from here would couple this hook to a path
# outside hooks/. Change both together.
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

echo "DBT_PROJECT=true"
PROJECT_NAME=$(grep -E "^name:" dbt_project.yml | head -1 | sed 's/name:[[:space:]]*//' | tr -d "'" | tr -d '"')
echo "DBT_PROJECT_NAME=$PROJECT_NAME"

# ========== Tool Availability ==========

if find_bin dbt >/dev/null; then
    echo "DBT_INSTALLED=true"
else
    echo "DBT_INSTALLED=false"
fi

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

exit 0
