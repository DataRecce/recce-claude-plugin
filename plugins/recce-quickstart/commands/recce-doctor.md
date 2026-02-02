---
name: recce-doctor
description: Configure or troubleshoot Recce Cloud CI/CD integration - set up GitHub Actions workflows or diagnose pipeline issues
args:
  - name: issue
    description: Optional issue description (e.g., "workflow failing", "baseline not found")
    required: false
---

# Recce Doctor - Cloud CI/CD Configuration & Troubleshooting

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
1. **Prerequisites** - Login status, project binding
2. **Environment Detection** - Git repo, dbt project, CI/CD workflows
3. **Gap Analysis** - What's missing for Recce Cloud integration
4. **Setup Assistance** - Help configure CI/CD workflows

---

## Phase 1: Prerequisites Check

### 1.1 Check Recce Cloud Login

Run: `recce-cloud login --status`

**If exit code is 0 (logged in):**
- Parse output for email (e.g., "Logged in as user@example.com")
- Display: `✅ Logged in as user@example.com`
- Continue to next check

**If exit code is non-zero (not logged in):**
- Display:
  ```
  ❌ Not logged in to Recce Cloud

  To authenticate, run:
    recce-cloud login

  This will open a browser for OAuth authentication.
  For headless environments, use:
    recce-cloud login --token <your-api-token>
  ```
- Stop here and wait for user to login

### 1.2 Check Project Binding

Run: `recce-cloud init --status`

**If exit code is 0 (bound):**
- Parse output for org/project info
- Display: `✅ Bound to org/project`
- Continue to next phase

**If exit code is non-zero (not bound):**
- Display:
  ```
  ❌ Project not bound to Recce Cloud

  To bind this project, run:
    recce-cloud init

  This will let you select an organization and project interactively.
  For scripting, use:
    recce-cloud init --org <org-name> --project <project-name>
  ```
- Stop here and wait for user to bind project

---

## Phase 2: Environment Detection

Once prerequisites pass, detect the environment:

### 2.1 Git Repository

Run: `git remote get-url origin 2>/dev/null`

**If succeeds:**
- Parse remote URL to extract:
  - Platform: `github.com` → GitHub, `gitlab.com` → GitLab
  - Repository: `owner/repo` format
- Display: `📦 Repository: owner/repo (GitHub)`

**If fails:**
- Display: `⚠️ No git remote found`
- This is a warning, not a blocker

### 2.2 dbt Project

Check: `ls dbt_project.yml 2>/dev/null`

**If exists:**
- Read `dbt_project.yml` to get project name
- Display: `📊 dbt Project: project_name`

**If not exists:**
- Display: `⚠️ No dbt_project.yml found in current directory`
- This is a warning for CI/CD setup

### 2.3 CI/CD Workflows

Run: `ls .github/workflows/*.yml .github/workflows/*.yaml 2>/dev/null`

**If workflows found:**
- List each workflow file
- For each file, check if it contains:
  - `dbt` commands (dbt build, dbt run, dbt test, dbt docs generate)
  - `recce-cloud` commands (recce-cloud upload, recce-cloud download)
  - `DataRecce/recce-cloud-cicd-action` (GitHub Action)

Display summary:
```
📋 CI/CD Workflows Detected:

.github/workflows/ci.yml
  • dbt commands: ✅ (dbt deps, dbt build, dbt test)
  • dbt docs generate: ❌
  • Recce integration: ❌

.github/workflows/deploy.yml
  • dbt commands: ❌
  • Recce integration: ❌
```

**If no workflows found:**
- Display: `📋 No GitHub Actions workflows found`

---

## Phase 3: Gap Analysis

Based on detection results, identify what's needed:

### 3.1 Determine Recce Integration Status

**Already configured if ANY of:**
- Workflow contains `recce-cloud upload`
- Workflow contains `recce-cloud download`
- Workflow contains `DataRecce/recce-cloud-cicd-action`

**If already configured:**
```
✅ Recce Cloud integration detected!

Your CI/CD is already configured with Recce. To verify it's working:
1. Create a PR with a dbt model change
2. Check the PR for Recce Cloud comments
3. Run `recce-cloud doctor` (CLI) for detailed diagnostics

View your project: https://cloud.datarecce.io
```
- End here (success state)

### 3.2 Identify Gaps

**If NOT configured, show gaps:**

