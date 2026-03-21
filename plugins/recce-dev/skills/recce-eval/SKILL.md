---
name: recce-eval
description: >
  Use when the user asks to "run eval", "recce eval", "evaluate plugin",
  "benchmark recce", "compare with plugin", "compare without plugin",
  "eval case", "score eval", "eval report", "eval history", "list eval scenarios",
  "list eval cases", "show eval history", "run eval case",
  or wants to measure the Recce Review Agent's effectiveness
  compared to pure Claude Code without the plugin.
version: 0.1.0
---

# /recce-eval — Evaluate Recce Plugin Effectiveness

Measure the Recce Review Agent's impact by running headless Claude Code sessions with and without the Recce plugin, then scoring results against known ground truth.

**Relationship to mcp-e2e-validate:** The `mcp-e2e-validate` skill tests whether the plugin *mechanism* works (hooks fire, MCP responds). This skill tests whether the plugin provides *value* (better accuracy, fewer false positives). Run `mcp-e2e-validate` first to confirm plumbing works, then `recce-eval` to measure how much it helps.

---

## Prerequisites

Before running eval, confirm:

1. **dbt project with data loaded** — seeds populated, `dbt run` succeeds on the target
2. **Recce installed** — `recce` CLI in PATH (for MCP server)
3. **`target-base/` artifacts exist** — `dbt docs generate --target-path target-base` on the base branch
4. **No other Recce MCP server on eval port** — default 8085 (configurable via `RECCE_EVAL_MCP_PORT`)
5. **Claude Code CLI installed** — `claude` in PATH
6. **Sufficient API budget** — each run costs ~$1-5 depending on scenario complexity

---

## Subcommand Routing

Parse user input to determine which flow to execute:

- **`run --case <id> [-n N]`** → Run Flow (single scenario)
- **`run --all [-n N]`** → Run Flow (all scenarios)
- **`score <run-dir>`** → Score Flow
- **`report [eval-id]`** → Report Flow
- **`list`** → List Flow (short-circuit)
- **`history`** → History Flow (short-circuit)

Shared flags (apply to all flows that accept them):

| Flag | Description | Default |
|------|-------------|---------|
| `--target` | dbt target name | `dev-local` |
| `--adapter` | Override adapter detection | Auto-detect from profiles.yml |
| `--plugin-dir` | Recce plugin path | Auto-resolve via `resolve-recce-root.sh` |
| `--model` | Claude model for headless runs | Inherits from current session |

### List Flow (short-circuit)

Read all YAML files in `${CLAUDE_PLUGIN_ROOT}/skills/recce-eval/scenarios/`. For each file, use Python to extract `id`, `name`, `case_type`, `chapter`:

```bash
python3 -c "
import yaml, glob, os
base = '${CLAUDE_PLUGIN_ROOT}/skills/recce-eval/scenarios'
for f in sorted(glob.glob(os.path.join(base, '*.yaml'))):
    with open(f) as fh:
        d = yaml.safe_load(fh)
    print(f\"{d['id']}|{d['name']}|{d['case_type']}|{d.get('chapter', '-')}\")
"
```

Display results as a table:

| ID | Name | Case Type | Chapter |
|----|------|-----------|---------|

**STOP here.** Do not proceed to the Run Flow.

### History Flow (short-circuit)

Read `.claude/recce-eval/history.json` in the dbt project root:

```bash
cat .claude/recce-eval/history.json 2>/dev/null || echo "NO_HISTORY"
```

- If the file is missing or reads `NO_HISTORY`, tell the user: "No eval history found. Run `/recce-eval run` first."
- If present, parse the JSON array and display as a table:

| Eval ID | Timestamp | Adapter | Scenario | Baseline Det. | Plugin Det. | Baseline Judge | Plugin Judge |
|---------|-----------|---------|----------|--------------|-------------|----------------|--------------|

**STOP here.** Do not proceed to the Run Flow.

---

## Run Flow

This is the core orchestration — 14 steps that set up scenarios, run headless Claude Code, score results, and produce a report.

### Step 1: Read Scenario(s)

