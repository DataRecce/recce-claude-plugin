---
name: mcp-e2e-validate
description: >
  Use when the user asks to "validate MCP", "run MCP E2E", "run E2E validation",
  "benchmark MCP performance", "test the plugin flow", "test MCP integration",
  "compare MCP versions", "驗證 MCP", "跑 E2E", or wants to verify the recce
  plugin's full event chain works end-to-end and measure agent performance metrics.
version: 0.2.0
---

# /mcp-e2e-validate — MCP Integration E2E Validation & Benchmark

Validate the recce plugin's full event chain against a real dbt project and produce a performance benchmark report. Optionally compare against a baseline to quantify improvements across recce versions or PR changes.

**Dependencies:** This skill relies on the sibling `recce` plugin's scripts (`start-mcp.sh`, `stop-mcp.sh`, `check-mcp.sh`) and hooks (`track-changes.sh`, `suggest-review.sh`). It also dispatches the `recce-reviewer` agent.

**Cross-plugin path:** The `recce` plugin is located via `resolve-recce-root.sh`, which auto-detects both monorepo and cache layouts:

```bash
eval "$(bash ${CLAUDE_PLUGIN_ROOT}/scripts/resolve-recce-root.sh)"
# Sets RECCE_PLUGIN_ROOT and LAYOUT (monorepo|cache)
```

If the script is unavailable or fails, abort with an error — do not hardcode paths.

**Shell variable note:** Each Bash tool invocation runs in a fresh shell. Steps that reference sibling plugin scripts must re-evaluate `resolve-recce-root.sh` to set `RECCE_PLUGIN_ROOT`.

---

## Inputs

Parse user input for optional parameters:

- **`--baseline`**: Previous benchmark metrics for comparison (e.g., `"tool_uses=35 tokens=30311 duration_s=483"`)
- **`--model`**: Model to edit for testing (default: first `.sql` file under `models/staging/`)
- **`--marker`**: Comment marker to inject (default: `-- recce-e2e-validation`)
- **`--skip-dbt`**: Skip the `dbt run` step if models were already built

If no parameters provided, use defaults and run the full flow.

---

## Step 1: Pre-flight

Run the pre-flight check script:

```bash
bash ${CLAUDE_PLUGIN_ROOT}/skills/mcp-e2e-validate/scripts/preflight.sh
```

Parse KEY=VALUE output. Abort if any `BLOCK=` line appears — show the message verbatim.

Handle warnings:
- `SSE_SUPPORT=false` → Inform user: editable install may need `rm -rf site-packages/recce/` then `pip install -e ".[mcp]"`. See memory for details.
- `PORT_STATUS=occupied_by_other` → Suggest changing port in `.claude/recce/settings.json`
- `STALE_FILES=found` → Auto-clean: `rm -f /tmp/recce-mcp-*.pid /tmp/recce-changed-*.txt`

Record `RECCE_VERSION` and `PORT` for the report.

---

## Step 2: Start MCP Server

Resolve the recce plugin root, then start:

```bash
eval "$(bash ${CLAUDE_PLUGIN_ROOT}/scripts/resolve-recce-root.sh)"
bash "${RECCE_PLUGIN_ROOT}/scripts/start-mcp.sh"
```

- If `STATUS=STARTED` or `STATUS=ALREADY_RUNNING` → record `PORT` and `PID`, proceed.
- If `ERROR=` → abort with error details.

Verify with health check:

```bash
bash "${RECCE_PLUGIN_ROOT}/scripts/check-mcp.sh"
```

Confirm `RUNNING=true` before proceeding.

---

## Step 3: Inject Test Edit (Tier 1 Trigger)

1. Select the target model file (from `--model` or default staging model).
2. Read the file and record its original content.
3. Append the marker comment (`-- recce-e2e-validation`) on a new line at the end.
4. Use the Edit tool (this triggers `track-changes.sh` PostToolUse hook).
5. Wait 2 seconds for async hook execution, then verify tracking:

```bash
PROJECT_HASH=$(printf '%s' "$PWD" | md5 2>/dev/null | cut -c1-8 || printf '%s' "$PWD" | md5sum | cut -c1-8)
cat /tmp/recce-changed-${PROJECT_HASH}.txt
```

6. **Evaluate result:**
   - File exists and contains the edited model path → **Tier 1 PASS**
   - File missing → **Tier 1 FAIL (hook)** — apply fallback below, then continue

