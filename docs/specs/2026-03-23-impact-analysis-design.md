# impact_analysis MCP Tool — Design Spec

**Date**: 2026-03-23
**Author**: Kent + Claude
**Status**: Draft
**Target**: `recce/mcp_server.py` (Recce MCP Server)

## Problem

Agents using Recce MCP tools to assess model impact make frequent errors:
- **False positives**: reporting sibling models as impacted (ch3-join-shift: 9/12 → 3 FPs)
- **Under-reporting**: finding root cause but missing downstream impact (ch3-phantom-filter)
- **Stochastic noise**: different runs produce different results because agents chain 4+ tool calls with prompt-driven reasoning

The current workflow requires agents to call `lineage_diff` → `schema_diff` → `row_count_diff` → `profile_diff` sequentially, interpreting each result and deciding next steps. This is error-prone regardless of prompt quality — both the Claude Code plugin's reviewer agent and the Recce Cloud PR analyzer's haiku-based subagent suffer from the same issues.

## Solution

A single MCP tool that surfaces impact signals for agent investigation. Not a replacement for other tools — a discovery tool that tells agents where to look, so they can follow up with `profile_diff`, `query_diff`, etc. until confident.

## Design Principles

1. **Every field is grounded in data** — no arbitrary thresholds, no heuristic judgments, no AI-generated narratives
2. **No semantic ambiguity** — field names mean exactly one thing regardless of context
3. **Discovery, not diagnosis** — surfaces signals and anomalies; agents investigate further with other tools
4. **Null means "unknown, go investigate"** — not "no impact"

## Input Schema

```json
{
  "type": "object",
  "properties": {
    "select": {
      "type": "string",
      "description": "dbt selector syntax. Default: 'state:modified+' (all modified models and downstream)"
    },
    "skip_value_diff": {
      "type": "boolean",
      "description": "Skip row-level value comparison on modified models. Default: false"
    }
  }
}
```

Most callers pass no arguments — `state:modified+` covers 95% of use cases.

## Internal Workflow

```
Step 1: lineage_diff(select)
  → nodes with change_status, impacted, materialized
  → classify: which are modified, which are downstream, which are not impacted

Step 2: row_count_diff + schema_diff (all impacted non-view models)
  → skip materialized="view" (expensive full-table scan)
  → skip change_status="removed" (table doesn't exist in current)

Step 3: value_diff (modified non-view models only, unless skip_value_diff=true)
  → detect PK: dbt unique_key (incremental config) → unique test columns
  → PK available: PK Join query → per-column rows_changed + base_mean/current_mean
  → PK not available: value_diff = null (no EXCEPT fallback — ambiguous semantics)
  → skip materialized="view"

Step 4: suggested_deep_dives (deterministic rules on Step 2-3 results)
  → R1: rows_changed high + row_count stable → suggest profile_diff on changed columns
  → R2: row_count delta > 5% (either direction) → suggest profile_diff on model
  → R3: schema_changes non-empty → suggest profile_diff on changed columns
  → R4: value_diff null (view, no PK, error) → suggest profile_diff as fallback

Error handling: individual model query failures are captured in errors[], never abort the whole analysis.
```

## Output Schema

```json
{
  "impacted_models": [
    {
      "name": "orders",
      "change_status": "modified",
      "materialized": "table",
      "row_count": { "base": 100463, "current": 100463, "delta": 0, "delta_pct": 0.0 },
      "schema_changes": [],
      "value_diff": {
        "rows_changed": 97221,
        "rows_added": 0,
        "rows_removed": 0,
        "columns": {
          "amount": { "rows_changed": 97221, "base_mean": 26.16, "current_mean": 25.98 }
        }
      }
    },
    {
      "name": "orders_daily_summary",
      "change_status": null,
      "materialized": "incremental",
      "row_count": { "base": 334, "current": 334, "delta": 0, "delta_pct": 0.0 },
      "schema_changes": [],
      "value_diff": null
    }
  ],
  "not_impacted_models": ["customers", "customer_segments", "customer_order_pattern",
                           "stg_orders", "stg_payments", "stg_customers"],
  "suggested_deep_dives": [
    { "model": "orders", "tool": "profile_diff", "columns": ["amount"] }
  ],
  "errors": []
}
```

