# Inter-rater proxy — Eval Run `2026-06-09` (DRC-3585)

The DRC-3585 rubric lock requires a **second grader** (Andy) to independently grade the same traces and reach ≥90% agreement on the three axes. That is an irreducibly-human step (see `andy-second-grader-packet.md`). This note records the **automatable proxy** that the spike driver provides in the meantime, per DRC-3586's design (`--judge-stability` + `--baseline-dir`).

## 1. Judge self-consistency (`--judge-stability`, two independent judge passes per transcript)

From the canonical 12-cell run (`spike-driver/summary.md`, `claude-opus-4-8` judge):

| Axis | Agreement | Verdict |
|------|-----------|---------|
| catch | **100%** (12/12) | stable |
| evidence tier | **75%** (9/12) | **below the 80% bar** |
| delta | **83%** (10/12) | marginal |

The judge is stable on the binary catch but **noisy on the evidence-tier axis** — it intermittently labels `1b`/`1c` where the agent used only tier-0 artifacts. Lens-2's W5 clarification ("evidence tier = what was actually used; `1c` requires a cited query result") targets exactly this noise.

## 2. Judge vs. human first-grade (catch axis, Tier-0 cells)

Computed directly from the frozen baselines (human) vs. the run-1 judge verdicts:

| Fixture (Tier-0) | Human (frozen baseline) | Judge (run 1) | Agree? |
|---|---|---|---|
| pr1-fix-clv | catch | catch | ✓ |
| pr2-refactor-cte-to-models | catch | catch | ✓ |
| pr3-amount-double-to-decimal | **partial** | catch | ✗ |
| pr42-is-closed-filter | catch | catch | ✓ |
| pr44-promotion-flags | catch | catch | ✓ |
| pr46-net-clv-segments | catch | catch | ✓ |

**Judge–human catch agreement: 5/6 = 83%.** The single divergence is `pr3`, where the judge credited the agent's approve-with-caveats as `catch` while the human graded `partial` (missed the incremental schema-drift risk). This is precisely the catch/partial boundary that lens-1's W3 decisive-issue rule now governs — and the empirical reason the judge cannot yet replace human grading at that boundary.

## 3. Conclusion for the rubric lock

- The judge is a usable **first-pass** screen on the catch axis (100% self-consistent) but **must be overridden by a human at the catch/partial boundary and on evidence-tier** (75% self-consistent, 83% vs human).
- This validates the DRC-3585 → DRC-3405 ordering: lock the rubric and freeze human baselines first; let the judge run the bulk pass but keep a human override at lens-1 boundaries and lens-3 deltas.

## 4. Resolution — second-grade closed via #42 review (2026-06-22)

The blind grade-first-compare-second pass described above and in `andy-second-grader-packet.md` was **deliberately not performed for v1**. Instead, #42's review-and-merge stands in for the second-grade sign-off (see the PR's reviewer/merge record).

This is a **waiver** of the ≥90% blind measurement, not an achievement of it — and the reason is substantive, not schedule:

- **Two of the three axes are degenerate in this run.** Recce was never exercised (gap report entry 1), so lens-2 (evidence tier) is `0` on all 12 cells and lens-3 (delta) is `n/a` on the 6 Tier-0 cells and `confounded` on the 6 Tier-1 cells. Inter-rater agreement on a constant column is trivially ~100% and measures nothing.
- **The one live axis has unstable ground truth on 2/6 fixtures.** `pr3` and `pr44` ship a Snowflake `profiles.yml` next to DuckDB-compiled artifacts, so the catch verdict flips with the assumed dialect (gap report entry 4) — and `pr3` is exactly the catch/partial boundary flagged as "expected to discuss" in the second-grader packet. There is no single correct answer to grade against there.
- A ≥90% number computed over this matrix would therefore be inflated and meaningless.

**What the rubric lock did validate:** the W5 and W7 guards fired correctly — W5 caught the judge hallucinating evidence tiers `1b`/`1c` where only tier-0 artifacts were used; W7 marked every Tier-1 delta `confounded` because no run cited a Recce tool result. The rubric was sharp enough to detect that this run measured nothing about Recce. That detection is the real v1 deliverable, not an agreement score.

**When to run the real second-grade:** after gap report entries 1 and 4 land (eval actually invokes `/recce-verify` against a reachable Recce MCP + a materialized dev env, on dialect-consistent fixtures), re-run the `andy-second-grader-packet.md` pass against a matrix where all three axes vary, and only then measure ≥90%.

## Reproducing the automated proxy

```bash
uv run evals/agent-blind-spots/spike-driver/driver.py --no-run \
  --run-dir evals/agent-blind-spots/runs/2026-06-09/spike-driver \
  --baseline-dir evals/agent-blind-spots/fixtures \
  --judge-stability --agents claude --model claude-opus-4-8
```

> Note: a re-judge run on 2026-06-10 hit transient `claude-opus-4-8` unavailability and returned `judge_error` on 10/12 cells (rate-limit during the nested judge subprocess calls). The numbers above are therefore taken from the complete run-1 judging (`spike-driver/summary-run1.md`) and direct computation against the frozen baselines, not from that partial re-run. Re-run the command above when Opus quota is free to regenerate the `--baseline-dir` summary section across all 6 Tier-0 cells with the **locked** rubric.
