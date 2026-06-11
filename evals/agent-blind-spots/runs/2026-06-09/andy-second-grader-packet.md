# Second-grader packet — DRC-3585 rubric lock (for Andy)

**Goal:** independently grade the same 12 traces I (first grader) graded, using the locked rubric, so we can measure inter-rater agreement. DRC-3585 acceptance target: **≥90% agreement on the three axes**. The rubric is *provisionally locked* until this holds.

**~30–40 min.** Grade first, compare second — please don't read my verdicts until your sheet is filled in (they're deliberately not in this file).

## What you're grading

12 cells = 6 fixtures × Claude Code × {Tier-0, Tier-1}, all `claude-opus-4-8`. One agent PR-review transcript per cell.

- **Traces:** `runs/2026-06-09/traces/<fixture>_claude_t{0,1}.md` (12 files). Each ends with a `VERDICT: <catch|miss|partial> · <approve|request-changes|abstain>` line — that's the *agent's self-report*; your job is to grade it, not copy it.
- **Rubric:** `evals/agent-blind-spots/RUBRIC.md` — read the three lenses + the **Waffle log** (the W1/W3/W5/W7 clarifications are the whole point of this exercise). Key rules to apply:
  - **Lens 1 (catch):** score against the **decisive issue** named per fixture (RUBRIC.md lens 1).
  - **Lens 2 (evidence tier):** what the agent **actually used**, not what was permitted. `1c` only if the transcript shows a real query result. (In this run Recce was not reachable — expect tier `0` throughout.)
  - **Lens 3 (delta):** `n/a` for Tier-0 cells; for Tier-1, `confounded` unless the transcript cites a Recce tool result as decisive.
- **Fixture intent (for the decisive issue only):** you may read `fixtures/<id>/README.md` for what each PR does — but note those READMEs contain *expected-verdict anchors* written before this run; treat them as context, not answer keys (several were exceeded).

## Grading sheet (fill in)

| Cell | catch (catch/miss/partial) | evidence tier (0/1a/1b/1c/2) | delta (n/a / x→y / confounded) |
|------|----------------------------|------------------------------|--------------------------------|
| pr1-fix-clv · t0 | | | n/a |
| pr1-fix-clv · t1 | | | |
| pr2-refactor-cte-to-models · t0 | | | n/a |
| pr2-refactor-cte-to-models · t1 | | | |
| pr3-amount-double-to-decimal · t0 | | | n/a |
| pr3-amount-double-to-decimal · t1 | | | |
| pr42-is-closed-filter · t0 | | | n/a |
| pr42-is-closed-filter · t1 | | | |
| pr44-promotion-flags · t0 | | | n/a |
| pr44-promotion-flags · t1 | | | |
| pr46-net-clv-segments · t0 | | | n/a |
| pr46-net-clv-segments · t1 | | | |

## After you grade — compare

My first-grade verdicts:
- **Tier-0 catch** (the 6 frozen baselines): `fixtures/<id>/tier-0-baseline.md` → "Verdict" section.
- **Tier-1 catch + evidence + delta** (the 6 case studies): `runs/2026-06-09/<id>-scoring.md`.
- **Full first-grade log + per-axis reasoning:** ask Even / see the DRC-3585 PR description.

Agreement = (cells where your axis value == mine) / (gradeable cells), per axis. Tier-0 delta is `n/a` for both, so the delta axis is measured on the 6 Tier-1 cells.

## Known boundary I expect us to discuss

`pr3` Tier-0: the agent approved a money-column type change. I graded **partial** (it missed the downstream incremental schema-drift risk that the Tier-1 run found); the LLM judge graded it **catch**. This is the catch/partial boundary lens-1's decisive-issue rule (W3) is meant to settle — if we diverge here, that's the rule to sharpen. If we agree, the rule holds.

## If agreement < 90%

Each disagreement is a rubric gap, not a grading error. Log it as a new waffle point, sharpen the relevant lens rule in RUBRIC.md, re-grade only the affected cells, and re-measure. Lock only when ≥90% holds on all three axes.
