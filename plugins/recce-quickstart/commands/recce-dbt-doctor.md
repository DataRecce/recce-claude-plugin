---
name: recce-dbt-doctor
description: Configure or troubleshoot Recce Cloud CI/CD integration for dbt projects - set up GitHub Actions workflows or diagnose pipeline issues
args:
  - name: issue
    description: Optional issue description (e.g., "workflow failing", "baseline not found")
    required: false
---

# Recce dbt Doctor - Cloud CI/CD Configuration & Troubleshooting

You are helping the user configure or troubleshoot Recce Cloud CI/CD integration. This command can:
- **Set up new CI/CD** - Add Recce Cloud to GitHub Actions workflows
- **Diagnose issues** - Troubleshoot failing CI/CD pipelines
- **Verify configuration** - Check if existing setup is correct

## Entry Point: Determine User Intent

First, understand what the user needs:

**If user mentions a specific issue** (e.g., "workflow failing", "baseline not found", "permission error"):
→ Jump to **CI/CD Troubleshooting** section, diagnose the specific issue

**If user wants to set up or verify CI/CD**:
→ Follow the **Setup Flow** below

---

## Setup Flow Overview

Run checks in this order:
1. **Environment Detection** - Git repo, dbt project, Python tooling, CI/CD workflows
2. **Gap Analysis** - What's missing for Recce Cloud integration
3. **Setup Assistance** - Help configure CI/CD workflows

---

## Phase 1: Environment Detection

Run all detection checks and store results. Do NOT display output until all checks complete.

### 1.1 Git Repository

```bash
git remote get-url origin 2>/dev/null
```

Store:
- `REPO_REMOTE`: Full URL or `none`
- `REPO_OWNER_NAME`: `owner/repo` format (parsed from URL)

### 1.2 dbt Project

```bash
ls dbt_project.yml 2>/dev/null
```

If exists, read to extract project name.

Store:
- `DBT_PROJECT_NAME`: Project name or `none`

### 1.3 Python Tooling

**Check project files:**
```bash
ls pyproject.toml uv.lock requirements.txt 2>/dev/null
```

- If `uv.lock` exists → `uv`
- If `pyproject.toml` exists (without uv.lock) → likely `uv`
- If only `requirements.txt` exists → `pip`

**Check CI configs for tooling hints:**
```bash
grep -r "astral-sh/setup-uv" <ci_config_files> 2>/dev/null
grep -r "pip install" <ci_config_files> 2>/dev/null
grep -r "python-version" <ci_config_files> 2>/dev/null
```

Store:
- `DETECTED_PKG_MANAGER`: `uv` | `pip` | `unknown`
- `DETECTED_PYTHON_VERSION`: e.g., `3.12` | `unknown`

### 1.4 CI/CD Platform Detection

Check for CI config files in order:

```bash
# Check all common CI platforms
ls .github/workflows/*.yml .github/workflows/*.yaml 2>/dev/null  # GitHub Actions
ls .gitlab-ci.yml 2>/dev/null                                     # GitLab CI
ls .circleci/config.yml 2>/dev/null                               # CircleCI
ls Jenkinsfile 2>/dev/null                                        # Jenkins
ls azure-pipelines.yml 2>/dev/null                                # Azure Pipelines
ls bitbucket-pipelines.yml 2>/dev/null                            # Bitbucket Pipelines
```

Store:
- `CI_PLATFORM`: `github-actions` | `gitlab` | `circleci` | `jenkins` | `azure` | `bitbucket` | `none`
- `CI_CONFIG_FILES`: List of detected config files

### 1.5 dbt Command Analysis

**For each CI config file found, extract dbt commands with context:**

```bash
grep -n -E "dbt (build|run|test|seed|snapshot|deps)" <config_file>
```

**For each dbt command found, extract:**

1. **Line number** - Where the command is
2. **Full command** - e.g., `dbt build --target ci`
3. **Target** - Extract `--target <value>` if present
4. **Job/stage context** - Which job or stage contains this command

**Determine job type (CI vs CD) by looking for triggers:**

- GitHub Actions: Look for `on: pull_request` vs `on: push` in the workflow
- GitLab CI: Look for `rules:` with `merge_request` vs `branches: [main]`
- CircleCI: Look for workflow triggers
- Others: Infer from job names (e.g., "test", "deploy", "prod")

