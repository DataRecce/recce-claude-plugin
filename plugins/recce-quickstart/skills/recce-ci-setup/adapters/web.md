# Web Agent Tool Mapping

Maps abstract operations to Web Agent tools (GitHub API) for the Recce Cloud assistant.

## Detection Operations

| Abstract Operation | Web Agent Tool |
|---|---|
| Determine git remote URL | `get_github_status(organizationId, projectId)` — returns repo URL |
| Check if file exists | `list_repo_files(path="{dir}")` — check if filename appears in listing |
| Find file by name | `list_repo_files(path="", recursive=true)` — search for filename |
| Read file content | `read_repo_file(path="{file}")` |
| Search for pattern in file | `read_repo_file(path="{file}")` then search content in response |
| List directory contents | `list_repo_files(path="{dir}")` |
| Search for dbt commands | `read_repo_file(path="{config}")` then parse for dbt commands |

## CI/CD Operations

All write operations are batched into a single PR:

| Abstract Operation | Web Agent Tool |
|---|---|
| Create files + Commit + Push + Create PR | `create_cicd_pull_request(files, commitMessage, prTitle, prBody)` |

The `create_cicd_pull_request` tool handles:
- Creating/modifying multiple files
- Committing changes on a new branch
- Pushing to remote
- Creating the pull request

Pass all file changes as a single batch:
```json
{
  "files": [
    { "path": ".github/workflows/recce-ci.yml", "content": "..." },
    { "path": ".github/workflows/recce-prod.yml", "content": "..." }
  ],
  "commitMessage": "ci: add Recce Cloud CI/CD integration",
  "prTitle": "Add Recce Cloud CI/CD integration",
  "prBody": "..."
}
```

## User Interaction

In the web agent, present choices inline in the response text.
There is no AskUserQuestion tool — instead, describe options and ask the user
to respond with their choice.

## Notes

- The web agent can only access GitHub repositories (not GitLab, CircleCI, etc.)
- All repository operations go through the GitHub API
- File reads are limited to the default branch unless specified
