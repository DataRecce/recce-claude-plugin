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

## Dependencies

Eval scripts require:

- **yq** — YAML processor ([mikefarah/yq](https://github.com/mikefarah/yq)). Install: `brew install yq`
- **jq** — JSON processor. Install: `brew install jq`
- **git** — required for v2 eval flows that clone/manage projects. Install: `brew install git` (or use your OS package manager)
- **Python 3 with venv + pip** — required for v2 eval flows via `setup-v2-project.sh`. Ensure `python3`, `python3 -m venv`, and `pip` are available in your PATH.

## Setup

Read learned patterns before starting:

```
Read → ${CLAUDE_PLUGIN_ROOT}/reference/learned-patterns.md
```

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

- **`run --case <id>[,<id2>,...] [-n N]`** → Run Flow (one or more scenarios by ID)
- **`run --all [-n N]`** → Run Flow (all scenarios)
- **`run --select [-n N]`** → Select Flow → Run Flow (interactive scenario picker)
- **`score <run-dir>`** → Score Flow
- **`report [eval-id]`** → Report Flow
- **`list`** → List Flow (short-circuit)
- **`history`** → History Flow (short-circuit)

Shared flags (apply to all flows that accept them):

| Flag | Description | Default |
|------|-------------|---------|
| `--version` | Scenario version: `v1` or `v2` | `v2` |
| `--target` | dbt target name | `dev-local` (v1), `dev` (v2) |
| `--adapter` | Override adapter detection | Auto-detect from profiles.yml |
| `--plugin-dir` | Recce plugin path | Auto-resolve via `resolve-recce-root.sh` |
| `--model` | Claude model for headless runs | Inherits from current session |
| `--no-bare` | Disable bare mode — use OAuth auth, no API key needed | `--bare` is ON by default |

### Version-Based Path Routing

Based on `--version`, determine the scenario subdirectory and default target:

- `--version v1`: scenarios live in `skills/recce-eval/scenarios/v1/`, default target is `dev-local`
- `--version v2` (default): scenarios live in `skills/recce-eval/scenarios/v2/`, default target is `dev`

**IMPORTANT**: Throughout this document, all references to the scenarios directory must use the version-appropriate path. Use `scenarios/v1/` for v1 and `scenarios/v2/` for v2 in every scenario path lookup, glob, and `--patch-file` reference.

The `--target` flag overrides the default if provided.

### List Flow (short-circuit)

```bash
bash ${CLAUDE_PLUGIN_ROOT}/skills/recce-eval/scripts/list-scenarios.sh --version <v1|v2>
```

Display results as a table:

| ID | Name | Case Type | Difficulty |
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

### Select Flow (interactive picker)

When `--select` is used, present the user with an interactive scenario picker before entering the Run Flow.

1. Load all scenario YAML files from the version-appropriate directory (same as List Flow).
2. Use `AskUserQuestion` with `multiSelect: true` to let the user pick scenarios:
   - Each option's `label` is the scenario ID
   - Each option's `description` is the scenario name and difficulty
3. Parse the selected IDs and proceed to the Run Flow with those scenarios (same as `--case <id1>,<id2>,...`).

If the user selects nothing (cancels), **STOP**.

---

## Run Flow

This is the core orchestration — 12 steps that set up scenarios, run headless Claude Code, score results, and produce a report.

### Step 1: Read Scenario(s)

Use the version-appropriate scenario directory (see Version-Based Path Routing above).

If `--case <id>` (single ID): read `<scenario-dir>/<id>.yaml`.
If `--case <id1>,<id2>,...` (comma-separated): read each `<scenario-dir>/<id>.yaml`.
If `--all`: read all `.yaml` files in `<scenario-dir>/`.
If `--select`: scenarios were already selected in the Select Flow above.

Where `<scenario-dir>` is `${CLAUDE_PLUGIN_ROOT}/skills/recce-eval/scenarios/v1` (v1) or `${CLAUDE_PLUGIN_ROOT}/skills/recce-eval/scenarios/v2` (v2).

For each scenario file, extract the required fields in a single `yq` call.

**v2 scenarios** use `prompt.template` + `prompt.vars` (template-based):

```bash
yq -o=json '{
  "id": .id,
  "case_type": .case_type,
  "setup_strategy": .setup.strategy,
  "patch_file": .setup.patch_reverse_file,
  "prompt_template": .prompt.template,
  "prompt_vars": .prompt.vars,
  "max_budget_usd": .headless.max_budget_usd,
  "ground_truth": .ground_truth,
  "judge_criteria": .judge_criteria,
  "restore_files": .teardown.restore_files
}' "<scenario-dir>/<id>.yaml"
```

**v1 scenarios** use `prompt:` as an inline string (no template/vars):

```bash
yq -o=json '{
  "id": .id,
  "case_type": .case_type,
  "setup_strategy": .setup.strategy,
  "patch_file": .setup.patch_reverse_file,
  "prompt_inline": .prompt,
  "max_budget_usd": .headless.max_budget_usd,
  "ground_truth": .ground_truth,
  "judge_criteria": .judge_criteria,
  "restore_files": .teardown.restore_files
}' "<scenario-dir>/<id>.yaml"
```

When `prompt_template` is non-null (v2), read the template file and substitute vars in Step 5. When `prompt_inline` is non-null (v1), use it directly as the prompt text.

### Step 1b: Clone & Bootstrap v2 Project (v2 only)

**Skip this step entirely for `--version v1`.** Only execute when `--version v2`.

v2 scenarios include `environment.repo` and `environment.ref` fields that specify the dbt project to clone. Parse these from the first scenario (all v2 scenarios share the same repo):

```bash
yq -o=json '{"repo": .environment.repo, "ref": .environment.ref // "main"}' "<scenario-dir>/<first-scenario-id>.yaml"
```

Clone the repo and bootstrap dbt:

```bash
eval "$(bash ${CLAUDE_PLUGIN_ROOT}/skills/recce-eval/scripts/setup-v2-project.sh \
    --repo "$REPO" --ref "$REF")"
echo "PROJECT_DIR=$PROJECT_DIR"
```

Record `PROJECT_DIR` — pass it as `--project-dir "$PROJECT_DIR"` to all `run-case.sh` invocations in Step 8.

**Cleanup**: At the very end of the Run Flow (after Step 12), remove the temp project:

```bash
if [ -n "$WORK_DIR" ] && [[ "$WORK_DIR" == "${TMPDIR:-/tmp}"* ]]; then
    rm -rf "$WORK_DIR"
fi
```

### Step 2: Detect Adapter

Determine the dbt adapter type from profiles.yml. Use `--adapter` if provided; otherwise auto-detect:

```bash
TARGET="${USER_TARGET:-dev}"
# Try the requested target first; fall back to the profile's default target
ADAPTER=$(yq "
  .. | select(has(\"outputs\")) |
  .outputs[\"$TARGET\"].type //
  .outputs[.target // \"dev\"].type //
  \"unknown\"
" profiles.yml 2>/dev/null | head -1)
ADAPTER="${ADAPTER:-unknown}"
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
# Always use the invoking CWD (the plugin repo) as the eval output base.
# v2 PROJECT_DIR is a temp dir that gets cleaned up — output must survive cleanup.
EVAL_BASE="$(pwd)"
BATCH_DIR="${EVAL_BASE}/.claude/recce-eval/runs/$EVAL_ID"
mkdir -p "$BATCH_DIR"
echo "EVAL_ID=$EVAL_ID"
echo "BATCH_DIR=$BATCH_DIR"
```

Record `EVAL_ID` and `BATCH_DIR` for later steps. `BATCH_DIR` is always absolute and anchored to the invoking CWD, so eval output survives v2 temp project cleanup.

### Step 5: Prepare Prompt

Build the prompt text for each scenario, then write to a temp file.

**v2 (template+vars):** Read the template file from `prompt_template` (relative to `${CLAUDE_PLUGIN_ROOT}/skills/recce-eval/`), then substitute `{variables}` with values from `prompt_vars` and runtime values (`{target}`, `{adapter_description}`).

**v1 (inline prompt):** Use the `prompt_inline` string directly, substituting only runtime values (`{target}`, `{adapter_description}`).

```bash
PROMPT_FILE="/tmp/recce-eval-prompt-${EVAL_ID}-${SCENARIO_ID}.txt"
cat > "$PROMPT_FILE" << 'PROMPT_EOF'
<substituted prompt content here>
PROMPT_EOF
echo "PROMPT_FILE=$PROMPT_FILE"
```

### Step 6: Generate Eval MCP Config

Create a temporary MCP config JSON using **stdio** transport for Recce MCP. This avoids DuckDB lock conflicts — claude spawns the MCP server as a child process after run-case.sh setup completes, so `dbt run` in setup never competes for the database lock.

```bash
cat > /tmp/recce-eval-mcp-config.json << EOF
{
  "mcpServers": {
    "recce": {
      "type": "stdio",
      "command": "recce",
      "args": ["mcp-server"]
    },
    "recce-docs": {
      "type": "stdio",
      "command": "node",
      "args": ["${RECCE_PLUGIN_ROOT}/servers/recce-docs-mcp/dist/cli.js"]
    }
  }
}
EOF
echo "MCP_CONFIG=/tmp/recce-eval-mcp-config.json"
```

**Why stdio, not SSE**: SSE mode (`start-eval-mcp.sh`) keeps a persistent DuckDB read connection that blocks `dbt run`'s exclusive write lock during setup. stdio transport defers MCP startup to claude's process, which runs after setup. No external MCP server lifecycle management needed.

**Why `--strict-mcp-config`**: The `--mcp-config` flag is additive and its merge behavior with plugin `.mcp.json` for same-name keys is undocumented. Using `--strict-mcp-config` guarantees the eval config is the sole MCP source.

### Step 7: Interleaved Run Loop

Set `NO_BARE` based on whether the user passed `--no-bare`:
- If `--no-bare` was passed: `NO_BARE=true` (passes `--no-bare --no-clean-profile` to `run-case.sh`, uses OAuth auth)
- Otherwise: `NO_BARE=""` (default `--bare` mode, requires `ANTHROPIC_API_KEY`)

Run each scenario with both variants in interleaved order. For N runs, the execution order is: baseline run1 → with-plugin run1 → baseline run2 → with-plugin run2 → ... This reduces systematic bias from cache warming or temporal effects.

For each run number (1 to N), for each variant (`baseline` first, then `with-plugin`):

```bash
# Create scenario output dir
mkdir -p "$BATCH_DIR/$SCENARIO_ID"

# ---- Baseline variant ----
# --bare is default: no memory, no CLAUDE.md, pure prompt-driven evaluation
# When user passes --no-bare: add --no-bare --no-clean-profile (uses OAuth, no API key needed)
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
    --run-number "$RUN_NUM" \
    ${NO_BARE:+--no-bare --no-clean-profile} \
    ${PROJECT_DIR:+--project-dir "$PROJECT_DIR"}
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
# --bare is default; --plugin-dir injects the plugin even in bare mode
# When user passes --no-bare: add --no-bare --no-clean-profile (uses OAuth, no API key needed)
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
    --run-number "$RUN_NUM" \
    ${NO_BARE:+--no-bare --no-clean-profile} \
    ${PROJECT_DIR:+--project-dir "$PROJECT_DIR"}
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

### Step 8: Dispatch LLM Judge

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

### Step 9: Merge Judge Scores

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

### Step 10: Write meta.json

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

### Step 11: Generate Report

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

### Step 12: Update History and Print Summary

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
3. Look up the corresponding scenario YAML from the version-appropriate directory (`scenarios/v1/` or `scenarios/v2/`) using the `scenario_id` in the JSON.
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

## Isolation Modes

`run-case.sh` supports three isolation modes:

| Flag | Memory | CLAUDE.md | Plugin Hooks | Auth | Use Case |
|------|--------|-----------|-------------|------|----------|
| `--no-bare` | ✅ | ✅ | ✅ | OAuth | Internal dev testing |
| **`--bare`** (default) | ❌ | ❌ | ❌ | API key | **Recommended: identical isolation for both variants** |
| `--clean-profile` | ❌ | ❌ | ✅ | API key | Deprecated — causes baseline to produce only 1 turn |

### `--bare` (default, recommended)

Both variants run with `--bare` for identical isolation. The with-plugin variant adds `--plugin-dir` which injects the Recce plugin even in bare mode — hooks fire, MCP tools are available, but there is no user memory or CLAUDE.md leaking into results.

```bash
# Baseline: --bare (implicit default)
bash run-case.sh --id ch3-phantom-filter --variant baseline ...

# With-plugin: --bare + --plugin-dir (plugin injected in bare mode)
bash run-case.sh --id ch3-phantom-filter --variant with-plugin \
    --plugin-dir "$RECCE_PLUGIN_ROOT" --mcp-config /tmp/eval-mcp.json ...
```

**Why `--bare` over `--clean-profile`**: `--clean-profile` (HOME override) causes baseline agents to produce only 1 text turn with no structured JSON output, making scoring impossible. `--bare` provides clean isolation while the agent still engages with tools normally. `--bare --plugin-dir` injects the plugin, so with-plugin runs get the full plugin experience.

## Common Mistakes

- **Shell variables do not persist**: Each Bash tool invocation starts a fresh shell. Re-derive `EVAL_ID`, `BATCH_DIR`, `TARGET`, `ADAPTER`, `RECCE_PLUGIN_ROOT`, and other state in every Bash block that needs them. Do not assume a previous Bash call's variables are available.

- **Forgetting `eval`**: Running `bash resolve-recce-root.sh` without `eval "$(...)"` does not set `RECCE_PLUGIN_ROOT` in the current shell.

- **Platform-specific `md5`**: macOS uses `md5`, Linux uses `md5sum`. The eval scripts handle both — do not simplify to one.

- **MCP config uses `--strict-mcp-config`**: The eval config must be the sole MCP source. `run-case.sh` passes `--strict-mcp-config --mcp-config` so the eval port is guaranteed. The eval config in Step 6 must include both `recce` (eval port) and `recce-docs` (from `$RECCE_PLUGIN_ROOT`).

- **`--mcp-config` is variadic**: `--mcp-config <configs...>` consumes subsequent positional arguments. The `--` separator before the prompt in `run-case.sh` prevents the prompt from being parsed as a config argument. Do not remove it.

- **Interleaved order matters**: Run baseline then with-plugin for the same run number before moving to the next run number. Do not group all baselines then all with-plugins — this introduces systematic bias.

- **Teardown is trap-based in run-case.sh**: The script restores files even if `claude -p` fails. Do not add separate teardown calls in the SKILL.md orchestration.

- **Ground truth as JSON string**: When passing `--ground-truth` to `score-deterministic.sh`, the value must be a valid JSON string. Use single quotes around the entire JSON value in bash to prevent shell expansion.

- **Adapter detection uses `yq`**: Do not use grep to parse profiles.yml. The target's adapter type depends on the nested YAML structure which requires proper YAML parsing.

- **stdio MCP needs no lifecycle management**: With stdio transport, claude spawns/kills the MCP server automatically. No `start-eval-mcp.sh` / `stop-eval-mcp.sh` calls needed. The `start-eval-mcp.sh` and `stop-eval-mcp.sh` scripts are retained for SSE mode fallback only.

- **Prompt file per scenario**: When running `--all`, create a separate prompt file for each scenario (use `${EVAL_ID}-${SCENARIO_ID}` in the filename) since each scenario has a different prompt.

- **v2 project cleanup**: When `--version v2`, clean up `WORK_DIR` at the end of the Run Flow. Always guard with a `$TMPDIR` prefix check before `rm -rf` to avoid accidental deletion outside temp.

- **v2 default target is `dev`, not `dev-local`**: The jaffle-shop-simulator profiles.yml uses `dev` as its default target. If `--target` is not provided with `--version v2`, use `dev`.

- **v2 clone is shared across scenarios**: When running `--all --version v2`, clone the repo ONCE (from the first scenario's `environment.repo` and `environment.ref`) and reuse `PROJECT_DIR` for all scenarios. Do not clone per-scenario.

---

## Additional Resources

### Scripts

- **`scripts/list-scenarios.sh`** — List scenarios for a version. Single `yq eval-all` call. Outputs pipe-delimited rows.
- **`scripts/run-case.sh`** — Atomic runner: setup state, invoke `claude -p`, capture output, teardown, write per-run JSON. Outputs KEY=VALUE lines.
- **`scripts/score-deterministic.sh`** — jq-based scoring against ground truth. Reads and updates per-run JSON in-place. Outputs KEY=VALUE lines.
- **`scripts/setup-v2-project.sh`** — Clone a dbt project repo to a temp dir and bootstrap (venv, dbt deps, seed). Used by v2 scenarios only. Outputs `PROJECT_DIR=<path>` and `WORK_DIR=<path>`.
- **`scripts/start-eval-mcp.sh`** — Start Recce MCP server on eval-specific port (default 8085). Retained for SSE mode fallback only.
- **`scripts/stop-eval-mcp.sh`** — Stop eval MCP server. Retained for SSE mode fallback only.
- **`scripts/resolve-recce-root.sh`** (plugin-level, at `${CLAUDE_PLUGIN_ROOT}/scripts/`) — Locate sibling `recce` plugin across monorepo and cache layouts.

### Agents

- **`${CLAUDE_PLUGIN_ROOT}/agents/eval-judge.md`** — LLM-as-judge subagent. Scores reasoning quality, evidence quality, fix quality, false positive discipline, and completeness. Dispatched via `recce-dev:eval-judge`.

### References

- **`references/scoring-rubric.md`** — Deterministic scoring rules per case_type and LLM judge dimension definitions.
- **`references/report-template.md`** — Report structure guide with placeholder format and generation rules.

### Scenarios

- **`scenarios/v1/ch1-null-amounts.yaml`** — Case A (problem_exists): broken pipeline with NULL amounts from missing COALESCE.
- **`scenarios/v1/ch1-healthy-audit.yaml`** — Case B (no_problem): healthy pipeline audit that should find no issues.
- **`scenarios/v1/ch2-silent-filter.yaml`** — Case C (problem_exists): WHERE clause silently drops return_pending orders, all tests pass.
- **`scenarios/v1/ch2-amount-misscale.yaml`** — Case D (problem_exists): amount/1000 instead of /100 makes payments 10x too small, all tests pass.
- **`scenarios/v1/ch3-phantom-filter.yaml`** — Case E (problem_exists): WHERE amount > 0 silently drops 2,326 valid $0 transactions, looks like intentional cleanup.
- **`scenarios/v1/ch3-join-shift.yaml`** — Case F (problem_exists): join key typo (customer_id vs order_id) produces plausible but wrong amounts, all tests pass.
- **`scenarios/v1/ch3-count-distinct.yaml`** — Case G (problem_exists): count(*) → count(distinct customer_id) changes metric semantics without changing column name.

### Patches

- **`scenarios/v1/patches/ch1-add-coalesce.patch`** — The COALESCE fix. Reverse-applied during setup to create the broken state for ch1-null-amounts.
- **`scenarios/v1/patches/ch2-remove-status-filter.patch`** — Removes the return_pending filter from stg_orders.
- **`scenarios/v1/patches/ch2-fix-amount-scale.patch`** — Fixes amount/1000 → amount/100 in stg_payments.
- **`scenarios/v1/patches/ch3-phantom-filter.patch`** — Removes the WHERE amount > 0 filter from stg_payments.
- **`scenarios/v1/patches/ch3-join-shift.patch`** — Restores correct join key (order_id) in orders.sql.
- **`scenarios/v1/patches/ch3-count-distinct.patch`** — Restores count(*) in orders_daily_summary.

---

## Learning

After completing the main workflow:

1. **Detection**: Any unexpected failure, workaround, or pattern not in learned-patterns.md?
   - Yes → check `${CLAUDE_PLUGIN_ROOT}/reference/learned-patterns.md`, if not covered → append D1 entry
   - No → one question: "What was most unexpected?" → three-question test → capture or done
2. "Nothing novel" is a valid and encouraged outcome.
