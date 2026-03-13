# E2E Pass Criteria

## Section-Level Checks

| Section | Check | Pass Condition |
|---------|-------|----------------|
| Pre-flight | dbt project detected | `DBT_PROJECT=true` |
| Pre-flight | recce installed with SSE | `SSE_SUPPORT=true` |
| Pre-flight | Artifacts exist | `TARGET_EXISTS=true` AND `TARGET_BASE_EXISTS=true` |
| MCP Startup | start-mcp.sh succeeds | `STATUS=STARTED` or `STATUS=ALREADY_RUNNING` |
| MCP Health | check-mcp.sh confirms | `RUNNING=true` |
| Tier 1 Track | Edit hook records model | File `/tmp/recce-changed-{hash}.txt` contains edited model path |
| Tier 2 Suggest | dbt run triggers suggestion | Hook injects "Consider running /recce-review" context |
| Review Agent | Summary produced | Output contains `## Data Review Summary` |
| Review Agent | Concrete row counts | At least one model shows non-zero integer in both base and current |
| Review Agent | Risk level present | Summary contains `LOW`, `MEDIUM`, or `HIGH` |
| Review Agent | Model names present | Changed model name appears in summary |
| Review Agent | No MCP errors | All MCP tool calls complete without connection/timeout errors |
| Cleanup | Model reverted | Edited file restored to original |
| Cleanup | MCP stopped | stop-mcp.sh returns `STATUS=STOPPED` |
| Stale State | No leftovers | No `/tmp/recce-mcp-*.pid` or `/tmp/recce-changed-*.txt` remaining |

## Performance Metrics to Capture

From the review agent dispatch result, extract:

| Metric | Source | Format |
|--------|--------|--------|
| `tool_uses` | Agent result `<usage>` block | Integer |
| `total_tokens` | Agent result `<usage>` block | Integer |
| `duration_ms` | Agent result `<usage>` block | Integer (convert to seconds for display) |

## Benchmark Report Template

```markdown
## MCP E2E Benchmark Report

**Date:** {YYYY-MM-DD}
**recce version:** {version}
**Project:** {dbt_project_name}
**Environment:** {adapter_type} (dual-env | single-env)
**Test model:** {model_name}

### Event Chain Results

| Step | Result | Notes |
|------|--------|-------|
| Pre-flight | {PASS/FAIL} | {details} |
| MCP Startup | {PASS/FAIL} | Port {port}, PID {pid} |
| Tier 1 Tracking | {PASS/FAIL} | |
| Tier 2 Suggestion | {PASS/FAIL} | |
| Review Agent | {PASS/FAIL} | Risk: {level} |
| Cleanup | {PASS/FAIL} | |

### Agent Performance

| Metric | Value |
|--------|-------|
| Tool calls | {N} |
| Tokens consumed | {N} |
| Wall-clock time | {N}s |

### Comparison (if baseline provided)

| Metric | Baseline | Current | Delta |
|--------|----------|---------|-------|
| Tool calls | {N} | {N} | {±N} ({±%}) |
| Tokens | {N} | {N} | {±N} ({±%}) |
| Time | {N}s | {N}s | {±N}s ({±%}) |

### Data Review Summary

{Paste the agent's ## Data Review Summary output here}

### Verdict: {PASS / FAIL}
{If FAIL: list which criteria failed}
```
