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

---

## Step 3: Recce Cloud Project Setup

### Important Prerequisite

Display this reminder to the user:

```
⚠️  重要：請先在 Recce Cloud 建立 Project

CI/CD 上傳需要對應的 Recce Cloud Project。
Project 由 Repository URL + Project Directory 唯一識別。

您的設定：
• Repository: ${REPO_URL}
• Project Directory: ${PROJECT_DIR:-"(repo root)"}

請確認已在 Recce Cloud 建立對應 Project：
👉 https://cloud.datarecce.io/projects/new

設定時請確保：
1. Repository URL 完全匹配
2. Project Directory 設為: ${PROJECT_DIR:-"(留空)"}
```

Use AskUserQuestion with options:

1. **已建立，繼續** - User confirms project exists, proceed to Step 4
2. **開啟 Recce Cloud** - Inform user to create project in browser, then wait for confirmation
3. **稍後設定，先生成 workflow** - Skip for now, proceed with workflow generation (will show warning in generated files)

---

## Step 4: Generate Workflows

### 4a: Standalone Mode (MODE=standalone)

Create `.github/workflows/` directory if it doesn't exist:
```bash
mkdir -p .github/workflows
```

#### Generate recce-ci-pr.yml

Create `.github/workflows/recce-ci-pr.yml` using the Write tool with this template:

**Template variables to substitute:**
- `${PATHS_FILTER}` - If PROJECT_DIR is empty: `"**"`, else: `"${PROJECT_DIR}/**"`
- `${WORKING_DIR_DEFAULTS}` - If PROJECT_DIR is empty: omit, else: include defaults block
- `${PROJECT_DIR_WITH}` - If PROJECT_DIR is empty: omit, else: include with block
- `${ADAPTER_ENV_VARS}` - Based on ADAPTER_TYPE (see Step 5 for mapping)

```yaml
name: Recce CI - PR Review

on:
  pull_request:
    branches: [main]
    paths:
      - "${PATHS_FILTER}"

# ⚠️ Prerequisites:
# 1. Create Recce Cloud Project: https://cloud.datarecce.io
#    - Repository: ${REPO_URL}
#    - Project Dir: ${PROJECT_DIR}
# 2. Configure GitHub Secrets (see comments in env section)

concurrency:
  group: recce-pr-${{ github.event.pull_request.number }}
  cancel-in-progress: true

env:
  GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
${ADAPTER_ENV_VARS}

jobs:
  recce-pr-review:
    runs-on: ubuntu-latest
${WORKING_DIR_DEFAULTS}
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: "pip"

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: dbt Build & Docs
        run: |
          dbt deps
          dbt build
          dbt docs generate

      - name: Recce Cloud Review
        uses: DataRecce/recce-cloud-cicd-action@v1
${PROJECT_DIR_WITH}
```

#### Generate recce-ci-main.yml

Create `.github/workflows/recce-ci-main.yml` using the Write tool:

```yaml
name: Recce CI - Main Branch

on:
  push:
    branches: [main]
    paths:
      - "${PATHS_FILTER}"
  workflow_dispatch:

# ⚠️ Prerequisites: (same as PR workflow)

concurrency:
  group: recce-main-${{ github.ref }}
  cancel-in-progress: true

env:
  GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
  DBT_TARGET: prod
${ADAPTER_ENV_VARS}

jobs:
  recce-base-update:
    runs-on: ubuntu-latest
${WORKING_DIR_DEFAULTS}
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: "pip"

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Download previous artifacts
        run: recce cloud download-artifacts --target-path previous
        continue-on-error: true

      - name: dbt Build & Docs
        run: |
          dbt deps
          dbt build --target ${{ env.DBT_TARGET }}
          dbt docs generate --target ${{ env.DBT_TARGET }}

      - name: Recce Cloud Upload
        uses: DataRecce/recce-cloud-cicd-action@v1
${PROJECT_DIR_WITH}
```

#### Template Substitution Rules

**WORKING_DIR_DEFAULTS (if PROJECT_DIR is not empty):**
```yaml
    defaults:
      run:
        working-directory: ${PROJECT_DIR}
```

**PROJECT_DIR_WITH (if PROJECT_DIR is not empty):**
```yaml
        with:
          project-dir: ${PROJECT_DIR}
```

After generating both files, display:
```
✅ Generated workflow files:
• .github/workflows/recce-ci-pr.yml
• .github/workflows/recce-ci-main.yml
```

---

### 4b: Integration Mode (MODE=integrate)

When user selects integration mode, help them add Recce steps to their existing CI workflow.

#### 4b.1 Analyze Existing Workflow

Read the user's selected `TARGET_WORKFLOW` file using the Read tool.

Look for:
1. **dbt build step** - Where dbt commands are executed
2. **Python setup** - How Python environment is configured
3. **Workflow trigger** - What triggers the workflow (push, pull_request)
4. **Job structure** - Single job or matrix build

#### 4b.2 Determine Integration Strategy

**If workflow has a dbt build step:**

Suggest adding after the dbt build step:
```yaml
      - name: Generate dbt docs
        run: dbt docs generate

      - name: Recce Cloud Review
        uses: DataRecce/recce-cloud-cicd-action@v1
        # with:
        #   project-dir: ${PROJECT_DIR}  # Uncomment if monorepo
```

**If workflow doesn't have dbt:**

Tell user: "This workflow doesn't appear to have dbt commands. Consider using standalone mode instead, or show me the workflow where you run dbt."

#### 4b.3 Search Documentation for Best Practices

Use `recce-docs` MCP to search for integration guidance:

```
Search: "GitHub Actions integration existing CI"
```

Apply relevant recommendations from the documentation.

#### 4b.4 Present Changes

Show the user the proposed changes using diff format:

```diff
+ # Added by Recce CI Setup
+       - name: Generate dbt docs
+         run: dbt docs generate
+
+       - name: Recce Cloud Review
+         uses: DataRecce/recce-cloud-cicd-action@v1
```

Ask for confirmation before applying changes.

#### 4b.5 Apply Changes

Use the Edit tool to modify the workflow file.

Display:
```
✅ Updated workflow: ${TARGET_WORKFLOW}
   Added Recce Cloud integration steps.
```

**Important notes for integration mode:**
- Preserve existing workflow structure and formatting
- Add comments explaining new steps
- Don't remove or modify existing steps
- If workflow uses matrix builds, apply Recce step to appropriate jobs only
