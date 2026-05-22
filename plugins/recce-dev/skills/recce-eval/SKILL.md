---
name: recce-eval
description: >
  Use when the user asks to "run eval", "recce eval", "evaluate plugin",
  "benchmark recce", "compare with plugin", "compare without plugin",
  "eval case", "score eval", "eval report", "eval history", "list eval scenarios",
  "list eval cases", "show eval history", "run eval case",
  or wants to measure the Recce Review Agent's effectiveness
  compared to pure Claude Code without the plugin.
argument-hint: "[run|score|report|list|history] [--case <id>] [--all] [-n N] [--version v1|v2]"
version: 0.2.0
---

# /recce-eval — Evaluate Recce Plugin Effectiveness

Measure the Recce Review Agent's impact by running headless Claude Code sessions with and without the Recce plugin, then scoring results against known ground truth.

**Relationship to mcp-e2e-validate:** `mcp-e2e-validate` tests whether the plugin *mechanism* works (hooks fire, MCP responds). This skill tests whether the plugin provides *value* (accuracy, false positives). Run `mcp-e2e-validate` first, then `recce-eval`.

---

## Dependencies

- **yq**, **jq** — `brew install yq jq`
- **git** (v2 only — for clone/checkout)
- **Python 3** with venv + pip (v2 only — for `setup-v2-project.sh`)
- **recce** CLI in PATH (for MCP server)
- **claude** CLI in PATH (v2.x with `--plugin-dir`, `--mcp-config`, `--max-budget-usd` support)

## Setup

Read learned patterns and operational notes before starting:

```
Read → ${CLAUDE_PLUGIN_ROOT}/reference/learned-patterns.md
Read → ${CLAUDE_PLUGIN_ROOT}/skills/recce-eval/references/operational-notes.md
```

## Prerequisites

1. dbt project with data loaded — `dbt run` succeeds on the target
2. `target-base/` artifacts exist — `dbt docs generate --target-path target-base` on the base branch
3. Sufficient API budget — each run costs ~$1-5 depending on scenario complexity

---

## Subcommand Routing

Parse user input to determine flow:

| Subcommand | Action |
|-----------|--------|
| `run --case <id>[,<id2>...] [-n N]` | Run Flow (specific scenarios) |
| `run --all [-n N]` | Run Flow (all scenarios) |
| `run --select [-n N]` | Select Flow → Run Flow |
| `score <run-dir>` | Score Flow |
| `report [eval-id]` | Report Flow |
| `list` | List Flow (short-circuit) |
| `history` | History Flow (short-circuit) |

### Shared flags

| Flag | Description | Default |
|------|-------------|---------|
| `--version` | `v1` or `v2` | `v2` |
| `--target` | dbt target name | `dev-local` (v1), `dev` (v2) |
| `--adapter` | Override adapter detection | Auto-detect from profiles.yml |
| `--plugin-dir` | Recce plugin path | Auto-resolve via `resolve-recce-root.sh` |
| `--model` | Claude model for headless runs | Inherits from session |
| `--no-bare` | Disable bare mode (use OAuth, no API key) | `--bare` is default |

### List Flow (short-circuit)

```bash
bash ${CLAUDE_PLUGIN_ROOT}/skills/recce-eval/scripts/list-scenarios.sh --version <v1|v2>
```
Display as table: `| ID | Name | Case Type | Difficulty |`. **STOP** — do not proceed to Run Flow.

### History Flow (short-circuit)

```bash
cat .claude/recce-eval/history.json 2>/dev/null || echo "NO_HISTORY"
```
- Missing → "No eval history found. Run `/recce-eval run` first."
- Present → parse JSON array, display as table with Eval ID / Timestamp / Adapter / Scenario / Baseline Det / Plugin Det / Baseline Judge / Plugin Judge. **STOP**.

### Select Flow

When `--select` is used:
1. Load scenarios via `list-scenarios.sh` (same as List Flow).
2. Use `AskUserQuestion` with `multiSelect: true` — `label` = scenario ID, `description` = name + difficulty.
3. Proceed to Run Flow with `CASES` set to the comma-joined selected IDs. If user cancels, **STOP**.

---

## Run Flow

Six steps. Most setup and finalization is encapsulated in helper scripts; the skill orchestrates only the three LLM-driven pieces (judge dispatch, report narrative, user summary).

### Step 1: Prepare Batch

One script call resolves scenarios, clones v2 project (if v2), detects adapter, resolves sibling plugin, creates batch dir, and generates MCP config:

```bash
eval "$(bash ${CLAUDE_PLUGIN_ROOT}/skills/recce-eval/scripts/prepare-batch.sh \
    --version "${VERSION:-v2}" \
    ${CASES:+--cases "$CASES"} \
    ${ALL:+--all} \
    ${TARGET:+--target "$TARGET"} \
    ${PLUGIN_DIR:+--plugin-dir "$PLUGIN_DIR"})"
```

