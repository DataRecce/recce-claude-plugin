---
name: dbt Project Detection
description: >
  This skill should be used when the user needs to "detect dbt project",
  "find dbt_project.yml", "identify warehouse adapter", "check dbt environment",
  "detect CI/CD platform", or when any CI/CD setup needs environment information.
  Covers git repository detection, dbt project parsing, warehouse adapter
  identification, Python tooling detection, CI/CD platform scanning, and
  dbt command analysis.
version: 0.1.0
---

# dbt Project Detection

Detect and characterize a dbt project environment by collecting repository metadata,
project configuration, warehouse adapter, Python tooling, CI/CD platform, and existing
dbt commands. All detection steps store results into named variables for downstream
skills to consume.

Run all detection steps (1.1 through 1.8) sequentially. Do NOT display output to
the user until the Detection Report in step 1.8 is fully assembled.

---

## 1.1 Git Repository

Determine the git remote URL for the current repository.

**Action:** Retrieve the default remote (origin) URL from the local git configuration.

**Store:**
- `REPO_REMOTE` — the full remote URL (e.g., `https://github.com/owner/repo.git`), or `none` if no remote is configured
- `REPO_OWNER_NAME` — the `owner/repo` slug parsed from the URL (strip `.git` suffix and any protocol/host prefix)

**Edge cases:**
- If no git remote exists, set `REPO_REMOTE` to `none` and `REPO_OWNER_NAME` to `none`. Flag as a warning ("No git remote configured") but do not block further detection steps.
- If the remote uses SSH format (`git@github.com:owner/repo.git`), parse equivalently to the HTTPS format.

---

## 1.2 dbt Project

Check if `dbt_project.yml` exists in the current working directory or any subdirectory.

**Action:** Locate the `dbt_project.yml` file. If found, read the file and extract the `name` field.

**Store:**
- `DBT_PROJECT_NAME` — the value of the `name` key in `dbt_project.yml`, or `none` if the file is not found

**Edge cases:**
- If `dbt_project.yml` does not exist, set `DBT_PROJECT_NAME` to `none` and flag as a warning ("No dbt_project.yml found"). Do not block further detection steps.
- If multiple `dbt_project.yml` files exist (e.g., in a monorepo), use the one closest to the current working directory.

---

## 1.3 Monorepo Detection

Determine if the dbt project resides in a subdirectory of the git repository root.

**Action:** Obtain the git repository root directory. Obtain the directory containing `dbt_project.yml`. Calculate the relative path from the repository root to the dbt project directory.

**Logic:**
1. Identify the top-level directory of the git repository.
2. Identify the directory where `dbt_project.yml` is located.
3. Compute the relative path between these two directories.
4. If the relative path is `.` (the project is at the repository root), treat it as a standard (non-monorepo) layout.

**Store:**
- `PROJECT_DIR` — the relative path from the git root to the dbt project directory (empty string if at root)
- `IS_MONOREPO` — `true` if `PROJECT_DIR` is non-empty, `false` otherwise

**Edge cases:**
- If the git root cannot be determined (not a git repo), set `PROJECT_DIR` to empty string and `IS_MONOREPO` to `false`.
- If `dbt_project.yml` was not found in step 1.2, skip this step and set both variables to their defaults.

---

## 1.4 Warehouse Adapter Detection

Read the dbt profiles configuration to identify which warehouse adapter the project uses.

**Action:** Read the `profiles.yml` file to extract the `type` field under the target configuration. Look first for `profiles.yml` in the project directory, then fall back to the user-level dbt configuration directory (typically `~/.dbt/profiles.yml`).

**Adapter package mapping:**

| Adapter Type | dbt Package |
|-------------|-------------|
| snowflake | dbt-snowflake |
| bigquery | dbt-bigquery |
| postgres | dbt-postgres |
| redshift | dbt-redshift |
| databricks | dbt-databricks |
| duckdb | dbt-duckdb |
| spark | dbt-spark |
| trino | dbt-trino |
| athena | dbt-athena-community |
| clickhouse | dbt-clickhouse |