### Field Reference

**Top-level:**

| Field | Source | Nullable | Description |
|-------|--------|----------|-------------|
| `impacted_models` | lineage_diff DAG traversal | No (may be empty array) | Models that are modified or downstream of modified |
| `not_impacted_models` | lineage_diff DAG traversal | No (may be empty array) | Models confirmed NOT in impact path |
| `suggested_deep_dives` | Deterministic rules R1-R4 | No (may be empty array) | Models worth investigating further |
| `errors` | Runtime error collection | No (may be empty array) | Non-fatal errors encountered during analysis |

**Per impacted model:**

| Field | Source | Nullable | Description |
|-------|--------|----------|-------------|
| `name` | lineage_diff node name | No | dbt model name |
| `change_status` | lineage_diff `change_status` | Yes | "modified", "added", "removed", or null (downstream) |
| `materialized` | lineage_diff node config | No | "table", "view", "incremental" |
| `row_count` | `row_count_diff` tool | Yes (null for views) | Row counts from database |
| `row_count.base` | row_count_diff | Yes (null for added models) | Base environment row count |
| `row_count.current` | row_count_diff | No (within row_count) | Current environment row count |
| `row_count.delta` | `current - base` | Yes (null if base is null) | Absolute difference |
| `row_count.delta_pct` | `delta / base * 100` | Yes (null if base is null or 0) | Percentage difference |
| `schema_changes` | `schema_diff` tool | No (may be empty array) | Column additions, removals, type changes |
| `value_diff` | PK Join SQL query | Yes | null when: view, downstream, no PK, error, or skip_value_diff |
| `value_diff.rows_changed` | PK Join COUNT | No (within value_diff) | Rows present in both envs with at least one column value different |
| `value_diff.rows_added` | PK Join COUNT | No (within value_diff) | Rows in current but not in base (by PK) |
| `value_diff.rows_removed` | PK Join COUNT | No (within value_diff) | Rows in base but not in current (by PK) |
| `value_diff.columns` | PK Join per-column COUNT | No (within value_diff) | Per-column change counts |
| `value_diff.columns[].rows_changed` | PK Join COUNT | No | Rows where this column's value differs |
| `value_diff.columns[].base_mean` | SQL AVG on base | Yes (null for non-numeric) | Mean value in base environment |
| `value_diff.columns[].current_mean` | SQL AVG on current | Yes (null for non-numeric) | Mean value in current environment |

**Per suggested_deep_dive:**

| Field | Source | Nullable | Description |
|-------|--------|----------|-------------|
| `model` | Triggered model name | No | Which model to investigate |
| `tool` | Always "profile_diff" | No | Which tool to use |
| `columns` | Top changed columns from value_diff | Yes | Specific columns to profile (null = whole model) |

### Null Semantics

`null` consistently means "unknown — investigate further":
- `row_count: null` → view model, not queried (expensive)
- `value_diff: null` → no comparison available (view, downstream, no PK, or error)
- `base_mean: null` → non-numeric column
- `row_count.delta: null` → added model (no base to compare)
- `columns: null` in suggested_deep_dives → profile the whole model

## Tool Description

```
Discover the impact of dbt model changes. Returns which models are
modified or downstream-impacted, with row count and value-level signals
for non-view models.

This is a starting point for investigation, not a complete analysis.
Use the results to identify anomalies, then follow up with profile_diff,
query_diff, or other tools until you have confidence in the root cause.

Models with value_diff: null have unknown data impact — use
suggested_deep_dives or call profile_diff/query_diff to investigate.
```

## What This Tool Does NOT Do

