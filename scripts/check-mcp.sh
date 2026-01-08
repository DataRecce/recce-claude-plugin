#!/bin/bash
# Check Recce MCP Server status

PORT=${RECCE_MCP_PORT:-8081}
PID_FILE="/tmp/recce-mcp-server.pid"

if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ps -p "$PID" > /dev/null 2>&1; then
        # Check if endpoint responds
        if curl -s --max-time 2 "http://localhost:$PORT/sse" > /dev/null 2>&1; then
            echo "STATUS=RUNNING"
            echo "RECCE_MCP_PORT=$PORT"
            echo "RECCE_MCP_URL=http://localhost:$PORT/sse"
            echo "RECCE_MCP_PID=$PID"
            exit 0
        else
            echo "STATUS=UNHEALTHY"
            echo "MESSAGE=Process running but endpoint not responding"
            echo "RECCE_MCP_PID=$PID"
            exit 1
        fi
    else
        rm "$PID_FILE"
        echo "STATUS=NOT_RUNNING"
        echo "MESSAGE=Stale PID file removed"
        exit 1
    fi
else
    echo "STATUS=NOT_RUNNING"
    echo "MESSAGE=Recce MCP Server is not running"
    exit 1
fi
