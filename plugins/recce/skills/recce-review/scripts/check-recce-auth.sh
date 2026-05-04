#!/bin/bash
# check-recce-auth.sh -- Detect Recce Cloud credentials.
#
# Used by /recce-review Step 0.4 (cloud-mode auth precondition).
# Checks two locations, in priority order:
#   1. RECCE_API_TOKEN environment variable (wins if set and non-empty)
#   2. api_token entry in ~/.recce/profile.yml (non-empty value)
#
# This script does NOT print or transmit the token itself -- it only
# reports which source supplied it. The grep against profile.yml looks
# for the key/non-empty-value shape; it does not extract the secret.
#
# Args:    none
# Stdout:  exactly one of:
#            AUTH=env       -- RECCE_API_TOKEN is set
#            AUTH=file      -- api_token present in ~/.recce/profile.yml
#            AUTH=missing   -- neither source has a credential
# Exit:    always 0 (caller branches on stdout).

set -u

if [ -n "${RECCE_API_TOKEN:-}" ]; then
    echo "AUTH=env"
elif [ -f "$HOME/.recce/profile.yml" ] \
    && grep -qE '^[[:space:]]*api_token[[:space:]]*:[[:space:]]*[^[:space:]]' "$HOME/.recce/profile.yml"; then
    echo "AUTH=file"
else
    echo "AUTH=missing"
fi