If `--case <id>`: read `${CLAUDE_PLUGIN_ROOT}/skills/recce-eval/scenarios/<id>.yaml`.
If `--all`: read all `.yaml` files in the scenarios directory.

For each scenario file, parse the YAML content:

```bash
python3 -c "
import yaml, json
with open('${CLAUDE_PLUGIN_ROOT}/skills/recce-eval/scenarios/<id>.yaml') as f:
    d = yaml.safe_load(f)
print(json.dumps(d))
"
```

Extract and record these fields for each scenario: `id`, `case_type`, `setup` (strategy, patch_reverse_file, dbt_commands), `prompt`, `headless` (max_budget_usd), `ground_truth`, `judge_criteria`, `teardown` (restore_files).

### Step 2: Detect Adapter

Determine the dbt adapter type from profiles.yml. Use `--adapter` if provided; otherwise auto-detect:

```bash
TARGET="${USER_TARGET:-dev-local}"
ADAPTER=$(python3 -c "
import yaml
with open('profiles.yml') as f:
    p = yaml.safe_load(f)
for proj in p.values():
    if isinstance(proj, dict) and 'outputs' in proj:
        t = proj.get('target', 'dev')
        outputs = proj['outputs']
        target_cfg = outputs.get('$TARGET', outputs.get(t, {}))
        print(target_cfg.get('type', 'unknown'))
        break
" 2>/dev/null || echo "unknown")
echo "ADAPTER=$ADAPTER"
```

Set template variables based on adapter:

| Adapter | `{target}` | `{adapter_description}` |
|---------|-----------|------------------------|
| duckdb | `dev-local` | `DuckDB (local file database, target: dev-local)` |
| snowflake | `dev` | `Snowflake (cloud data warehouse, target: dev)` |

If a custom `--target` was provided, use that value for `{target}` regardless of adapter defaults.

### Step 3: Resolve Plugin Dir

Resolve the sibling `recce` plugin directory. This is needed for the `with-plugin` variant's `--plugin-dir` flag:

```bash
eval "$(bash ${CLAUDE_PLUGIN_ROOT}/scripts/resolve-recce-root.sh)"
echo "RECCE_PLUGIN_ROOT=$RECCE_PLUGIN_ROOT"
echo "LAYOUT=$LAYOUT"
```

If `ERROR=` appears in output, abort with the error message. Cannot run the `with-plugin` variant without a valid plugin directory.

If the user provided `--plugin-dir`, use that value instead and skip this resolution.

### Step 4: Create Batch Directory

Create a timestamped directory for this eval batch:

```bash
EVAL_ID=$(date +"%Y%m%d-%H%M")
BATCH_DIR=".claude/recce-eval/runs/$EVAL_ID"
mkdir -p "$BATCH_DIR"
echo "EVAL_ID=$EVAL_ID"
echo "BATCH_DIR=$BATCH_DIR"
```

Record `EVAL_ID` and `BATCH_DIR` for later steps.

### Step 5: Prepare Prompt

For each scenario, substitute template variables (`{target}`, `{adapter_description}`) in the scenario's `prompt` field. Write the substituted prompt to a temp file:

```bash
PROMPT_FILE="/tmp/recce-eval-prompt-${EVAL_ID}-${SCENARIO_ID}.txt"
cat > "$PROMPT_FILE" << 'PROMPT_EOF'
<substituted prompt content here>
PROMPT_EOF
echo "PROMPT_FILE=$PROMPT_FILE"
```

The prompt text comes from the scenario YAML's `prompt` field, with `{target}` and `{adapter_description}` replaced by the values determined in Step 2.

### Step 6: Generate Eval MCP Config

