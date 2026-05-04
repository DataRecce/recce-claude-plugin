#!/bin/bash
# gitlab-ready.sh -- Check whether GitLab access is usable.
#
# Used by /recce-review Step 0.2 when SCM=gitlab.
# Two access mechanisms are supported (either is sufficient):
#   1. `glab` CLI    -- `glab auth status` returns 0
#   2. API token     -- GITLAB_TOKEN env var is set and non-empty
# Both work for self-hosted GitLab. When both are available, the CLI is
# preferred (it already knows about self-hosted host config).
#
# Args:    none
# Stdout:  GITLAB=ready + GITLAB_VIA=cli|token   when usable
#          GITLAB=unavailable                    otherwise
# Exit:    always 0.
#
# Note: this script does NOT print the token itself.

set -u

GLAB_OK=0
if command -v glab >/dev/null 2>&1 && glab auth status >/dev/null 2>&1; then
    GLAB_OK=1
fi
TOKEN_OK=0
if [ -n "${GITLAB_TOKEN:-}" ]; then
    TOKEN_OK=1
fi

if [ "$GLAB_OK" -eq 1 ]; then
    echo "GITLAB=ready"
    echo "GITLAB_VIA=cli"
elif [ "$TOKEN_OK" -eq 1 ]; then
    echo "GITLAB=ready"
    echo "GITLAB_VIA=token"
else
    echo "GITLAB=unavailable"
fi
