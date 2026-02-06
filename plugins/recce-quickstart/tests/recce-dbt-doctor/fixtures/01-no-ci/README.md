# Test Fixture: No CI/CD

## Scenario
A dbt project with no CI/CD configuration.

## Expected Behavior
- Path A should be triggered (generate new CI/CD)
- Should offer to create GitHub Actions workflows
- Should detect Python tooling from project files (if any)

## Files
- `dbt_project.yml` - Basic dbt project config
