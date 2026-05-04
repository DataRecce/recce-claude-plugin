#!/bin/bash
# detect.sh -- Identify which source-control host owns a PR/MR URL.
#
# Used by /recce-review Step 0 to dispatch to the correct adapter scripts.
# Detection is path-first (most robust for self-hosted hosts), then
# hostname-fallback for the well-known public services.
#
# Path signatures:
#   /pull/<n>             -- GitHub
#   /-/merge_requests/<n> -- GitLab (the "/-/" segment is GitLab-specific)
#   /pull-requests/<n>    -- Bitbucket
#
# Args:    $1 = full URL (required)
# Stdout:  SCM=github | SCM=gitlab | SCM=bitbucket | SCM=unknown
# Exit:    always 0 (caller branches on stdout). Prints SCM=unknown when
#          the URL is missing or the shape is unrecognized.

set -u

URL="${1:-}"
if [ -z "$URL" ]; then
    echo "SCM=unknown"
    exit 0
fi

# Path-based detection (works for self-hosted GitLab, GHE, etc.)
case "$URL" in
    *"/-/merge_requests/"*) echo "SCM=gitlab"; exit 0 ;;
    *"/pull-requests/"*)    echo "SCM=bitbucket"; exit 0 ;;
    *"/pull/"*)             echo "SCM=github"; exit 0 ;;
esac

# Hostname fallback (e.g., user pasted just a project URL)
HOST=$(printf '%s' "$URL" | sed -E 's#^[a-z]+://##; s#/.*##; s#:.*##')
case "$HOST" in
    github.com|*.github.com) echo "SCM=github" ;;
    gitlab.com)              echo "SCM=gitlab" ;;
    bitbucket.org)           echo "SCM=bitbucket" ;;
    *)                       echo "SCM=unknown" ;;
esac
