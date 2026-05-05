---
name: recce-analyze
description: One-shot Recce setup + PR impact analysis
---

# Recce Analyze — One-Shot PR Impact

Run this single command to bootstrap your Recce environment and produce a
complete PR-impact summary. No separate setup step required.

Record the wall-clock start time at the beginning of Step 1 and log total
elapsed time after Step 7.

---

## Step 1: Prerequisites

Run the following checks before proceeding. If any fail, help the user resolve
them before continuing.

```bash
# 1a. Confirm this is a dbt project
ls dbt_project.yml
```

- If `dbt_project.yml` is **not found**: Tell the user this is not a dbt project
  directory. Ask them to navigate to their project root.

```bash
# 1b. Confirm required tools are available
dbt --version
python --version || python3 --version
recce --version
```

- If `dbt` is missing: guide the user through adapter-specific installation
  (`pip install dbt-<adapter>`).
- If `recce` is missing: run `pip install recce`.
- Continue once all three tools are present.

---

## Step 2: Branch Detection

```bash
git branch --show-current
```

Determine the **target branch** (current) and **base branch**:

- If current branch is `main` or `master`: ask the user which feature branch to
  compare against.
- Otherwise: target = current branch; base = `main` or `master` (check which
  exists via `git branch --list main master`).

Present the detected configuration to the user and confirm before proceeding.

---

## Step 3: Base Strategy

```bash
recce check-base --format json
```

Parse the JSON response and branch on `recommendation`:

| `recommendation` | Action |
|---|---|
| `reuse` | Skip artifact generation — base artifacts are fresh. |
| `docs_generate` | Warn user about staleness; run `dbt docs generate --target-path target-base` to refresh. Emit: _"⚠️ Base artifacts are stale. Refreshing with dbt docs generate…"_ (AC-3) |
| `full_build` | Run the full base build (see below). |

**Full base build** (only for `full_build`):
```bash
git stash
git checkout <base-branch>
dbt build --target-path target-base
git checkout <target-branch>
git stash pop
```

---

## Step 4: Target Artifacts

```bash
ls target/manifest.json 2>/dev/null || echo MISSING
```

- If `target/manifest.json` is **missing**: run `dbt docs generate`.
- If present: reuse existing target artifacts.

---

## Step 5: Start MCP Server

```bash
bash ${CLAUDE_PLUGIN_ROOT}/scripts/start-mcp.sh
```

Parse the output:

- `STATUS=STARTED` or `STATUS=ALREADY_RUNNING`: continue.
- `ERROR=*`: show the error and the fix suggestion from `start-mcp.sh` output.
  Do not proceed until the server is running.

---

## Step 6: Analysis — Call MCP Tools in Order

Call each tool in sequence. Collect all four results before composing the
output.

1. **`mcp__recce__impact_analysis`** — fast impact summary (call first; no
   parameters needed for the default scope).
2. **`mcp__recce__lineage_diff`** — model-level lineage changes.
3. **`mcp__recce__schema_diff`** — column structure changes.
4. **`mcp__recce__row_count_diff`** with selector
   `select: "config.materialized:table"` — row count changes on tables only
   (never views; they trigger expensive queries).

---

## Step 7: Output — Compose Markdown Summary

Render the following four-section markdown report using the data collected in
Step 6. All four sections MUST appear even if a section has no changes (write
_"No changes detected."_ in that case).

```markdown
## Impact Summary

<narrative paragraph from impact_analysis result>

## Lineage Changes

<list or DAG of modified models and their change_status from lineage_diff>

## Schema Changes

| Model | Change Type | Details |
|-------|-------------|---------|
<rows from schema_diff result>

## Row Count Changes

| Model | Base | Current | Change |
|-------|------|---------|--------|
<rows from row_count_diff result>
```

After rendering the report, log total elapsed time (Step 1 → Step 7). If
elapsed time exceeds 120 s, append a note:
_"⏱ Analysis took <N> s. Consider pre-generating base artifacts to speed up
future runs."_

---

## Error Recovery

If the MCP server fails to start, check the log:

```bash
cat /tmp/recce-mcp-server.log
```

Common issues:
- Database connection errors: check `profiles.yml`.
- Missing artifacts: re-run the relevant artifact generation step.
- Port conflicts: set `RECCE_MCP_PORT` to a different port.
