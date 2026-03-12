#!/bin/bash
# Stop Recce MCP Server (recce-dev plugin) using project-scoped PID file

# ========== Project-scoped PID / Log Files ==========
# Same derivation as start-mcp.sh — must be identical

PROJECT_HASH=$(printf '%s' "$PWD" | md5 2>/dev/null | cut -c1-8 || printf '%s' "$PWD" | md5sum | cut -c1-8)
PID_FILE="/tmp/recce-mcp-${PROJECT_HASH}.pid"
LOG_FILE="/tmp/recce-mcp-${PROJECT_HASH}.log"

if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ps -p "$PID" > /dev/null 2>&1; then
        kill "$PID"
        rm -f "$PID_FILE"
        rm -f "$LOG_FILE"
        echo "STATUS=STOPPED"
        echo "MESSAGE=Recce MCP Server stopped (PID: $PID)"
    else
        rm -f "$PID_FILE"
        rm -f "$LOG_FILE"
        echo "STATUS=NOT_RUNNING"
        echo "MESSAGE=Recce MCP Server was not running (stale PID file removed)"
    fi
else
    echo "STATUS=NOT_RUNNING"
    echo "MESSAGE=Recce MCP Server is not running (no PID file for this project)"
fi
