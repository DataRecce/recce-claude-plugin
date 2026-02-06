# Test Fixture: GitHub Actions - Basic CI/CD

## Scenario
A dbt project with basic GitHub Actions CI/CD:
- CI job on pull_request (dbt build --target ci)
- CD job on push to main (dbt build --target prod)
- No dbt docs generate
- No Recce integration

## Expected Behavior
- Path B should be triggered (augment existing CI/CD)
- Should detect two dbt commands with different targets
- Should propose adding:
  - `dbt docs generate --target ci` after CI dbt build
  - `dbt docs generate --target prod` after CD dbt build
  - `recce-cloud upload` after CI
  - `recce-cloud upload --type prod` after CD
  - `recce-cloud` to pip install

## Files
- `dbt_project.yml` - Basic dbt project config
- `.github/workflows/ci.yml` - GitHub Actions workflow
