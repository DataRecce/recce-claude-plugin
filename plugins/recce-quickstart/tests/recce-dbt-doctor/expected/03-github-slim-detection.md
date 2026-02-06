# Expected Output: 03-github-slim

## Detection Report

```
🔍 **Environment Detection Report**

**Repository**
- Remote: ⚠️ No git remote

**dbt Project**
- Name: jaffle_shop

**CI/CD Platform**
- Detected: github-actions
- Config files: .github/workflows/ci.yml

**dbt Commands Found:**

| File | Line | Command | Target | Type |
|------|------|---------|--------|------|
| .github/workflows/ci.yml | 30 | `dbt build --target ci --select state:modified+` | ci | CI |
| .github/workflows/ci.yml | 51 | `dbt build --target prod` | prod | CD |
| .github/workflows/ci.yml | 52 | `dbt docs generate --target prod` | prod | CD |

**dbt docs generate:** ✅ Found (CD only)
**Recce Cloud:** ❌ Not configured

**Python Tooling**
- Package manager: pip
- Python version: 3.12
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

  [CI job "test" - after line 30 (dbt build --target ci --select state:modified+)]
+   dbt docs generate --target ci
+   recce-cloud upload
+   env:
+     GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}

  [CD job "deploy" - after line 52 (dbt docs generate --target prod)]
+   recce-cloud upload --type prod
+   env:
+     GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

## Notes

- CI already uses slim CI pattern (state:modified+)
- CD already has dbt docs generate, so only need to add recce-cloud upload
