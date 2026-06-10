# Tier-0 Baseline — Fixture `pr46-net-clv-segments`

Agent-only verdict. **Frozen at commit** (2026-06-09): do not edit; revisions go to a new dated baseline file.

## Fixture

- PR: <https://github.com/DataRecce/jaffle_shop_golden/pull/2>
- Title: `PR46 — Net revenue, net CLV, customer segments`
- Verification class: `multi-model semantic (stress test)`

## Agent run

- Agent: `Claude Code`
- Model: `claude-opus-4-8` (pinned across the matrix)
- Date captured: `2026-06-09`
- Inputs available to agent: per the Tier-0 runtime contract in `../../RUBRIC.md`, staged at `_eval_inputs/`; cwd = `../../.tmp/sources/pr46-net-clv-segments/`. **No Recce, no warehouse, no dbt-regen.**

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

Verbatim verdict-bearing passage (full trace: `../../runs/2026-06-09/traces/pr46-net-clv-segments_claude_t0.txt`):

```
The net-CLV feature itself is reasonable, but the PR silently regresses an existing, downstream-consumed
metric (customer_lifetime_value) and documents it misleadingly, plus ships a likely test-failing model
and an internal net-revenue inconsistency. This should not merge as-is.

VERDICT: catch · request-changes
```

Decisive evidence tier: **0**. The agent caught the **decisive** buried issue — the in-place redefinition of the existing public `customer_lifetime_value` (now completed-orders-only + `amount > 0`), hidden inside an additive-looking PR — plus the downstream `value_segment` shift, the LEFT-JOIN-filter anti-pattern, the fragile `finance_revenue` `not_null` tests, and the copy-pasted net thresholds. All from artifacts; Recce noted as unavailable.

## Notes

Stress-test fixture (≥3 distinct issues). The agent caught all of them, including the decisive metric redefinition the README expected it to miss. Defines the **decisive issue** for the W3 catch/partial rule: catching the `customer_lifetime_value` redefinition = catch; catching only the additive surface (new columns/model) while missing the redefinition = partial.

### Sandbox profile used

- Agent runtime: Claude Code
- Tier: 0
- Profile source: `evals/agent-blind-spots/runner-configs/claude-code/tier-0 @ 996e1db`
- Enforcement mechanism summary: rendered `settings.json` loaded via `claude --settings <abs-path>` from outside cwd + PreToolUse `deny-tier-0.py` (bashlex AST allowlist); cwd = `.tmp/sources/pr46-net-clv-segments/` (spoiler isolation).
- Deviation from the recipe: `CLAUDE_CONFIG_DIR` not neutered (driver default preserves auth); benign stderr warning `Permission deny rule "MultiEdit" matches no known tool` (non-load-bearing).