**Check for existing Recce and dbt docs:**

```bash
grep -n "dbt docs generate" <config_file>
grep -n "recce-cloud" <config_file>
```

Store for each dbt command:
```
DBT_COMMANDS:
  - file: <config_file>
    line: <line_number>
    command: <full_command>
    target: <target_value or "default">
    job_name: <job_or_stage_name>
    job_type: "ci" | "cd" | "unknown"

DBT_DOCS_GENERATE_EXISTS: true | false
RECCE_CONFIGURED: true | false
```

### 1.6 Detection Report

After ALL detection completes, display this fixed template:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔍 Environment Detection Report
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Repository
  • Remote: {REPO_OWNER_NAME} | ⚠️ No git remote

dbt Project
  • Name: {DBT_PROJECT_NAME} | ⚠️ No dbt_project.yml

CI/CD Platform
  • Detected: {CI_PLATFORM} | ⚠️ No CI config found
  • Config files: {CI_CONFIG_FILES}

dbt Commands Found:
┌──────────────────────┬──────┬─────────────────────────┬────────┬──────┐
│ File                 │ Line │ Command                 │ Target │ Type │
├──────────────────────┼──────┼─────────────────────────┼────────┼──────┤
│ .github/workflows/ci │ 24   │ dbt build --target ci   │ ci     │ CI   │
│ .github/workflows/cd │ 31   │ dbt build --target prod │ prod   │ CD   │
└──────────────────────┴──────┴─────────────────────────┴────────┴──────┘

dbt docs generate: ✅ Found | ❌ Not found
Recce Cloud: ✅ Configured | ❌ Not configured

Python Tooling
  • Package manager: {DETECTED_PKG_MANAGER}
  • Python version: {DETECTED_PYTHON_VERSION}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## Phase 2: Gap Analysis & Path Selection

Based on detection results, determine which path to follow:

### 2.1 Check if Already Configured

**If `RECCE_CONFIGURED=true`:**
```
✅ Recce Cloud integration detected!

Your CI/CD is already configured with Recce. To verify it's working:
1. Create a PR with a dbt model change
2. Check the PR for Recce Cloud comments

View your project: https://cloud.datarecce.io
```
→ End here (success state)

### 2.2 Determine Path

**Path A: No CI/CD Found** (`CI_PLATFORM=none`)
→ Go to **Phase 3A: Generate New CI/CD**

**Path B: Existing CI/CD Found** (`CI_PLATFORM` is set, `DBT_COMMANDS` list is not empty)
→ Go to **Phase 3B: Augment Existing CI/CD**

**Edge Case: CI exists but no dbt commands found**
→ Show warning, suggest adding dbt to CI first or use Path A to create separate Recce workflows

---

## Phase 3A: Generate New CI/CD (No existing CI)

For users without CI/CD, generate standard GitHub Actions workflows.

### 3A.1 Resolve Unknown Preferences

**Only ask if detection was unclear.** Use AskUserQuestion for unknowns:

**If `DETECTED_PKG_MANAGER` is `unknown`:**
- Options: uv (Recommended), pip

**If `DETECTED_PYTHON_VERSION` is `unknown`:**
- Options: 3.12 (Recommended), 3.11, 3.10

### 3A.2 Generate Workflows

**CI Workflow** (`.github/workflows/recce-ci.yml`):
- Trigger: `pull_request` to main
- Steps: checkout → setup Python → install deps + recce-cloud → dbt build → dbt docs generate → recce-cloud upload
- Uses slim CI with `state:modified+` for efficiency (advanced)

**CD Workflow** (`.github/workflows/recce-prod.yml`):
- Trigger: `push` to main + `workflow_dispatch`
- Steps: checkout → setup Python → install deps + recce-cloud → dbt build → dbt docs generate → recce-cloud upload --type prod

Use the `python-uv-ci`, `python-pip-ci`, and `dbt-ci` skills to generate proper workflow steps.

### 3A.3 Apply Changes

→ Go to **Phase 4: Commit and Push Workflow**

---

## Phase 3B: Augment Existing CI/CD (Has existing CI)

For users with existing CI/CD, identify where to add Recce commands.

### 3B.1 Analyze dbt Commands

