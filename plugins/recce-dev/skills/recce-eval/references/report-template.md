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
- **Isolation**: {isolation_mode} (e.g., --clean-profile both variants)

## Value Layer Comparison

The Recce plugin provides two layers:
1. **MCP tools** — impact_analysis, profile_diff, value_diff_detail (DAG-based analysis)
2. **Plugin hooks + guidance** — SessionStart IMPACT_RULE, PostToolUse review suggestions

This report separates these layers to show where value comes from.

### Three-Way Summary (per scenario)

| Scenario | Baseline | (B) MCP Only | (A) Full Plugin | B→A Delta | Key Finding |
|----------|----------|-------------|-----------------|-----------|-------------|
| {scenario_id} | {score}/12 | {score}/12 | {score}/12 | {delta} | {one-line finding} |

- **Baseline**: `--clean-profile`, no plugin (pure Claude)
- **(B) MCP Only**: `--bare --plugin-dir` (tools available, hooks skipped)
- **(A) Full Plugin**: `--clean-profile --plugin-dir` (tools + hooks fire organically)

### Efficiency

| Scenario | Baseline Turns | Plugin Turns | Δ Turns | Baseline Cost | Plugin Cost | Δ Cost |
|----------|---------------|-------------|---------|--------------|------------|--------|
| {scenario_id} | {turns} | {turns} | {pct}% | ${cost} | ${cost} | {pct}% |

## Key Findings

### {scenario_name}

**Score**: baseline {X}/12 → MCP only {Y}/12 → full plugin {Z}/12

**Why MCP tools alone don't help** (B vs baseline):
- {explain why having tools without guidance doesn't change behavior}

**Why full plugin helps** (A vs baseline):
- {explain what hooks/guidance enable that tools alone don't}

**Baseline failure pattern** (across {N} runs):
- {describe common failures from deterministic checks}

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
| full-plugin det. pass rate | {prev}% | {curr}% | {delta}% |
| MCP-only det. pass rate | {prev}% | {curr}% | {delta}% |
| baseline det. pass rate | {prev}% | {curr}% | {delta}% |

{If no previous eval: "First eval run — no historical comparison available."}

## Methodology Notes

### Isolation Modes

| Mode | Memory | CLAUDE.md | Hooks | Auth | Use Case |
|------|--------|-----------|-------|------|----------|
| Baseline (--clean-profile) | ❌ | ❌ | ✅ (none to fire) | API key | Pure Claude performance |
| (B) MCP only (--bare) | ❌ | ❌ | ❌ skipped | API key | Tools without guidance |
| (A) Full plugin (--clean-profile) | ❌ | ❌ | ✅ organic | API key | Production-equivalent experience |

Each run gets a fresh temp HOME (`mktemp -d`) with seeded settings.json. Zero state shared between runs.

### What changed between baseline and with-plugin?
Only `--plugin-dir` and `--mcp-config` flags. The eval prompt is identical.
Plugin hooks fire organically — no manual injection of IMPACT_RULE or other context.
```

## Generation Rules

1. **Three-Way Summary**: Always include Baseline, MCP Only, and Full Plugin columns. If MCP-only data is not available for a batch, note "MCP-only: not tested in this batch" and use data from the most recent --bare batch.
2. **Value Layer Analysis**: The Key Findings section MUST explain why MCP tools alone don't help AND why the full plugin does. This is the core insight — don't skip it.
3. **Efficiency metrics**: Always include turns and cost comparison. Plugin efficiency (fewer turns) is valuable even when scores are equal.
4. **Detailed Scores**: One sub-section per run, showing all deterministic checks and judge scores.
5. **Cross-Eval Comparison**: Read `.claude/recce-eval/history.json`. Find the most recent entry with the same adapter. Compute deltas for all three modes.
6. **If no judge scores**: Mark "LLM judge: unavailable" in the detailed section.
7. **Honesty rule**: If baseline scores equal or exceed plugin on a scenario, say so explicitly. Do not hide inconvenient data.