- **No risk scoring** — no arbitrary HIGH/MEDIUM/LOW thresholds. Agents interpret signals.
- **No narrative generation** — no reason strings or risk explanations. Agents write their own.
- **No EXCEPT fallback** — without PK, value_diff semantics are ambiguous. Returns null instead.
- **No DAG rendering** — no Mermaid diagrams. Use `lineage_diff` for graph edges.
- **No check persistence** — no create_check. Agents call it separately after analysis.
- **No profile_diff** — deep statistical profiling is a separate tool, suggested via `suggested_deep_dives`.

## PK Detection

Primary key detection for value_diff PK Join, in priority order:

1. **`unique_key` in model config** (incremental models) — from manifest.json
2. **`unique` test on column(s)** — from manifest.json test definitions
3. **No PK found** → `value_diff: null`, R4 triggers suggested_deep_dive

## Suggested Deep Dives Rules

All rules are deterministic, computed from analysis results. Internal to the server — rule IDs (R1-R4) do not appear in output.

| Rule | Trigger Condition | Columns |
|------|-------------------|---------|
| R1 | value_diff.rows_changed high + abs(row_count.delta_pct) < 5% | Top changed columns from value_diff |
| R2 | abs(row_count.delta_pct) > 5% | null (whole model) |
| R3 | schema_changes non-empty | Changed columns |
| R4 | value_diff is null on modified model | null (whole model) |

R1's "high" threshold is internal implementation (e.g., rows_changed / matched_rows > 0.2). Not exposed in output.

## Validation Against Scenarios

### ch3-join-shift (join key bug in orders.sql)

- `impacted_models`: orders (modified, value_diff: 97221 rows_changed), orders_daily_summary (downstream, null)
- `not_impacted_models`: customers, customer_segments, customer_order_pattern, stg_* — **deterministic, 0 false positives**
- `suggested_deep_dives`: profile_diff on orders.amount (R1)
- Agent flow: reads value_diff → "97221 rows changed, avg shifted" → reads code → finds join key bug

### ch3-phantom-filter (WHERE amount > 0 in stg_payments)

- `impacted_models`: stg_payments (modified, view → row_count=null, value_diff=null), orders/customers/etc (downstream, shallow)
- `suggested_deep_dives`: profile_diff on stg_payments (R4: value_diff null)
- Agent flow: sees "stg_payments data unknown" → calls profile_diff → discovers min(amount) changed from 0 to >0 → reads code → finds WHERE filter

### ch3-count-distinct (count(*) → count(distinct customer_id))

- `impacted_models`: orders_daily_summary (modified, value_diff: 253 rows_changed, order_count avg 300→184)
- `not_impacted_models`: all other models — **deterministic**
- `suggested_deep_dives`: profile_diff on orders_daily_summary.order_count (R1)
- Agent flow: reads value_diff → "order_count avg dropped 300→184" → reads code → finds count(*) changed to count(distinct)

## Consumers

| Consumer | Before | After |
|----------|--------|-------|
| Claude Code plugin (recce-reviewer) | 4 tool calls + prompt reasoning | 1 impact_analysis + follow-up as needed |
| Recce Cloud (pr_analyzer subagent) | 245-line prompt orchestrating 5 tools | 1 impact_analysis + profile_diff + create_check |
| Any MCP agent | Must learn tool chaining from docs | 1 tool call with self-documenting output |

## Implementation Phases

**Phase 1 — Core (lineage + row_count + schema + suggested_deep_dives)**
- No value_diff yet — uses aggregate comparison from existing row_count_diff
- Already solves false positive / under-reporting (deterministic impact list)
- Estimated: ~150 lines Python

**Phase 2 — Value diff (PK detection + PK Join queries)**
- PK detection from manifest.json
- Per-column rows_changed + base_mean/current_mean
- Estimated: ~100 lines Python

**Phase 3 — Consumer migration**
- Claude Code plugin: simplify recce-reviewer to use impact_analysis
- Recce Cloud: simplify recce-analysis subagent prompt
- Eval: verify score improvement

## Related Work

- **DRC-3068** (merged): lineage_diff tool description — added `impacted` column guidance
- **Next**: `render_lineage_dag` tool design (Mermaid DAG generation server-side)