From `DBT_COMMANDS` list, identify:
- **CI jobs**: Jobs triggered on PRs/merge requests
- **CD jobs**: Jobs triggered on main branch push

### 3B.2 Determine Required Changes

For each dbt command found:

**Check if `dbt docs generate` exists after it:**
- If NO → Need to add `dbt docs generate --target {same_target}`

**Check if `recce-cloud upload` exists after it:**
- If NO and job_type=CI → Need to add `recce-cloud upload`
- If NO and job_type=CD → Need to add `recce-cloud upload --type prod`

**Check if `recce-cloud` is in dependencies:**
- If NO → Need to add to install step

### 3B.3 Show Proposed Changes

Display changes in diff format:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📝 Proposed Changes
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{CI_CONFIG_FILE}:

  [Install step - add recce-cloud to dependencies]
    pip install dbt-core dbt-snowflake
+   pip install recce-cloud

  [CI job "{job_name}" - after line {line} (dbt build --target {ci_target})]
+   dbt docs generate --target {ci_target}
+   recce-cloud upload
+   env:
+     GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}  # or platform equivalent

  [CD job "{job_name}" - after line {line} (dbt build --target {cd_target})]
+   dbt docs generate --target {cd_target}
+   recce-cloud upload --type prod
+   env:
+     GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}  # or platform equivalent

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**Platform-specific token notes:**
- GitHub Actions: `${{ secrets.GITHUB_TOKEN }}` (auto-provided)
- GitLab CI: `$CI_JOB_TOKEN` or project access token
- CircleCI: `$GITHUB_TOKEN` from context
- Others: User must configure authentication

### 3B.4 Ask User to Confirm

Use AskUserQuestion:
```
Apply these changes?
```
Options:
1. **Yes, apply changes** - I'll modify the files and create a branch
2. **Show me the full files** - Display complete modified files
3. **Skip for now** - Exit without changes

### 3B.5 Apply Changes

If user confirms, edit the CI config files to add the required lines.

→ Go to **Phase 4: Commit and Push Workflow**

---

## Phase 4: Commit and Push Workflow

After making changes (Path A or Path B):

### 4.1 Create Branch

```bash
git checkout -b recce/setup-cloud-integration
git add <modified_files>
```

### 4.2 Ask to Commit

Use AskUserQuestion:
```
Commit these changes?
```
Options:
1. **Yes** - Commit with standard message
2. **Yes, with custom message** - Let me specify the message
3. **No** - Keep changes staged but don't commit

**If yes:**
```bash
git commit -s -m "ci: add Recce Cloud integration

- Add dbt docs generate step
- Add recce-cloud upload for PR artifacts
- Add recce-cloud upload --type prod for production baseline

Generated by /recce-dbt-doctor"
```

### 4.3 Ask to Push

Use AskUserQuestion:
```
Push to remote?
```
Options:
1. **Yes** - Push branch to origin
2. **No** - Keep local only

**If yes:**
```bash
git push -u origin recce/setup-cloud-integration
```

### 4.4 Ask to Create PR/MR

Use AskUserQuestion:
```
Create pull request?
```
Options:
1. **Yes** - Create PR (uses `gh` CLI if available)
2. **No** - Just push the branch

**If yes:**

```bash
# Try gh CLI first (works for GitHub repos)
if gh --version >/dev/null 2>&1; then
  gh pr create --title "Add Recce Cloud CI/CD integration" --body "## Summary
Add Recce Cloud integration to CI/CD workflow.

- Add dbt docs generate step after dbt build
- Add recce-cloud upload for PR artifacts
- Add recce-cloud upload --type prod for production baseline

Generated by /recce-dbt-doctor"
else
  # gh not available - show manual instructions
  echo "Branch pushed: recce/setup-cloud-integration"
  echo "Create a pull request from your repository's web interface."
fi
```

### 4.5 Success Output

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

💡 Advanced: For slim CI (only build changed models), see:
   https://docs.datarecce.io/recce-cloud/slim-ci

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## Error Handling & Troubleshooting

### recce-cloud CLI not found

If `recce-cloud` commands fail with "command not found":

```
❌ recce-cloud CLI not found

Install with pip:
  pip install recce-cloud

Install with uv:
  uv pip install recce-cloud

Or run directly without installing (uv only):
  uvx recce-cloud login
  uvx recce-cloud init
```

