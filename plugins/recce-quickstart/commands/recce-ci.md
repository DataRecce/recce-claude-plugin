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

---

## Step 2: Check Existing CI & Select Mode

### 2.1 Scan for Existing Workflows

Run: `ls .github/workflows/*.yml .github/workflows/*.yaml 2>/dev/null`

Parse results into a list of existing workflow files.

### 2.2 Mode Selection

**If NO existing workflows found:**

Inform user:
```
📋 No existing CI workflows detected.
   I'll create standalone Recce CI workflows for you.
```

Set `MODE=standalone` and proceed to Step 3.

**If existing workflows found:**

Use AskUserQuestion to present options:

```
偵測到現有 CI workflows:
• .github/workflows/ci.yml
• .github/workflows/deploy.yml

請選擇設置方式：
```

Options:
1. **建立獨立 Recce workflow (推薦)** - Creates separate recce-ci-pr.yml and recce-ci-main.yml files that won't interfere with existing CI
2. **整合到現有 CI workflow** - I'll help you add Recce steps to an existing workflow

Store selection as `MODE` (standalone or integrate).

**If MODE=integrate:**
- List the workflow files
- Ask user which workflow to modify
- Store as `TARGET_WORKFLOW`
