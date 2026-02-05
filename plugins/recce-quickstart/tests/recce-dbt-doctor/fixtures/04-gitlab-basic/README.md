# Test Fixture: GitLab CI - Basic CI/CD

## Scenario
A dbt project with basic GitLab CI/CD:
- test job on merge_request (dbt build --target ci)
- deploy job on main branch (dbt build --target prod)
- No dbt docs generate
- No Recce integration

## Expected Behavior
- Path B should be triggered (augment existing CI/CD)
- Should detect GitLab CI platform
- Should detect two dbt commands with different targets
- Should propose adding:
  - `dbt docs generate --target ci` after CI dbt build
  - `dbt docs generate --target prod` after CD dbt build
  - `recce-cloud upload` after CI
  - `recce-cloud upload --type prod` after CD
  - `recce-cloud` to pip install
- Should show GitLab MR URL for PR creation (not gh)

## Files
- `dbt_project.yml` - Basic dbt project config
- `.gitlab-ci.yml` - GitLab CI configuration
