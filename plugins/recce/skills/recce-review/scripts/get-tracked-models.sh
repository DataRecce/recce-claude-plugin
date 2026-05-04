#!/bin/bash
# get-tracked-models.sh -- Read the project-scoped tracked-changes file
# written by the PostToolUse hook (track-changes.sh) and report the
# models that the user has edited this session.
#
# Used by /recce-review Step 1 (model scope determination).
#
# Args:    none (project is identified by $PWD)
# Stdout:  one of two shapes --
#          When tracked changes exist:
#              TRACKED=true
#              MODEL_COUNT=<integer>
#              MODELS=<comma+space separated model names>
#          When no tracked changes file exists or it is empty:
#              TRACKED=false
# Exit:    always 0 (the "no tracked changes" case is normal, e.g. for
#          cloud-mode reviewers with no local edits).

set -u

# shellcheck source=_project-hash.sh
. "$(dirname "$0")/_project-hash.sh"

if [ -f "$RECCE_CHANGES_FILE" ] && [ -s "$RECCE_CHANGES_FILE" ]; then
    echo "TRACKED=true"
    echo "MODEL_COUNT=$(wc -l < "$RECCE_CHANGES_FILE" | tr -d ' ')"
    MODELS=$(while IFS= read -r f; do basename "$f" .sql; done < "$RECCE_CHANGES_FILE" \
        | awk 'NR==1{printf "%s",$0; next} {printf ", %s",$0} END{print ""}')
    echo "MODELS=$MODELS"
else
    echo "TRACKED=false"
fi
