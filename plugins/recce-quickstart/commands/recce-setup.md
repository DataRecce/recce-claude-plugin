---
name: recce-setup
description: Guided setup for Recce environment in a dbt project
---

# Recce Setup - Guided Environment Configuration

You are helping the user set up Recce in their dbt project. Follow these steps in order, checking each prerequisite before proceeding.

## Setup Checklist

Execute each step sequentially. If a step fails, help the user resolve it before continuing.

### Step 1: Check Python/pip

Run: `python3 --version || python --version`

- If NOT installed: Tell the user they need Python 3.8+ installed and provide installation guidance for their OS.
- If installed: Continue to next step.

### Step 2: Check dbt Installation

Run: `dbt --version`

- If NOT installed: Ask the user which database they use, then suggest:
  - PostgreSQL: `pip install dbt-postgres`
  - BigQuery: `pip install dbt-bigquery`
  - Snowflake: `pip install dbt-snowflake`
  - DuckDB: `pip install dbt-duckdb`
  - Redshift: `pip install dbt-redshift`
  - Databricks: `pip install dbt-databricks`
- If installed: Continue to next step.

### Step 3: Check dbt Project

Run: `ls dbt_project.yml`

- If NOT found: Tell the user this is not a dbt project directory. Ask them to navigate to their dbt project or run `dbt init` to create one.
- If found: Continue to next step.

### Step 4: Check profiles.yml Connection

Run: `dbt debug`

- If FAILS: Help the user configure their `profiles.yml`. The file should be at `~/.dbt/profiles.yml` or in the project directory.
- If PASSES: Continue to next step.

### Step 5: Detect and Configure Branches

Run: `git branch --show-current`

Determine base and target branches:

1. Get current branch
2. If current is `main` or `master`:
   - Base = current branch
   - Ask user for target branch (list recent branches with `git for-each-ref --sort=-committerdate refs/heads/ --format='%(refname:short) (%(committerdate:relative))' | head -5`)
3. If current is NOT `main`/`master`:
   - Target = current branch
   - Base = `main` or `master` (check which exists)

Present the detected configuration to the user and ask for confirmation:
```
Detected branch configuration:
• Base branch: main (comparison baseline)
• Target branch: feature/new-model (your changes)

Is this correct?
[1] Yes, continue
[2] Change base branch
[3] Change target branch
[4] Enter branch names manually
```

### Step 6: Generate Base Artifacts

Check if `target-base/manifest.json` exists.

- If EXISTS: Skip this step, artifacts already present.
- If NOT EXISTS: Ask user permission, then run:
  ```bash
  git stash  # Save any uncommitted changes
  git checkout <base-branch>
  dbt build --target-path target-base
  git checkout <target-branch>
  git stash pop  # Restore uncommitted changes (if any)
  ```

### Step 7: Generate Current Artifacts

Check if `target/manifest.json` exists.

- If EXISTS: Ask if user wants to regenerate (their code may have changed).
- If NOT EXISTS: Run `dbt build`

### Step 8: Install Recce

Run: `recce --version`

- If NOT installed: Run `pip install recce`
- If installed: Continue to next step.

### Step 9: Start Recce MCP Server

Run: `bash ${CLAUDE_PLUGIN_ROOT}/scripts/start-mcp.sh`

Parse the output:
- If `STATUS=STARTED` or `STATUS=ALREADY_RUNNING`: Success!
- If `ERROR=*`: Show the error message and FIX suggestion to the user.

### Step 10: Setup Complete!

Show success message:

```
🎉 Recce environment setup complete!

You can now use:
• /recce-pr - Analyze PR data changes
• /recce-check - Run data validation checks

Or use Recce MCP tools directly:
• lineage_diff - See model changes and impact
• schema_diff - Compare schema changes
• row_count_diff - Compare row counts
• profile_diff - Statistical profiles

---
💡 **Recce Cloud** can help you:
• ☁️ Save Recce state in the cloud
• 👥 Collaborate with team members
• 📊 Track historical changes

👉 Learn more: https://cloud.datarecce.io
```

## Error Recovery

If the MCP server fails to start, check the log file:

```bash
cat /tmp/recce-mcp-server.log
```

Common issues:
- Database connection errors: Check `profiles.yml` configuration
- Missing artifacts: Re-run the artifact generation steps
- Port conflicts: Set `RECCE_MCP_PORT` to a different port
