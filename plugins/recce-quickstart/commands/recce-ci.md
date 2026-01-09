---
name: recce-ci
description: Set up Recce Cloud CI/CD for GitHub Actions - generates PR review and main branch workflows
---

# Recce CI/CD Setup

You are helping the user set up Recce Cloud CI/CD for their dbt project. This command generates GitHub Actions workflows for automated data validation on pull requests.

## Prerequisites

Before starting, ensure:
- User is in a git repository
- User has a dbt project (dbt_project.yml exists)
- User has a GitHub repository

## Workflow Overview

This command will:
1. Detect dbt project location and warehouse adapter
2. Check for existing CI workflows
3. Remind user to create Recce Cloud Project
4. Generate workflow files (PR + Main branch)
5. Provide secrets configuration guidance
6. Optionally commit and push changes

---

## Step 1: Environment Detection

### 1.1 Verify Git Repository

Run: `git rev-parse --git-dir`

- If FAILS: Tell user "This is not a git repository. Please run this command from within a git repository."
- If PASSES: Continue.

### 1.2 Get Repository URL

Run: `git remote get-url origin`

Parse the output to extract:
- Owner/Repo format (e.g., `DataRecce/jaffle_shop`)
- Full URL for display

Store as `REPO_URL` for later use.

### 1.3 Find dbt Project Location

Run: `find . -name "dbt_project.yml" -type f 2>/dev/null | head -1`

- If NOT FOUND: Tell user "No dbt_project.yml found. Please run this command from a dbt project directory."
- If FOUND: Calculate `PROJECT_DIR` relative to repo root.

**Monorepo Detection:**
```bash
# Get repo root
REPO_ROOT=$(git rev-parse --show-toplevel)

# Get dbt_project.yml directory
DBT_DIR=$(dirname $(find . -name "dbt_project.yml" -type f | head -1))

# Calculate relative path
PROJECT_DIR=$(realpath --relative-to="$REPO_ROOT" "$DBT_DIR")

# If PROJECT_DIR is ".", set to empty string
if [ "$PROJECT_DIR" = "." ]; then
  PROJECT_DIR=""
fi
```

Display to user:
```
📁 Detected Configuration:
• Repository: ${REPO_URL}
• dbt Project Directory: ${PROJECT_DIR:-"(repo root)"}
```

### 1.4 Detect Warehouse Adapter

Read profiles.yml to detect adapter type:

```bash
# Try project profiles.yml first, then ~/.dbt/profiles.yml
PROFILES_PATH="profiles.yml"
if [ ! -f "$PROFILES_PATH" ]; then
  PROFILES_PATH="$HOME/.dbt/profiles.yml"
fi

# Extract adapter type (look for 'type:' field)
grep -E "^\s+type:\s*" "$PROFILES_PATH" | head -1 | sed 's/.*type:\s*//' | tr -d ' '
```

Store detected adapter as `ADAPTER_TYPE` (snowflake, bigquery, postgres, databricks, redshift, duckdb, etc.)

Display:
```
🔌 Detected Warehouse: ${ADAPTER_TYPE}
```
