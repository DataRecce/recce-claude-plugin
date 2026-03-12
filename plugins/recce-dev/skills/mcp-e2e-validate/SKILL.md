---
name: mcp-e2e-validate
description: >
  This skill should be used when the user asks to "validate MCP", "run E2E",
  "benchmark MCP performance", "test the plugin flow", "compare MCP versions",
  "驗證 MCP", "跑 E2E", or wants to verify the recce plugin's full event
  chain (SessionStart → model tracking → dbt suggestion → /recce-review → cleanup)
  works end-to-end and measure agent performance metrics.
version: 0.1.0
---

# /mcp-e2e-validate — MCP Integration E2E Validation & Benchmark

Validate the recce plugin's full event chain against a real dbt project and produce a performance benchmark report. Optionally compare against a baseline to quantify improvements across recce versions or PR changes.

**Dependencies:** This skill relies on the sibling `recce` plugin's scripts (`start-mcp.sh`, `stop-mcp.sh`, `check-mcp.sh`) and hooks (`track-changes.sh`, `suggest-review.sh`). It also dispatches the `recce-reviewer` agent.

**Cross-plugin path:** The `recce` plugin is a sibling under the same parent directory. Use `RECCE_PLUGIN_ROOT` (derived below) to reference its scripts:

```bash
RECCE_PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT}/../recce"
```

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

Derive the recce plugin root and run:

```bash
RECCE_PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT}/../recce"
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
5. Verify tracking:

```bash
PROJECT_HASH=$(printf '%s' "$PWD" | md5 2>/dev/null | cut -c1-8 || printf '%s' "$PWD" | md5sum | cut -c1-8)
cat /tmp/recce-changed-${PROJECT_HASH}.txt
```

- File exists and contains the edited model path → **Tier 1 PASS**
- File missing → **Tier 1 FAIL** (record and continue)

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

Dispatch the `recce-reviewer` agent with the tracked model context:

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
   RECCE_PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT}/../recce"
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

## Additional Resources

### Reference Files

- **`references/pass-criteria.md`** — Detailed pass/fail criteria per section, performance metrics extraction guide, and the benchmark report template.

### Scripts

- **`scripts/preflight.sh`** — Pre-flight environment checks (dbt project, recce version, SSE support, port availability, stale files). Outputs KEY=VALUE lines.
