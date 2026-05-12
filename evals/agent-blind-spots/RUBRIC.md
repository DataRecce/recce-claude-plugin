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

Binary catch (lens 1) is recorded **for both** the Tier-0 baseline run and the with-Recce run. The case study's headline finding is the **delta** between those two binary-catch values, not the absolute with-Recce value.

Order the three catch values as `catch > partial > miss` (closer to ground truth → less close). Every baseline → with-Recce pair falls into one of three buckets:

| Delta bucket | Examples | What it means |
|--------------|----------|---------------|
| **Improvement** | `miss → catch`, `miss → partial`, `partial → catch` | Recce shifted the verdict toward ground truth. Positive signal — describe *what* evidence drove the shift. |
| **Same** | `miss → miss`, `partial → partial`, `catch → catch` | No shift in verdict. Still useful — for `catch → catch`, record what Recce showed (validates redundancy or reveals Recce wasn't needed); for `miss → miss` or `partial → partial`, the agent ignored or didn't surface decisive evidence — feed back into the skill prompt. |
| **Regression** | `catch → partial`, `catch → miss`, `partial → miss` | Recce misled the agent. Rare but important — investigate in Notes; this is a v1-release-blocker signal. |

The baseline file is **frozen at commit**: once it lands on the branch, the with-Recce run can begin, and the baseline must not be edited even if later evidence suggests it should be revised. Without this control, results conflate model variance with Recce signal. Baseline format → see `templates/tier-0-baseline.md`.

## Tier-0 agent runtime contract

To make Tier-0 baselines reproducible across runs, the agent receives **the same raw material Recce ingests, minus Recce's structured surfacing**. This isolates "what Recce contributes" from "what the agent could have figured out from artifacts alone." A weaker Tier-0 setup (e.g., diff-only, no artifacts) would understate the agent's solo capability and overstate Recce's signal.

**Inputs per fixture** (populated by `build_fixtures.sh`):

- `fixtures/<id>/diff.patch` — source-model diff between base and head
- `fixtures/<id>/artifacts/manifest-before.json`, `manifest-after.json` — dbt manifests pre/post
- `fixtures/<id>/artifacts/compiled-before/`, `compiled-after/` — compiled SQL trees pre/post
- `fixtures/<id>/artifacts/catalog-before.json`, `catalog-after.json` — schema-only (row/col stats are zero in this fixture set; documented in the fixtures README)
- Read access to the dbt project source at the head SHA (the `.tmp/jaffle_shop_golden/` checkout left by the build script)

**Generic tools allowed at Tier 0:** file read, grep / ripgrep, `jq`, `git log` / `git diff` / `git show` against the head-SHA checkout. Anything the agent could plausibly run on a developer's laptop without Recce installed.

**Explicitly NOT allowed at Tier 0:** Recce CLI, Recce MCP, any `/recce-*` skill (including `/recce-verify`), warehouse access, `dbt run`, `dbt test`, live SQL execution, comparison against a base/prod environment beyond what is already in the artifacts above.

**Prompt shape** — eval runners may adapt wording; the *capabilities* above are the contract:

> "Review this dbt PR. The inputs above are available. Decide catch / miss / partial per the rubric, recommend approve / request-changes / abstain, and write verdict + verbatim reasoning into `tier-0-baseline.md`."

Agent-specific implementations (Claude Code, Codex, …) MAY add scaffolding (file-access mode, tool whitelisting) but MUST NOT add Recce capabilities or anything beyond the generic-tools list. Any deviation must be recorded in the Tier-0 baseline's Notes section so the delta is interpretable.

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
