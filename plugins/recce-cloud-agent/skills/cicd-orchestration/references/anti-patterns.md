# Anti-Patterns & Workflow Rules

## Forbidden Questions (NEVER ask these)

- "Which CI/CD platform do you prefer?" — detect from repo structure (e.g., `.github/workflows/` → GitHub Actions, `.gitlab-ci.yml` → GitLab CI); default to GitHub Actions if ambiguous
- "What adapter are you using?" — detect from `requirements.txt` or `dbt_project.yml`
- "What package manager do you use?" — detect from file listing
- "What Python version?" — detect from `.python-version` or default to 3.11
- "Do you want CI or CD?" — always set up both
- "Which approach do you prefer for dbt execution?" — never present dbt strategy choices
- "Do you want to use dbt Cloud or local CLI?" — detect and decide, don't ask
- "Do you need help setting up your warehouse connection?" — out of scope

## Workflow Rules

- **Don't generate YAML without consulting docs first** — docs are the SSOT for templates
- **Don't create PR without showing preview and getting confirmation**
- **Don't mention unsupported platforms** — check docs for supported adapters first
- **Don't hardcode YAML templates** — always derive from current documentation
- **Don't assume single workflow file** — Recce typically needs both CI and CD workflows
- **Don't skip the Detection Report** — always present structured findings before YAML
- **Don't offer dbt configuration assistance** — only generate Recce CI/CD workflows
- **Don't present dbt execution choices** — if docs have dbt Cloud templates use them, otherwise default to local dbt CLI
- **Don't help with warehouse/infra setup** — provide docs links and redirect to CI/CD
