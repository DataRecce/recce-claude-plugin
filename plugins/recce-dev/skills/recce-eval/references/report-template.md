# Eval Report Template

Generate `report.md` following this structure. Replace `{placeholders}` with actual values.

---

## Structure

```
# Recce Eval Report — {timestamp}

## Environment
- **Target**: {target} ({adapter})
- **Recce version**: {recce_version}
- **Claude model**: {claude_model}
- **Runs per scenario**: {N}
- **Budget per run**: ${max_budget_usd}

## Summary

| Scenario | Variant | Det. Pass Rate | Judge Avg | Tokens (mean) | Duration (mean) | Cost (mean) |
|----------|---------|---------------|-----------|---------------|-----------------|-------------|
| {scenario_id} | baseline | {det_pass_rate}% | {judge_avg} | {tokens} | {duration}s | ${cost} |
| {scenario_id} | with-plugin | {det_pass_rate}% | {judge_avg} | {tokens} | {duration}s | ${cost} |

## Key Findings

### {scenario_name}

**Delta**: with-plugin {+/-}X% det. accuracy, {+/-}Y judge score

**Baseline failure pattern** (across {N} runs):
- {describe common failures from deterministic checks}

**With-plugin advantage**:
- {describe what Recce MCP tools enabled}

## Detailed Scores

### {scenario_id} — {variant} Run {N}

| Check | Expected | Actual | Result |
|-------|----------|--------|--------|
| {check_name} | {expected} | {actual} | {PASS/FAIL} |

**Judge scores**: reasoning={score}, evidence={score}, fix={score}, false_positive={score}, completeness={score}
**Notable**: "{observation from judge}"

## Cross-Eval Comparison
{Only if history.json has a previous entry with the same adapter}

| Metric | Previous ({prev_eval_id}) | Current | Delta |
|--------|--------------------------|---------|-------|
| with-plugin det. pass rate | {prev}% | {curr}% | {delta}% |
| with-plugin judge avg | {prev} | {curr} | {delta} |
| baseline det. pass rate | {prev}% | {curr}% | {delta}% |

{If no previous eval: "First eval run — no historical comparison available."}
```

## Generation Rules

1. **Summary table**: Compute means across runs for the same scenario+variant
2. **Key Findings**: Analyze failure patterns from deterministic checks. The skill (Claude) writes this section — it is NOT a template fill, but an AI-generated analysis
3. **Detailed Scores**: One sub-section per run, showing all deterministic checks and judge scores
4. **Cross-Eval Comparison**: Read `.claude/recce-eval/history.json`. Find the most recent entry with the same adapter. Compute deltas.
5. **If no judge scores**: Mark "LLM judge: unavailable" in the detailed section
