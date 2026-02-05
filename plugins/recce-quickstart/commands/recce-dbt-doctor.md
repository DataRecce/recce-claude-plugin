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

**Check workflows first:**
```bash
grep -r "astral-sh/setup-uv" .github/workflows/ 2>/dev/null
grep -r "pip install" .github/workflows/ 2>/dev/null
grep -r "python-version" .github/workflows/ 2>/dev/null
```

**Check project files:**
```bash
ls pyproject.toml uv.lock requirements.txt 2>/dev/null
```

Store:
- `DETECTED_PKG_MANAGER`: `uv` | `pip` | `unknown`
- `DETECTED_PYTHON_VERSION`: e.g., `3.12` | `unknown`

### 1.4 CI/CD Workflows & Patterns

```bash
ls .github/workflows/*.yml .github/workflows/*.yaml 2>/dev/null
```

**If no workflows found:**
Store `WORKFLOWS_FOUND=false` and skip to Detection Report.

**If workflows found, for each workflow file extract:**

**Triggers:**
```bash
grep -A5 "^on:" <workflow_file>
```
Look for:
- `pull_request:` → CI trigger
- `push:` with `branches: [main]` → CD trigger
- `workflow_dispatch:` → Manual trigger

**Build strategy:**
```bash
grep -E "state:modified|--state" <workflow_file>
```
- If found → Slim CI (incremental)
- If not found but has `dbt build` → Full build

**State source:**
```bash
grep -E "recce-cloud download|target-base|--state" <workflow_file>
```
- If `recce-cloud download` → Recce Cloud baseline
- If `--state` with local path → Local baseline
- If neither → No state management

**Recce integration:**
```bash
grep -E "recce-cloud|DataRecce/recce-cloud" <workflow_file>
```

Store:
- `WORKFLOWS_FOUND`: `true` | `false`
- `CI_TRIGGER`: `pull_request` | `none`
- `CD_TRIGGER`: `push to main` | `none`
- `BUILD_STRATEGY`: `slim` | `full` | `unknown`
- `STATE_SOURCE`: `recce-cloud` | `local` | `none`
- `RECCE_CONFIGURED`: `true` | `false`
- `DBT_DOCS_GENERATE`: `true` | `false`

### 1.5 Detection Report

After ALL detection completes, display this fixed template:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔍 Environment Detection Report
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Repository
  • Remote: {REPO_OWNER_NAME} | ⚠️ No git remote

dbt Project
  • Name: {DBT_PROJECT_NAME} | ⚠️ No dbt_project.yml

GitHub Actions Workflows
  • Found: {count} workflow(s) | ⚠️ None found
  • CI trigger: {CI_TRIGGER} | ⚠️ None
  • CD trigger: {CD_TRIGGER} | ⚠️ None

Current CI Pattern
  • Build strategy: {BUILD_STRATEGY}
    - slim = uses state:modified+ (efficient)
    - full = rebuilds everything
  • State source: {STATE_SOURCE}
    - recce-cloud = downloads prod baseline
    - local = uses local state path
    - none = no state comparison
  • dbt docs generate: ✅ | ❌

Python Tooling
  • Package manager: {DETECTED_PKG_MANAGER}
  • Python version: {DETECTED_PYTHON_VERSION}

Recce Cloud Integration
  • Status: ✅ Configured | ❌ Not configured

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**If `WORKFLOWS_FOUND=false`:**

Add after the report:
```
⚠️ No GitHub Actions workflows detected.

This command currently supports GitHub Actions.
For dbt Cloud or other orchestration, see:
  https://docs.datarecce.io/recce-cloud/ci-integration
```

---

## Phase 2: Gap Analysis

Based on detection results, identify what's needed:

### 2.1 Determine Recce Integration Status

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

### 2.2 Identify Gaps

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

## Phase 3: Setup Assistance

If gaps exist, offer to help:

### 3.1 Resolve Unknown Preferences

**Only ask if detection was unclear.** Use AskUserQuestion for unknowns:

