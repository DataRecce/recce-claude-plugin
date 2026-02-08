# Workflow Templates

## PR Review Workflow (recce-ci-pr.yml)

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

## Main Branch Workflow (recce-ci-main.yml)

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

## Template Substitution Rules

### PATHS_FILTER
- If PROJECT_DIR is empty: `"**"`
- If PROJECT_DIR is set: `"{PROJECT_DIR}/**"`

### WORKING_DIR_DEFAULTS (if PROJECT_DIR is not empty)
```yaml
    defaults:
      run:
        working-directory: {PROJECT_DIR}
```

### PROJECT_DIR_WITH (if PROJECT_DIR is not empty)
```yaml
        with:
          project-dir: {PROJECT_DIR}
```

### ADAPTER_ENV_VARS
Load from the warehouse-secrets reference for the detected ADAPTER_TYPE.

## Integration Mode: Diff Format

When augmenting existing CI (Path B), show proposed changes in this format:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📝 Proposed Changes
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{CI_CONFIG_FILE}:

  [Install step - add recce-cloud to dependencies]
    {existing_install_command}
+   {pkg_manager} install recce-cloud

  [{job_type} job "{job_name}" - after line {line} ({command})]
+   dbt docs generate --target {target}
+   recce-cloud upload [--type prod]
+   env:
+     GITHUB_TOKEN: {platform_token}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```
