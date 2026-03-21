#!/bin/bash
# Start Recce MCP Server for eval with isolated port and PID namespace
# Does NOT delegate to start-mcp.sh — manages its own PID file.
set -euo pipefail

# ========== Port Resolution ==========
EVAL_PORT="${RECCE_EVAL_MCP_PORT:-8085}"

# ========== Project .env Loading ==========
if [ -f ".env" ]; then
    set -a
    source .env
    set +a
fi

# ========== Eval-scoped PID / Log Files ==========
EVAL_HASH=$(printf '%s-eval' "$PWD" | md5 2>/dev/null | cut -c1-8 \
    || printf '%s-eval' "$PWD" | md5sum | cut -c1-8)
PID_FILE="/tmp/recce-mcp-${EVAL_HASH}.pid"
LOG_FILE="/tmp/recce-mcp-${EVAL_HASH}.log"

# ========== Venv Auto-Detection ==========
# If recce is not on PATH, try activating a local venv
if ! command -v recce &>/dev/null; then
    for VENV_DIR in venv .venv; do
        if [ -f "$VENV_DIR/bin/activate" ]; then
            # shellcheck disable=SC1091
            source "$VENV_DIR/bin/activate"
            break
        fi
    done
fi

# ========== Prerequisite Checks ==========
if [ ! -f "dbt_project.yml" ]; then
    echo "ERROR=NOT_DBT_PROJECT"
    echo "MESSAGE=Current directory is not a dbt project"
    exit 1
fi

if [ ! -f "target/manifest.json" ]; then
    echo "ERROR=MISSING_TARGET_ARTIFACTS"
    echo "MESSAGE=Missing target/manifest.json"
    echo "FIX=Run: dbt build"
    exit 1
fi

if ! command -v recce &>/dev/null; then
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
        echo "PORT=$EVAL_PORT"
        echo "PID=$OLD_PID"
        echo "URL=http://localhost:$EVAL_PORT/sse"
        exit 0
    else
        rm "$PID_FILE"
    fi
fi

# ========== Check Port Availability ==========
if lsof -i :"$EVAL_PORT" > /dev/null 2>&1; then
    echo "ERROR=PORT_IN_USE"
    echo "MESSAGE=Eval port $EVAL_PORT is already in use"
    echo "FIX=Set RECCE_EVAL_MCP_PORT or stop the process using port $EVAL_PORT"
    exit 1
fi

# ========== Start MCP Server ==========
nohup recce mcp-server --sse --port "$EVAL_PORT" > "$LOG_FILE" 2>&1 &
MCP_PID=$!
echo "$MCP_PID" > "$PID_FILE"

echo "STARTING=true"
echo "PORT=$EVAL_PORT"
echo "PID=$MCP_PID"
echo "LOG_FILE=$LOG_FILE"

# Wait for startup (max 15 seconds)
for i in {1..15}; do
    sleep 1
    if ! ps -p "$MCP_PID" > /dev/null 2>&1; then
        echo "ERROR=STARTUP_FAILED"
        echo "MESSAGE=Recce MCP Server failed to start"
        echo "LOG_FILE=$LOG_FILE"
        rm -f "$PID_FILE"
        exit 1
    fi
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 2 "http://localhost:$EVAL_PORT/sse" 2>/dev/null)
    if [ "$HTTP_CODE" = "200" ]; then
        echo "STATUS=STARTED"
        echo "URL=http://localhost:$EVAL_PORT/sse"
        exit 0
    fi
done

echo "ERROR=STARTUP_TIMEOUT"
echo "MESSAGE=Recce MCP Server startup timed out (15 seconds)"
echo "LOG_FILE=$LOG_FILE"
exit 1
