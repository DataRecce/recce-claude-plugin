#!/bin/bash
# Start Recce MCP Server with prerequisite checks

PORT=${RECCE_MCP_PORT:-8081}
LOG_FILE="/tmp/recce-mcp-server.log"
PID_FILE="/tmp/recce-mcp-server.pid"

# ========== Prerequisite Checks ==========

# 1. Check if in dbt project directory
if [ ! -f "dbt_project.yml" ]; then
    echo "ERROR=NOT_DBT_PROJECT"
    echo "MESSAGE=Current directory is not a dbt project (dbt_project.yml not found)"
    echo "FIX=Please switch to a dbt project directory"
    exit 1
fi

# 2. Check base artifacts
if [ ! -f "target-base/manifest.json" ]; then
    echo "ERROR=MISSING_BASE_ARTIFACTS"
    echo "MESSAGE=Missing base artifacts (target-base/manifest.json)"
    echo "FIX=Run: git checkout <base-branch> && dbt build --target-path target-base"
    exit 1
fi

# 3. Check current artifacts
if [ ! -f "target/manifest.json" ]; then
    echo "ERROR=MISSING_TARGET_ARTIFACTS"
    echo "MESSAGE=Missing current artifacts (target/manifest.json)"
    echo "FIX=Run: dbt build"
    exit 1
fi

# 4. Check Recce installation
if ! command -v recce &> /dev/null; then
    echo "ERROR=RECCE_NOT_INSTALLED"
    echo "MESSAGE=Recce is not installed"
    echo "FIX=Run: pip install recce"
    exit 1
fi

# ========== Check if Already Running ==========

if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if ps -p "$OLD_PID" > /dev/null 2>&1; then
        echo "STATUS=ALREADY_RUNNING"
        echo "RECCE_MCP_PORT=$PORT"
        echo "RECCE_MCP_PID=$OLD_PID"
        exit 0
    else
        rm "$PID_FILE"
    fi
fi

# ========== Check Port Availability ==========

if lsof -i :$PORT > /dev/null 2>&1; then
    echo "ERROR=PORT_IN_USE"
    echo "MESSAGE=Port $PORT is already in use"
    echo "FIX=Set RECCE_MCP_PORT to use a different port, or stop the process using port $PORT"
    exit 1
fi

# ========== Start MCP Server ==========

nohup recce mcp-server --sse --port $PORT > "$LOG_FILE" 2>&1 &
MCP_PID=$!
echo $MCP_PID > "$PID_FILE"

# Wait for startup (max 15 seconds)
for i in {1..15}; do
    sleep 1

    # Check if process is still running
    if ! ps -p $MCP_PID > /dev/null 2>&1; then
        ERROR_LOG=$(tail -20 "$LOG_FILE" 2>/dev/null || echo "No log available")
        echo "ERROR=STARTUP_FAILED"
        echo "MESSAGE=Recce MCP Server failed to start"
        echo "LOG_FILE=$LOG_FILE"
        rm -f "$PID_FILE"
        exit 1
    fi

    # Check if SSE endpoint is available (use HTTP status code since SSE keeps connection open)
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 2 "http://localhost:$PORT/sse" 2>/dev/null)
    if [ "$HTTP_CODE" = "200" ]; then
        echo "STATUS=STARTED"
        echo "RECCE_MCP_PORT=$PORT"
        echo "RECCE_MCP_URL=http://localhost:$PORT/sse"
        echo "RECCE_MCP_PID=$MCP_PID"
        exit 0
    fi
done

# Timeout
echo "ERROR=STARTUP_TIMEOUT"
echo "MESSAGE=Recce MCP Server startup timed out (15 seconds)"
echo "LOG_FILE=$LOG_FILE"
exit 1
