# Tier-0 Baseline — Fixture `pr2-refactor-cte-to-models`

Agent-only verdict. **Frozen at commit** (2026-06-09): do not edit; revisions go to a new dated baseline file.

## Fixture

- PR: <https://github.com/DataRecce/jaffle_shop_golden/pull/15>
- Title: `PR2 — Refactor CTEs into intermediate models`
- Verification class: `refactor (behavior-preserving, equality expected)`

## Agent run

- Agent: `Claude Code`
- Model: `claude-opus-4-8` (pinned across the matrix)
- Date captured: `2026-06-09`
- Inputs available to agent: per the Tier-0 runtime contract in `../../RUBRIC.md`, staged at `_eval_inputs/`; cwd = `../../.tmp/sources/pr2-refactor-cte-to-models/`. **No Recce, no warehouse, no dbt-regen.**

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
- Action the agent recommended: `approve`

## Reasoning the agent gave

Verbatim verdict-bearing passage (full trace: `../../runs/2026-06-09/traces/pr2-refactor-cte-to-models_claude_t0.md`):

```
The change is correct and behavior-preserving — customers and all downstream tables produce identical
data. The findings (materialization-as-table, missing tests/docs) are convention/quality, not
correctness, and don't block. Approve with non-blocking suggestions: set the int models to ephemeral
(or confirm table is intended) and add minimal unique/not_null grain tests on their customer_id.

VERDICT: catch · approve
```

Decisive evidence tier: **0**. Equivalence proven by tracing `compiled-before/` vs `compiled-after/` (byte-equivalent join logic); no Recce invoked. The agent independently flagged that the new `int_*` models materialize as `table` (not `ephemeral`) — a quality observation beyond the fixture spec.

## Notes

Negative control: the agent correctly approved a behavior-preserving refactor without raising a false alarm. The rubric's intended differentiator for this fixture (a with-Recce 100% value-match receipt) could not be produced — Recce was not invoked/available.

### Sandbox profile used

- Agent runtime: Claude Code
- Tier: 0
- Profile source: `evals/agent-blind-spots/runner-configs/claude-code/tier-0 @ 996e1db`
- Enforcement mechanism summary: rendered `settings.json` loaded via `claude --settings <abs-path>` from outside cwd + PreToolUse `deny-tier-0.py` (bashlex AST allowlist); cwd = `.tmp/sources/pr2-refactor-cte-to-models/` (spoiler isolation).
- Deviation from the recipe: `CLAUDE_CONFIG_DIR` not neutered (driver default preserves auth); benign stderr warning `Permission deny rule "MultiEdit" matches no known tool` (stale tool name in template; non-load-bearing).
