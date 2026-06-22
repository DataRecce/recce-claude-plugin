# Scoring Rubric — Agent Blind Spots / `/recce-verify` v1

> **Status: provisionally locked (2026-06-09, DRC-3585).** The lens clarifications and waffle log below were derived from a hand-graded run of 6 fixtures × Claude Code × {Tier-0, Tier-1} on `claude-opus-4-8` (`runs/2026-06-09/`). They are frozen pending a second grader's independent pass on the same traces (≥90% inter-rater agreement on the three axes, per DRC-3585 acceptance). See the **Waffle log** appendix for what changed and why.

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

**Decisive-issue rule (multi-issue PRs).** When a PR contains more than one independent issue (e.g., `pr46`, `pr3`), score the binary catch against the single **decisive** (blocking) issue named in that fixture's `tier-0-baseline.md` Notes — not against the *count* of issues found:

- `catch` — the agent identified the decisive issue and recommended the right action.
- `partial` — the agent caught a real but non-decisive issue (or caught the decisive issue for the wrong reason / via a wrong mechanism) while missing or mishandling the decisive one.
- `miss` — the agent missed the decisive issue entirely (shipped-as-safe, or rejected a safe change).

The decisive issue per fixture: `pr46` → in-place redefinition of the public `customer_lifetime_value`; `pr42` / `pr44-intermediate` → the silent row drop; `pr3` → the unverifiable downstream impact of the money-column type change; `pr1` → the CLV semantic narrowing + downstream rebucketing; `pr2` → behaviour preservation (a false alarm is the failure mode); `pr44-head` → adapter portability / "no row impact" (depends on declared dialect — see waffle log W8). Naming it up front is what lets two graders converge.

### 2. Primary evidence tier (+ capability subset used)

Which capability tier produced the **decisive** piece of evidence the agent cited in its verdict? Tiers are nested — a higher tier always has access to lower-tier inputs.

