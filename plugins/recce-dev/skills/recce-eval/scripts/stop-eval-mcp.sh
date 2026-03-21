#!/bin/bash
# Stop eval Recce MCP Server using eval-scoped PID file
set -euo pipefail

EVAL_HASH=$(printf '%s-eval' "$PWD" | md5 2>/dev/null | cut -c1-8 \
    || printf '%s-eval' "$PWD" | md5sum | cut -c1-8)
PID_FILE="/tmp/recce-mcp-${EVAL_HASH}.pid"
LOG_FILE="/tmp/recce-mcp-${EVAL_HASH}.log"

if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ps -p "$PID" > /dev/null 2>&1; then
        kill "$PID"
        rm -f "$PID_FILE" "$LOG_FILE"
        echo "STATUS=STOPPED"
        echo "MESSAGE=Eval MCP Server stopped (PID: $PID)"
    else
        rm -f "$PID_FILE" "$LOG_FILE"
        echo "STATUS=NOT_RUNNING"
        echo "MESSAGE=Eval MCP Server was not running (stale PID file removed)"
    fi
else
    echo "STATUS=NOT_RUNNING"
    echo "MESSAGE=Eval MCP Server is not running (no PID file)"
fi
