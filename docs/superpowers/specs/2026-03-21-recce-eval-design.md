# Recce Eval Skill Design

**Date**: 2026-03-21
**Location**: `plugins/recce-dev/skills/recce-eval/`
**Purpose**: Evaluate the Recce Review Agent's effectiveness by comparing headless Claude Code runs with and without the Recce plugin, using deterministic scoring and LLM-as-judge.

## Context

The Recce plugin provides MCP tools (lineage diff, row count diff, query diff) that help Claude Code validate dbt pipeline changes. Without these tools, Claude relies on code reading and assumptions — leading to false positives (claiming unaffected models are impacted) and missed issues.

This eval skill measures the delta. It runs the same prompt through Claude Code twice — once without the plugin (baseline) and once with it — then scores both runs against a known ground truth.

### Source Material

- [Evaluation PoC of Native Agentic Data Review](https://www.notion.so/infuseai/31e79451d35780a39825d44ca15f1120) — plugin architecture and eval framework
- [E2E Test Scenario: Accounting Pipeline Fix & Enhancement](https://www.notion.so/infuseai/32979451d35781338042f7fc18ab5ace) — test scenarios, prompts, ground truth, scoring scripts
- Test data: [DataRecce/jaffle_shop_golden](https://github.com/DataRecce/jaffle_shop_golden) `poc/jaffle-shop-simulator` branch (~100K orders, ~10K customers, ~115K payments)

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Execution model | Hybrid: `claude -p` headless + in-session scoring | Headless for isolated eval runs; session for orchestration and reporting |
| Plugin control | `--plugin-dir` flag on `claude -p` | Baseline omits flag (no plugin); with-plugin passes recce plugin path |
| Scope | Pluggable multi-chapter via scenario YAML | Start with Chapter 1; add scenarios without changing skill logic |
| Adapter support | DuckDB + Snowflake | Both are production targets; adapter detected from profiles.yml |
| MCP lifecycle | Eval skill pre-starts server before `claude -p` | Avoids timing race between SSE connection and SessionStart hook in headless mode |
| Scoring | Deterministic (jq) + LLM-as-judge (subagent) | Deterministic for answer correctness; LLM judge for reasoning quality |
| LLM judge | Dispatched subagent | Isolated context; receives both variants for direct comparison |
| Reports | Per-run JSON + aggregated markdown report | Raw data preserved; report is a derived view |
| Trigger | Subcommands (`run`, `score`, `report`, `list`, `history`) | Supports iterative development and full-suite runs |

## File Structure

```
plugins/recce-dev/skills/recce-eval/
  SKILL.md                          # Skill definition + subcommand routing
  scenarios/
    ch1-null-amounts.yaml           # Case A: broken state (NULL amounts)
    ch1-healthy-audit.yaml          # Case B: clean state (no problem)
  patches/
    ch1-add-coalesce.patch          # Reverse-apply to create broken state
  scripts/
    run-case.sh                     # Atomic: setup → claude -p → teardown → JSON
    score-deterministic.sh          # jq scoring against ground truth
    start-eval-mcp.sh              # Start MCP server for eval
    stop-eval-mcp.sh               # Stop eval MCP server
  agents/
    eval-judge.md                   # LLM-as-judge subagent
  references/
    scoring-rubric.md               # Deterministic rules + LLM judge criteria
    report-template.md              # Report structure guide
```

## Headless Invocation

The `claude -p` command template for each variant:

**Baseline (no plugin):**
```bash
claude -p "$(cat "$PROMPT_FILE")" \
  --output-format json \
  --dangerously-skip-permissions \
  --max-budget-usd "$BUDGET" \
  > "$OUTPUT_FILE" 2>"$ERROR_FILE"
```

**With plugin:**
```bash
claude -p "$(cat "$PROMPT_FILE")" \
  --output-format json \
  --dangerously-skip-permissions \
  --max-budget-usd "$BUDGET" \
  --plugin-dir "$PLUGIN_DIR" \
  --mcp-config "$EVAL_MCP_CONFIG" \
  > "$OUTPUT_FILE" 2>"$ERROR_FILE"
```

Key flags:
- **`--dangerously-skip-permissions`**: Headless agent must run `dbt`, edit files, and execute SQL without permission prompts. Eval runs in a controlled dbt project — this is acceptable.
- **`--max-budget-usd`**: Replaces the non-existent `--max-turns`. Default: `5.00` per run. Configurable in scenario YAML.
- **`--plugin-dir`**: Points to the recce plugin directory. Loads skills, hooks, agents, and `.mcp.json`.
- **`--mcp-config`**: Passes a temporary MCP config JSON that connects to the eval MCP server. This ensures the headless session connects to the correct port, even if the plugin's `.mcp.json` declares a different default.

### MCP Config for Eval

`run-case.sh` generates a temporary MCP config file before invoking `claude -p`:

```json
{
  "mcpServers": {
    "recce": {
      "type": "sse",
      "url": "http://localhost:{eval_port}/sse"
    }
  }
}
```

This is passed via `--mcp-config /tmp/recce-eval-mcp-config.json`. Combined with `--plugin-dir`, the headless session gets:
- Skills, hooks, agents from the plugin directory
- MCP connection to the eval-specific port (overriding the plugin's `.mcp.json` default)
- `recce-docs` MCP server from the plugin's `.mcp.json` (stdio, no port conflict)

**Assumption**: When both `--plugin-dir` and `--mcp-config` define a server with the same key (`"recce"`), `--mcp-config` takes precedence. This must be validated during implementation. If the CLI merges in the other direction (plugin wins), use `--strict-mcp-config` to force only `--mcp-config` servers, and add `recce-docs` to the eval config explicitly.

### `claude -p --output-format json` Response Structure

The headless output is a single JSON object:

```json
{
  "result": "... full text response including fenced JSON block ...",
  "usage": {
    "input_tokens": 45000,
    "output_tokens": 3200
  },
  "num_turns": 12,
  "total_cost_usd": 1.23,
  "duration_ms": 180000,
  "session_id": "..."
}
```

Extraction logic in `run-case.sh`:
- **Agent's structured JSON**: Parse from `.result` using regex to find the fenced ` ```json ... ``` ` block
- **Performance metrics**: Map `.usage.input_tokens`, `.usage.output_tokens`, `.num_turns`, `.total_cost_usd`, `.duration_ms` directly
- **Tool call count**: Not directly available in `json` output format. Marked as `null` in per-run JSON. If needed in the future, use `--output-format stream-json` and count `tool_use` events.

## Scenario Format

Each scenario is a standalone YAML file describing setup, prompt, ground truth, and teardown.

### Template Variables

| Variable | DuckDB | Snowflake |
|----------|--------|-----------|
| `{target}` | `dev-local` | `dev` |
| `{adapter_description}` | `DuckDB (local file database, target: dev-local)` | `Snowflake (cloud data warehouse, target: dev)` |

### Case A: problem_exists

```yaml
id: ch1-null-amounts
name: "Chapter 1: NULL Amount Orders"
description: "Find and fix NULL amount orders caused by LEFT JOIN without COALESCE"
chapter: 1
case_type: problem_exists   # problem_exists | no_problem

setup:
  strategy: git_patch       # git_patch | git_checkout | script
  patch_reverse_file: patches/ch1-add-coalesce.patch
  dbt_commands:
    - "dbt run --target {target}"

prompt: |
  You are a new accounting hire at Jaffle Shop. The dbt pipeline runs on
  {adapter_description}. Your job is to audit the data pipeline for
  financial reporting accuracy.

  1. Run the pipeline: dbt run --target {target}
  2. Run the tests: dbt test --target {target}
  3. Investigate any test failures
  4. Fix the root cause
  5. Re-run and confirm all tests pass
  6. Report your findings.

  At the end of your response, output a fenced JSON block with exactly these keys:
    "issue_found": true or false,
    "root_cause": "description of the root cause",
    "fix_applied": "description of the fix",
    "impacted_models": ["list", "of", "impacted", "models"],
    "not_impacted_models": ["list", "of", "models", "not", "impacted"],
    "affected_row_count": number,
    "all_tests_pass": true or false

headless:
  max_budget_usd: 5.00
  output_format: json

ground_truth:
  issue_found: true
  root_cause_keywords: ["null", "left join", "coalesce"]
  impacted_models: ["orders", "orders_daily_summary"]
  not_impacted_models: ["customers", "customer_segments", "customer_order_pattern"]
  affected_row_count: 1584
  all_tests_pass: true

judge_criteria:
  - "Agent correctly traces the causal chain: LEFT JOIN → missing payments → NULL amounts"
  - "Agent does NOT claim models that read from stg_orders/stg_payments (not orders) are impacted"
  - "Fix is minimal and correct (coalesce, not INNER JOIN or WHERE filter)"

teardown:
  restore_files: ["models/orders.sql"]
```

**Note on `affected_row_count`**: The value 1584 is derived from the test data in the `poc/jaffle-shop-simulator` branch and is adapter-independent (same CSV seeds loaded into both DuckDB and Snowflake). If seed data changes, update this value accordingly.

**Note on teardown**: No `dbt_commands` in teardown. The next run's setup phase handles `dbt run` after creating its state. This avoids a redundant rebuild between interleaved runs.

### Case B: no_problem

```yaml
id: ch1-healthy-audit
name: "Chapter 1: Healthy Month Audit"
description: "Audit October 2025 orders — no issues should be found"
chapter: 1
case_type: no_problem

setup:
  strategy: none             # No state change needed — pipeline is already fixed
  dbt_commands: []

prompt: |
  You are a new accounting hire at Jaffle Shop. The dbt pipeline runs on
  {adapter_description}. The pipeline has already been fixed and all tests pass.

  Please audit October 2025 orders specifically:
  1. Check row counts for October orders
  2. Check for NULL or zero amounts
  3. Check payment method distribution
  4. Check order status distribution
  5. Report: Are there any data quality issues in October 2025?

  At the end of your response, output a fenced JSON block with exactly these keys:
    "issue_found": true or false,
    "issues": ["list of issues found, or empty array"],
    "evidence": "summary of evidence checked",
    "conclusion": "no_issues or description of issues"

headless:
  max_budget_usd: 3.00
  output_format: json

ground_truth:
  issue_found: false
  false_positive_keywords: ["bug", "broken", "incorrect", "wrong", "missing data"]

judge_criteria:
  - "Agent does NOT hallucinate problems that don't exist"
  - "Agent provides concrete evidence for its 'no issues' conclusion (checked row counts, NULLs, distributions)"
  - "Agent's tone is appropriately confident, not hedging with vague concerns"

teardown:
  restore_files: []
```

## Skill Interface

### Subcommands

| Command | Description |
|---------|-------------|
| `run --case <id>` | Run one scenario (both variants, 1 run each) |
| `run --case <id> -n N` | Run one scenario N times per variant |
| `run --all` | Run all scenarios (1 run each) |
| `run --all -n N` | Run all scenarios N times each |
| `score <run-dir>` | Re-score existing runs (deterministic + LLM judge) |
| `report` | Generate report from latest eval batch |
| `report <eval-id>` | Generate report from specific batch |
| `list` | List available scenarios |
| `history` | Show historical eval results |

### Shared Flags

| Flag | Description | Default |
|------|-------------|---------|
| `--target` | dbt target name | `dev-local` |
| `--adapter` | Override adapter detection | Auto-detect from profiles.yml |
| `--plugin-dir` | Recce plugin path | Auto-resolve via `resolve-recce-root.sh` |
| `--model` | Claude model for headless runs | Inherits from current session |

### Trigger Keywords

```
"run eval", "recce eval", "evaluate plugin", "benchmark recce",
"compare with plugin", "compare without plugin", "eval case",
"score eval", "eval report", "eval history"
```

## Script Architecture

### `run-case.sh`

Atomic operation: create state → invoke `claude -p` → capture output → teardown → write per-run JSON.

```bash
bash run-case.sh \
  --id ch1-null-amounts \
  --case-type problem_exists \
  --variant baseline|with-plugin \
  --prompt-file /tmp/prompt.txt \
  --setup-strategy git_patch \
  --patch-file patches/ch1-add-coalesce.patch \
  --restore-files "models/orders.sql" \
  --target dev-local \
  --max-budget-usd 5.00 \
  --output-dir .claude/recce-eval/runs/<timestamp>/ch1-null-amounts \
  [--plugin-dir /path/to/recce/plugin] \
  [--mcp-config /tmp/recce-eval-mcp-config.json]
```

Internal flow:
1. **Setup**: Apply patch (reverse) or checkout ref to create broken/clean state
2. **dbt rebuild**: `dbt run --target <target>` after state change (skipped if `setup.strategy: none`)
3. **Invoke headless Claude**: Assemble `claude -p` command with appropriate flags per variant
4. **Capture**: Save raw JSON output, extract structured JSON block from `.result`, map performance metrics
5. **Teardown**: `git checkout -- <files>` (skipped if `restore_files` is empty)
6. **Write**: Per-run JSON to output dir

Teardown executes regardless of `claude -p` success or failure (trap-based).

**Working directory**: `run-case.sh` must execute from the dbt project root (`$PWD` is the dbt project). The skill ensures this before invoking the script.

### `score-deterministic.sh`

Reads per-run JSON + ground truth, runs jq comparisons, writes scores back into the JSON.

**`problem_exists` checks**: issue_found, root_cause keywords, impacted models (true positives), not-impacted models (false positive check), affected_row_count, all_tests_pass.

**`no_problem` checks**: issue_found == false, issues array empty, no false positive keywords in response.

### `start-eval-mcp.sh` / `stop-eval-mcp.sh`

Wrappers around recce plugin's `start-mcp.sh` / `stop-mcp.sh`.

**Port isolation**: Sets `RECCE_MCP_PORT` env var before delegating to `start-mcp.sh`. Default eval port: `8085`.

**PID isolation**: Sets a custom `PROJECT_HASH` suffix (appends `-eval`) to prevent collision with a user's active MCP server on the same project. The PID file becomes `/tmp/recce-mcp-{hash}-eval.pid` instead of `/tmp/recce-mcp-{hash}.pid`.

**Prerequisite**: No MCP server already running on the eval port. The script checks port availability and fails with a clear error if occupied.

```bash
# start-eval-mcp.sh internals:
# Does NOT delegate to start-mcp.sh — manages its own PID file
# because start-mcp.sh has no PID suffix support.
EVAL_PORT="${RECCE_EVAL_MCP_PORT:-8085}"
EVAL_HASH=$(printf '%s-eval' "$PWD" | md5 2>/dev/null | cut -c1-8 \
  || printf '%s-eval' "$PWD" | md5sum | cut -c1-8)
PID_FILE="/tmp/recce-mcp-${EVAL_HASH}.pid"
LOG_FILE="/tmp/recce-mcp-${EVAL_HASH}.log"

# Port check, start server, write PID, health poll — same logic as
# start-mcp.sh but with eval-specific PID/port namespace.
```

**Implementation note**: `start-eval-mcp.sh` copies the server lifecycle logic from `start-mcp.sh` (port check → nohup start → health poll) rather than delegating, because `start-mcp.sh` computes its own `PROJECT_HASH` from `$PWD` with no suffix support. This avoids modifying the recce plugin's script for eval-only needs.

## Agent: `eval-judge.md`

LLM-as-judge subagent. Receives both baseline and with-plugin runs for the same scenario, along with ground truth and judge criteria. Scores five dimensions (1-5 each):

| Dimension | What it measures |
|-----------|------------------|
| Reasoning Chain | Did the agent trace the actual causal path? |
| Evidence Quality | Did the agent cite specific data (row counts, query results)? |
| Fix Quality | Is the fix minimal and correct? (problem_exists only, N/A for no_problem) |
| False Positive Discipline | Did the agent avoid claiming unaffected models? |
| Completeness | Did the agent address all prompt steps? |

Returns structured JSON with per-dimension scores + rationale, overall score, notable observations, and comparison notes (when both variants are provided).

The judge receives both variants together so it can produce meaningful `comparison_notes` about the difference in approach, not just isolated scores.

## Storage Layout

```
<dbt-project>/.claude/recce-eval/
  runs/
    <timestamp>/                      # eval batch
      meta.json                       # batch metadata (adapter, versions, config)
      ch1-null-amounts/
        baseline_run1.json
        with-plugin_run1.json
      ch1-healthy-audit/
        baseline_run1.json
        with-plugin_run1.json
      report.md                       # aggregated comparison report
    latest/                           # symlink to most recent batch
  history.json                        # append-only summary of all batches
```

**`latest/` is a symlink** (not a copy) pointing to the most recent batch directory. Avoids duplicating potentially large raw response data.

### `meta.json`

```json
{
  "eval_id": "20260320-1430",
  "timestamp": "2026-03-20T14:30:00Z",
  "target": "dev-local",
  "adapter": "duckdb",
  "scenarios_run": ["ch1-null-amounts", "ch1-healthy-audit"],
  "runs_per_scenario": 3,
  "plugin_dir": "/path/to/plugins/recce",
  "recce_version": "1.40.0.dev0",
  "claude_model": "claude-sonnet-4-5-20250514",
  "max_budget_usd_per_run": 5.00
}
```

### `history.json`

```json
[
  {
    "eval_id": "20260320-1430",
    "timestamp": "2026-03-20T14:30:00Z",
    "adapter": "duckdb",
    "claude_model": "claude-sonnet-4-5-20250514",
    "summary": {
      "ch1-null-amounts": {
        "baseline": { "det_pass_rate": 0.75, "judge_avg": 3.2 },
        "with-plugin": { "det_pass_rate": 1.0, "judge_avg": 4.6 }
      }
    }
  }
]
```

### Per-Run JSON Structure

```json
{
  "meta": {
    "scenario_id": "ch1-null-amounts",
    "variant": "with-plugin",
    "run_number": 1,
    "timestamp": "2026-03-20T14:30:00Z",
    "target": "dev-local",
    "adapter": "duckdb"
  },
  "performance": {
    "duration_ms": 180000,
    "input_tokens": 45000,
    "output_tokens": 3200,
    "total_cost_usd": 1.23,
    "num_turns": 12,
    "tool_calls": null
  },
  "agent_output": {
    "raw_response": "... full text from .result field ...",
    "structured_json": { "issue_found": true, "...": "..." },
    "json_extracted": true
  },
  "scores": {
    "deterministic": {
      "checks": [
        { "name": "issue_found", "expected": true, "actual": true, "result": "PASS" }
      ],
      "pass_count": 7,
      "fail_count": 1,
      "total": 8,
      "pass_rate": 0.875
    },
    "llm_judge": {
      "reasoning_chain": { "score": 4, "rationale": "..." },
      "evidence_quality": { "score": 5, "rationale": "..." },
      "fix_quality": { "score": 4, "rationale": "..." },
      "false_positive_discipline": { "score": 3, "rationale": "..." },
      "completeness": { "score": 5, "rationale": "..." },
      "overall_score": 4.2,
      "notable_observations": ["..."],
      "comparison_notes": "..."
    }
  }
}
```

**`performance.tool_calls`**: Always `null` in v1. The `--output-format json` response does not include tool call counts. A future version can use `--output-format stream-json` and count `tool_use` events if this metric proves important.

## End-to-End Flow (`run --case ch1-null-amounts -n 2`)

```
1.  Skill reads scenarios/ch1-null-amounts.yaml
2.  Detects adapter from profiles.yml (or uses --target flag)
3.  Resolves recce plugin dir via resolve-recce-root.sh
4.  Creates batch dir: .claude/recce-eval/runs/<timestamp>/
5.  Substitutes template variables in prompt, writes to temp file
6.  Starts eval MCP server: bash start-eval-mcp.sh
7.  Generates eval MCP config JSON (pointing to eval port)

    ── Loop: interleaved runs (baseline→plugin→baseline→plugin) ──

8.  bash run-case.sh --variant baseline    (run 1) → baseline_run1.json
9.  bash score-deterministic.sh            → scores.deterministic
10. bash run-case.sh --variant with-plugin (run 1) → with-plugin_run1.json
11. bash score-deterministic.sh            → scores.deterministic
12. bash run-case.sh --variant baseline    (run 2) → baseline_run2.json
13. bash score-deterministic.sh            → scores.deterministic
14. bash run-case.sh --variant with-plugin (run 2) → with-plugin_run2.json
15. bash score-deterministic.sh            → scores.deterministic

16. Stop eval MCP server: bash stop-eval-mcp.sh
17. Dispatch eval-judge subagent (all 4 run JSONs + ground truth + criteria)
18. Merge judge scores into per-run JSONs
19. Read history.json for previous eval comparison
20. Generate report.md
21. Update latest/ symlink, append to history.json
22. Print summary to user
```

Runs are interleaved (baseline→plugin→baseline→plugin) rather than grouped — this reduces systematic bias from cache warming or temporal effects.

## Error Handling

| Failure | Handling |
|---------|----------|
| Setup fails (patch won't apply) | Log error, skip run, continue |
| `claude -p` exceeds budget | Partial output saved, `json_extracted` may be false |
| `claude -p` crashes | Save stderr, mark run as failed |
| No structured JSON in output | Deterministic scoring all FAIL; LLM judge still scores |
| MCP server won't start | Skip all with-plugin runs, run baseline only, flag in report |
| Eval port occupied | Fail fast with clear error before any runs |
| Judge subagent fails | Report contains only deterministic scores, flagged |

## Prerequisites

Before running eval:
1. **dbt project with data loaded** — seeds populated, `dbt run` succeeds on the target
2. **Recce installed** — `recce` CLI in PATH (for MCP server)
3. **`target-base/` artifacts exist** — `dbt docs generate --target-path target-base` on the base branch
4. **No other Recce MCP server on eval port** — default 8085 (configurable via `RECCE_EVAL_MCP_PORT`)
5. **Claude Code CLI installed** — `claude` in PATH
6. **Sufficient API budget** — each run costs ~$1-5 depending on scenario complexity

## Relationship to Existing Skills

| Skill | Purpose | Overlap |
|-------|---------|---------|
| `mcp-e2e-validate` | Validates plugin event chain (hooks fire, MCP responds) | Tests the plugin *mechanism*; eval tests the plugin *value* |
| `recce-eval` (this) | Measures plugin impact on agent accuracy/efficiency | Complementary — e2e-validate confirms plumbing works, eval confirms it helps |

Both live in recce-dev. A natural workflow: run `mcp-e2e-validate` first to confirm the plugin works, then `recce-eval` to measure how much it helps.