After eval, these vars are set in the caller's shell: `EVAL_ID`, `BATCH_DIR`, `VERSION`, `TARGET`, `ADAPTER`, `ADAPTER_DESC`, `SCENARIO_LIST` (comma-sep absolute paths), `SCENARIO_IDS`, `MCP_CONFIG`, `RECCE_PLUGIN_ROOT`, `LAYOUT`, `PROJECT_DIR` (v2 only), `WORK_DIR` (v2 only).

If Selection Flow provided IDs, set `CASES="$SELECTED_IDS"` before calling. Do not combine `--cases` and `--all`.

### Step 2: Run Eval Batch

```bash
bash ${CLAUDE_PLUGIN_ROOT}/skills/recce-eval/scripts/run-batch.sh \
    --scenarios "$SCENARIO_LIST" \
    --batch-dir "$BATCH_DIR" \
    --eval-id "$EVAL_ID" \
    --skill-dir "${CLAUDE_PLUGIN_ROOT}/skills/recce-eval" \
    --recce-plugin "$RECCE_PLUGIN_ROOT" \
    --target "$TARGET" \
    --adapter-desc "$ADAPTER_DESC" \
    --mcp-config "$MCP_CONFIG" \
    -n "${N:-1}" \
    ${MODEL:+--model "$MODEL"} \
    ${NO_BARE:+--no-bare} \
    ${PROJECT_DIR:+--project-dir "$PROJECT_DIR"}
```

`run-batch.sh` handles: prompt rendering (v1 inline, v2 template+vars via `render-prompt.py`), interleaved run loop (for each run number → for each scenario → baseline → with-plugin), per-run JSON output, deterministic scoring merged into each per-run JSON. Can be executed via Bash tool `run_in_background: true` for long batches.

**Output files** in `$BATCH_DIR`:
- `<scenario-id>/baseline_run<N>.json` — per-run with deterministic scores
- `<scenario-id>/with-plugin_run<N>.json` — per-run with deterministic scores
- `batch-summary.json` — machine-readable batch metadata

### Step 3: Dispatch LLM Judge

For each scenario, dispatch `recce-dev:eval-judge` via the Agent tool and save its JSON output to `$BATCH_DIR/<scenario_id>/judge.json`.

The dispatch prompt must include:
- **Absolute paths** to all per-run JSONs for that scenario (both variants, all run numbers)
- **Ground truth** extracted from the scenario YAML (`yq -o=json '.ground_truth'`)
- **Judge criteria** from the scenario YAML (`yq -r '.judge_criteria[]'`)
- **Case type** (`problem_exists` or `no_problem`)

The agent returns a fenced JSON block with `runs[]` + `comparison_notes`. Extract it and save:

```bash
mkdir -p "$BATCH_DIR/<scenario_id>"
echo '<judge JSON>' > "$BATCH_DIR/<scenario_id>/judge.json"
```

**Parallel dispatch**: Dispatching scenarios sequentially is safe but slow. If multiple scenarios are being judged, prefer parallel Agent dispatches in a single tool-use block (one Agent call per scenario) to reduce wall time.

**Error handling**: If the judge agent fails or returns invalid JSON, skip saving that scenario's judge.json — `finalize-eval.sh` tolerates missing judge files (history entry shows null for that scenario's judge averages).

### Step 4: Finalize Batch

One script call merges judge scores into per-run JSONs, writes `meta.json`, appends `history.json`, and updates the `latest` symlink:

```bash
bash ${CLAUDE_PLUGIN_ROOT}/skills/recce-eval/scripts/finalize-eval.sh \
    --batch-dir "$BATCH_DIR" \
    --eval-id "$EVAL_ID" \
    --adapter "$ADAPTER" \
    --target "$TARGET" \
    --claude-model "${MODEL:-inherited}" \
    --recce-plugin-root "$RECCE_PLUGIN_ROOT" \
    --scenarios "$SCENARIO_IDS" \
    --runs-per-scenario "${N:-1}" \
    --max-budget-usd "${MAX_BUDGET:-5}" \
    --eval-base "$(pwd)"
```

### Step 5: Generate Report

Read all per-run JSONs in `$BATCH_DIR/<scenario_id>/*.json` (now containing both deterministic and judge scores). Read `${CLAUDE_PLUGIN_ROOT}/skills/recce-eval/references/report-template.md` for structure. Generate narrative analysis and write to `$BATCH_DIR/report.md`.

The report should include:
1. **Environment** — target, adapter, versions, budget, isolation mode
2. **Summary table** — per-scenario per-variant metrics (det pass rate, judge avg, cost, turns)
3. **Key Findings** — failure patterns, plugin advantages, false positives avoided
4. **Detailed Scores** — per-run deterministic checks + judge rationale excerpts
5. **Cross-Eval Comparison** — deltas vs. previous runs (read `history.json` for same adapter)

### Step 6: Cleanup + User Summary

**v2 only** — remove temp project dir:

```bash
if [ -n "${WORK_DIR:-}" ] && [[ "$WORK_DIR" == "${TMPDIR:-/tmp}"* ]]; then
    rm -rf "$WORK_DIR"
fi
```

Print to the user:
- Total runs completed
- Per-scenario comparison table (baseline vs with-plugin)
- Path to `$BATCH_DIR/report.md`
- Any warnings (missing judge files, MCP issues)

