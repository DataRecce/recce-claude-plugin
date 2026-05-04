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

RECCE_PROJECT_HASH=$(printf '%s' "$PWD" | md5 2>/dev/null | cut -c1-8 \
    || printf '%s' "$PWD" | md5sum | cut -c1-8)
RECCE_CHANGES_FILE="/tmp/recce-changed-${RECCE_PROJECT_HASH}.txt"
