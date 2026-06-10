# Tier-0 Baseline — Fixture `pr42-is-closed-filter`

Agent-only verdict. **Frozen at commit** (2026-06-09): do not edit; revisions go to a new dated baseline file.

## Fixture

- PR: <https://github.com/DataRecce/jaffle_shop_golden/pull/14>
- Title: `PR42 — Add is_closed and filter orders`
- Verification class: `row-grain`

## Agent run

- Agent: `Claude Code`
- Model: `claude-opus-4-8` (pinned across the matrix)
- Date captured: `2026-06-09`
- Inputs available to agent: per the Tier-0 runtime contract in `../../RUBRIC.md`, staged at `_eval_inputs/`; cwd = `../../.tmp/sources/pr42-is-closed-filter/`. **No Recce, no warehouse, no dbt-regen.** (Note: this fixture uses an older base SHA `62d6dc9` than the rest.)

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

Verbatim verdict-bearing passage (full trace: `../../runs/2026-06-09/traces/pr42-is-closed-filter_claude_t0.txt`):

```
Request changes. Either remove the where is_closed = true line (keep is_closed as a non-destructive
flag column), or — if filtering is genuinely intended — make it explicit: update schema.yml (drop the
now-impossible status values, document is_closed), rename/re-scope the model so consumers know orders
means "completed orders only," and confirm every downstream/BI consumer expects the reduced
population. A row-count diff (e.g., Recce row_count_diff / value_diff) should be attached to quantify
the drop before merge.

VERDICT: catch · request-changes
```

Decisive evidence tier: **0**. The agent caught the silent row-grain reduction from the compiled-SQL `where is_closed = true` plus the `accepted_values` status domain (only 1 of 5 statuses survives), and correctly identified `orders` as a terminal published mart. It explicitly noted the magnitude is unquantifiable without a Recce row-count diff.

## Notes

The agent explicitly argued against the fixture README's `partial`/`miss` Tier-0 anchor: "the direction and mechanism of the regression are fully determinable from the diff plus the accepted_values status domain, which is enough to block on." Opus 4.8 exceeded the anchor → catch.

### Sandbox profile used

- Agent runtime: Claude Code
- Tier: 0
- Profile source: `evals/agent-blind-spots/runner-configs/claude-code/tier-0 @ 996e1db`
- Enforcement mechanism summary: rendered `settings.json` loaded via `claude --settings <abs-path>` from outside cwd + PreToolUse `deny-tier-0.py` (bashlex AST allowlist); cwd = `.tmp/sources/pr42-is-closed-filter/` (spoiler isolation).
- Deviation from the recipe: `CLAUDE_CONFIG_DIR` not neutered (driver default preserves auth); benign stderr warning `Permission deny rule "MultiEdit" matches no known tool` (non-load-bearing).
