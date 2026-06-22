# Tier-0 Baseline — Fixture `pr44-promotion-flags`

Agent-only verdict. **Frozen at commit** (2026-06-09): do not edit; revisions go to a new dated baseline file.

## Fixture

- PR: <https://github.com/DataRecce/jaffle_shop_golden/pull/20>
- Title: `PR44 — Add promotion payment flag + customer has-promotion flag`
- Verification class: `schema-expansion (+ intermediate row-filter accident, not exercised by default — see Notes)`

## Agent run

- Agent: `Claude Code`
- Model: `claude-opus-4-8` (pinned across the matrix)
- Date captured: `2026-06-09`
- Inputs available to agent: per the Tier-0 runtime contract in `../../RUBRIC.md`, staged at `_eval_inputs/` (the **base..head** `diff.patch` = benign schema expansion); cwd = `../../.tmp/sources/pr44-promotion-flags/`. **No Recce, no warehouse, no dbt-regen.**

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

- Catch / miss / partial: `catch`
- Action the agent recommended: `request-changes`

## Reasoning the agent gave

Verbatim verdict-bearing passage (full trace: `../../runs/2026-06-09/traces/pr44-promotion-flags_claude_t0.md`):

```
Request changes. The primary issue is hard-blocking: the model cannot build against the project's
actual adapter, so the feature ships broken and no data diff is even possible. Swap boolor_agg ->
bool_or (or the dbt_utils macro) before merge.

VERDICT: catch · request-changes
```

Decisive evidence tier: **0**. The agent assumed the **DuckDB** dialect (manifest macros + identifier quoting) and caught that `boolor_agg` is a Snowflake-only function that will fail at `dbt run` on DuckDB — a genuine portability bug.

## Notes

Two caveats make this baseline's interpretation subtle:

1. **The default cell evaluates the BENIGN head state** (two new columns, no row filter). The fixture's intended blind-spot — the `where has_promoted_orders = true` row-filter accident at intermediate commit `23b96ca` — is **not** exercised by the default `diff.patch` and is logged as waffle/harness point **W2**. A separate `pr44-intermediate` cell is needed to exercise it.
2. **Dialect ambiguity (W8).** The agent caught a real bug (`boolor_agg` on DuckDB), but the verdict is dialect-contingent: the Tier-1 run assumed Snowflake (where `boolor_agg` is valid) and approved. Both verdicts are internally correct for their assumed adapter; there is no single ground truth for the head state because the fixture ships a Snowflake `profiles.yml` alongside DuckDB-compiled artifacts.

### Sandbox profile used

- Agent runtime: Claude Code
- Tier: 0
- Profile source: `evals/agent-blind-spots/runner-configs/claude-code/tier-0 @ 996e1db`
- Enforcement mechanism summary: rendered `settings.json` loaded via `claude --settings <abs-path>` from outside cwd + PreToolUse `deny-tier-0.py` (bashlex AST allowlist); cwd = `.tmp/sources/pr44-promotion-flags/` (spoiler isolation).
- Deviation from the recipe: `CLAUDE_CONFIG_DIR` not neutered (driver default preserves auth); benign stderr warning `Permission deny rule "MultiEdit" matches no known tool` (non-load-bearing).
