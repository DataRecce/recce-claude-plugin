# Expected Output: 01-no-ci

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
  • Detected: ⚠️ No CI config found
  • Config files: none

dbt Commands Found:
  (none)

dbt docs generate: ❌ Not found
Recce Cloud: ❌ Not configured

Python Tooling
  • Package manager: unknown
  • Python version: unknown

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

## Expected Path

**Path A: Generate New CI/CD**

Should offer to create:
- `.github/workflows/recce-ci.yml`
- `.github/workflows/recce-prod.yml`

## Expected Questions

1. "Which package manager do you use?" (uv/pip)
2. "Which Python version?" (3.12/3.11/3.10)
3. "Apply these changes?" (Yes/Show files/Skip)