### Network/API errors

If Recce Cloud API calls fail:

```
⚠️ Could not connect to Recce Cloud

Check your network connection and try again.
If the problem persists, check status at:
  https://status.datarecce.io
```

---

## CI/CD Troubleshooting

When users report CI/CD issues, diagnose with these checks:

### Issue: "Production baseline not found" in CI

**Symptoms**: CI workflow fails with error about missing production baseline

**Diagnosis**:
1. Check if CD workflow has run successfully: `gh run list --workflow=recce-prod.yml`
2. Check if baseline was uploaded: Look for successful `recce-cloud upload --type prod` in logs

**Solutions**:
```
This error means no production baseline exists yet.

To fix:
1. Go to GitHub Actions → "Recce Production Baseline" workflow
2. Click "Run workflow" → Select main branch → Run
3. Wait for it to complete successfully
4. Re-run your PR workflow

Alternative (local):
  git checkout main
  dbt build && dbt docs generate
  recce-cloud upload --type prod
```

### Issue: "Permission denied" or "401 Unauthorized"

**Symptoms**: `recce-cloud upload` or `download` fails with auth error

**Diagnosis**:
1. Check GITHUB_TOKEN is passed: Look for `env: GITHUB_TOKEN:` in workflow
2. Check repository permissions: Settings → Actions → General → Workflow permissions

**Solutions**:
```
GitHub token authentication issue.

Check your workflow has:
  env:
    GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}

Also verify repository settings:
  Settings → Actions → General → Workflow permissions
  → Select "Read and write permissions"
```

### Issue: "No artifacts found" or empty upload

**Symptoms**: Upload succeeds but no data appears in Recce Cloud

**Diagnosis**:
1. Check `dbt docs generate` ran: Look for manifest.json and catalog.json in target/
2. Check target path: Ensure upload runs from correct directory

**Solutions**:
```
Artifacts not generated or not found.

Ensure your workflow includes:
  - name: Run dbt
    run: |
      dbt deps
      dbt build
      dbt docs generate  # <-- This generates the artifacts

Verify artifacts exist:
  ls -la target/manifest.json target/catalog.json
```

### Issue: Workflow not triggering on PR

**Symptoms**: PR created but Recce CI workflow doesn't run

**Diagnosis**:
1. Check workflow trigger: Should have `on: pull_request: branches: [main]`
2. Check if workflow file is on the PR branch
3. Check Actions tab for any workflow run errors

**Solutions**:
```
Workflow not triggered.

Common causes:
1. Workflow file not on the PR branch - merge main first
2. Wrong trigger configuration - check 'on:' section
3. Actions disabled - Settings → Actions → Enable

Verify trigger:
  on:
    pull_request:
      branches: [main]
```

### Issue: dbt build fails in CI

**Symptoms**: Workflow fails at dbt build step

This is a dbt configuration issue, not a Recce issue. Common causes:
- Missing warehouse credentials (secrets not configured)
- profiles.yml not set up for CI environment
- Wrong dbt adapter installed

**Recommendation**: Fix dbt CI setup first, then re-run `/recce-dbt-doctor` to add Recce integration.

### Issue: Download fails in CI but upload worked

**Symptoms**: `recce-cloud download --prod` fails but production upload succeeded

**Diagnosis**:
1. Check timing: Production upload must complete before PR workflow runs
2. Check project binding: Both workflows must use same Recce Cloud project

**Solutions**:
```
Download failing despite successful upload.

Verify:
1. Production workflow completed BEFORE PR was opened
2. Both workflows are bound to same Recce Cloud project
3. Check with: recce-cloud init --status

If project mismatch, re-run:
  recce-cloud init --org <org> --project <project>
```

---

## Summary Output Format

At the end, always show a summary:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🩺 Recce Doctor Summary
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Prerequisites:
  ✅ Logged in as user@example.com
  ✅ Bound to myorg/myproject

Environment:
  ✅ Git repository: owner/repo (GitHub)
  ✅ dbt project: jaffle_shop
  ✅ CI workflows found: 2

Recce Cloud Integration:
  ✅ PR workflow configured
  ✅ Production baseline workflow configured

Status: Ready! 🎉

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```
