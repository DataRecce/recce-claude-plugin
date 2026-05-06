#!/bin/bash
# Probe whether `recce` is available on PATH, mirroring the venv auto-detection
# used by run-mcp-stdio.sh so the skill check matches the MCP server launcher.
# Prints exactly one of:
#   RECCE=ready        (with RECCE_VIA=venv|system and RECCE_VERSION=<version>)
#   RECCE=missing
# Always exits 0.
set -u

for VENV_DIR in venv .venv; do
    if [ -f "$VENV_DIR/bin/activate" ]; then
        # shellcheck disable=SC1091
        source "$VENV_DIR/bin/activate"
        RECCE_VIA=venv
        break
    fi
done

if command -v recce >/dev/null 2>&1; then
    echo "RECCE=ready"
    echo "RECCE_VIA=${RECCE_VIA:-system}"
    VERSION=$(recce --version 2>/dev/null | head -1 | awk '{print $NF}')
    [ -n "$VERSION" ] && echo "RECCE_VERSION=$VERSION"
else
    echo "RECCE=missing"
fi

exit 0