```
🔍 Gap Analysis

To enable Recce Cloud on PRs, you need:

[CI - Pull Request Workflow]
  1. ❌ Add `dbt docs generate` step (required for artifacts)
  2. ❌ Add `recce-cloud upload` step (uploads to Cloud)
  3. ✅ GITHUB_TOKEN available (auto-provided by GitHub)

[CD - Production Baseline Workflow]
  4. ❌ Add workflow to upload prod artifacts on main branch
     OR add conditional step to existing workflow
```

---

## Phase 4: Setup Assistance

If gaps exist, offer to help:

### 4.1 Ask User How to Proceed

Use AskUserQuestion:

```
How would you like to set up Recce Cloud CI/CD?
```

Options:
1. **Create PR with changes (Recommended)** - I'll create a branch, add Recce to your workflows, and open a PR
2. **Show me the changes** - I'll show the exact changes needed, you apply manually
3. **Skip for now** - Exit without making changes

### 4.2 Option 1: Create PR with Changes

#### Determine which workflow to modify

**If exactly one workflow has dbt commands:**
- Use that workflow (no need to ask)

**If multiple workflows have dbt commands:**
- Ask user which one to modify

**If no workflows have dbt commands:**
- Create new standalone workflows

#### Generate CI changes

**For CI workflow (create new file `.github/workflows/recce-ci.yml`):**

This workflow runs on PRs: downloads production baseline, runs dbt, uploads PR artifacts.

```yaml
name: Recce CI

on:
  pull_request:
    branches: [main]

env:
  # Warehouse credentials - user must configure these secrets
  # For Snowflake:
  SNOWFLAKE_ACCOUNT: ${{ secrets.SNOWFLAKE_ACCOUNT }}
  SNOWFLAKE_USER: ${{ secrets.SNOWFLAKE_USER }}
  SNOWFLAKE_PASSWORD: ${{ secrets.SNOWFLAKE_PASSWORD }}

jobs:
  recce-ci:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install uv
        uses: astral-sh/setup-uv@v4

      - name: Install dbt
        run: uv pip install dbt-core dbt-<ADAPTER> --system

      - name: Install recce-cloud
        run: uv pip install recce-cloud --system

      - name: Download production artifacts from Recce Cloud
        run: recce-cloud download --prod --target-path target-base
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}

      - name: Run dbt
        run: |
          dbt deps
          dbt build
          dbt docs generate

      - name: Upload to Recce Cloud
        run: recce-cloud upload
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

**For CD workflow (create new file `.github/workflows/recce-prod.yml`):**

This workflow runs on push to main: runs dbt, uploads as production baseline.

```yaml
name: Recce Production Baseline

on:
  push:
    branches: [main]
  workflow_dispatch:

env:
  # Warehouse credentials - user must configure these secrets
  # For Snowflake:
  SNOWFLAKE_ACCOUNT: ${{ secrets.SNOWFLAKE_ACCOUNT }}
  SNOWFLAKE_USER: ${{ secrets.SNOWFLAKE_USER }}
  SNOWFLAKE_PASSWORD: ${{ secrets.SNOWFLAKE_PASSWORD }}

jobs:
  recce-prod:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install uv
        uses: astral-sh/setup-uv@v4

      - name: Install dbt
        run: uv pip install dbt-core dbt-<ADAPTER> --system

      - name: Run dbt
        run: |
          dbt deps
          dbt build
          dbt docs generate

      - name: Upload to Recce Cloud
        run: uvx recce-cloud upload --type prod
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

**Note:** Replace `<ADAPTER>` with detected adapter from profiles.yml (snowflake, bigquery, postgres, etc.)

**Adapter-specific env vars:**
- **Snowflake**: `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`, `SNOWFLAKE_PASSWORD`
- **BigQuery**: `GOOGLE_APPLICATION_CREDENTIALS_JSON` (service account JSON)
- **PostgreSQL**: `POSTGRES_HOST`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DATABASE`
- **Databricks**: `DATABRICKS_HOST`, `DATABRICKS_TOKEN`, `DATABRICKS_HTTP_PATH`

#### Create branch and PR

```bash
# Create branch
git checkout -b recce/setup-cloud-integration

# Stage changes
git add .github/workflows/

# Commit
git commit -m "ci: add Recce Cloud integration

- Add dbt docs generate step for artifact generation
- Add recce-cloud upload for PR review
- Add production baseline workflow

