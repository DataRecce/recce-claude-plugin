# Test Fixture: GitHub Actions - Slim CI/CD

## Scenario
A dbt project with slim CI using state:modified+:
- CI job uses `--select state:modified+ --state target-base` (slim CI)
- CD job does full build and uploads manifest to S3
- CD has `dbt docs generate` already
- CI missing `dbt docs generate`
- No Recce integration

## Expected Behavior
- Path B should be triggered (augment existing CI/CD)
- Should detect slim CI pattern (state:modified+)
- Should detect existing state management (S3)
- Should detect dbt docs generate in CD but not CI
- Should propose adding:
  - `dbt docs generate --target ci` after CI dbt build
  - `recce-cloud upload` after CI
  - `recce-cloud upload --type prod` after CD (after existing dbt docs generate)
  - `recce-cloud` to pip install

## Files
- `dbt_project.yml` - Basic dbt project config
- `.github/workflows/ci.yml` - GitHub Actions workflow with slim CI
