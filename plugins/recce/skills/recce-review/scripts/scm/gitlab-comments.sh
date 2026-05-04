#!/bin/bash
# gitlab-comments.sh -- Fetch MR note (comment) bodies as plain text.
#
# Used by /recce-review Step 0.3 when SCM=gitlab. Works for both
# gitlab.com and self-hosted GitLab.
#
# URL shape expected:
#   https://<host>/<group>[/<subgroup>...]/<project>/-/merge_requests/<iid>
#
# Access mechanism, in priority order:
#   1. `glab api` -- preferred; uses glab's own host/token configuration
#                    (handles self-hosted hosts the user has glab-auth'd to)
#   2. curl + GITLAB_TOKEN -- direct REST against /api/v4 on the URL host
#
# Args:    $1 = full MR URL (required)
# Stdout:  one note body per line (jq -r), in API order.
# Stderr:  parse / auth / HTTP errors.
# Exit:    0 on success; 2 on usage / parse error; non-zero on API failure.

set -eu

URL="${1:-}"
if [ -z "$URL" ]; then
    echo "ERROR=missing MR URL" >&2
    exit 2
fi

# --- Parse host, project path, and IID from the URL ---
HOST=$(printf '%s' "$URL" | sed -E 's#^[a-z]+://##; s#/.*##')
PATH_PART=$(printf '%s' "$URL" | sed -E 's#^[a-z]+://[^/]+/##; s#\?.*##; s#/$##')
PROJECT_PATH=$(printf '%s' "$PATH_PART" | sed -E 's#/-/merge_requests/.*##')
IID=$(printf '%s' "$PATH_PART" | sed -nE 's#.*/-/merge_requests/([0-9]+).*#\1#p')

if [ -z "$HOST" ] || [ -z "$PROJECT_PATH" ] || [ -z "$IID" ]; then
    echo "ERROR=could not parse GitLab MR URL: $URL" >&2
    echo "       expected https://<host>/<group>/<project>/-/merge_requests/<iid>" >&2
    exit 2
fi

# URL-encode the project path: every '/' becomes '%2F'
ENC_PROJECT=$(printf '%s' "$PROJECT_PATH" | sed 's#/#%2F#g')

# Require jq for downstream parsing
if ! command -v jq >/dev/null 2>&1; then
    echo "ERROR=jq is required" >&2
    exit 2
fi

API_PATH="projects/$ENC_PROJECT/merge_requests/$IID/notes?per_page=100"

# --- Fetch via glab if available, else fall back to curl + token ---
if command -v glab >/dev/null 2>&1 && glab auth status >/dev/null 2>&1; then
    glab api --hostname "$HOST" "$API_PATH" 2>/dev/null \
        | jq -r '.[].body'
    exit 0
fi

if [ -n "${GITLAB_TOKEN:-}" ]; then
    curl -sSf -H "PRIVATE-TOKEN: $GITLAB_TOKEN" \
        "https://$HOST/api/v4/$API_PATH" \
        | jq -r '.[].body'
    exit 0
fi

echo "ERROR=no GitLab credentials (run \`glab auth login\` or set GITLAB_TOKEN)" >&2
exit 2
