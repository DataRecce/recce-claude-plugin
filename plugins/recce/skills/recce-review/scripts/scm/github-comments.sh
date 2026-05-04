#!/bin/bash
# github-comments.sh -- Fetch PR comment bodies as plain text.
#
# Used by /recce-review Step 0.3 when SCM=github. The skill then searches
# the bodies for a Recce Cloud session URL of the form
# https://cloud.reccehq.com/sessions/<UUID>.
#
# Args:    $1 = PR URL or PR number (required)
# Stdout:  one comment body per record (separated by blank lines from gh).
# Exit:    0 on success; non-zero if `gh` errors (e.g., not authenticated,
#          PR not found). Errors propagate from `gh` on stderr.

set -eu

PR_REF="${1:-}"
if [ -z "$PR_REF" ]; then
    echo "ERROR=missing PR reference (URL or number)" >&2
    exit 2
fi

gh pr view "$PR_REF" --json comments --jq '.comments[].body'
