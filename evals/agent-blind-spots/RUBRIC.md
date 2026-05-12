# Scoring Rubric — Agent Blind Spots / `/recce-verify` v1

## Framing

Qualitative case studies, **not** quantitative eval. N=6 PR fixtures is too small for statistics. The rubric below produces structured case studies; reading them as "X% accuracy" or "Y% improvement" is wrong and breaks credibility with Super / 205DataLab. Always present results as named-case narratives, not aggregates.

## Per-fixture scoring (3 dimensions)

### 1. Binary catch

Did the agent reach the correct verdict — catch the intentional bug, or correctly flag a behavior-preserving refactor as safe?

| Value | Meaning |
|-------|---------|
| `catch` | Agent correctly identified the situation and recommended the right action (block or approve). |
| `miss` | Agent shipped the change as safe when it wasn't, or rejected a safe change. |
| `partial` | Agent flagged a real concern but for the wrong reason, or missed half of a multi-issue PR. |

### 2. Confidence tier

Which capability tier did the agent use to reach the verdict? Record the *minimum* tier that actually produced the verdict — if a higher tier was available and the agent ignored it, score at the tier actually used.

| Tier | Agent capability set |
|------|----------------------|
| 0 | dbt manifest + compiled SQL + git diff only — no Recce |
| 1 | Tier 0 + Recce against a **single dev environment** — CLL, AST analysis, and structured queries scoped to current state. No base-environment comparison. This is the `/recce-verify` v1 target. |
| 2 | Tier 1 + **base environment** available — Recce diff against prod or a stable base: lineage delta, data diff, row-grain delta. Out of v1 scope; recorded only if a fixture genuinely needs it. |

### 3. Counterfactual control (delta, not absolute)

For each fixture, freeze a **Tier-0 agent-only baseline** verdict in writing **before** running with Recce. The eval measures the *delta* between baseline and with-Recce, not absolute correctness. Without this control, results conflate agent variance with Recce signal.

Tier-0 baseline format → see `templates/tier-0-baseline.md`.

## Per-fixture artifact

Each fixture's scoring lives in `runs/<YYYY-MM-DD>/<pr-id>-scoring.md` with this structure:

```markdown
# Fixture <pr-id> — <one-line title>

- Tier-0 baseline (frozen): <link to fixtures/<pr-id>/tier-0-baseline.md>
- Run date: <YYYY-MM-DD>
- Agent / model: <name>
- Tier used to reach verdict: <0 | 1 | 2>
- Binary catch: <catch | miss | partial>

## Evidence Recce surfaced

Verbatim from tool output (or paraphrased with a link). One bullet per piece of evidence.

## Conclusion the agent reached

What the agent actually said / recommended. Quote.

## Delta vs Tier-0 baseline

What changed between Tier-0 baseline and this run. Why. If no delta, say so explicitly.

## Notes

Failure modes, hallucinations, suspicious reasoning, anything worth feeding back into the skill prompt.
```

## Gap report (output of the eval run)

The eval output is **ranked**, **capped at 5 entries**, and lives at `runs/<YYYY-MM-DD>/gap-report.md`. Format → see `templates/gap-report.md`.

The 33-item Notion capability list is reference material; the gap report is the prioritized cut of "what to do next" derived from the six case studies. Not all 33 items — at most 5.

## What this rubric is NOT

- **Not a leaderboard.** Don't compute "agent A vs agent B" scores.
- **Not a regression suite.** Don't run it on every commit; re-run when the skill prompt or backend changes meaningfully.
- **Not statistical evidence.** N=6 means stories, not averages. If a stakeholder asks for "the number", refer them to this section.
