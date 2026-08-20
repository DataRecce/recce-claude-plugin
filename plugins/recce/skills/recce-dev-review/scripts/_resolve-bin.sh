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
#
# Claude Code's Bash tool does not inherit an activated venv, so a bare
# `command -v <name>` reports "missing" for a correctly installed project.
# That false negative silently disables whole code paths -- it is why
# session-start.sh grew its own copy of this lookup. Order mirrors
# run-mcp-stdio.sh, which activates venv/.venv before looking for `recce`:
#   1. venv/bin/<name>
#   2. .venv/bin/<name>
#   3. <name> on PATH (global install, or an already-activated venv)

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