**If `DETECTED_PKG_MANAGER` is `unknown`:**
```
Which package manager do you use for Python dependencies?
```
Options:
1. **uv (Recommended)** - Fast, modern Python package manager
2. **pip** - Traditional Python package manager

**If `DETECTED_PYTHON_VERSION` is `unknown`:**
```
Which Python version should the CI use?
```
Options:
1. **3.12 (Recommended)** - Latest stable
2. **3.11** - Previous stable
3. **3.10** - Older stable

### 3.2 Ask User How to Proceed

Use AskUserQuestion:

```
How would you like to set up Recce Cloud CI/CD?
```

Options:
1. **Create PR with changes (Recommended)** - I'll create a branch, add Recce to your workflows, and open a PR
2. **Show me the changes** - I'll show the exact changes needed, you apply manually
3. **Skip for now** - Exit without making changes

### 3.3 Option 1: Create PR with Changes

#### Determine which workflow to modify

**If exactly one workflow has dbt commands:**
- Use that workflow (no need to ask)

**If multiple workflows have dbt commands:**
- Ask user which one to modify

**If no workflows have dbt commands:**
- Create new standalone workflows

#### Generate CI Workflow

Create `.github/workflows/recce-ci.yml` with these components:

**Workflow header:**
```yaml
name: Recce CI

on:
  pull_request:
    branches: [main]
```

**Job steps - Python/Package Setup:**

Generate based on `DETECTED_PKG_MANAGER` and `DETECTED_PYTHON_VERSION`:

**If uv:** Use the `python-uv-ci` skill to generate the setup steps with:
- `{PYTHON_VERSION}` = `DETECTED_PYTHON_VERSION`
- `{DEPENDENCIES}` = user's existing dbt packages + `recce-cloud`
- `{COMMAND}` = dbt and recce-cloud commands

**If pip:** Use the `python-pip-ci` skill to generate the setup steps with:
- `{PYTHON_VERSION}` = `DETECTED_PYTHON_VERSION`
- `{DEPENDENCIES}` = user's existing dbt packages + `recce-cloud`
- `{COMMAND}` = dbt and recce-cloud commands

**Note:** If the user already has dbt installation steps in their workflows, just add `recce-cloud` to their existing install command.

**Job steps - CI workflow order:**

1. **Download baseline** (before dbt):
   ```yaml
   - name: Download production baseline from Recce Cloud
     run: uv run recce-cloud download --prod --target-path target-base  # pip: source .venv/bin/activate && recce-cloud ...
     env:
       GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
   ```

2. **Run dbt** - Use the `dbt-ci` skill (Incremental Build) with:
   - `{TARGET}` = user's CI target (e.g., `ci`, `dev`)
   - `{STATE_PATH}` = `target-base`

   This runs `dbt build --select state:modified+ --state target-base` to only rebuild changed models.

3. **Upload artifacts** (after dbt):
   ```yaml
   - name: Upload PR artifacts to Recce Cloud
     run: uv run recce-cloud upload  # pip: source .venv/bin/activate && recce-cloud ...
     env:
       GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
   ```

#### Generate CD Workflow

Create `.github/workflows/recce-prod.yml` (or add to existing main branch workflow):

**Workflow header:**
```yaml
name: Recce Production Baseline

on:
  push:
    branches: [main]
  workflow_dispatch:
```

**Job steps - CD workflow order:**

1. Python/package setup - Use `python-uv-ci` or `python-pip-ci` skill (same as CI)

2. Run dbt - Use the `dbt-ci` skill (Full Build) with:
   - `{TARGET}` = user's production target (e.g., `prod`)

   This runs a full `dbt build` without `--state` flag.

3. **Upload as production baseline**:
   ```yaml
   - name: Upload production baseline to Recce Cloud
     run: uv run recce-cloud upload --type prod  # pip: source .venv/bin/activate && recce-cloud ...
     env:
       GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
   ```

#### Key Integration Points

The only additions needed for Recce Cloud are:

1. **Install recce-cloud** - Add to existing pip/uv install step
2. **`dbt docs generate`** - Ensure this runs (generates required artifacts)
3. **CI workflow**: Add `recce-cloud download` (before dbt) and `recce-cloud upload` (after dbt)
4. **CD workflow**: Add `recce-cloud upload --type prod` (after dbt on main branch)

`GITHUB_TOKEN` is automatically provided by GitHub Actions - no additional secrets needed for Recce Cloud.

#### Create branch, push, and PR

After generating the workflow files:

```bash
# Create branch
git checkout -b recce/setup-cloud-integration

# Stage changes
git add .github/workflows/

# Commit
git commit -s -m "ci: add Recce Cloud integration

- Add recce-ci.yml for PR artifact uploads
- Add recce-prod.yml for production baseline

Generated by /recce-dbt-doctor"

# Always push first (don't block on gh availability)
git push -u origin recce/setup-cloud-integration
```

**After push succeeds, check for gh CLI and create PR:**

```bash
# Check if gh is available
if gh --version >/dev/null 2>&1; then
  # gh available - create PR automatically
  gh pr create \
    --title "Add Recce Cloud CI/CD integration" \
    --body "## Summary
  This PR adds Recce Cloud integration to the CI/CD pipeline.

  ### Changes
  - Added \`recce-ci.yml\` - Downloads prod baseline, runs dbt, uploads PR artifacts
  - Added \`recce-prod.yml\` - Uploads production baseline on merge to main

  ### How it works
  - **On PRs**: Downloads production baseline → runs dbt → uploads PR artifacts to Recce Cloud
  - **On merge to main**: Runs dbt → uploads new production baseline

  No additional secrets required - uses the built-in \`GITHUB_TOKEN\`.

  ### Next Steps
  1. Merge this PR
  2. Trigger the production workflow manually to create initial baseline:
     - Go to Actions → 'Recce Production Baseline' → Run workflow
  3. Create a test PR with a dbt change to verify integration

  ### Documentation
  - [Recce Cloud CI/CD Guide](https://datarecce.io/docs/recce-cloud/ci-integration)

  ---
  Generated by \`/recce-dbt-doctor\`"
fi
```

**Display based on result:**

**If gh available and PR created:**
```
✅ Branch pushed and PR created!

PR URL: https://github.com/{owner}/{repo}/pull/123

Next steps:
1. Review and merge the PR
2. Trigger production workflow manually to create initial baseline
3. Create a test PR with a dbt change to see Recce in action

View your project: https://cloud.datarecce.io
```

**If gh NOT available:**
```
✅ Branch pushed: recce/setup-cloud-integration

⚠️ gh CLI not found — create PR manually:
   https://github.com/{owner}/{repo}/compare/recce/setup-cloud-integration

To install gh CLI for automatic PR creation:
   https://cli.github.com/

Next steps after creating PR:
1. Review and merge the PR
2. Trigger production workflow manually to create initial baseline
3. Create a test PR with a dbt change to see Recce in action

View your project: https://cloud.datarecce.io
```

### 3.4 Option 2: Show Changes

Generate and display the exact workflow files (using the dynamic generation rules above):

```
📝 Changes needed for Recce Cloud integration:

Configuration detected:
  • Package manager: {DETECTED_PKG_MANAGER}
  • Python version: {DETECTED_PYTHON_VERSION}

──────────────────────────────────────────────
File: .github/workflows/recce-ci.yml (CREATE)
──────────────────────────────────────────────

{GENERATE_FULL_CI_WORKFLOW_YAML}

──────────────────────────────────────────────
File: .github/workflows/recce-prod.yml (CREATE)
──────────────────────────────────────────────

{GENERATE_FULL_PROD_WORKFLOW_YAML}

──────────────────────────────────────────────

No additional GitHub Secrets required - Recce Cloud uses the
built-in GITHUB_TOKEN which is automatically available.

After adding these files:
1. Commit and push to main
2. Trigger production workflow manually to create baseline
3. Create a test PR to verify CI workflow
```

### 3.5 Option 3: Skip

```
Okay, no changes made.

When you're ready to set up Recce Cloud CI/CD, run:
  /recce-dbt-doctor

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
