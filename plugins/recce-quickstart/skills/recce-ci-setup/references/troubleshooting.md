# CI/CD Troubleshooting

## recce-cloud CLI not found

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

## Network/API errors

If Recce Cloud API calls fail:

```
⚠️ Could not connect to Recce Cloud

Check your network connection and try again.
If the problem persists, check status at:
  https://status.datarecce.io
```

## Issue: "Production baseline not found" in CI

**Symptoms**: CI workflow fails with error about missing production baseline

**Diagnosis**:
1. Check if CD workflow has run successfully
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

## Issue: "Permission denied" or "401 Unauthorized"

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

## Issue: "No artifacts found" or empty upload

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

## Issue: Workflow not triggering on PR

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

## Issue: dbt build fails in CI

**Symptoms**: Workflow fails at dbt build step

This is a dbt configuration issue, not a Recce issue. Common causes:
- Missing warehouse credentials (secrets not configured)
- profiles.yml not set up for CI environment
- Wrong dbt adapter installed

**Recommendation**: Fix dbt CI setup first, then re-run CI setup to add Recce integration.

## Issue: Download fails in CI but upload worked

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