Create a temporary MCP config JSON that points to the eval MCP server port. This is passed via `--mcp-config` to the `with-plugin` variant so the headless session connects to the eval-specific port (not the plugin's default):

```bash
EVAL_PORT="${RECCE_EVAL_MCP_PORT:-8085}"
cat > /tmp/recce-eval-mcp-config.json << EOF
{
  "mcpServers": {
    "recce": {
      "type": "sse",
      "url": "http://localhost:${EVAL_PORT}/sse"
    }
  }
}
EOF
echo "MCP_CONFIG=/tmp/recce-eval-mcp-config.json"
echo "EVAL_PORT=$EVAL_PORT"
```

**Assumption**: `--mcp-config` takes precedence over the plugin's `.mcp.json` for the same server key. If this does not hold, use `--strict-mcp-config` and add `recce-docs` to the eval config explicitly.

### Step 7: Start Eval MCP Server

Start the MCP server with eval-specific port and PID isolation:

```bash
bash ${CLAUDE_PLUGIN_ROOT}/skills/recce-eval/scripts/start-eval-mcp.sh
```

Parse the KEY=VALUE output:
- `STATUS=STARTED` or `STATUS=ALREADY_RUNNING` → record `PORT` and `PID`, proceed.
- `ERROR=` → abort with the error details. If `ERROR=PORT_IN_USE`, suggest setting `RECCE_EVAL_MCP_PORT` to a different port.

### Step 8: Interleaved Run Loop

Run each scenario with both variants in interleaved order. For N runs, the execution order is: baseline run1 → with-plugin run1 → baseline run2 → with-plugin run2 → ... This reduces systematic bias from cache warming or temporal effects.

For each run number (1 to N), for each variant (`baseline` first, then `with-plugin`):

```bash
# Create scenario output dir
mkdir -p "$BATCH_DIR/$SCENARIO_ID"

# ---- Baseline variant ----
bash ${CLAUDE_PLUGIN_ROOT}/skills/recce-eval/scripts/run-case.sh \
    --id "$SCENARIO_ID" \
    --case-type "$CASE_TYPE" \
    --variant baseline \
    --prompt-file "$PROMPT_FILE" \
    --setup-strategy "$SETUP_STRATEGY" \
    --patch-file "${CLAUDE_PLUGIN_ROOT}/skills/recce-eval/$PATCH_FILE" \
    --restore-files "$RESTORE_FILES" \
    --target "$TARGET" \
    --max-budget-usd "$MAX_BUDGET" \
    --output-dir "$BATCH_DIR/$SCENARIO_ID" \
    --run-number "$RUN_NUM"
```

Parse the KEY=VALUE output from `run-case.sh`. Record `OUTPUT_FILE`, `JSON_EXTRACTED`, `TOTAL_COST_USD`, `DURATION_MS`.

Immediately score the baseline run:

```bash
bash ${CLAUDE_PLUGIN_ROOT}/skills/recce-eval/scripts/score-deterministic.sh \
    --run-file "$BATCH_DIR/$SCENARIO_ID/baseline_run${RUN_NUM}.json" \
    --case-type "$CASE_TYPE" \
    --ground-truth '$GROUND_TRUTH_JSON'
```

Then run the with-plugin variant:

```bash
# ---- With-plugin variant ----
bash ${CLAUDE_PLUGIN_ROOT}/skills/recce-eval/scripts/run-case.sh \
    --id "$SCENARIO_ID" \
    --case-type "$CASE_TYPE" \
    --variant with-plugin \
    --prompt-file "$PROMPT_FILE" \
    --setup-strategy "$SETUP_STRATEGY" \
    --patch-file "${CLAUDE_PLUGIN_ROOT}/skills/recce-eval/$PATCH_FILE" \
    --restore-files "$RESTORE_FILES" \
    --target "$TARGET" \
    --max-budget-usd "$MAX_BUDGET" \
    --output-dir "$BATCH_DIR/$SCENARIO_ID" \
    --plugin-dir "$RECCE_PLUGIN_ROOT" \
    --mcp-config /tmp/recce-eval-mcp-config.json \
    --run-number "$RUN_NUM"
```

Score the with-plugin run:

```bash
bash ${CLAUDE_PLUGIN_ROOT}/skills/recce-eval/scripts/score-deterministic.sh \
    --run-file "$BATCH_DIR/$SCENARIO_ID/with-plugin_run${RUN_NUM}.json" \
    --case-type "$CASE_TYPE" \
    --ground-truth '$GROUND_TRUTH_JSON'
```

**Important**: The `--ground-truth` value must be a valid JSON string. Extract the `ground_truth` object from the scenario YAML and pass it as a single-quoted JSON string. Example:

```bash
--ground-truth '{"issue_found":true,"root_cause_keywords":["null","left join","coalesce"],"impacted_models":["orders","orders_daily_summary"],"not_impacted_models":["customers","customer_segments","customer_order_pattern"],"affected_row_count":1584,"all_tests_pass":true}'
```

**Handling setup.strategy**: When calling `run-case.sh`:
- If `setup.strategy` is `git_patch`, pass `--patch-file` pointing to `${CLAUDE_PLUGIN_ROOT}/skills/recce-eval/<setup.patch_reverse_file>` and `--restore-files` as a comma-separated list from `teardown.restore_files`.
- If `setup.strategy` is `none`, pass `--setup-strategy none`. Omit `--patch-file` and `--restore-files`.

**Error handling**: If `run-case.sh` fails (non-zero exit), log the error and continue to the next run. The teardown trap inside `run-case.sh` handles file restoration automatically. Do not add separate teardown calls here.

Report progress to the user after each run completes: "Run {N} {variant} complete: cost=${cost}, duration=${duration}s, json_extracted={yes/no}".

### Step 9: Stop Eval MCP Server

After all runs complete (or if aborting due to an error), stop the eval MCP server:

```bash
bash ${CLAUDE_PLUGIN_ROOT}/skills/recce-eval/scripts/stop-eval-mcp.sh
```

Confirm `STATUS=STOPPED` or `STATUS=NOT_RUNNING`. Always execute this step, even if earlier steps failed.

### Step 10: Dispatch LLM Judge

Use the Agent tool to dispatch `recce-dev:eval-judge` with a prompt that includes all the information the judge needs. Group runs by scenario so the judge can compare variants:

> For scenario `{scenario_id}` (case_type: {case_type}):
>
> Per-run JSON files:
> - {absolute path to baseline_run1.json}
> - {absolute path to with-plugin_run1.json}
> - {absolute path to baseline_run2.json} (if N > 1)
> - {absolute path to with-plugin_run2.json} (if N > 1)
>
> Ground truth:
> ```json
> {ground_truth from scenario YAML}
> ```
>
> Judge criteria:
> - {criterion 1}
> - {criterion 2}
> - {criterion 3}
>
> Read each file and score according to the eval-judge rubric.

If running multiple scenarios, dispatch the judge once per scenario (not once per run) so it can compare variants within the scenario.

**Error handling**: If the judge agent fails or returns invalid JSON, continue without judge scores. The report will note "LLM judge: unavailable" for affected runs.

### Step 11: Merge Judge Scores

Parse the judge's JSON output. For each run entry in the judge's `runs` array, read the corresponding per-run JSON file and merge `scores.llm_judge` into it:

```bash
# For each run scored by the judge, merge the scores
jq --argjson judge '<judge scores for this run>' \
    '.scores.llm_judge = $judge' \
    "$RUN_FILE" > "${RUN_FILE}.tmp" && mv "${RUN_FILE}.tmp" "$RUN_FILE"
```

The judge returns scores per run in the format:
```json
{
  "reasoning_chain": {"score": N, "rationale": "..."},
  "evidence_quality": {"score": N, "rationale": "..."},
  "fix_quality": {"score": N, "rationale": "..."},
  "false_positive_discipline": {"score": N, "rationale": "..."},
  "completeness": {"score": N, "rationale": "..."},
  "overall_score": N.N,
  "notable_observations": ["..."],
  "comparison_notes": "..."
}
```

Write `comparison_notes` to each run's `scores.llm_judge.comparison_notes` as well.

### Step 12: Write meta.json

Write batch metadata to the batch directory:

```bash
cat > "$BATCH_DIR/meta.json" << EOF
{
  "eval_id": "$EVAL_ID",
  "timestamp": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "target": "$TARGET",
  "adapter": "$ADAPTER",
  "scenarios_run": $SCENARIOS_JSON_ARRAY,
  "runs_per_scenario": $N,
  "plugin_dir": "$RECCE_PLUGIN_ROOT",
  "recce_version": "$(recce --version 2>/dev/null || echo unknown)",
  "claude_model": "$CLAUDE_MODEL",
  "max_budget_usd_per_run": $MAX_BUDGET
}
EOF
```

Where `$SCENARIOS_JSON_ARRAY` is a JSON array of scenario IDs (e.g., `["ch1-null-amounts", "ch1-healthy-audit"]`), and `$CLAUDE_MODEL` is from `--model` flag or the current session's model.

### Step 13: Generate Report

Read all per-run JSONs in the batch directory (now containing both deterministic and judge scores). Follow the structure defined in `${CLAUDE_PLUGIN_ROOT}/skills/recce-eval/references/report-template.md`.

Read `.claude/recce-eval/history.json` for cross-eval comparison data. If a previous entry exists with the same adapter, compute deltas for the Cross-Eval Comparison section.

Write `report.md` to the batch directory:

```bash
# Write the generated report
cat > "$BATCH_DIR/report.md" << 'REPORT_EOF'
<generated report content>
REPORT_EOF
```

The report includes:
1. **Environment** section with target, adapter, versions, budget
2. **Summary** table with per-scenario per-variant aggregated metrics
3. **Key Findings** with AI-generated analysis of failure patterns and plugin advantages
4. **Detailed Scores** with per-run deterministic checks and judge scores
5. **Cross-Eval Comparison** with historical deltas (if available)

### Step 14: Update History and Print Summary

Append a summary entry to `.claude/recce-eval/history.json`:

```bash
# Read existing history or start empty array
HISTORY=$(cat .claude/recce-eval/history.json 2>/dev/null || echo "[]")

# Build new entry and append
NEW_ENTRY='{
  "eval_id": "'"$EVAL_ID"'",
  "timestamp": "'"$(date -u +"%Y-%m-%dT%H:%M:%SZ")"'",
  "adapter": "'"$ADAPTER"'",
  "claude_model": "'"$CLAUDE_MODEL"'",
  "summary": { ... per-scenario summary with det_pass_rate and judge_avg ... }
}'

echo "$HISTORY" | jq --argjson entry "$NEW_ENTRY" '. + [$entry]' > .claude/recce-eval/history.json
```

Update the `latest` symlink:

```bash
ln -sfn "$EVAL_ID" .claude/recce-eval/runs/latest
```

Print a summary to the user:

- Total runs completed
- Per-scenario comparison table (baseline vs with-plugin)
- Path to the full report: `$BATCH_DIR/report.md`
- Any warnings (judge failures, MCP issues, etc.)

---

## Score Flow (`score <run-dir>`)

Re-score existing runs without re-running them. Useful after updating scoring logic or ground truth.

1. Read all `*_run*.json` files in the specified directory.
2. For each file, determine `case_type` from the JSON's `case_type` field.
3. Look up the corresponding scenario YAML from `${CLAUDE_PLUGIN_ROOT}/skills/recce-eval/scenarios/` using the `scenario_id` in the JSON.
4. Extract `ground_truth` from the scenario YAML.
5. Re-run `score-deterministic.sh` on each file:

```bash
bash ${CLAUDE_PLUGIN_ROOT}/skills/recce-eval/scripts/score-deterministic.sh \
    --run-file "$RUN_FILE" \
    --case-type "$CASE_TYPE" \
    --ground-truth '$GROUND_TRUTH_JSON'
```

6. Re-dispatch `recce-dev:eval-judge` on each scenario's runs (group by scenario).
7. Merge judge scores into per-run JSONs.
8. Regenerate `report.md` in the run directory.

---

## Report Flow (`report [eval-id]`)

Regenerate the report from existing scored runs without re-scoring.

1. If no eval-id provided, resolve the latest batch:

```bash
LATEST=$(readlink .claude/recce-eval/runs/latest 2>/dev/null || echo "")
```

If empty, tell user "No eval runs found." and **STOP**.

2. Set `BATCH_DIR=".claude/recce-eval/runs/$EVAL_ID"`.
3. Read all per-run JSONs in the batch directory. They must already have `scores.deterministic` and optionally `scores.llm_judge`.
4. Read `${CLAUDE_PLUGIN_ROOT}/skills/recce-eval/references/report-template.md` for the report structure.
5. Generate `report.md` following the template. Write to `$BATCH_DIR/report.md`.
6. Print the report to the user.

---

## Common Mistakes

- **Shell variables do not persist**: Each Bash tool invocation starts a fresh shell. Re-derive `EVAL_ID`, `BATCH_DIR`, `TARGET`, `ADAPTER`, `RECCE_PLUGIN_ROOT`, and other state in every Bash block that needs them. Do not assume a previous Bash call's variables are available.

- **Forgetting `eval`**: Running `bash resolve-recce-root.sh` without `eval "$(...)"` does not set `RECCE_PLUGIN_ROOT` in the current shell.

- **Platform-specific `md5`**: macOS uses `md5`, Linux uses `md5sum`. The eval scripts handle both — do not simplify to one.

- **MCP config precedence**: If `--mcp-config` does not override the plugin's `.mcp.json` for the `"recce"` key, use `--strict-mcp-config` and add `recce-docs` to the eval config explicitly.

- **Interleaved order matters**: Run baseline then with-plugin for the same run number before moving to the next run number. Do not group all baselines then all with-plugins — this introduces systematic bias.

- **Teardown is trap-based in run-case.sh**: The script restores files even if `claude -p` fails. Do not add separate teardown calls in the SKILL.md orchestration.

- **Ground truth as JSON string**: When passing `--ground-truth` to `score-deterministic.sh`, the value must be a valid JSON string. Use single quotes around the entire JSON value in bash to prevent shell expansion.

- **Adapter detection uses Python + PyYAML**: Do not use grep to parse profiles.yml. The target's adapter type depends on the nested YAML structure which requires proper parsing.

- **Always stop the eval MCP server**: Even if runs fail or the judge errors out, execute `stop-eval-mcp.sh` before finishing. Leaving the server running on the eval port will block future eval runs.

- **Prompt file per scenario**: When running `--all`, create a separate prompt file for each scenario (use `${EVAL_ID}-${SCENARIO_ID}` in the filename) since each scenario has a different prompt.

---

## Additional Resources

### Scripts

- **`scripts/run-case.sh`** — Atomic runner: setup state, invoke `claude -p`, capture output, teardown, write per-run JSON. Outputs KEY=VALUE lines.
- **`scripts/score-deterministic.sh`** — jq-based scoring against ground truth. Reads and updates per-run JSON in-place. Outputs KEY=VALUE lines.
- **`scripts/start-eval-mcp.sh`** — Start Recce MCP server on eval-specific port (default 8085) with isolated PID file. Outputs KEY=VALUE lines.
- **`scripts/stop-eval-mcp.sh`** — Stop eval MCP server using eval-scoped PID file.
- **`scripts/resolve-recce-root.sh`** (plugin-level, at `${CLAUDE_PLUGIN_ROOT}/scripts/`) — Locate sibling `recce` plugin across monorepo and cache layouts.

### Agents

- **`agents/eval-judge.md`** — LLM-as-judge subagent. Scores reasoning quality, evidence quality, fix quality, false positive discipline, and completeness. Dispatched via `recce-dev:eval-judge`.

### References

- **`references/scoring-rubric.md`** — Deterministic scoring rules per case_type and LLM judge dimension definitions.
- **`references/report-template.md`** — Report structure guide with placeholder format and generation rules.

### Scenarios

- **`scenarios/ch1-null-amounts.yaml`** — Case A (problem_exists): broken pipeline with NULL amounts from missing COALESCE.
- **`scenarios/ch1-healthy-audit.yaml`** — Case B (no_problem): healthy pipeline audit that should find no issues.

### Patches

- **`patches/ch1-add-coalesce.patch`** — The COALESCE fix. Reverse-applied during setup to create the broken state for ch1-null-amounts.
