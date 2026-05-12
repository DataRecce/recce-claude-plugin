# Tier-0 Baseline — Fixture `<pr-id>`

Agent-only verdict for the fixture below. **Frozen at commit**: once this file lands on the branch (via the commander's normal change-control flow), the with-Recce run for this fixture can begin, and this file must not be edited even if later evidence suggests it should be revised. Captured before any Recce-aware run so the eval measures delta, not absolute correctness.

## Fixture

- PR: `<link to DataRecce/jaffle_shop_golden PR>`
- Title: `<one-line>`
- Verification class: `<semantic | row-grain | refactor | type | schema-expansion | multi-model>`

## Agent run

- Agent: `<Claude Code | Codex | other>`
- Model: `<provider/model-id — record exactly as reported by the agent runtime>`
- Date captured: `<YYYY-MM-DD>`
- Inputs available to agent: per the Tier-0 runtime contract in `RUBRIC.md` — `diff.patch`, `manifest-before.json` / `manifest-after.json`, `compiled-before/` / `compiled-after/`, `catalog-before.json` / `catalog-after.json`, plus read access to the per-fixture head-SHA source tree at `.tmp/sources/<fixture-id>/`. **No Recce, no warehouse access, no `dbt parse`/`compile`/`docs generate` (regenerating the artifacts violates the frozen-input contract).**

## Prompt given to agent

Verbatim, including any framing about it being a PR review task.

```
<paste exact prompt>
```

## Verdict

- Catch / miss / partial: `<one>`
- Action the agent recommended: `<approve | request changes | abstain>`

## Reasoning the agent gave

Verbatim. The baseline reasoning is the thing Recce's evidence will or won't shift, so paraphrasing here destroys the signal. If the agent's output is very long, quote the verdict-bearing passage verbatim and link to the full transcript.

```
<paste>
```

## Notes

Anything weird about the run worth flagging: hallucinations, refusal, looping, contradictory statements, references to information the agent didn't actually have, etc.
