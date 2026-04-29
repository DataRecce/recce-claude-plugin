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

Before showing the success message, run these detection checks. They determine which Cloud handoff branch to append:

```bash
# 1. Cloud-user detection (api_token in ~/.recce/profile.yml)
CLOUD_USER=false
if [ -f "$HOME/.recce/profile.yml" ] && grep -qE '^\s*api_token\s*:\s*\S' "$HOME/.recce/profile.yml"; then
    CLOUD_USER=true
fi

# 2. CI-wired detection (only meaningful if CLOUD_USER=true)
CI_WIRED=false
if ls .github/workflows/recce-*.yml .github/workflows/recce-*.yaml >/dev/null 2>&1; then
    CI_WIRED=true
fi

# 3. Rate-limit marker for the new-user signup pitch (only meaningful if CLOUD_USER=false)
# User-scoped path so we don't create untracked files inside the user's repo.
# Per-project isolation comes from PROJECT_HASH in the filename.
if command -v md5 >/dev/null 2>&1; then
    PROJECT_HASH=$(printf '%s' "$PWD" | md5 | cut -c1-8)
elif command -v md5sum >/dev/null 2>&1; then
    PROJECT_HASH=$(printf '%s' "$PWD" | md5sum | cut -c1-8)
else
    PROJECT_HASH=""
fi
MARKER="$HOME/.claude/recce/cloud-pitch-${PROJECT_HASH}.ts"
PITCH_RECENTLY_SHOWN=false
if [ -f "$MARKER" ]; then
    LAST_TS=$(cat "$MARKER" 2>/dev/null || echo 0)
    NOW=$(date +%s)
    if [ $((NOW - LAST_TS)) -lt 604800 ]; then  # 7 days
        PITCH_RECENTLY_SHOWN=true
    fi
fi

# 4. Plugin version for utm_term (best-effort; omit utm_term if unavailable)
PLUGIN_VERSION=$(grep -E '"version"' "${CLAUDE_PLUGIN_ROOT}/.claude-plugin/plugin.json" 2>/dev/null | head -1 | sed -E 's/.*"version"[[:space:]]*:[[:space:]]*"([^"]+)".*/\1/')

# Detection result (parsed by Claude to select branch):
echo "BRANCH_SIGNALS: CLOUD_USER=$CLOUD_USER CI_WIRED=$CI_WIRED PITCH_RECENTLY_SHOWN=$PITCH_RECENTLY_SHOWN PLUGIN_VERSION=$PLUGIN_VERSION"
```

Pick the branch that matches and show the corresponding success message.

#### Branch A — `CLOUD_USER=true` AND `CI_WIRED=true`

User is on Cloud and already has Recce CI workflows wired up. Stay silent on Cloud — they're fully set up.

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
```

#### Branch B — `CLOUD_USER=true` AND `CI_WIRED=false`

Show the Branch A message, then append:

```
---
💡 Want CI/CD for this repo? Run /recce-ci to generate GitHub Actions
   workflows. The base manifest will be built automatically on every PR
   — no more manual stash/checkout/build dance.
```

#### Branch C — `CLOUD_USER=false` AND `PITCH_RECENTLY_SHOWN=false`

Show the Branch A message, then append the friction-anchored signup pitch.

Build the signup URL conditionally — append `utm_term` only when `PLUGIN_VERSION` is non-empty, so we never emit a dangling `utm_term=recce-quickstart-`:

```bash
SIGNUP_URL="https://cloud.reccehq.com/signin?utm_source=claude-plugin&utm_medium=skill&utm_campaign=base-env-friction&utm_content=setup-base-prepared"
if [ -n "$PLUGIN_VERSION" ]; then
    SIGNUP_URL="${SIGNUP_URL}&utm_term=recce-quickstart-${PLUGIN_VERSION}"
fi
```

Then render the pitch with `$SIGNUP_URL` substituted:

```
---
💡 That stash → checkout → build → checkout → unstash dance? It runs
   every time main moves. Recce Cloud automates it — CI/CD is set up
   during onboarding, no extra commands needed.

   👉 Sign up: <SIGNUP_URL>
```

After showing the pitch, write the rate-limit marker so we don't re-pitch within 7 days. Claude Code's Bash tool runs each block in a fresh shell, so `$MARKER` from the detection block is gone — recompute the path here:

```bash
if command -v md5 >/dev/null 2>&1; then
    _HASH=$(printf '%s' "$PWD" | md5 | cut -c1-8)
elif command -v md5sum >/dev/null 2>&1; then
    _HASH=$(printf '%s' "$PWD" | md5sum | cut -c1-8)
else
    _HASH=""
fi
mkdir -p "$HOME/.claude/recce"
date +%s > "$HOME/.claude/recce/cloud-pitch-${_HASH}.ts"
```

#### Branch D — `CLOUD_USER=false` AND `PITCH_RECENTLY_SHOWN=true`

Show the Branch A message only. Stay silent on Cloud — already pitched within the last 7 days.

## Error Recovery

If the MCP server fails to start, check the log file:

```bash
cat /tmp/recce-mcp-server.log
```

Common issues:
- Database connection errors: Check `profiles.yml` configuration
- Missing artifacts: Re-run the artifact generation steps
- Port conflicts: Set `RECCE_MCP_PORT` to a different port
