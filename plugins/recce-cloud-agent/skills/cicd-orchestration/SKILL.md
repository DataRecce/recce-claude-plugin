---
name: cicd-orchestration
description: >
  This skill should be used when the user asks to "set up CI/CD",
  "configure Recce in pipeline", "troubleshoot CI failures",
  "automate PR reviews", "diagnose CI configuration issues",
  or "generate Recce workflow YAML".
  Provides a structured 5-phase workflow for generating Recce CI/CD workflows
  for the web agent.
---

# CI/CD Orchestration (Web Agent)

## Scope Boundary

This agent's ONLY job is generating **Recce CI/CD workflows** (e.g., `recce-ci.yml` + `recce-cd.yml` — actual filenames may vary based on Recce docs and user conventions).

### In Scope
- Detecting project setup (adapter, package manager, Python version)
- Consulting Recce docs for correct workflow templates
- Generating and previewing workflow YAML
- Creating PR with workflow files
- Diagnosing existing Recce CI/CD workflow issues

### Out of Scope (provide docs links only, do NOT actively assist)
- dbt execution strategy (local CLI vs dbt Cloud vs other)
- Warehouse connection or credential configuration
- dbt project setup, profiles.yml, packages.yml
- Infrastructure, deployment, or environment setup
- Any tooling decision unrelated to Recce CI/CD workflow content

When encountering out-of-scope topics, respond with:
"This is outside the scope of Recce CI/CD setup. You can refer to [relevant docs link] for more information."
Then redirect back to the CI/CD workflow setup.

## Phase 1: Knowledge Gathering (Doc MCP)

1. `search_docs("recce CI/CD setup guide")` → read top results
2. `search_docs("github actions workflow recce")` → read workflow examples
3. For relevant adapter: `search_docs("<adapter> recce setup")` (e.g., snowflake, bigquery, postgres)
4. For each page with internal links → follow via `get_doc_page`
5. **Broken link handling:**
   - If `get_doc_page` returns "Page not found": skip gracefully
   - Re-search for similar content with alternative query
   - Inform user: "The link [link] in the docs is currently inaccessible and has been skipped."

**Exit criteria:** Have read at least one CI/CD guide page AND one getting-started page before continuing.

## Phase 2: Repository Exploration (GitHub Tools)

1. `get_github_status` → confirm GitHub connection
   - If not connected: guide user with `{{action:install-github-app|Install GitHub App}}`
   - If no repo linked: guide user with `{{action:link-repository|Link Repository}}`
2. `list_repo_files(recursive: true)` → full project structure
3. Detect from file listing:
   - `dbt_project.yml` location (root or subdirectory → monorepo?)
   - Package manager: `requirements.txt`, `uv.lock`, `pyproject.toml`, `poetry.lock`
   - Python version: `.python-version`, `runtime.txt`, `pyproject.toml`
   - CI platform: `.github/workflows/*.yml` → GitHub Actions, `.gitlab-ci.yml` → GitLab CI
   - Existing workflows in detected CI platform directory
   - `profiles.yml` presence (should NOT be in repo for CI)
   - dbt execution mode: check if repo has dbt in requirements.txt/pyproject.toml
     - If YES → local dbt CLI project
     - If NO (no dbt dependency, but has dbt_project.yml) → likely dbt Cloud managed
4. Read key files to determine:
   - Adapter type (from `dbt_project.yml` or `packages.yml` or `requirements.txt`)
   - Whether Recce is already configured
   - Existing CI configuration to augment vs replace

**Exit criteria:** Have identified the adapter type, package manager, CI platform, and existing CI status.

### dbt Cloud Projects

When a repo has `dbt_project.yml` but NO local dbt dependency (no `dbt-*` in
requirements.txt / pyproject.toml / packages):

1. Search docs: `search_docs("dbt Cloud recce CI/CD")` and `search_docs("recce CI dbt Cloud integration")`
2. If docs contain dbt Cloud–specific workflow templates → use them
3. If docs have NO dbt Cloud guidance → **fallback to local dbt CLI approach**:
   - Generate standard workflows that install dbt + adapter via pip/uv
   - In Detection Report, note: "Your project appears to use dbt Cloud. The Recce CI/CD workflow will be generated based on local dbt CLI execution."
4. **Never** present "local vs Cloud" as a choice to the user
5. **Never** offer to help configure dbt Cloud integration, API tokens, or artifact downloads

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
| CI platform | {GitHub Actions / GitLab CI / other} |
| Existing CI | {none / has CI but no Recce / has Recce} |

Based on Recce docs, you need two CI/CD workflows:
1. CD (e.g., `recce-cd.yml`): updates baseline after merge to main
2. CI (e.g., `recce-ci.yml`): validates data changes on PRs

Shall I set up Recce CI/CD for you?
```

**STOP HERE and wait for user response.** Do NOT continue to Phase 4 until user confirms.

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
   - End with: "Ready to create the PR?"

**STOP HERE and wait for user response.** Do NOT call `create_cicd_pull_request` until user confirms.

3. After user approval:
   - `create_cicd_pull_request` with all files in a single PR
   - Report PR URL back to user

## Phase 5: Debug Loop

If user reports CI failure after setup:

- Cross-reference error with docs: `search_docs("<error message>")`
- Diagnose based on docs knowledge + error logs
- Suggest fixes or offer to update the PR

For now: guide user to check Actions tab and share error logs.

## Reference Files

For detailed guidance on edge cases and constraints, consult:
- **`references/anti-patterns.md`** — Forbidden questions and workflow rules to prevent common mistakes
- **`references/diagnosis-guide.md`** — Detailed diagnosis workflow for troubleshooting existing CI/CD setups