If the agent cited evidence from multiple tiers, record the higher tier as decisive (tier ordering `0 < 1 < 2` applies across tiers) and list secondary citations under Notes. Within Tier 1, the subsets `1a / 1b / 1c` are **not** ordered — they are orthogonal capability surfaces (and `1a` is computed via `1b`, so they're entangled). If the agent cited evidence from multiple Tier-1 subsets, mark the subset whose evidence appeared in the verdict sentence as **primary**, the rest as **supporting**; primary/supporting replaces "highest" within Tier 1.

| Tier | Agent capability set |
|------|----------------------|
| 0 | dbt manifest + compiled SQL + git diff only — no Recce. |
| 1 | Tier 0 + Recce against a **single dev environment**. v1 target. Record *which subset* the agent actually used: **1a** column-level lineage (CLL), **1b** AST / SQL semantic analysis, **1c** structured queries against the current dev env (row counts, distributions, nulls). "Tier 1" alone is ambiguous — always record the subset(s). |
| 2 | **Beyond v1 — base environment needed.** Not part of `/recce-verify` v1's offering. Record only when a fixture's verdict provably requires a base/prod comparison (data diff, row-grain delta, lineage delta vs prod). A fixture reaching Tier 2 is a **v2 signal** for the gap report, not a v1 capability claim. |

**Evidence tier is what the agent *actually used*, not what was *available*.** A Tier-1 *cell* (Recce permitted) scores evidence-tier **0** if the agent reached its verdict from artifacts alone without invoking Recce. Do not credit a tier the agent did not exercise — "Recce was allowed" is not evidence.

**`1c` requires a cited query result.** Score `1c` only when the transcript contains an actual structured-query result (a row count, distribution, or null rate the agent ran against the dev env). An agent that merely *names* `value_diff` / `profile_diff` / `row_count` as a wanted-but-unrun next step has **not** reached `1c` — classify it by what it did use (`1a` / `1b` / `0`). This guards against a judge model hallucinating `1c` from aspirational language (see waffle log W5).

### 3. Counterfactual delta against frozen baseline

Binary catch (lens 1) is recorded **for both** the Tier-0 baseline run and the with-Recce run. The case study's headline finding is the **delta** between those two binary-catch values, not the absolute with-Recce value.

Order the three catch values as `catch > partial > miss` (closer to ground truth → less close). Every baseline → with-Recce pair falls into one of three buckets:

| Delta bucket | Examples | What it means |
|--------------|----------|---------------|
| **Improvement** | `miss → catch`, `miss → partial`, `partial → catch` | Recce shifted the verdict toward ground truth. Positive signal — describe *what* evidence drove the shift. |
| **Same** | `miss → miss`, `partial → partial`, `catch → catch` | No shift in verdict. Still useful — for `catch → catch`, record what Recce showed (validates redundancy or reveals Recce wasn't needed); for `miss → miss` or `partial → partial`, the agent ignored or didn't surface decisive evidence — feed back into the skill prompt. |
| **Regression** | `catch → partial`, `catch → miss`, `partial → miss` | Recce misled the agent. Rare but important — investigate in Notes; this is a v1-release-blocker signal. |

**Delta is recorded only on with-Recce (Tier-1+) cells.** A Tier-0 *cell* is the baseline — its delta is `n/a`, not `same`. (A judge asked for a delta on a Tier-0 cell will invent one; see waffle log W1.)

**Recce-attribution rule (run-variance guard).** The Tier-0 baseline and the with-Recce run are *separate stochastic runs of the same model*. The same-model contract (below) controls for model **drift** (a version change) but **not** for within-model run-to-run **variance** — two runs can reach different verdicts for reasons unrelated to Recce (e.g., anchoring on a different artifact; see waffle log W7/W8). Therefore a delta counts as **Recce-attributable** only if the with-Recce transcript **cites a Recce tool result** as decisive in the shift. If the verdict moved but the with-Recce run cites no Recce evidence, record the delta as **`confounded (run variance — no Recce evidence cited)`** and do **not** attribute it to Recce. At N=1 run per cell, an uncited delta is noise, not signal — describe it in Notes and, where it matters, re-run the pair to see whether the shift is stable.

The baseline file is **frozen at commit**: once it lands on the branch, the with-Recce run can begin, and the baseline must not be edited even if later evidence suggests it should be revised. Without this control, results conflate model variance with Recce signal. Baseline format → see `templates/tier-0-baseline.md`.

**Same-model contract.** The with-Recce run MUST use the same agent + model as the frozen Tier-0 baseline (the `Agent` and `Model` fields in `templates/tier-0-baseline.md`). If a model upgrade lands mid-eval, either re-capture the baseline (and re-commit it) or record the mismatch in the per-fixture artifact's Notes section and treat that fixture's delta as confounded. Without this constraint, the lens-3 delta conflates Recce signal with model drift.

## Tier-0 agent runtime contract

To make Tier-0 baselines reproducible across runs, the agent receives **the same raw material Recce ingests, minus Recce's structured surfacing**. This isolates "what Recce contributes" from "what the agent could have figured out from artifacts alone." A weaker Tier-0 setup (e.g., diff-only, no artifacts) would understate the agent's solo capability and overstate Recce's signal.

**Inputs per fixture** (populated by `build_fixtures.sh`):

- `fixtures/<id>/diff.patch` — source-model diff between base and head
- `fixtures/<id>/artifacts/manifest-before.json`, `manifest-after.json` — dbt manifests pre/post
- `fixtures/<id>/artifacts/compiled-before/`, `compiled-after/` — compiled SQL trees pre/post
- `fixtures/<id>/artifacts/catalog-before.json`, `catalog-after.json` — schema-only (row/col stats are zero in this fixture set; documented in the fixtures README)
- Read access to the dbt project source at the head SHA — materialized **per fixture** by `build_fixtures.sh` at `evals/agent-blind-spots/.tmp/sources/<id>/`. The shared clone at `.tmp/jaffle_shop_golden/` is build-script scratch; do NOT read from it because the build loop leaves it at the last fixture's SHA.

**Generic tools allowed at Tier 0:** file read, grep / ripgrep, `jq`, `git log` / `git diff` / `git show` against the per-fixture source tree at `.tmp/sources/<id>/`. Anything the agent could plausibly run on a developer's laptop without Recce installed *and without regenerating any frozen Tier-0 input*.

**Explicitly NOT allowed at Tier 0:** Recce CLI, Recce MCP, any `/recce-*` skill (including `/recce-verify`), warehouse access, `dbt run`, `dbt test`, `dbt parse`, `dbt compile`, `dbt docs generate`, live SQL execution, or any other command that regenerates the manifest/compiled/catalog artifacts. The artifacts under `fixtures/<id>/artifacts/` are the **frozen Tier-0 inputs**; regenerating them lets the agent reach beyond the captured snapshot (e.g., picking up later upstream-package changes) and breaks reproducibility across runs. Also not allowed: comparison against a base/prod environment beyond what is already in the artifacts above.

**Agent view restriction (eval-runner contract).** The runner MUST restrict the agent's file-read access to `.tmp/sources/<id>/` (the per-fixture standalone repo from `build_fixtures.sh`). The agent MUST NOT be able to read `fixtures/<id>/README.md` (contains expected-verdict spoilers), `RUBRIC.md`, other fixtures' files, or anywhere else in the eval host repository. Enforcement is runner-specific (`.claude/settings.json` PreToolUse hook for Claude Code, `--sandbox` + PATH scrub for Codex) — see [`ENFORCEMENT.md`](ENFORCEMENT.md) for the recipes and the sandbox profile templates in [`runner-configs/`](runner-configs/). The mechanism used for each baseline MUST be recorded in `templates/tier-0-baseline.md`'s Notes section — without that record, the baseline is unreproducible and disqualified.

**Prompt shape** — eval runners write the actual prompt and **MUST record it verbatim** in the Tier-0 baseline's "Prompt given to agent" section, including any agent-specific framing. To keep baselines comparable across runs:

- The prompt MUST describe the inputs above without paraphrasing what each contains (re-describing the inputs primes the agent in ways that vary between runners).
- The prompt MUST ask for catch / miss / partial and approve / request-changes / abstain in those terms.
- The prompt MUST NOT add steering language toward humility ("be cautious about flagging issues", "only flag when you're confident") OR aggression ("find as many issues as possible", "be thorough"). Use neutral framing; "review this PR" is enough.
- Agent-specific scaffolding (file-access mode, tool whitelisting, system prompt) is allowed but must be recorded in the baseline's Notes section so the delta is interpretable.

A reference shape that satisfies the constraints:

> "Review this dbt PR. The inputs listed in the Tier-0 runtime contract are available. Decide catch / miss / partial per the rubric, recommend approve / request-changes / abstain, and write verdict + verbatim reasoning into `tier-0-baseline.md`."

## Per-fixture artifact

Each fixture's scoring lives in `runs/<YYYY-MM-DD>/<pr-id>-scoring.md` with this structure:

```markdown
# Fixture <pr-id> — <one-line title>

- Tier-0 baseline (frozen): <link to fixtures/<pr-id>/tier-0-baseline.md>
- Run date: <YYYY-MM-DD>
- Agent / model: <name>
- Primary evidence tier + subset: <0 | 1a | 1b | 1c | 2>  (what the agent *actually used*; `1c` only with a cited query result — see lens 2)
- Binary catch (this run): <catch | miss | partial>  (scored against the decisive issue — see lens 1)
- Binary catch (Tier-0 baseline): <catch | miss | partial>
- Delta: <`n/a` for a Tier-0 cell · `baseline → this run` (e.g. `miss → catch`) · or `confounded (run variance — no Recce evidence cited)` per the lens-3 Recce-attribution rule>

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

## Waffle log (DRC-3585, 2026-06-09)

Every place a grader waffled during the hand-graded rubric-lock run, and how the rubric now resolves it. "Rubric" entries changed the rules above; "harness/fixture" entries are recorded here and routed to the gap report (DRC-3405) — they are not rule changes. Source traces: `runs/2026-06-09/traces/`; first-grade log + verdicts: `runs/2026-06-09/`.

| # | Type | Where the grader waffled | Resolution |
|---|------|--------------------------|------------|
| **W1** | rubric | The judge produced a *delta* for Tier-0 cells (`same` vs `improvement` across two passes), but a Tier-0 cell has no with-Recce comparison. | Lens 3: delta is recorded **only on Tier-1+ cells**; a Tier-0 cell's delta is `n/a`. |
| **W3** | rubric | `catch` vs `partial` was undefined for multi-issue PRs (`pr46` has ≥3 issues; `pr3` has 3 sub-issues). "Missed half" is unmeasurable. | Lens 1: score against the single **decisive issue**, named per fixture. catch/partial/miss defined relative to it. |
| **W5** | rubric | The judge labelled `pr1` Tier-1 evidence `1c` though the agent ran **no** query — it only *named* `value_diff`/`profile_diff`. Evidence-tier was being credited by availability, not use. | Lens 2: evidence tier = what was **actually used**; `1c` requires a **cited query result**. A Tier-1 cell can score evidence-tier `0`. |
| **W7** | rubric | On `pr3` and `pr44` the verdict differed between Tier-0 and Tier-1, but **Recce was not invoked in either** — the shift was stochastic run variance, not a Recce effect. The rubric invited attributing it to Recce. | Lens 3: **Recce-attribution rule** — a delta is Recce-attributable only if the with-Recce run cites a Recce tool result as decisive; else record `confounded (run variance)`. |
| **W2** | harness/fixture | `pr44`'s default cell evaluates the **benign head** (two new columns, no filter). The intended blind-spot — the `where has_promoted_orders = true` row filter at intermediate commit `23b96ca` — is never staged. | Run a separate `pr44-intermediate` cell that stages `diff-from-base-to-intermediate.patch` + `artifacts/intermediate-commit-23b96ca/`. → gap report. |
| **W4** | harness/fixture | Tier-1 fixtures are built with `dbt docs generate --empty-catalog` → no row data, so `1c` (structured queries) cannot fire on data, and single-env Recce cannot show before/after deltas (those need a base env = Tier 2). | Out of v1 rubric scope; the eval base needs a materialized dev env before Tier-1 can exercise `1c`. → gap report #1. |
| **W6** | harness/fixture | In the spike-driver run the agent prompt was the neutral "review this PR" for **both** tiers (never invokes `/recce-verify`), and the Recce MCP server was **permitted but not configured/running** in the cells ("MCP isn't available"). So no cell exercised Recce. | The spike driver de-risks judge + sandbox, not skill fidelity. A faithful DRC-3405 Tier-1 must invoke `/recce-verify` against a reachable Recce MCP + materialized env. → gap report #1. |
| **W8** | harness/fixture | Verdicts on `pr3` and `pr44` flipped on **SQL dialect**: the per-fixture tree ships the upstream Snowflake `profiles.yml` while the artifacts are DuckDB-compiled, so the agent's verdict depends on which it anchors to. No single ground truth. | Make each fixture internally dialect-consistent (drop/replace `profiles.yml` in `.tmp/sources/`, or state the dialect in the prompt). → gap report. Feeds the W7 variance. |

**Net effect on graded outcomes.** All 6 Tier-0 baselines were gradeable; 5 scored `catch`, 1 (`pr3`) `partial`. All 12 cells used evidence-tier `0` (Recce never fired). No fixture produced a Recce-attributable delta. These are the inputs to the DRC-3405 gap report, whose #1 item is W4+W6 (the eval base does not yet exercise Recce).
