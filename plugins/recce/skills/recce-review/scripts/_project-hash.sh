#!/bin/bash
# _project-hash.sh -- Sourced helper. Single source of truth for the
# project-scoped tracked-changes file path.
#
# Usage (from another script in this directory):
#   . "$(dirname "$0")/_project-hash.sh"
#   echo "$RECCE_CHANGES_FILE"
#
# Exposes:
#   RECCE_PROJECT_HASH  -- 8-char md5 of $PWD
#   RECCE_CHANGES_FILE  -- /tmp/recce-changed-<hash>.txt
#
# Hash scheme matches plugins/recce/hooks/scripts/track-changes.sh so the
# tracked file written by the hook is the same one this skill reads/clears.

# Use an explicit `command -v md5` branch instead of `md5 ... || md5sum ...`.
# The pipeline form returns `cut`'s exit status (which is 0 on empty input),
# so on Linux without `md5` the `||` fallback never fires and the hash
# silently becomes empty -- causing all projects to collide on
# `/tmp/recce-changed-.txt`.
if command -v md5 >/dev/null 2>&1; then
    RECCE_PROJECT_HASH=$(printf '%s' "$PWD" | md5 | cut -c1-8)
else
    RECCE_PROJECT_HASH=$(printf '%s' "$PWD" | md5sum | cut -c1-8)
fi
RECCE_CHANGES_FILE="/tmp/recce-changed-${RECCE_PROJECT_HASH}.txt"
