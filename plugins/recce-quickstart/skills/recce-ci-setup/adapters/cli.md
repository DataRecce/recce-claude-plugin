# CLI Tool Mapping

Maps abstract operations to CLI (bash) commands for use with Claude Code.

## Detection Operations

| Abstract Operation | CLI Command |
|---|---|
| Determine git remote URL | `git remote get-url origin 2>/dev/null` |
| Verify git repository | `git rev-parse --git-dir 2>/dev/null` |
| Get repo root | `git rev-parse --show-toplevel` |
| Check if file exists | `ls {file} 2>/dev/null` or `test -f {file}` |
| Find file by name | `find . -name "{filename}" -type f -maxdepth 5 2>/dev/null \| head -1` |
| Read file content | Use the Read tool |
| Search for pattern in file | Use the Grep tool or `grep -n "{pattern}" {file}` |
| List directory contents | `ls {dir}/*.yml {dir}/*.yaml 2>/dev/null` |
| Search for dbt commands in CI | `grep -n -A 5 -E "dbt (build\|run\|test\|seed\|snapshot)" {config_file}` |
| Check for string in files | `grep -r "{string}" {dir} 2>/dev/null` |
| Read profiles.yml | Check `profiles.yml` in project dir, then `~/.dbt/profiles.yml` |
| Extract adapter type | `grep -E "^\s+type:\s*" {profiles_path} \| head -1 \| sed 's/.*type:\s*//' \| tr -d ' '` |

## CI/CD Operations

| Abstract Operation | CLI Command |
|---|---|
| Create directory | `mkdir -p {dir}` |
| Write workflow file | Use the Write tool to create the file |
| Edit existing file | Use the Edit tool to modify lines |
| Create branch | `git checkout -b {branch_name}` |
| Stage files | `git add {files}` |
| Commit changes | `git commit -s -m "{message}"` |
| Push branch | `git push -u origin {branch}` |
| Create GitHub PR | `gh pr create --title "{title}" --body "{body}"` |
| Create GitLab MR | `glab mr create --title "{title}" --description "{body}"` |

## User Interaction

| Abstract Operation | CLI Command |
|---|---|
| Ask user a question | Use the AskUserQuestion tool with options |
| Present choices | Use the AskUserQuestion tool with labeled options |
