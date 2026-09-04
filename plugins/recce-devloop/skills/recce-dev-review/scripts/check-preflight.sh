#!/bin/bash
# check-preflight.sh -- Decide the single thing the user must do before
# /recce-dev-review can prepare a Cloud dev session.
#
# Used by /recce-dev-review's Precondition step, on every invocation.
#
# Args:    --tools present|absent   (required). Whether the recce MCP tools
#          (mcp__plugin_recce-devloop_recce__*) are bound is the one fact no
#          script can read: only the model sees its own tool list.
# Stdout:  REMEDY=install|dbt-docs|restart|none
#          INSTALL=<pip argument list>       (only when REMEDY=install)
#          RECCE_CLOUD=<path>|missing        (only when REMEDY=none)
#          Nothing else. The resolved `recce` path and the presence of
#          target/manifest.json are inputs to REMEDY and nothing more, so
#          printing them only creates output the caller must be told to ignore.
# Exit:    0 always, except 64 for a bad --tools value (a caller bug, not a
#          user state -- do not paper over it with a default).

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
    # pip command saves the user a second restart cycle.
    if [ "$RECCE_CLOUD" = "missing" ]; then
        echo "INSTALL='recce[mcp]' recce-cloud"
    else
        echo "INSTALL='recce[mcp]'"
    fi
fi

[ "$REMEDY" = "none" ] && echo "RECCE_CLOUD=$RECCE_CLOUD"

exit 0
