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

**Exit criteria:** You have read at least one CI/CD guide page AND one getting-started page before continuing.

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
   - Adapter type (from `dbt_project.yml` or `packages.yml` or `requirements.txt`)
   - Whether Recce is already configured
   - Existing CI configuration to augment vs replace

**Exit criteria:** You have identified the adapter type, package manager, and existing CI status.

## Phase 3: Detection Report & Confirmation

Present findings using this **exact format**:

```
## Detection Report
| Item | Detected |
|------|----------|
| Repository | {owner/repo} |
| dbt adapter | {from dbt_project.yml/requirements.txt} |
| Package manager | {requirements.txt / uv.lock / pyproject.toml} |
| Python version | {detected or default 3.11} |
| Existing CI | {none / has CI but no Recce / has Recce} |

Based on Recce docs, you need two GitHub Actions workflows:
1. CD (`recce-cd.yml`): updates baseline after merge to main
2. CI (`recce-ci.yml`): validates data changes on PRs

要幫你設定 Recce CI/CD 嗎？
```

**⚠️ STOP HERE and wait for user response.** Do NOT continue to Phase 4 until user confirms.

- If anything was undetectable (e.g., adapter type ambiguous), ask about ONLY that specific item.
- Everything else should be stated as detected facts, not questions.

## Phase 4: Workflow Generation & PR

1. Based on docs knowledge (Phase 1) + detection results (Phase 2):
   - Generate workflow YAML files (typically 2: `recce-ci.yml` + `recce-cd.yml`)
   - Adapt templates from docs to match detected project setup
   - Use the adapter, package manager, and Python version from the Detection Report
2. Show full preview to user:
   - All workflow files with file paths and complete YAML content
   - Explain what each workflow does
   - List required secrets and how to configure them
   - End with: "確認送出 PR 嗎？"

**⚠️ STOP HERE and wait for user response.** Do NOT call `create_cicd_pull_request` until user confirms.

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

### Forbidden Questions (NEVER ask these)
- "Which CI/CD platform do you prefer?" — the user is on GitHub, always use GitHub Actions
- "What adapter are you using?" — detect from `requirements.txt` or `dbt_project.yml`
- "What package manager do you use?" — detect from file listing
- "What Python version?" — detect from `.python-version` or default to 3.11
- "Do you want CI or CD?" — always set up both

### Workflow Rules
- **Don't generate YAML without consulting docs first** — docs are the SSOT for templates
- **Don't create PR without showing preview and getting confirmation**
- **Don't mention unsupported platforms** — check docs for supported adapters first
- **Don't hardcode YAML templates** — always derive from current documentation
- **Don't assume single workflow file** — Recce typically needs both CI and CD workflows
- **Don't skip the Detection Report** — always present structured findings before YAML

## Diagnosis Mode

When the trigger is troubleshooting/diagnosis rather than setup:

1. Follow Phase 1 (docs) and Phase 2 (repo exploration) as above
2. In Phase 3, focus on:
   - Comparing existing workflows against docs recommendations
   - Identifying missing secrets, wrong branch references, outdated versions
   - Checking dbt project configuration for common issues
3. Present diagnosis as a checklist of issues found
4. Offer to fix via PR if issues are workflow-related
