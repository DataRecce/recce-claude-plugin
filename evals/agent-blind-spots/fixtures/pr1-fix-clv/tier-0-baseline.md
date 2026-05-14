# Tier-0 Baseline — Fixture `pr1-fix-clv`

Agent-only verdict for the fixture below. **Frozen at commit**: once this file lands on the branch (via the commander's normal change-control flow), the with-Recce run for this fixture can begin, and this file must not be edited even if later evidence suggests it should be revised. Captured before any Recce-aware run so the eval measures delta, not absolute correctness.

## Fixture

- PR: <https://github.com/DataRecce/jaffle_shop_golden/pull/13>
- Title: `PR1 — Fix CLV to completed orders only`
- Verification class: `semantic`

## Agent run

- Agent: `<TBD by eval run>`
- Model: `<TBD by eval run — provider/model-id as reported by agent runtime>`
- Date captured: `<TBD by eval run — YYYY-MM-DD>`
- Inputs available to agent: per the Tier-0 runtime contract in `../../RUBRIC.md` — `diff.patch`, `manifest-before.json` / `manifest-after.json`, `compiled-before/` / `compiled-after/`, `catalog-before.json` / `catalog-after.json`, plus read access to the head-SHA source tree at `../../.tmp/sources/pr1-fix-clv/`. **No Recce, no warehouse access, no `dbt parse`/`compile`/`docs generate` (regenerating the artifacts violates the frozen-input contract).**

## Prompt given to agent

Verbatim, including any framing about it being a PR review task.

```
<TBD by eval run — paste exact prompt>
```

## Verdict

- Catch / miss / partial: `<TBD by eval run>`
- Action the agent recommended: `<TBD by eval run — approve | request changes | abstain>`

## Reasoning the agent gave

Verbatim. The baseline reasoning is the thing Recce's evidence will or won't shift, so paraphrasing here destroys the signal. If the agent's output is very long, quote the verdict-bearing passage verbatim and link to the full transcript.

```
<TBD by eval run — paste>
```

## Notes

`<TBD by eval run — hallucinations, refusals, loops, contradictions, or references to information the agent didn't have>`