---

## Score Flow (`score <run-dir>`)

Re-score existing runs without re-running them. Useful after updating scoring logic or ground truth.

1. For each `*_run*.json` in the dir, extract `scenario_id` and `case_type`; look up the scenario YAML under `scenarios/v1/` or `scenarios/v2/`.
2. Re-run `score-deterministic.sh` on each file with the current ground truth.
3. Re-dispatch `eval-judge` per scenario (same as Run Flow Step 3). Save each to `$BATCH_DIR/<scenario_id>/judge.json`.
4. Run `finalize-eval.sh` with the same args as Run Flow Step 4 to merge + update meta/history.
5. Regenerate `report.md` (same as Run Flow Step 5).

---

## Report Flow (`report [eval-id]`)

Regenerate the report from existing scored runs without re-scoring.

1. If no eval-id provided: `EVAL_ID=$(readlink .claude/recce-eval/runs/latest 2>/dev/null)`. If empty, tell user "No eval runs found." and **STOP**.
2. Set `BATCH_DIR=".claude/recce-eval/runs/$EVAL_ID"`.
3. Read all per-run JSONs (must already have `scores.deterministic` and optionally `scores.llm_judge`).
4. Read `references/report-template.md`, generate `report.md`, write to `$BATCH_DIR/report.md`, print to user.

---

## Isolation & Gotchas

`run-case.sh` defaults to `--bare`. With-plugin variant additionally sets `--plugin-dir`, which injects the Recce plugin into the bare profile — hooks fire, MCP tools are available, but no user memory/CLAUDE.md leak into results.

**Top 3 gotchas** (full list in `references/operational-notes.md`):

- **Shell variables don't persist** across Bash tool invocations. `prepare-batch.sh` / `run-batch.sh` / `finalize-eval.sh` each mitigate this per-phase, but the three top-level calls are still three separate shells — re-derive any vars consumed outside those scripts.
- **Always `eval` the script output**: `prepare-batch.sh` emits `printf %q`-escaped KEY=VALUE lines. Use `eval "$(bash ...)"` to import into the caller's shell.
- **Save judge output to `$BATCH_DIR/<scenario_id>/judge.json`** before calling `finalize-eval.sh`. Missing files are tolerated but expected ones must be in place, otherwise history entries show null judge averages.

Full isolation modes table, 18 common mistakes, and MCP transport rationale: see `references/operational-notes.md`.

---

## Additional Resources

### Scripts (`scripts/`)

- **`prepare-batch.sh`** — Pre-run orchestration: scenario resolution, v2 clone, adapter detection, plugin dir, batch dir, MCP config. Outputs `eval`-safe KEY=VALUE lines.
- **`run-batch.sh`** — Batch runner: prompt rendering, interleaved run loop, per-run deterministic scoring. Background-capable.
- **`run-case.sh`** — Atomic single-run: setup state, invoke `claude -p`, capture output, teardown, write per-run JSON. Called by `run-batch.sh`.
- **`finalize-eval.sh`** — Post-run orchestration: judge merge, meta.json, history append, latest symlink.
- **`score-deterministic.sh`** — jq-based scoring against ground truth. Called by `run-batch.sh`.
- **`setup-v2-project.sh`** — Clone + bootstrap a dbt project for v2 scenarios. Called by `prepare-batch.sh`.
- **`list-scenarios.sh`** — Pipe-delimited scenario table. Used by List Flow and Select Flow.
- **`render-prompt.py`** — Template + vars substitution for v2 prompts. Called by `run-batch.sh`.
- **`resolve-recce-root.sh`** (plugin-level, at `${CLAUDE_PLUGIN_ROOT}/scripts/`) — Locate sibling `recce` plugin across monorepo and cache layouts. Called by `prepare-batch.sh`.

### Agents

- **`${CLAUDE_PLUGIN_ROOT}/agents/eval-judge.md`** — LLM judge subagent (sonnet, Read-only). Dispatched as `recce-dev:eval-judge`. Scores 5 dimensions: reasoning chain, evidence quality, fix quality, false positive discipline, completeness.

### References

- **`references/scoring-rubric.md`** — Deterministic scoring rules per case_type + LLM judge dimension definitions.
- **`references/report-template.md`** — Report structure guide with placeholder format and generation rules.
- **`references/operational-notes.md`** — Full isolation modes table, MCP transport rationale, 18 common mistakes.

### Scenarios

Run `/recce-eval list --version v1` or `--version v2` to enumerate available scenarios. v1 lives in `scenarios/v1/` (7 chapter cases), v2 lives in `scenarios/v2/` (10+ data/code cases on jaffle-shop-simulator).

---

## Learning

After completing the main workflow:

1. **Detection**: Any unexpected failure, workaround, or pattern not in learned-patterns.md?
   - Yes → check `${CLAUDE_PLUGIN_ROOT}/reference/learned-patterns.md`, if not covered → append D1 entry
   - No → one question: "What was most unexpected?" → three-question test → capture or done
2. "Nothing novel" is a valid and encouraged outcome.
