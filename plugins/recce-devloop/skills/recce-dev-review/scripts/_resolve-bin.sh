#!/bin/bash
# _resolve-bin.sh -- Sourced helper. Resolve a binary that normally lives in
# the dbt project's virtualenv rather than on PATH.
#
# Usage (from another script in this directory):
#   . "$(dirname "$0")/_resolve-bin.sh"
#   path=$(resolve_bin recce) || path=""
#
# Exposes:
#   resolve_bin <name>  -- prints the absolute path and exits 0 when found;
#                          prints nothing and exits 1 when not.

# Claude Code's Bash tool does not inherit an activated venv, so a bare
# `command -v <name>` reports "missing" for a correctly installed project, and
# that false negative silently disables whole code paths. Order mirrors
# run-mcp-stdio.sh, which activates venv/.venv before looking for `recce`, then
# falls back to PATH (a global install, or an already-activated venv).
# hooks/scripts/session-start.sh keeps its own copy of this lookup.
resolve_bin() {
    local name="$1" venv_dir candidate
    for venv_dir in venv .venv; do
        candidate="$venv_dir/bin/$name"
        if [ -x "$candidate" ]; then
            # cd -P resolves symlinked project roots to a stable absolute path.
            printf '%s\n' "$(cd -P "$(dirname "$candidate")" && pwd)/$name"
            return 0
        fi
    done
    command -v "$name" 2>/dev/null
}
