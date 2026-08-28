#!/bin/bash
# check-preflight.sh -- Decide the single thing the user must do before
# /recce-dev-review can prepare a Cloud dev session.
#
# Used by /recce-dev-review's Precondition step, on every invocation.
#
# Whether the recce MCP tools (mcp__plugin_recce-devloop_recce__*) are bound in this
# session is the one fact no script can read -- only the model can see its own
# tool list. The caller passes that in as one word; every other decision is
# made here.
#
# Args:    --tools present|absent   (required)
# Stdout:  REMEDY=install|dbt-docs|restart|none
#          INSTALL=<pip argument list>       (only when REMEDY=install)
#          RECCE_CLOUD=<path>|missing        (only when REMEDY=none)
# Exit:    0 always, except 64 for a bad --tools value (a caller bug, not a
#          user state -- do not paper over it with a default).
#
# Only actionable keys are printed. The resolved `recce` path, the presence of
# target/manifest.json, and the state of target-base/ are all inputs to REMEDY
# and nothing else, so printing them only creates output the caller has to be
# told to ignore. RECCE_CLOUD is printed because the Cloud readiness step
# genuinely needs it, and only once there is a readiness step to reach.

set -u

. "$(dirname "$0")/_resolve-bin.sh"

TOOLS=""
while [ $# -gt 0 ]; do
    case "$1" in
        --tools) TOOLS="${2:-}"; shift 2 || shift ;;
        *)       shift ;;
    esac
done

case "$TOOLS" in
    present|absent) ;;
    *) echo "usage: check-preflight.sh --tools present|absent" >&2; exit 64 ;;
esac

RECCE=$(resolve_bin recce) || RECCE=missing
RECCE_CLOUD=$(resolve_bin recce-cloud) || RECCE_CLOUD=missing
[ -f "target/manifest.json" ] && TARGET=true || TARGET=false

# Ordering matters. `recce` gates the MCP server, and the server needs a
# manifest, so a restart only helps once both are in place.
if [ "$TOOLS" = "present" ]; then
    # The server answered, so it found what it needed.
    REMEDY=none
elif [ "$RECCE" = "missing" ]; then
    REMEDY=install
elif [ "$TARGET" = "false" ]; then
    REMEDY=dbt-docs
else
    REMEDY=restart
fi

echo "REMEDY=$REMEDY"

if [ "$REMEDY" = "install" ]; then
    # recce-cloud needs no restart of its own, so bundling it into this one
    # pip command saves the user a second restart cycle. The target user is an
    # existing Recce Cloud client who has only ever used the web app, so on a
    # first dev-time run neither package is present.
    if [ "$RECCE_CLOUD" = "missing" ]; then
        echo "INSTALL='recce[mcp]' recce-cloud"
    else
        echo "INSTALL='recce[mcp]'"
    fi
fi

[ "$REMEDY" = "none" ] && echo "RECCE_CLOUD=$RECCE_CLOUD"

exit 0
