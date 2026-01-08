#!/bin/bash
# Check if current directory is a dbt project and Recce status

# Check for dbt project
if [ -f "dbt_project.yml" ]; then
    echo "DBT_PROJECT_DETECTED=true"

    # Extract project name
    PROJECT_NAME=$(grep -E "^name:" dbt_project.yml | head -1 | sed 's/name:[[:space:]]*//' | tr -d "'" | tr -d '"')
    echo "DBT_PROJECT_NAME=$PROJECT_NAME"

    # Check Python/pip
    if command -v python3 &> /dev/null || command -v python &> /dev/null; then
        echo "PYTHON_INSTALLED=true"
    else
        echo "PYTHON_INSTALLED=false"
    fi

    # Check dbt
    if command -v dbt &> /dev/null; then
        echo "DBT_INSTALLED=true"
        DBT_VERSION=$(dbt --version 2>/dev/null | head -1)
        echo "DBT_VERSION=$DBT_VERSION"
    else
        echo "DBT_INSTALLED=false"
    fi

    # Check Recce
    if command -v recce &> /dev/null; then
        echo "RECCE_INSTALLED=true"
        RECCE_VERSION=$(recce --version 2>/dev/null | head -1)
        echo "RECCE_VERSION=$RECCE_VERSION"
    else
        echo "RECCE_INSTALLED=false"
    fi

    # Check target artifacts
    if [ -d "target" ] && [ -f "target/manifest.json" ]; then
        echo "TARGET_EXISTS=true"
    else
        echo "TARGET_EXISTS=false"
    fi

    # Check target-base artifacts
    if [ -d "target-base" ] && [ -f "target-base/manifest.json" ]; then
        echo "TARGET_BASE_EXISTS=true"
    else
        echo "TARGET_BASE_EXISTS=false"
    fi

    # Check profiles.yml
    if [ -f "profiles.yml" ] || [ -f "$HOME/.dbt/profiles.yml" ]; then
        echo "PROFILES_EXISTS=true"
    else
        echo "PROFILES_EXISTS=false"
    fi

    # Check MCP server status
    PID_FILE="/tmp/recce-mcp-server.pid"
    if [ -f "$PID_FILE" ] && ps -p "$(cat "$PID_FILE")" > /dev/null 2>&1; then
        echo "RECCE_MCP_RUNNING=true"
    else
        echo "RECCE_MCP_RUNNING=false"
    fi
else
    echo "DBT_PROJECT_DETECTED=false"
fi
