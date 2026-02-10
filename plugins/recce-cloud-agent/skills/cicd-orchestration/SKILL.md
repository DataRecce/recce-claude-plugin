# CI/CD Orchestration (Web Agent)

## Trigger

User asks about: setting up CI/CD, configuring Recce in pipeline,
troubleshooting CI failures, automating PR reviews, or diagnosing
dbt project / CI configuration issues.

## Phase 1: Knowledge Gathering (Doc MCP)

1. `search_docs("recce CI/CD setup guide")` → read top results
2. `search_docs("github actions workflow recce")` → read workflow examples
3. For relevant adapter: `search_docs("<adapter> recce setup")` (e.g., snowflake, bigquery, postgres)
4. For each page with internal links → follow via `get_doc_page`
5. **Broken link handling:**
   - If `get_doc_page` returns "Page not found": skip gracefully
   - Re-search for similar content with alternative query
   - Inform user: "文件中的 [link] 目前無法存取，已跳過"

## Phase 2: Repository Exploration (GitHub Tools)

1. `get_github_status` → confirm GitHub connection
   - If not connected: guide user with `{{action:install-github-app|Install GitHub App}}`
   - If no repo linked: guide user with `{{action:link-repository|Link Repository}}`
2. `list_repo_files(recursive: true)` → full project structure
3. Detect from file listing:
   - `dbt_project.yml` location (root or subdirectory → monorepo?)
   - Package manager: `requirements.txt`, `uv.lock`, `pyproject.toml`, `poetry.lock`
   - Python version: `.python-version`, `runtime.txt`, `pyproject.toml`
   - Existing workflows: `.github/workflows/*.yml`
   - `profiles.yml` presence (should NOT be in repo for CI)
4. Read key files to determine:
   - Adapter type (from `dbt_project.yml` or `packages.yml`)
   - Whether Recce is already configured
   - Existing CI configuration to augment vs replace

## Phase 3: Detection Report & Confirmation

Present findings to user in a structured format:

- **Project structure**: root dbt project vs monorepo
- **Detected adapter**: bigquery / snowflake / postgres / redshift / databricks
- **Package manager**: pip + requirements.txt / uv / poetry
- **Python version**: detected or default
- **Existing CI status**: no CI / has CI but no Recce / has Recce (needs update?)
- **Anything undetectable**: ask user explicitly (e.g., adapter credentials approach)

Ask for confirmation: "要幫你設定 Recce CI/CD 嗎？"

## Phase 4: Workflow Generation & PR

1. Based on docs knowledge (Phase 1) + detection results (Phase 2):
   - Generate workflow YAML files (typically 2: CI run + Recce PR review)
   - Adapt templates from docs to match detected project setup
2. Show full preview to user:
   - All workflow files with file paths
   - Explain what each workflow does
   - List required secrets and how to configure them
3. After user approval:
   - `create_cicd_pull_request` with all files in a single PR
   - Report PR URL back to user

## Phase 5: Debug Loop (Future — Placeholder)

If user reports CI failure after setup:

- Read GitHub Actions run results (future: `get_pr_checks` tool)
- Cross-reference error with docs: `search_docs("<error message>")`
- Diagnose based on docs knowledge + error logs
- Suggest fixes or offer to update the PR (future: `update_pr_files` tool)

For now: guide user to check Actions tab and share error logs.

## Anti-Patterns

- **Don't ask about things detectable from repo** (adapter type, package manager, Python version)
- **Don't generate YAML without consulting docs first** — docs are the SSOT for templates
- **Don't create PR without showing preview and getting confirmation**
- **Don't mention unsupported platforms** — check docs for supported adapters first
- **Don't hardcode YAML templates** — always derive from current documentation
- **Don't assume single workflow file** — Recce typically needs both CI and PR review workflows

## Diagnosis Mode

When the trigger is troubleshooting/diagnosis rather than setup:

1. Follow Phase 1 (docs) and Phase 2 (repo exploration) as above
2. In Phase 3, focus on:
   - Comparing existing workflows against docs recommendations
   - Identifying missing secrets, wrong branch references, outdated versions
   - Checking dbt project configuration for common issues
3. Present diagnosis as a checklist of issues found
4. Offer to fix via PR if issues are workflow-related
