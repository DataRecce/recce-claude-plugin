---
name: Recce CI/CD Setup
description: >
  This skill should be used when the user asks to "set up CI/CD",
  "configure GitHub Actions for Recce", "add Recce Cloud to CI pipeline",
  "automate PR review", "create CI workflow", or needs to create or augment
  CI/CD workflows for Recce Cloud integration.
version: 0.1.0
---

# Recce Cloud CI/CD Setup

Guide the user through setting up Recce Cloud CI/CD integration. This workflow
detects the existing environment, identifies gaps, and either generates new
workflows or augments existing ones.

## Prerequisite: Run Detection

Before starting, execute the **dbt Project Detection** skill to collect:
- REPO_REMOTE, REPO_OWNER_NAME
- DBT_PROJECT_NAME, PROJECT_DIR, IS_MONOREPO
- ADAPTER_TYPE, ADAPTER_PACKAGE
- DETECTED_PKG_MANAGER, DETECTED_PYTHON_VERSION
- CI_PLATFORM, CI_CONFIG_FILES
- DBT_COMMANDS[], DBT_DOCS_GENERATE_EXISTS, RECCE_CONFIGURED

Display the Detection Report before proceeding.

## Step 1: Gap Analysis & Path Selection

### 1.1 Already Configured

**If `RECCE_CONFIGURED=true`:**

Display:
```
✅ Recce Cloud integration already detected!
Your CI/CD is configured with Recce. To verify:
1. Create a PR with a dbt model change
2. Check the PR for Recce Cloud comments
View your project: https://cloud.datarecce.io
```

→ End (success state)

### 1.2 Determine Path

- **Path A** (`CI_PLATFORM=none`): No CI exists → Generate New CI/CD (Step 2)
- **Path B** (`CI_PLATFORM` set, `DBT_COMMANDS` not empty): Existing CI → Augment (Step 3)
- **Edge case** (CI exists but no dbt commands): Warn, suggest adding dbt first or use Path A

## Step 2: Path A — Generate New CI/CD

For users without CI/CD. Generate standard workflows.

### 2.1 Resolve Unknown Preferences

Only ask if detection returned "unknown":
- **Package manager**: If `DETECTED_PKG_MANAGER` is "unknown", ask: uv (Recommended) or pip
- **Python version**: If `DETECTED_PYTHON_VERSION` is "unknown", ask: 3.12 (Recommended), 3.11, 3.10

### 2.2 Generate Workflows

Create two workflow files using templates from the **workflow-templates** reference:

1. **CI Workflow** (PR trigger):
   - File: `.github/workflows/recce-ci.yml` (or `recce-ci-pr.yml`)
   - Trigger: `pull_request` to main
   - Steps: checkout → setup Python → install deps + recce-cloud → dbt build → dbt docs generate → Recce Cloud upload

2. **CD Workflow** (Main branch trigger):
   - File: `.github/workflows/recce-prod.yml` (or `recce-ci-main.yml`)
   - Trigger: `push` to main + `workflow_dispatch`
   - Steps: checkout → setup Python → install deps + recce-cloud → dbt build → dbt docs generate → Recce Cloud upload --type prod

Apply template substitution rules from the workflow-templates reference:
- Substitute `ADAPTER_PACKAGE`, `DETECTED_PKG_MANAGER`, `DETECTED_PYTHON_VERSION`, `PROJECT_DIR`
- If `IS_MONOREPO=true`: add `paths:` filter and `working-directory:` defaults

### 2.3 Apply Changes

Write the generated workflow files, then proceed to Step 5 (Commit & Push).

## Step 3: Path B — Augment Existing CI/CD

For users with existing CI/CD that lacks Recce Cloud integration.

### 3.1 Analyze Existing dbt Commands

From `DBT_COMMANDS[]`, identify:
- **CI jobs**: Commands in jobs triggered on PRs/merge requests
- **CD jobs**: Commands in jobs triggered on main branch push

### 3.2 Determine Required Changes

For each dbt command found:

1. **Check `dbt docs generate`**: If NOT present after this command → add `dbt docs generate --target {same_target}`
2. **Check `recce-cloud upload`**: If NOT present:
   - CI job → add `recce-cloud upload`
   - CD job → add `recce-cloud upload --type prod`
3. **Check `recce-cloud` in dependencies**: If NOT in install step → add to install

### 3.3 Show Proposed Changes

Display in diff format:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📝 Proposed Changes
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{CI_CONFIG_FILE}:

  [Install step - add recce-cloud to dependencies]
    {existing_install_command}
+   {pkg_manager} install recce-cloud

  [{job_type} job "{job_name}" - after line {line} ({command})]
+   dbt docs generate --target {target}    ← only if not already present
+   recce-cloud upload [--type prod]       ← --type prod for CD jobs only
+   env:
+     GITHUB_TOKEN: {platform_token}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**Platform-specific tokens:**
- GitHub Actions: `${{ secrets.GITHUB_TOKEN }}` (auto-provided)
- GitLab CI: `$CI_JOB_TOKEN` or project access token
- CircleCI: `$GITHUB_TOKEN` from context

### 3.4 Confirm & Apply

Ask user to confirm. Options:
1. Yes, apply changes
2. Show full modified files first
3. Skip for now

If confirmed, edit the CI config files to add the required lines.

## Step 4: Recce Cloud Project Prerequisite

Display this reminder (regardless of Path A or B):

```
⚠️ Important: Create Recce Cloud Project First

CI/CD upload requires a corresponding Recce Cloud Project.
Projects are identified by Repository URL + Project Directory.

Your settings:
• Repository: {REPO_OWNER_NAME}
• Project Directory: {PROJECT_DIR or "(repo root)"}

Create project at: https://cloud.datarecce.io/projects/new
```

## Step 5: Secrets Configuration

Load the **warehouse-secrets** reference file matching `ADAPTER_TYPE`.
Display the appropriate secrets table and setup link:

```
📝 Configure secrets at:
👉 https://github.com/{REPO_OWNER}/{REPO_NAME}/settings/secrets/actions
```

## Step 6: Commit & Push Workflow

### 6.1 Create Branch

- **Action**: Create a new branch for the changes
- **Branch name**: `recce/setup-cloud-integration`

### 6.2 Commit Changes

- **Action**: Stage and commit modified/created files
- **Message template**:
  ```
  ci: add Recce Cloud CI/CD integration

  - Add dbt docs generate step
  - Add recce-cloud upload for PR artifacts
  - Add recce-cloud upload --type prod for production baseline

  Generated by Recce CI Setup
  ```

### 6.3 Push & Create PR

- **Action**: Push branch to remote, optionally create PR/MR
- **PR title**: "Add Recce Cloud CI/CD integration"
- **PR body**: Summary of changes made

## Step 7: Summary Output

Display final summary:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ Recce Cloud Integration Setup Complete
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Branch: recce/setup-cloud-integration
Status: {committed/pushed/PR created}

Next steps:
1. Review and merge the changes
2. Run CD workflow to create initial production baseline
3. Create a test PR with a dbt change to verify

View your project: https://cloud.datarecce.io
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

## Additional Resources

### Reference Files
- **`references/workflow-templates.md`** -- Full YAML workflow templates with substitution rules
- **`references/warehouse-secrets.md`** -- Per-adapter GitHub Secrets configuration tables
- **`references/troubleshooting.md`** -- 8 diagnostic procedures for common CI/CD issues
- **`references/monorepo-guide.md`** -- Monorepo detection, path filtering, working directory config