**Store:**
- `ADAPTER_TYPE` — the detected adapter type string (e.g., `snowflake`, `bigquery`), or `unknown` if not determined
- `ADAPTER_PACKAGE` — the corresponding dbt adapter package name from the mapping table, or `unknown`

**Edge cases:**
- If `profiles.yml` is not found in either location, set both to `unknown` and flag as a warning.
- If the `type` field is not present or the adapter is not in the mapping table, store the raw type value in `ADAPTER_TYPE` and set `ADAPTER_PACKAGE` to `dbt-{type}` as a best-guess default.

---

## 1.5 Python Tooling Detection

Check project files and CI configuration to determine the Python package manager and version in use.

**Action:** Examine project root files to identify the package manager. Also inspect CI configuration files (if detected in step 1.6, or check common locations) for tooling hints.

**Logic for package manager:**
1. If `uv.lock` exists in the project directory, the package manager is `uv`.
2. If `pyproject.toml` exists (without `uv.lock`), the package manager is likely `uv`.
3. If only `requirements.txt` exists, the package manager is `pip`.
4. If CI configuration files reference `astral-sh/setup-uv`, confirm `uv`.
5. If CI configuration files reference `pip install`, confirm `pip`.
6. If none of the above match, set to `unknown`.

**Logic for Python version:**
1. Check CI configuration files for a `python-version` setting.
2. Check `pyproject.toml` for `requires-python` if present.
3. If neither is found, set to `unknown`.

**Store:**
- `DETECTED_PKG_MANAGER` — `uv`, `pip`, or `unknown`
- `DETECTED_PYTHON_VERSION` — version string (e.g., `3.12`) or `unknown`

**Edge cases:**
- If `pyproject.toml` exists with a `[tool.uv]` section, strongly prefer `uv` even without `uv.lock`.
- If CI files and project files give conflicting signals (e.g., `uv.lock` exists but CI uses `pip install`), prefer the CI configuration as the authoritative source.

---

## 1.6 CI/CD Platform Detection

Check for CI/CD configuration files to determine which platform the project uses.

**Action:** Examine the project directory for known CI/CD configuration file patterns.

**Platform detection table:**

| Platform | Config File Pattern |
|----------|-------------------|
| GitHub Actions | `.github/workflows/*.yml`, `.github/workflows/*.yaml` |
| GitLab CI | `.gitlab-ci.yml` |
| CircleCI | `.circleci/config.yml` |
| Jenkins | `Jenkinsfile` |
| Azure Pipelines | `azure-pipelines.yml` |
| Bitbucket Pipelines | `bitbucket-pipelines.yml` |

**Store:**
- `CI_PLATFORM` — `github-actions`, `gitlab`, `circleci`, `jenkins`, `azure`, `bitbucket`, or `none`
- `CI_CONFIG_FILES` — list of detected configuration file paths

**Edge cases:**
- If multiple platforms are detected (e.g., both `.github/workflows/` and `.gitlab-ci.yml`), store the platform with more config files as primary, and note all detected platforms.
- If no CI configuration files are found, set `CI_PLATFORM` to `none` and `CI_CONFIG_FILES` to an empty list.

---

## 1.7 dbt Command Analysis

Search CI/CD configuration files for dbt command invocations and classify them.

**Action:** For each file in `CI_CONFIG_FILES`, search for lines containing dbt commands (`dbt build`, `dbt run`, `dbt test`, `dbt seed`, `dbt snapshot`, `dbt deps`). Extract context for each match.

**For each dbt command found, extract:**
1. **File** — which configuration file contains the command
2. **Line** — the line number where the command appears
3. **Command** — the full dbt command string (e.g., `dbt build --target ci`)
4. **Target** — the `--target` value if present, otherwise `default`
5. **Job type** — classify as CI or CD based on trigger context

