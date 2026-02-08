# Monorepo Guide

## Detection

Determine if dbt project is in a subdirectory:
1. Get repo root directory
2. Get dbt_project.yml directory
3. Calculate relative path
4. If path is "." → not monorepo; otherwise → monorepo

Store: `PROJECT_DIR` (relative path), `IS_MONOREPO` (boolean)

## Workflow Path Filtering

When IS_MONOREPO is true, add paths filter to workflows:

```yaml
on:
  pull_request:
    branches: [main]
    paths:
      - "{PROJECT_DIR}/**"
```

## Working Directory Defaults

When IS_MONOREPO is true, add working directory to jobs:

```yaml
jobs:
  recce-review:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: {PROJECT_DIR}
```

## Recce Action Project Dir

When IS_MONOREPO is true, pass project-dir to Recce action:

```yaml
      - name: Recce Cloud Review
        uses: DataRecce/recce-cloud-cicd-action@v1
        with:
          project-dir: {PROJECT_DIR}
```
