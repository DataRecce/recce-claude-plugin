---
commissioned-by: spacedock@0.8.2
entity-type: eval_scenario
entity-label: scenario
entity-label-plural: scenarios
id-style: sequential
stages:
  defaults:
    worktree: false
    concurrency: 2
  states:
    - name: draft
      initial: true
    - name: ground-truth
    - name: eval-run
    - name: validated
      gate: true
      feedback-to: draft
    - name: integrated
      terminal: true
---

# Recce eval scenario pipeline

Design, verify, and validate eval scenarios from jaffle-shop-simulator issues to build a comprehensive benchmark for measuring Recce plugin effectiveness at data PR review.

## File Naming

Each scenario is a markdown file named `{slug}.md` — lowercase, hyphens, no spaces. Example: `exclude-zero-orders-v1.md`.

## Schema

Every scenario file has YAML frontmatter with these fields:

```yaml
---
id:
title: Human-readable name
status: draft
assignee:
source:
started:
completed:
verdict:
score:
worktree:
issue:
pr:
jaffle_issue: GitHub issue number in jaffle-shop-simulator
patch_file: Path to the reverse patch file
scenario_yaml: Path to the scenario YAML definition
prompt_file: Path to the eval prompt file
---
```

### Field Reference

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique identifier, format determined by id-style in README frontmatter |
| `title` | string | Human-readable scenario name |
| `status` | enum | One of: draft, ground-truth, eval-run, validated, integrated |
| `assignee` | string | Who is working on this scenario (GitHub username). Claim by setting + commit/push. |
| `source` | string | Where this scenario came from |
| `started` | ISO 8601 | When active work began |
| `completed` | ISO 8601 | When the scenario reached terminal status |
| `verdict` | enum | PASSED or REJECTED — set at final stage |
| `score` | number | Priority score, 0.0–1.0 (optional) |
| `worktree` | string | Worktree path while a dispatched agent is active, empty otherwise |
| `issue` | string | GitHub issue reference (e.g., `#42` or `owner/repo#42`). Optional cross-reference, set manually. |
| `pr` | string | GitHub PR reference (e.g., `#57` or `owner/repo#57`). Set when a PR is created for this entity's worktree branch. |
| `jaffle_issue` | number | Source issue number in DataRecce/jaffle-shop-simulator |
| `patch_file` | string | Relative path to the reverse patch file |
| `scenario_yaml` | string | Relative path to the scenario YAML definition |
| `prompt_file` | string | Relative path to the eval prompt template |

## Stages

### `draft`

A new scenario has been conceived. The worker designs a subtle, plausible bug variant based on a jaffle-shop-simulator issue, creates the reverse patch, writes the scenario YAML, and prepares the eval prompt.

- **Inputs:** jaffle-shop-simulator issue description, existing model SQL, existing scenario YAMLs as reference (r1/r2)
- **Outputs:** Patch file that applies cleanly and introduces a plausible bug; scenario YAML with all required fields (ground_truth values may be estimates); prompt file adapted to the scenario's story; dbt tests still pass after applying the patch
- **Good:** Bug is subtle enough that code review would approve; PR description is misleading but plausible; detection requires data comparison not just code reading
- **Bad:** Bug is obvious from code reading alone; dbt tests catch the bug; patch doesn't apply cleanly; scenario is a duplicate of an existing one

### `ground-truth`

The worker verifies the scenario's ground truth numbers by building dual-schema state (prod=clean, dev=buggy) and running SQL queries to confirm exact affected_row_count and model classification.

- **Inputs:** Patch file from draft stage, scenario YAML with estimated ground_truth
- **Outputs:** Exact affected_row_count from SQL query (not estimated); every model in impacted_models verified to have changed rows; every model in not_impacted_models verified to have 0 changed rows; dashboard_impact verified against dashboard column list
- **Good:** Numbers come from actual SQL queries against dual-schema data; model classification is exhaustive (every model in DAG checked)
- **Bad:** Using estimated or rounded numbers; assuming model impact from code reading without SQL verification; forgetting to check downstream models

### `eval-run`

The worker runs the eval batch (N=3, Mode A tool-only) using run-case.sh and scores each run with score-deterministic.sh. Records pass rates, failure patterns, and cost.

- **Inputs:** Verified scenario YAML with exact ground_truth, prompt file, MCP config, recce package installed in jaffle-shop-simulator venv
- **Outputs:** N=3 batch completed with all runs producing valid JSON output; each run scored with pass/fail per criterion; pass rate and failure pattern summary recorded in entity body; cost per run recorded
- **Good:** All 3 runs produce parseable JSON; scoring matches ground truth criteria; failures are analyzed not just counted
- **Bad:** Runs fail due to infrastructure issues (DuckDB lock, MCP timeout) rather than agent judgment; JSON extraction failures treated as agent errors

### `validated`

Captain reviews the eval results to confirm the scenario is good enough for the benchmark suite. This is a human approval gate.

- **Inputs:** Eval-run results with pass rates, failure patterns, and cost
- **Outputs:** Captain's approval or rejection with feedback
- **Good:** Pass rate ≥80% on Mode A (scenario is solvable but challenging); failure patterns are about agent judgment not infrastructure; scenario tests something different from existing scenarios
- **Bad:** Pass rate too low (ground truth may be wrong); all failures are the same JSON extraction issue; scenario is redundant with existing ones

### `integrated`

The scenario is part of the official benchmark suite. Patch, YAML, and prompt files are committed to recce-claude-plugin and included in future batch runs.

- **Inputs:** Approved scenario from validated stage
- **Outputs:** All scenario files committed to the repo
- **Good:** Scenario adds meaningful coverage to the benchmark
- **Bad:** N/A — terminal stage

## Workflow State

View the workflow overview:

```bash
docs/scenario-pipeline/status
```

Output columns: ID, SLUG, STATUS, TITLE, SCORE, SOURCE.

Include archived scenarios with `--archived`:

```bash
docs/scenario-pipeline/status --archived
```

Find dispatchable scenarios ready for their next stage:

```bash
docs/scenario-pipeline/status --next
```

Find scenarios in a specific stage:

```bash
grep -l "status: ground-truth" docs/scenario-pipeline/*.md
```

## Scenario Template

```yaml
---
id:
title: Scenario name here
status: draft
assignee:
source:
started:
completed:
verdict:
score:
worktree:
issue:
pr:
jaffle_issue:
patch_file:
scenario_yaml:
prompt_file:
---

Description of this scenario — what bug is introduced, why it's plausible, and what the agent needs to find.
```

## Commit Discipline

- Commit status changes at dispatch and merge boundaries
- Commit scenario body updates when substantive
