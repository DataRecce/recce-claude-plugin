#!/bin/bash
# resolve-recce-cloud.sh -- Locate the recce-cloud binary.
#
# Used by /recce-dev-review when the user reports a fresh recce-cloud install.
#
# Thin wrapper over _resolve-bin.sh, which carries the lookup order and the
# reason for it. Kept as its own script because check-preflight.sh reports
# RECCE_CLOUD only on a clean run, so a mid-session install needs a way to
# re-resolve it without re-running the whole precondition.
#
# Args:    none (run from the dbt project root)
# Stdout:  exactly one of:
#            RECCE_CLOUD=<absolute path>  -- use this path for every call
#            RECCE_CLOUD=missing          -- not installed anywhere we look
# Exit:    always 0 (caller branches on stdout).

set -u

# shellcheck source=_resolve-bin.sh
. "$(dirname "$0")/_resolve-bin.sh"

echo "RECCE_CLOUD=$(resolve_bin recce-cloud || echo missing)"
