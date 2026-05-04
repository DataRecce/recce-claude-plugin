#!/bin/bash
# github-ready.sh -- Check whether GitHub access is usable.
#
# Used by /recce-review Step 0.2 when SCM=github.
# Currently this only verifies the `gh` CLI is installed and authenticated.
# (Personal access tokens are a possible future addition; for GitHub the
# CLI is the dominant case in dev environments.)
#
# Args:    none
# Stdout:  GITHUB=ready  + GITHUB_VIA=cli   if `gh auth status` succeeds,
#          GITHUB=unavailable               otherwise.
# Exit:    always 0.

set -u

if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
    echo "GITHUB=ready"
    echo "GITHUB_VIA=cli"
else
    echo "GITHUB=unavailable"
fi
