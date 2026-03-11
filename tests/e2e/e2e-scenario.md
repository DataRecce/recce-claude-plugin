# recce-dev Plugin: Full E2E Validation Scenario

**Purpose:** This file is a standalone walkthrough prompt for validating the full `recce-dev` plugin flow in a real Claude Code session. Paste the prompt in Section 5 into a Claude Code session opened in `jaffle_shop_golden`.

**Test environment:** `/Users/kent/Project/recce/jaffle_shop_golden` (Snowflake dual-environment)
**Plugin source:** `/Users/kent/Project/recce/recce-claude-plugin`

---

## Section 1: Pre-Flight Setup (Human Steps — Before Opening Claude Code)

Complete these steps in your terminal before starting a Claude Code session in `jaffle_shop_golden`.

### 1.1 Activate the virtual environment

```bash
cd /Users/kent/Project/recce/jaffle_shop_golden
source .venv/bin/activate
```

Verify recce is installed with MCP support:

```bash
recce --version
pip show recce | grep -i mcp
# Or: pip install 'recce[mcp]'
```

If not installed:

```bash
pip install 'recce[mcp]'
```

### 1.2 Verify target-base symlink exists

```bash
ls -la target-base
# Expected: symlink pointing to a directory that contains manifest.json
ls target-base/manifest.json   # Must exist
ls target/manifest.json        # Must exist (current artifacts)
```

If the symlink is missing:

```bash
ln -sfn target-basess target-base   # Adjust target name as needed
```

### 1.3 Verify .env file has Snowflake credentials

```bash
ls .env
# Expected: file exists with SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, etc.
```

If `.env` is missing, create it from your dbt profiles credentials:

```bash
# Example .env structure:
# SNOWFLAKE_ACCOUNT=your_account
# SNOWFLAKE_USER=your_user
# SNOWFLAKE_PASSWORD=your_password
# SNOWFLAKE_WAREHOUSE=your_warehouse
# SNOWFLAKE_DATABASE=your_database
# SNOWFLAKE_SCHEMA=your_schema
```

### 1.4 Verify port 8082 is free (optional)

```bash
lsof -i :8082 || echo "port free"
```

If you want to use a custom port, create the settings file before starting Claude Code:

```bash
mkdir -p .claude/recce-dev
echo '{"mcp_port": 8082}' > .claude/recce-dev/settings.json
```

### 1.5 Clean up any stale PID files from previous runs

```bash
ls /tmp/recce-mcp-*.pid 2>/dev/null && rm /tmp/recce-mcp-*.pid || echo "no stale pids"
ls /tmp/recce-changed-*.txt 2>/dev/null && rm /tmp/recce-changed-*.txt || echo "no stale tracked files"
```

---

## Section 2: Plugin Install (Inside Claude Code Session)

Open a new Claude Code session with your working directory set to `jaffle_shop_golden`:

```bash
claude /Users/kent/Project/recce/jaffle_shop_golden
```

Then run these slash commands in the Claude Code session:

```
/plugin marketplace add /Users/kent/Project/recce/recce-claude-plugin
/plugin install recce-dev@recce-claude-plugin
```

**Expected:** Plugin appears in the Installed tab. No errors during installation.

---

## Section 3: Observe SessionStart Hook

When the Claude Code session starts (after plugin install and next session open), the `session-start.sh` hook fires automatically.

### Expected KEY=VALUE output lines

The hook output should contain (in any order):

```
DBT_PROJECT=true
DBT_PROJECT_NAME=jaffle_shop_golden
RECCE_INSTALLED=true
TARGET_EXISTS=true
MCP_STARTED=true
PORT=8081
STATUS=STARTED
URL=http://localhost:8081/sse
SETTINGS_SOURCE=defaults
```

**Note:** `SETTINGS_SOURCE=project` if you created `.claude/recce-dev/settings.json` in step 1.4.

### If MCP does not start

Check the log file path shown in `LOG_FILE=` output:

```bash
cat /tmp/recce-mcp-*.log
```

Common causes:
- `.env` not loaded (check `source .env` works manually)
- `target-base/manifest.json` missing (stale symlink)
- Port already in use

---

## Section 4: Model Edit — Trigger Tier 1 Tracking

Instruct Claude Code (in the session) to make a reversible edit to the staging orders model:

> Edit `models/staging/stg_orders.sql` and add the comment `-- recce-e2e-validation` on a new line at the very end of the file.

**Expected behavior after the Write hook fires:**

The `track-changes.sh` PostToolUse hook (Tier 1) runs silently and records the model:

```bash
# Verify the tracked file was created (run in terminal, not Claude Code):
PROJECT_HASH=$(printf '%s' "$(pwd)" | md5 | cut -c1-8)
cat /tmp/recce-changed-${PROJECT_HASH}.txt
# Expected output: models/staging/stg_orders.sql
```

**Important:** The hook is silent — Claude Code will not show any output from `track-changes.sh`. The tracking happens invisibly in the background.

---

## Section 5: dbt Run — Trigger Tier 2 Suggestion

Instruct Claude Code to run dbt on the modified model:

> Run `dbt run -s stg_orders+` in the terminal.

**Expected behavior after the Bash PostToolUse hook fires:**

The `suggest-review.sh` hook injects a `additionalContext` message into Claude Code suggesting a review:

```
1 model(s) changed: stg_orders
Consider running /recce-review to validate data impact before committing.
```

