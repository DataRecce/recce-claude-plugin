# Expected Output: 04-gitlab-basic

## Detection Report

```
🔍 **Environment Detection Report**

**Repository**
- Remote: ⚠️ No git remote

**dbt Project**
- Name: jaffle_shop

**CI/CD Platform**
- Detected: gitlab
- Config files: .gitlab-ci.yml

**dbt Commands Found:**

| File | Line | Command | Target | Type |
|------|------|---------|--------|------|
| .gitlab-ci.yml | 18 | `dbt build --target ci` | ci | CI |
| .gitlab-ci.yml | 27 | `dbt build --target prod` | prod | CD |

**dbt docs generate:** ❌ Not found
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

.gitlab-ci.yml:

  [test job - install step]
    - pip install dbt-core dbt-snowflake
+   - pip install recce-cloud

  [test job - after line 18 (dbt build --target ci)]
+   - dbt docs generate --target ci
+   - recce-cloud upload
+   variables:
+     GITHUB_TOKEN: $CI_JOB_TOKEN  # or project access token

  [deploy job - install step]
    - pip install dbt-core dbt-snowflake
+   - pip install recce-cloud

  [deploy job - after line 27 (dbt build --target prod)]
+   - dbt docs generate --target prod
+   - recce-cloud upload --type prod
+   variables:
+     GITHUB_TOKEN: $CI_JOB_TOKEN  # or project access token

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

## Notes

- GitLab uses different syntax for environment variables (`$CI_JOB_TOKEN`)
- PR creation: `gh` CLI won't work, should show manual instructions
