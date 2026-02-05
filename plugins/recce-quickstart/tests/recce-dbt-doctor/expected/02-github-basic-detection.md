# Expected Output: 02-github-basic

## Detection Report

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔍 Environment Detection Report
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Repository
  • Remote: ⚠️ No git remote
  • Platform: unknown

dbt Project
  • Name: jaffle_shop

CI/CD Platform
  • Detected: github-actions
  • Config files: .github/workflows/ci.yml

dbt Commands Found:
┌──────────────────────────┬──────┬─────────────────────────┬────────┬──────┐
│ File                     │ Line │ Command                 │ Target │ Type │
├──────────────────────────┼──────┼─────────────────────────┼────────┼──────┤
│ .github/workflows/ci.yml │ 25   │ dbt build --target ci   │ ci     │ CI   │
│ .github/workflows/ci.yml │ 47   │ dbt build --target prod │ prod   │ CD   │
└──────────────────────────┴──────┴─────────────────────────┴────────┴──────┘

dbt docs generate: ❌ Not found
Recce Cloud: ❌ Not configured

Python Tooling
  • Package manager: pip
  • Python version: 3.12

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

## Expected Path

**Path B: Augment Existing CI/CD**

## Expected Proposed Changes

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📝 Proposed Changes
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

.github/workflows/ci.yml:

  [Install step - add recce-cloud to dependencies]
    pip install dbt-core dbt-snowflake
+   pip install recce-cloud

  [CI job "test" - after line 25 (dbt build --target ci)]
+   dbt docs generate --target ci
+   recce-cloud upload
+   env:
+     GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}

  [CD job "deploy" - after line 47 (dbt build --target prod)]
+   dbt docs generate --target prod
+   recce-cloud upload --type prod
+   env:
+     GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```
