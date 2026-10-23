#!/bin/bash
# check-preflight.sh -- Decide the single thing the user must do before
# /recce-dev-review can prepare a Cloud dev session.
#
# Used by /recce-dev-review's Precondition step, on every invocation.
#
# Args:    --tools present|missing-set-backend|absent   (required). Whether
#          the recce MCP tools (mcp__plugin_recce-devloop_recce__*) are bound,
#          and whether set_backend is among them, is the one fact no script
#          can read: only the model sees its own tool list.
# Stdout:  REMEDY=install|upgrade|dbt-docs|restart|none
#          INSTALL=<pip argument list>       (only when REMEDY=install|upgrade)
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
    present|missing-set-backend|absent) ;;
    *) echo "usage: check-preflight.sh --tools present|missing-set-backend|absent" >&2; exit 64 ;;
esac

RECCE=$(resolve_bin recce) || RECCE=missing
RECCE_CLOUD=$(resolve_bin recce-cloud) || RECCE_CLOUD=missing
[ -f "target/manifest.json" ] && TARGET=true || TARGET=false

# set_backend, which Step 4 needs, first shipped in recce 1.46.3.
MIN_RECCE=1.46.3

# An unknown version does not block: --tools missing-set-backend and Step 4
# still catch an old server.
recce_too_old() {
    local v
    v=$("$RECCE" version 2>/dev/null | grep -Eo '^[0-9]+\.[0-9]+\.[0-9]+' | head -n 1)
    [ -n "$v" ] || return 1
    [ "$(printf '%s\n%s\n' "$v" "$MIN_RECCE" | sort -t. -k1,1n -k2,2n -k3,3n | head -n 1)" != "$MIN_RECCE" ]
}

# Ordering matters. `recce` gates the MCP server, and the server needs a
# manifest, so a restart only helps once both are in place. An old `recce`
# can still serve MCP tools, so its check comes before the tools check.
if [ "$TOOLS" = "missing-set-backend" ]; then
    REMEDY=upgrade
elif [ "$RECCE" != "missing" ] && recce_too_old; then
    REMEDY=upgrade
elif [ "$TOOLS" = "present" ]; then
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

if [ "$REMEDY" = "install" ] || [ "$REMEDY" = "upgrade" ]; then
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
