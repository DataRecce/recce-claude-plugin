---
name: mcp-e2e-validate
description: >
  Use when the user asks to "validate MCP", "run MCP E2E", "run E2E validation",
  "benchmark MCP performance", "test the plugin flow", "test MCP integration",
  "compare MCP versions", "show benchmark history", "驗證 MCP", "跑 E2E",
  "看歷史紀錄", or wants to verify the recce plugin's full event chain works
  end-to-end and measure agent performance metrics.
version: 0.3.0
flow_version: 1.0.0
---

# /mcp-e2e-validate — MCP Integration E2E Validation & Benchmark

Validate the recce plugin's full event chain against a real dbt project and produce a performance benchmark report. Automatically saves results for historical comparison and loads the previous run as baseline.

**Flow version:** The `flow_version` field in frontmatter tracks the test flow structure. Only compare benchmarks with the same MAJOR.MINOR flow version — different flow versions produce incomparable metrics.

| Flow version change | When |
|---------------------|------|
| MAJOR bump | Test steps added/removed, agent dispatch logic changed |
| MINOR bump | Selector strategy, parameter defaults, or validation criteria changed |
| PATCH bump | Report format, error messages, documentation only |

**Setup:** Read learned patterns before starting:

```
Read → ${CLAUDE_PLUGIN_ROOT}/reference/learned-patterns.md
```

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

- **`--baseline`**: Override auto-baseline. Accepts a timestamp (e.g., `2026-03-13T041957`) to compare against a specific historical run, or `none` to skip comparison entirely. Without this flag, the skill automatically loads `latest.json` as baseline.
- **`--model`**: Model to edit for testing (default: first `.sql` file under `models/staging/`)
- **`--marker`**: Comment marker to inject (default: `-- recce-e2e-validation`)
- **`--skip-dbt`**: Skip the `dbt run` step if models were already built
- **`--history`**: Show benchmark history table and exit (no E2E run). Accepts optional `--limit N` and `--flow-version X.Y.Z` filters.

If no parameters provided, use defaults and run the full flow.

**`--history` short-circuit:** If `--history` is present, skip Steps 1–6 entirely. Run:

```bash
bash ${CLAUDE_PLUGIN_ROOT}/skills/mcp-e2e-validate/scripts/show-history.sh [--limit N] [--flow-version X.Y.Z]
```

Parse the output:
- If `ERROR=` → show the error verbatim (e.g., "jq is required"). **STOP.**
- If `NO_HISTORY=true` → tell user "No benchmark history found. Run a full E2E validation first." **STOP here — do not proceed to Step 1.**
- If `HAS_HISTORY=true` → display the markdown table between `---TABLE_START---` and `---TABLE_END---`, then show `TOTAL_RUNS` count. **STOP here — do not proceed to Step 1.**

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

Record `RECCE_VERSION`, `PORT`, and `DBT_ADAPTER` for the report.

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

## Step 7: Save & Report

This step has three sub-phases: load baseline → save current → produce report.

**Ordering matters:** Load baseline BEFORE saving current, because `save-benchmark.sh` overwrites `latest.json`. If you save first, `load-baseline.sh` would load the run you just saved — comparing against itself (all-zero deltas).

### 7a: Load Baseline

**If `--baseline none`**: Skip comparison entirely.

**If `--baseline <timestamp>`**: Load a specific historical run:

```bash
bash ${CLAUDE_PLUGIN_ROOT}/skills/mcp-e2e-validate/scripts/load-baseline.sh --timestamp <timestamp>
```

**If no `--baseline` flag (default)**: Auto-load the most recent run:

```bash
bash ${CLAUDE_PLUGIN_ROOT}/skills/mcp-e2e-validate/scripts/load-baseline.sh
```

Parse the KEY=VALUE output. If `BASELINE_FOUND=true`, record the baseline metrics. If `BASELINE_FOUND=false`, this is the first run — no comparison available.

**Comparability check:** Compare the baseline's `FLOW_VERSION` with the current skill's `flow_version` from frontmatter. If the MAJOR or MINOR version differs, add a warning to the report: "⚠️ Flow version changed ({baseline_fv} → {current_fv}), delta may not be comparable."

### 7b: Save Current Benchmark

Save the current run's results. Build the JSON arguments from data collected during Steps 1–6 (`RECCE_VERSION`, `DBT_ADAPTER`, `DBT_PROJECT_NAME` from Step 1 preflight; performance metrics from Step 5 agent dispatch):