Generated by /recce-doctor"

# Push
git push -u origin recce/setup-cloud-integration

# Create PR
gh pr create \
  --title "Add Recce Cloud CI/CD integration" \
  --body "## Summary
This PR adds Recce Cloud integration to the CI/CD pipeline.

### Changes
- Added \`dbt docs generate\` step to generate artifacts
- Added \`recce-cloud upload\` step to upload PR artifacts
- Created \`recce-prod.yml\` workflow for production baseline updates

### Next Steps
1. Merge this PR
2. Trigger the production workflow manually to create baseline:
   - Go to Actions → 'Update Recce Production Baseline' → Run workflow
3. Create a test PR with a dbt change to verify integration

### Documentation
- [Recce Cloud CI/CD Guide](https://datarecce.io/docs/recce-cloud/ci-integration)

---
Generated by \`/recce-doctor\`"
```

Display:
```
✅ PR created!

PR URL: https://github.com/owner/repo/pull/123

Next steps:
1. Review and merge the PR
2. Trigger production workflow manually to create baseline
3. Create a test PR with a dbt change to see Recce in action

View your project: https://cloud.datarecce.io
```

### 4.3 Option 2: Show Changes

Display the exact changes needed:

```
📝 Changes needed for Recce Cloud integration:

──────────────────────────────────────────────
File: .github/workflows/recce-ci.yml (CREATE)
──────────────────────────────────────────────

[Show full CI workflow content from template above]

Key steps:
1. Download production baseline: recce-cloud download --prod --target-path target-base
2. Run dbt: dbt deps && dbt build && dbt docs generate
3. Upload PR artifacts: recce-cloud upload

──────────────────────────────────────────────
File: .github/workflows/recce-prod.yml (CREATE)
──────────────────────────────────────────────

[Show full CD workflow content from template above]

Key steps:
1. Run dbt: dbt deps && dbt build && dbt docs generate
2. Upload as production: recce-cloud upload --type prod

──────────────────────────────────────────────
GitHub Secrets Required:
──────────────────────────────────────────────

Configure at: https://github.com/<owner>/<repo>/settings/secrets/actions

For <ADAPTER>:
  • SECRET_NAME_1
  • SECRET_NAME_2
  • ...

──────────────────────────────────────────────

After adding these files:
1. Commit and push to main
2. Trigger production workflow manually to create baseline
3. Create a test PR to verify CI workflow
```

### 4.4 Option 3: Skip

```
Okay, no changes made.

When you're ready to set up Recce Cloud CI/CD, run:
  /recce-doctor

Key commands for manual setup:

  # In CI (PR workflow):
  recce-cloud download --prod --target-path target-base  # Get production baseline
  dbt build && dbt docs generate                          # Run dbt
  recce-cloud upload                                      # Upload PR artifacts

  # In CD (main branch workflow):
  dbt build && dbt docs generate                          # Run dbt
  recce-cloud upload --type prod                          # Upload as production baseline
```

---

## Error Handling & Troubleshooting

### recce-cloud CLI not found

If `recce-cloud` commands fail with "command not found":

```
❌ recce-cloud CLI not found

Install it with:
  pip install recce-cloud

Or run directly with uvx (no install needed):
  uvx recce-cloud login
  uvx recce-cloud init
```

### gh CLI not found (for PR creation)

If `gh pr create` fails:

```
⚠️ GitHub CLI (gh) not found

To create the PR automatically, install gh:
  https://cli.github.com/

Or I can show you the changes to apply manually.
```

Then fall back to Option 2 (show changes).

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

**Diagnosis**:
1. Check warehouse credentials: Are secrets configured?
2. Check profiles.yml: Is it committed or generated in CI?
3. Check dbt adapter: Is correct adapter installed?

**Solutions**:
```
dbt build failing in CI.

Check these GitHub Secrets are configured:
  Settings → Secrets and variables → Actions

For Snowflake:
  SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, SNOWFLAKE_PASSWORD

For BigQuery:
  GOOGLE_APPLICATION_CREDENTIALS_JSON

Ensure profiles.yml uses environment variables:
  snowflake:
    target: ci
    outputs:
      ci:
        account: "{{ env_var('SNOWFLAKE_ACCOUNT') }}"
        user: "{{ env_var('SNOWFLAKE_USER') }}"
        password: "{{ env_var('SNOWFLAKE_PASSWORD') }}"
```

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
