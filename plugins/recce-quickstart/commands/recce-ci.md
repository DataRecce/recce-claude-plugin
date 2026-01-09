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

---

## Step 5: Secrets Configuration Guide

Based on the detected `ADAPTER_TYPE`, provide specific guidance for configuring GitHub Secrets.

### 5.1 Display Secrets Guide

Display the appropriate secrets table based on the detected adapter:

---

#### Snowflake

```
🔐 Required GitHub Secrets for Snowflake:

┌────────────────────────┬─────────────────────────────────┐
│ Secret Name            │ Description                     │
├────────────────────────┼─────────────────────────────────┤
│ SNOWFLAKE_ACCOUNT      │ Account identifier (xxx.region) │
│ SNOWFLAKE_USER         │ Username                        │
│ SNOWFLAKE_PASSWORD     │ Password                        │
├────────────────────────┼─────────────────────────────────┤
│ SNOWFLAKE_ROLE         │ (Optional) Role name            │
│ SNOWFLAKE_WAREHOUSE    │ (Optional) Warehouse name       │
│ SNOWFLAKE_DATABASE     │ (Optional) Database name        │
└────────────────────────┴─────────────────────────────────┘

Add to workflow env section:
  SNOWFLAKE_ACCOUNT: ${{ secrets.SNOWFLAKE_ACCOUNT }}
  SNOWFLAKE_USER: ${{ secrets.SNOWFLAKE_USER }}
  SNOWFLAKE_PASSWORD: ${{ secrets.SNOWFLAKE_PASSWORD }}
```

---

#### BigQuery

```
🔐 Required GitHub Secrets for BigQuery:

┌────────────────────────┬─────────────────────────────────┐
│ Secret Name            │ Description                     │
├────────────────────────┼─────────────────────────────────┤
│ GCP_SERVICE_ACCOUNT    │ Service Account JSON key        │
└────────────────────────┴─────────────────────────────────┘

Add to workflow env section:
  GOOGLE_APPLICATION_CREDENTIALS_JSON: ${{ secrets.GCP_SERVICE_ACCOUNT }}

Alternative: Use Workload Identity Federation (recommended for production)
```

---

#### PostgreSQL

```
🔐 Required GitHub Secrets for PostgreSQL:

┌────────────────────────┬─────────────────────────────────┐
│ Secret Name            │ Description                     │
├────────────────────────┼─────────────────────────────────┤
│ POSTGRES_HOST          │ Database host                   │
│ POSTGRES_USER          │ Username                        │
│ POSTGRES_PASSWORD      │ Password                        │
│ POSTGRES_DATABASE      │ Database name                   │
│ POSTGRES_PORT          │ (Optional) Port, default 5432   │
└────────────────────────┴─────────────────────────────────┘

Add to workflow env section:
  POSTGRES_HOST: ${{ secrets.POSTGRES_HOST }}
  POSTGRES_USER: ${{ secrets.POSTGRES_USER }}
  POSTGRES_PASSWORD: ${{ secrets.POSTGRES_PASSWORD }}
  POSTGRES_DATABASE: ${{ secrets.POSTGRES_DATABASE }}
```

---

#### Databricks

```
🔐 Required GitHub Secrets for Databricks:

┌────────────────────────┬─────────────────────────────────┐
│ Secret Name            │ Description                     │
├────────────────────────┼─────────────────────────────────┤
│ DATABRICKS_HOST        │ Workspace URL                   │
│ DATABRICKS_TOKEN       │ Personal Access Token           │
│ DATABRICKS_HTTP_PATH   │ SQL Warehouse HTTP path         │
└────────────────────────┴─────────────────────────────────┘

Add to workflow env section:
  DATABRICKS_HOST: ${{ secrets.DATABRICKS_HOST }}
  DATABRICKS_TOKEN: ${{ secrets.DATABRICKS_TOKEN }}
  DATABRICKS_HTTP_PATH: ${{ secrets.DATABRICKS_HTTP_PATH }}
```

---

#### Redshift

```
🔐 Required GitHub Secrets for Redshift:

┌────────────────────────┬─────────────────────────────────┐
│ Secret Name            │ Description                     │
├────────────────────────┼─────────────────────────────────┤
│ REDSHIFT_HOST          │ Cluster endpoint                │
│ REDSHIFT_USER          │ Username                        │
│ REDSHIFT_PASSWORD      │ Password                        │
│ REDSHIFT_DATABASE      │ Database name                   │
│ REDSHIFT_PORT          │ (Optional) Port, default 5439   │
└────────────────────────┴─────────────────────────────────┘

Add to workflow env section:
  REDSHIFT_HOST: ${{ secrets.REDSHIFT_HOST }}
  REDSHIFT_USER: ${{ secrets.REDSHIFT_USER }}
  REDSHIFT_PASSWORD: ${{ secrets.REDSHIFT_PASSWORD }}
  REDSHIFT_DATABASE: ${{ secrets.REDSHIFT_DATABASE }}
```