**Tier 1 Fallback:** If the tracking file does not exist (common after mid-session plugin install — hooks require a fresh session to activate), manually create it so downstream steps can proceed:

```bash
PROJECT_HASH=$(printf '%s' "$PWD" | md5 2>/dev/null | cut -c1-8 || printf '%s' "$PWD" | md5sum | cut -c1-8)
echo "<ABSOLUTE_PATH_TO_EDITED_MODEL>" > /tmp/recce-changed-${PROJECT_HASH}.txt
```

Record in the report: "Tier 1 FAIL (hook not fired — manually simulated)".

---

## Step 4: dbt Run (Tier 2 Trigger)

Skip if `--skip-dbt` was specified.

Run dbt on the modified model and downstream:

```bash
dbt run -s {model_name}+
```

- dbt completes with `PASS` → record model count. The `suggest-review.sh` hook should inject a review suggestion into context. **Tier 2 PASS**.
- dbt fails → **Tier 2 FAIL** (record error, continue to cleanup)

---

## Step 5: Dispatch Review Agent

Use the Agent tool to dispatch the `recce-reviewer` agent (subagent_type: `recce:recce-reviewer`) with the tracked model context:

> "Changed models (from tracked file): {model_name}. Focus review on these models using selector: {model_name}+"

**Capture the full agent result**, including the `<usage>` block. Extract:
- `tool_uses` — number of MCP tool calls
- `total_tokens` — total token consumption
- `duration_ms` — wall-clock time

Check agent output for `## Data Review Summary`. Validate against pass criteria in `references/pass-criteria.md`:
- Concrete row count numbers (non-zero integers)
- Risk level present (LOW/MEDIUM/HIGH)
- Model names in summary
- No MCP tool errors

---

## Step 6: Cleanup

Execute in order:

1. **Revert model edit** — restore the file to its original content (remove marker comment).
2. **Stop MCP server**:
   ```bash
   eval "$(bash ${CLAUDE_PLUGIN_ROOT}/scripts/resolve-recce-root.sh)"
   bash "${RECCE_PLUGIN_ROOT}/scripts/stop-mcp.sh"
   ```
3. **Clean tracked files**:
   ```bash
   PROJECT_HASH=$(printf '%s' "$PWD" | md5 2>/dev/null | cut -c1-8 || printf '%s' "$PWD" | md5sum | cut -c1-8)
   rm -f "/tmp/recce-changed-${PROJECT_HASH}.txt"
   ```
4. **Stale state check** — verify no `/tmp/recce-mcp-*.pid` or `/tmp/recce-changed-*.txt` remain.

---

## Step 7: Produce Benchmark Report

Generate the report using the template in `references/pass-criteria.md`.

If `--baseline` was provided, compute deltas:
- `delta = current - baseline`
- `delta_pct = (delta / baseline) * 100`

Present negative deltas (improvements) with emphasis.

Output the full report to the user. If all pass criteria are met, end with **Verdict: PASS**. Otherwise list failures.

---

## Common Mistakes

- **Forgetting `eval`**: Running `bash resolve-recce-root.sh` without `eval "$(...)"` does not set `RECCE_PLUGIN_ROOT` in the current shell.
- **Shell variables do not persist**: Each Bash tool invocation starts a fresh shell. Re-run `resolve-recce-root.sh` in every step that needs `RECCE_PLUGIN_ROOT`.
- **Platform-specific `md5`**: macOS uses `md5`, Linux uses `md5sum`. The snippets in this skill handle both — do not simplify to one.
- **Not waiting after Edit**: The PostToolUse hook fires asynchronously. Wait 2 seconds before checking the tracking file.
- **Skipping cleanup on failure**: If any step fails, still execute Step 6 (cleanup). Never leave the MCP server running or model edits in place.
- **Agent dispatch**: Use the Agent tool with `subagent_type: recce:recce-reviewer`. Do not attempt to `bash` an agent markdown file.

---

## Additional Resources

### Reference Files

- **`references/pass-criteria.md`** — Detailed pass/fail criteria per section, performance metrics extraction guide, and the benchmark report template.

### Scripts

- **`scripts/preflight.sh`** — Pre-flight environment checks (dbt project, recce version, SSE support, port availability, stale files). Outputs KEY=VALUE lines.
- **`scripts/resolve-recce-root.sh`** (plugin-level) — Locates sibling `recce` plugin across monorepo and cache layouts. Outputs `RECCE_PLUGIN_ROOT` and `LAYOUT`.
