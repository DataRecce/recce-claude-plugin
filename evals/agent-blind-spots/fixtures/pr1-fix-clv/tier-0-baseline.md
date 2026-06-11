# Tier-0 Baseline — Fixture `pr1-fix-clv`

Agent-only verdict. **Frozen at commit** (2026-06-09): do not edit even if later evidence suggests revision; revisions go to a new dated baseline file. Captured before any Recce-aware run so the eval measures delta, not absolute correctness.

## Fixture

- PR: <https://github.com/DataRecce/jaffle_shop_golden/pull/13>
- Title: `PR1 — Fix CLV to completed orders only`
- Verification class: `semantic`

## Agent run

- Agent: `Claude Code`
- Model: `claude-opus-4-8` (pinned across the matrix per the same-model contract)
- Date captured: `2026-06-09`
- Inputs available to agent: per the Tier-0 runtime contract in `../../RUBRIC.md` — `diff.patch`, `manifest-{before,after}.json`, `compiled-{before,after}/`, `catalog-{before,after}.json` (staged at `_eval_inputs/`), plus the head-SHA source tree as cwd at `../../.tmp/sources/pr1-fix-clv/`. **No Recce, no warehouse, no dbt parse/compile/docs generate.**

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

Verbatim verdict-bearing passage (full trace: `../../runs/2026-06-09/traces/pr1-fix-clv_claude_t0.md`):

```
The change isn't a syntax bug, but it materially redefines a published metric, creates NULLs that
silently rebucket downstream, and introduces an internal inconsistency with number_of_orders — all
with no PR description, no test, and a doc mismatch. This should not merge as-is. Request changes:
(a) confirm "completed-only" is the intended CLV definition (vs. excluding only returns); (b) handle
the no-completed-order case explicitly (coalesce(..., 0) or an "Unknown" segment) rather than silently
labeling them 'Low Value'; (c) add a profile/value diff on the downstream customer_segments and a
test/doc for the metric.

VERDICT: catch · request-changes
```

Decisive evidence tier: **0** (git diff + compiled SQL + manifest + schema.yml). The agent traced the downstream `customer_segments` rebucketing and the silent NULL→'Low Value' masking from artifacts alone, and explicitly flagged that it could not *quantify* impact because the catalog is schema-only — naming `value_diff`/`profile_diff` as the wanted-but-unavailable evidence.

## Notes

The fixture README anchored Tier-0 at `partial` ("the agent will hedge"); Opus 4.8 exceeded that to `catch` with full downstream tracing. Anchors are not predictions — they predate current frontier models.

### Sandbox profile used

- Agent runtime: Claude Code
- Tier: 0
- Profile source: `evals/agent-blind-spots/runner-configs/claude-code/tier-0 @ 996e1db`
- Enforcement mechanism summary: rendered `settings.json` loaded via `claude --settings <abs-path>` from outside cwd + PreToolUse `deny-tier-0.py` (bashlex AST allowlist); cwd = `.tmp/sources/pr1-fix-clv/` (spoiler isolation). No Recce, no warehouse, no dbt-regen.
- Deviation from the recipe: `CLAUDE_CONFIG_DIR` not neutered (driver default preserves auth for unattended runs; load-bearing enforcement is `--settings` + hook). Stderr carried a benign `Permission deny rule "MultiEdit" matches no known tool` warning (stale tool name in the template; non-load-bearing).