```bash
bash ${CLAUDE_PLUGIN_ROOT}/skills/mcp-e2e-validate/scripts/save-benchmark.sh \
  --flow-version {flow_version_from_frontmatter} \
  --recce-version {recce_version_from_step1} \
  --adapter {DBT_ADAPTER_from_step1} \
  --project {dbt_project_name} \
  --model {test_model_name} \
  --results '{"preflight":"{PASS|FAIL}","mcp_startup":"{PASS|FAIL}","tier1_tracking":"{PASS|FAIL}","tier2_suggestion":"{PASS|FAIL}","review_agent":"{PASS|FAIL}","cleanup":"{PASS|FAIL}"}' \
  --performance '{"tool_uses":{N},"total_tokens":{N},"duration_s":{N}}' \
  --risk-level {HIGH|MEDIUM|LOW} \
  --verdict {PASS|FAIL}
```

Confirm `SAVED=true` in the output. Record `BENCHMARK_FILE` for the report.

**If save fails** (non-zero exit, `ERROR=` in output, or `SAVED=true` absent): report the error in the benchmark report's Persistence section as "Benchmark save failed: {error}". Do NOT change the overall verdict — persistence failure is informational, not a test failure. The E2E validation results (Steps 1–6) are still valid.

### 7c: Produce Report

Generate the report using the template in `references/pass-criteria.md`.

If baseline was loaded (Step 7a), compute deltas:
- `delta = current - baseline`
- `delta_pct = (delta / baseline) * 100`

Present negative deltas (improvements) with emphasis.

Include at the bottom of the report:
- `Benchmark saved: {BENCHMARK_FILE}` — so user knows where it was persisted
- `Baseline: {BASELINE_FILE}` (or "first run — no baseline") — so user knows what was compared

Output the full report to the user. If all pass criteria are met, end with **Verdict: PASS**. Otherwise list failures.

---

## Common Mistakes

- **Forgetting `eval`**: Running `bash resolve-recce-root.sh` without `eval "$(...)"` does not set `RECCE_PLUGIN_ROOT` in the current shell.
- **Shell variables do not persist**: Each Bash tool invocation starts a fresh shell. Re-run `resolve-recce-root.sh` in every step that needs `RECCE_PLUGIN_ROOT`.
- **Platform-specific `md5`**: macOS uses `md5`, Linux uses `md5sum`. The snippets in this skill handle both — do not simplify to one.
- **Not waiting after Edit**: The PostToolUse hook fires asynchronously. Wait 2 seconds before checking the tracking file.
- **Skipping cleanup on failure**: If any step fails, still execute Step 6 (cleanup). Never leave the MCP server running or model edits in place.
- **Agent dispatch**: Use the Agent tool with `subagent_type: recce:recce-reviewer`. Do not attempt to `bash` an agent markdown file.
- **Step 7 ordering**: Always load baseline BEFORE saving current. Reversing the order produces self-comparison (all-zero deltas) because save overwrites `latest.json`.
- **Benchmark scripts use cwd**: `save-benchmark.sh`, `load-baseline.sh`, and `show-history.sh` write/read `.claude/recce/benchmarks/` relative to the current working directory (the dbt project root). They are not affected by `CLAUDE_PLUGIN_ROOT`.
- **Benchmark artifacts are local-only**: `.claude/recce/benchmarks/` should be in the dbt project's `.gitignore` to avoid accidentally committing benchmark JSON files. The plugin's own `.gitignore` does not cover this — it must be added to the user's dbt project.

---

## Additional Resources

### Reference Files

- **`references/pass-criteria.md`** — Detailed pass/fail criteria per section, performance metrics extraction guide, and the benchmark report template.

### Scripts

- **`scripts/preflight.sh`** — Pre-flight environment checks (dbt project, recce version, SSE support, port availability, stale files). Outputs KEY=VALUE lines.
- **`scripts/save-benchmark.sh`** — Persists benchmark result as JSON to `.claude/recce/benchmarks/`. Updates `latest.json` for auto-baseline.
- **`scripts/load-baseline.sh`** — Loads baseline from `latest.json`, a specific timestamp, or a flow-version filter. Outputs KEY=VALUE lines.
- **`scripts/show-history.sh`** — Displays benchmark history as a markdown table with optional `--limit` and `--flow-version` filters.
- **`scripts/resolve-recce-root.sh`** (plugin-level) — Locates sibling `recce` plugin across monorepo and cache layouts. Outputs `RECCE_PLUGIN_ROOT` and `LAYOUT`.

---

## Learning

After completing the main workflow:

1. **Detection**: Any unexpected failure, workaround, or pattern not in learned-patterns.md?
   - Yes → check `${CLAUDE_PLUGIN_ROOT}/reference/learned-patterns.md`, if not covered → append D1 entry
   - No → one question: "What was most unexpected?" → three-question test → capture or done
2. "Nothing novel" is a valid and encouraged outcome.