**Job type classification logic:**
- GitHub Actions: `on: pull_request` indicates CI; `on: push` to main/master indicates CD
- GitLab CI: `rules:` with `merge_request` indicates CI; rules matching `branches: [main]` indicates CD
- CircleCI: Examine workflow triggers for PR vs branch push patterns
- Other platforms: Infer from job names containing keywords like "test", "review", "pr" (CI) or "deploy", "prod", "release" (CD)

**Multi-line handling:** dbt commands may span multiple lines using YAML multi-line syntax (`|`, `>`, or continuation characters). When a match is found, read surrounding lines to capture the complete command.

**Additional checks:**
- Search for `dbt docs generate` in each config file. Store whether it was found and whether it appears in CI jobs, CD jobs, or both.
- Search for `recce-cloud` references (package install, CLI invocation, or GitHub Action usage).

**Store:**
- `DBT_COMMANDS[]` — array of objects, each containing: `file`, `line`, `command`, `target`, `job_name`, `job_type`
- `DBT_DOCS_GENERATE_EXISTS` — `true` or `false`
- `RECCE_CONFIGURED` — `true` or `false`

**Edge cases:**
- If `CI_CONFIG_FILES` is empty, skip this step and set `DBT_COMMANDS` to an empty array, `DBT_DOCS_GENERATE_EXISTS` to `false`, and `RECCE_CONFIGURED` to `false`.
- If dbt commands are found but job type cannot be determined, set `job_type` to `unknown`.

---

## 1.8 Detection Report

After ALL detection steps (1.1 through 1.7) complete, assemble and display the following report.

**Detection Report Template:**

```
**Environment Detection Report**

**Repository**
- Remote: {REPO_OWNER_NAME} | (warning) No git remote

**dbt Project**
- Name: {DBT_PROJECT_NAME} | (warning) No dbt_project.yml
- Location: {PROJECT_DIR} (monorepo) | (repo root)

**CI/CD Platform**
- Detected: {CI_PLATFORM} | (warning) No CI config found
- Config files: {CI_CONFIG_FILES}

**dbt Commands Found:**

| File | Line | Command | Target | Type |
|------|------|---------|--------|------|
| {file} | {line} | `{command}` | {target} | {type} |

**dbt docs generate:** Found | Found (CD only) | Not found
**Recce Cloud:** Configured | Not configured

**Python Tooling**
- Package manager: {DETECTED_PKG_MANAGER}
- Python version: {DETECTED_PYTHON_VERSION}

**Warehouse Adapter**
- Type: {ADAPTER_TYPE}
- Package: {ADAPTER_PACKAGE}
```

**Rendering rules:**
- For each field, display the detected value if available, or the warning/fallback text if the value is `none` or `unknown`.
- The dbt commands table should contain one row per command found. If no commands were found, display "No dbt commands found in CI configuration" instead of the table.
- Use the markdown pipe-separated table format for dbt commands (not box-drawing characters).

---

## Stored Variables Summary

All variables produced by this skill, available for consumption by downstream skills:

| Variable | Type | Source Step |
|----------|------|-------------|
| `REPO_REMOTE` | string | 1.1 |
| `REPO_OWNER_NAME` | string | 1.1 |
| `DBT_PROJECT_NAME` | string | 1.2 |
| `PROJECT_DIR` | string | 1.3 |
| `IS_MONOREPO` | boolean | 1.3 |
| `ADAPTER_TYPE` | string | 1.4 |
| `ADAPTER_PACKAGE` | string | 1.4 |
| `DETECTED_PKG_MANAGER` | string | 1.5 |
| `DETECTED_PYTHON_VERSION` | string | 1.5 |
| `CI_PLATFORM` | string | 1.6 |
| `CI_CONFIG_FILES` | list | 1.6 |
| `DBT_COMMANDS[]` | array | 1.7 |
| `DBT_DOCS_GENERATE_EXISTS` | boolean | 1.7 |
| `RECCE_CONFIGURED` | boolean | 1.7 |

---

## Additional Resources

- `references/ci-workflows.md` — GitHub Actions templates for full and incremental builds
- `references/adapter-configs.md` — Per-adapter profiles.yml examples
