# Tier-0 Baseline — Fixture `pr3-amount-double-to-decimal`

Agent-only verdict. **Frozen at commit** (2026-06-09): do not edit; revisions go to a new dated baseline file.

## Fixture

- PR: <https://github.com/DataRecce/jaffle_shop_golden/pull/16>
- Title: `PR3 — Change payment amount from double to decimal`
- Verification class: `type / rounding drift`

## Agent run

- Agent: `Claude Code`
- Model: `claude-opus-4-8` (pinned across the matrix)
- Date captured: `2026-06-09`
- Inputs available to agent: per the Tier-0 runtime contract in `../../RUBRIC.md`, staged at `_eval_inputs/`; cwd = `../../.tmp/sources/pr3-amount-double-to-decimal/`. **No Recce, no warehouse, no dbt-regen.**

## Prompt given to agent

```
Review this dbt PR. The current working directory is the dbt project at the head SHA (models/, dbt_project.yml, etc.). The frozen Tier-0 inputs are staged under `_eval_inputs/`:
  - _eval_inputs/diff.patch — source-model diff base..head
  - _eval_inputs/artifacts/manifest-{before,after}.json — dbt manifests pre/post
  - _eval_inputs/artifacts/compiled-{before,after}/ — compiled SQL pre/post
  - _eval_inputs/artifacts/catalog-{before,after}.json — schema-only (row stats are zero)
Decide catch / miss / partial per the rubric. Recommend approve / request-changes / abstain. End your output with one line, exactly:
VERDICT: <catch|miss|partial> · <approve|request-changes|abstain>
```

## Verdict

- Catch / miss / partial: `partial`  *(grader override — see Notes)*
- Action the agent recommended: `approve`

## Reasoning the agent gave

Verbatim verdict-bearing passage (full trace: `../../runs/2026-06-09/traces/pr3-amount-double-to-decimal_claude_t0.txt`):

```
This is a benign, value-preserving, best-practice type refinement for monetary data. The real hazard
in reviewing it is the false positive — flagging phantom integer-division truncation or SUM overflow
that Snowflake's semantics rule out. Correctly read, there is nothing to block; at most a one-character
'as' style nit.

VERDICT: catch · approve
```

Decisive evidence tier: **0**. The agent assumed the **Snowflake** dialect (read `profiles.yml` → `type: snowflake`), reasoned the cast is value-preserving under Snowflake division semantics, and approved with only an overflow-bound mention and an `as` style nit.

## Notes

**Grader override (catch → partial).** The agent self-labeled `catch · approve`. As first grader I score this **partial**: the value-safety assessment is sound for jaffle-scale data, but the review *missed* the downstream incremental-model schema-drift risk on `orders_daily_summary` and the `sum(...)::bigint` rounding-boundary effect on `value_segment` — both of which the Tier-1 run of the same model surfaced. Approving a money-column type change while missing a real (if low-severity) downstream concern is "flagged correctly but incomplete" → partial.

This fixture is the clearest **catch/partial-boundary ambiguity** in the set (logged as waffle point W3 in `../../RUBRIC.md`) and the clearest **dialect-ambiguity** case (W8): the agent's verdict hinges on whether it reads the Snowflake `profiles.yml` or the DuckDB-compiled artifacts. The Tier-0 vs Tier-1 split on this fixture (approve vs request-changes) is dialect-driven run variance, **not** a Recce effect (W7).

### Sandbox profile used

- Agent runtime: Claude Code
- Tier: 0
- Profile source: `evals/agent-blind-spots/runner-configs/claude-code/tier-0 @ 996e1db`
- Enforcement mechanism summary: rendered `settings.json` loaded via `claude --settings <abs-path>` from outside cwd + PreToolUse `deny-tier-0.py` (bashlex AST allowlist); cwd = `.tmp/sources/pr3-amount-double-to-decimal/` (spoiler isolation).
- Deviation from the recipe: `CLAUDE_CONFIG_DIR` not neutered (driver default preserves auth); benign stderr warning `Permission deny rule "MultiEdit" matches no known tool` (stale tool name in template; non-load-bearing).
