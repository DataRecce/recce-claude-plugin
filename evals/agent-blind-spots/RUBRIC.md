# Scoring Rubric — Agent Blind Spots / `/recce-verify` v1

## Framing

Qualitative case studies, **not** quantitative eval. N=6 PR fixtures is too small for statistics. The rubric below produces structured case studies; reading them as "X% accuracy" or "Y% improvement" is wrong and breaks credibility with Super / 205DataLab. Always present results as named-case narratives, not aggregates.

## Per-fixture case-study lenses (3, not metrics)

Each lens produces a structured observation, not a score. The three together form one case study per fixture. **Do not aggregate across fixtures.**

### 1. Binary catch

Did the agent reach the correct verdict — catch the intentional bug, or correctly flag a behavior-preserving refactor as safe?

| Value | Meaning |
|-------|---------|
| `catch` | Agent correctly identified the situation and recommended the right action (block or approve). |
| `miss` | Agent shipped the change as safe when it wasn't, or rejected a safe change. |
| `partial` | Agent flagged a real concern but for the wrong reason, or missed half of a multi-issue PR. |

### 2. Primary evidence tier (+ capability subset used)

Which capability tier produced the **decisive** piece of evidence the agent cited in its verdict? If the agent cited evidence from multiple tiers, record the highest decisive tier and list secondary citations under Notes. Tiers are nested — a higher tier always has access to lower-tier inputs.

| Tier | Agent capability set |
|------|----------------------|
| 0 | dbt manifest + compiled SQL + git diff only — no Recce. |
| 1 | Tier 0 + Recce against a **single dev environment**. v1 target. Record *which subset* the agent actually used: **1a** column-level lineage (CLL), **1b** AST / SQL semantic analysis, **1c** structured queries against the current dev env (row counts, distributions, nulls). "Tier 1" alone is ambiguous — always record the subset(s). |
| 2 | **Beyond v1 — base environment needed.** Not part of `/recce-verify` v1's offering. Record only when a fixture's verdict provably requires a base/prod comparison (data diff, row-grain delta, lineage delta vs prod). A fixture reaching Tier 2 is a **v2 signal** for the gap report, not a v1 capability claim. |

### 3. Counterfactual delta against frozen baseline

Binary catch (lens 1) is recorded **for both** the Tier-0 baseline run and the with-Recce run. The case study's headline finding is the **delta** between those two binary-catch values, not the absolute with-Recce value:

- baseline `miss` → with-Recce `catch` = Recce shifted the verdict (positive signal)
- baseline `catch` → with-Recce `catch` = Recce was not needed for this fixture (still useful — explains *what* Recce showed)
- baseline `catch` → with-Recce `miss` = Recce misled the agent (rare but important — investigate Notes)

Freeze the Tier-0 baseline **before** running with Recce so it cannot be edited to fit the new evidence. Without this control, results conflate model variance with Recce signal. Baseline format → see `templates/tier-0-baseline.md`.

## Per-fixture artifact

Each fixture's scoring lives in `runs/<YYYY-MM-DD>/<pr-id>-scoring.md` with this structure:

```markdown
# Fixture <pr-id> — <one-line title>

- Tier-0 baseline (frozen): <link to fixtures/<pr-id>/tier-0-baseline.md>
- Run date: <YYYY-MM-DD>
- Agent / model: <name>
- Primary evidence tier + subset: <0 | 1a | 1b | 1c | 2>  (list secondary citations under Notes if any)
- Binary catch (this run): <catch | miss | partial>
- Binary catch (Tier-0 baseline): <catch | miss | partial>
- Delta: <baseline → this run, e.g. `miss → catch`>

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

The eval output is **prioritized for action**, **targets ≤5 entries**, and lives at `runs/<YYYY-MM-DD>/gap-report.md`. Format → see `templates/gap-report.md`.

The broader capability backlog (e.g., the 33-item Notion list) is reference material; the gap report is the deliberate cut of "what to do next" derived from the six case studies. The ≤5 target is a discipline against the backlog bleeding back in — if a receipts-style review leaves ≥6 genuinely independent blockers, exceed the target and add a one-line note explaining why one couldn't be subsumed or deferred. "Prioritized" here means *priority of action*, not ordinal performance.

## What this rubric is NOT

- **Not a leaderboard.** Don't compute "agent A vs agent B" scores.
- **Not a regression suite.** Don't run it on every commit; re-run when the skill prompt or backend changes meaningfully.
- **Not statistical evidence.** N=6 means stories, not averages. If a stakeholder asks for "the number", refer them to this section.