**Note on async behavior:** The Tier 1 hook (`track-changes.sh`) runs with `async: true` — it will not add latency to Write/Edit operations. The Tier 2 hook (`suggest-review.sh`) runs synchronously after Bash tool use.

---

## Section 6: Run /recce-review

In the Claude Code session, invoke the review command:

```
/recce-review
```

The skill (`skills/recce-review/SKILL.md`) will:

1. Check MCP server health via `check-mcp.sh`
2. Auto-start MCP if not running via `start-mcp.sh`
3. Read the tracked models from `/tmp/recce-changed-{hash}.txt`
4. Dispatch the `recce-reviewer` sub-agent with MCP tools

### Expected review output

The `recce-reviewer` agent will produce a **Data Review Summary** containing:

```markdown
## Data Review Summary

**Models reviewed:** stg_orders (and downstream)
**Risk Level:** LOW | MEDIUM | HIGH

### Lineage Impact
[Output from mcp__recce-dev__lineage_diff]

### Row Counts
| Model          | Base Count | Current Count | Diff |
|----------------|------------|---------------|------|
| stg_orders     | NNNN       | NNNN          | +/-N |

### Schema Comparison
[Column-level diff if any columns changed]

### Recommendation
[Risk-based guidance]
```

**Known limitation (MKTD-02):** The `recce-docs` MCP server uses a relative path (`../../packages/recce-docs-mcp/dist/index.js`) that will fail after marketplace install. Expect path errors related to recce-docs in the MCP configuration. This is an accepted PoC limitation and does NOT affect the `recce-dev` MCP tools.

---

## Section 7: Pass Criteria

The E2E validation **PASSES** if the review summary contains ALL of the following:

### 7.1 Concrete row count numbers

The `stg_orders` row count (or a downstream model) must show a **non-zero integer** in both base and current columns. Values of `N/A`, `null`, `error`, or `0` are failures.

Example passing value: `12,453`

### 7.2 Risk level present

The summary must contain one of: `LOW`, `MEDIUM`, or `HIGH` as the Risk Level assessment.

### 7.3 Model names in summary

The model name `stg_orders` (and likely `fct_orders` or other downstream models) must appear in the summary text.

### 7.4 No MCP tool errors

The `recce-dev` MCP tools (`lineage_diff`, `row_count_diff`, `schema_diff`) must complete without error. Timeouts or connection errors indicate the MCP server did not start correctly.

---

## Section 8: Cleanup

After a successful review, revert the model change:

> Revert the `-- recce-e2e-validation` comment from `models/staging/stg_orders.sql`

Then stop the MCP server:

```bash
bash ~/.claude/plugins/recce-dev/scripts/stop-mcp.sh
# Or, if running from source:
bash /Users/kent/Project/recce/recce-claude-plugin/plugins/recce-dev/scripts/stop-mcp.sh
```

Clean up the tracked models file:

```bash
PROJECT_HASH=$(printf '%s' "$(pwd)" | md5 | cut -c1-8)
rm -f /tmp/recce-changed-${PROJECT_HASH}.txt
```

---

## Section 9: Stale State Check

After plugin uninstall (or to validate clean state), verify no leftover files exist:

```bash
# No stale PID files
ls /tmp/recce-mcp-*.pid 2>/dev/null && echo "FAIL: stale PID files found" || echo "PASS: no stale PID files"

# No stale tracked model files
ls /tmp/recce-changed-*.txt 2>/dev/null && echo "FAIL: stale tracked files found" || echo "PASS: no stale tracked files"

# Plugin directory removed after uninstall
ls ~/.claude/plugins/recce-dev/ 2>/dev/null && echo "FAIL: plugin dir still present" || echo "PASS: plugin dir removed"

# Project-level settings directory cleaned up
ls .claude/recce-dev/ 2>/dev/null && echo "NOTE: project settings dir present (expected if you created settings.json)" || echo "PASS: no project settings dir"
```

**Note:** The `.claude/recce-dev/` directory is created by the user (not the plugin install), so its presence after uninstall is expected if the user created project-level settings. The plugin install/uninstall only manages `~/.claude/plugins/recce-dev/`.

---

## Summary: Full Event Chain

```
SessionStart
    └─> session-start.sh
            ├─> Detects dbt project (dbt_project.yml)
            ├─> Checks recce installation
            └─> Starts MCP server (start-mcp.sh)
                    └─> Loads .env (Snowflake credentials)
                    └─> Starts: recce mcp-server --sse --port 8081

PostToolUse (Write/Edit)
    └─> track-changes.sh [async]
            └─> Appends models/staging/stg_orders.sql to /tmp/recce-changed-{hash}.txt

PostToolUse (Bash: dbt run)
    └─> suggest-review.sh
            └─> Injects: "Consider running /recce-review" with model names

/recce-review (skill trigger)
    └─> skills/recce-review/SKILL.md
            ├─> check-mcp.sh (health check)
            ├─> start-mcp.sh (auto-start if needed)
            ├─> Reads /tmp/recce-changed-{hash}.txt
            └─> Dispatches: agents/recce-reviewer.md
                    ├─> mcp__recce-dev__lineage_diff
                    ├─> mcp__recce-dev__row_count_diff
                    ├─> mcp__recce-dev__schema_diff
                    └─> Outputs: ## Data Review Summary
```

---

*Last updated: 2026-03-11*
*Phase: 07-e2e-validation*
*Validates: VALD-01, VALD-02*