---

#### DuckDB

```
🔐 GitHub Secrets for DuckDB:

┌────────────────────────┬─────────────────────────────────┐
│ Secret Name            │ Description                     │
├────────────────────────┼─────────────────────────────────┤
│ (No secrets required)  │ DuckDB is a local file database │
└────────────────────────┴─────────────────────────────────┘

DuckDB doesn't require external credentials.
```

---

### 5.2 Provide Setup Link

Display:
```
📝 Configure secrets at:
👉 https://github.com/${REPO_OWNER}/${REPO_NAME}/settings/secrets/actions

Steps:
1. Click "New repository secret"
2. Add each secret from the table above
3. Ensure values match your profiles.yml configuration
```

---

## Step 6: Commit & Complete

### 6.1 Show Summary

Display a summary of all changes:

```
📋 Recce CI/CD Setup Summary

Configuration:
• Repository: ${REPO_URL}
• dbt Project: ${PROJECT_DIR:-"(repo root)"}
• Warehouse: ${ADAPTER_TYPE}
• Mode: ${MODE}

Files created/modified:
${FILE_LIST}

Next steps:
1. Configure GitHub Secrets (see guide above)
2. Create Recce Cloud Project (if not done)
3. Push changes to trigger workflows
```

### 6.2 Ask to Commit

Use AskUserQuestion to offer commit options:

```
要我幫你 commit 這些變更嗎？
```

Options:
1. **Commit 並 push** - Commit changes and push to remote
2. **只 commit** - Commit locally, don't push yet
3. **不要 commit** - Keep changes uncommitted for manual review

### 6.3 Execute Commit

**If option 1 (Commit and push):**

```bash
git add .github/workflows/recce-ci-*.yml
git commit -m "ci: add Recce Cloud CI/CD workflows

- Add PR review workflow (recce-ci-pr.yml)
- Add main branch workflow (recce-ci-main.yml)
- Configured for ${ADAPTER_TYPE} warehouse

Generated by /recce-ci command"

git push origin HEAD
```

Display:
```
✅ Changes committed and pushed!

Your Recce CI/CD is now set up. On your next PR:
1. The PR workflow will run automatically
2. Recce will analyze data changes
3. Results will be posted as PR comments

📖 Learn more: https://datarecce.io/docs/recce-cloud/github-integration
```

**If option 2 (Commit only):**

```bash
git add .github/workflows/recce-ci-*.yml
git commit -m "ci: add Recce Cloud CI/CD workflows

- Add PR review workflow (recce-ci-pr.yml)
- Add main branch workflow (recce-ci-main.yml)
- Configured for ${ADAPTER_TYPE} warehouse

Generated by /recce-ci command"
```

Display:
```
✅ Changes committed locally.

When you're ready, push with:
  git push origin HEAD

📖 Learn more: https://datarecce.io/docs/recce-cloud/github-integration
```

**If option 3 (No commit):**

Display:
```
✅ Setup complete! Changes are staged but not committed.

Review the generated files:
• .github/workflows/recce-ci-pr.yml
• .github/workflows/recce-ci-main.yml

When ready, commit manually:
  git add .github/workflows/recce-ci-*.yml
  git commit -m "ci: add Recce Cloud CI/CD workflows"
  git push origin HEAD

📖 Learn more: https://datarecce.io/docs/recce-cloud/github-integration
```

---

## Troubleshooting Tips

If users encounter issues:

### Workflow not triggering
- Check that the PR targets the `main` branch
- Verify the `paths` filter matches their dbt project location
- Ensure GitHub Actions is enabled for the repository

### Recce Cloud upload fails
- Verify the Recce Cloud Project exists with matching repo URL and project directory
- Check GitHub Secrets are correctly configured
- Ensure `GITHUB_TOKEN` has appropriate permissions

### dbt build fails
- Verify all warehouse secrets are set correctly
- Check that `requirements.txt` includes all necessary dbt packages
- Ensure profiles.yml target names match workflow configuration

### For more help
- Use `/recce-check` to validate your Recce setup
- Check Recce documentation: https://datarecce.io/docs
- Contact support: support@datarecce.io
