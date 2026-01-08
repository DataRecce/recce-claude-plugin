#!/bin/bash
# Stop Recce MCP Server

PID_FILE="/tmp/recce-mcp-server.pid"

if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ps -p "$PID" > /dev/null 2>&1; then
        kill "$PID"
        rm "$PID_FILE"
        echo "STATUS=STOPPED"
        echo "MESSAGE=Recce MCP Server stopped (PID: $PID)"
    else
        rm "$PID_FILE"
        echo "STATUS=NOT_RUNNING"
        echo "MESSAGE=Recce MCP Server was not running (stale PID file removed)"
    fi
else
    echo "STATUS=NOT_RUNNING"
    echo "MESSAGE=Recce MCP Server is not running"
fi
