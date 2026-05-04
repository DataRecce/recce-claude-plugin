#!/bin/bash
# clear-tracked-models.sh -- Remove the project-scoped tracked-changes
# file after a successful review, so the pre-commit guard no longer
# warns about already-reviewed models.
#
# Used by /recce-review Step 3 (post-review cleanup, success path only).
#
# Args:    none (project is identified by $PWD)
# Stdout:  CLEARED=<absolute path>  -- path that was removed (or would
#          have been removed; rm -f is a no-op if the file is absent).
# Exit:    always 0.

set -u

# shellcheck source=_project-hash.sh
. "$(dirname "$0")/_project-hash.sh"

rm -f "$RECCE_CHANGES_FILE"
echo "CLEARED=$RECCE_CHANGES_FILE"
