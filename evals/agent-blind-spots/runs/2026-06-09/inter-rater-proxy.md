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

## Reproducing the automated proxy

```bash
uv run evals/agent-blind-spots/spike-driver/driver.py --no-run \
  --run-dir evals/agent-blind-spots/runs/2026-06-09/spike-driver \
  --baseline-dir evals/agent-blind-spots/fixtures \
  --judge-stability --agents claude --model claude-opus-4-8
```

> Note: a re-judge run on 2026-06-10 hit transient `claude-opus-4-8` unavailability and returned `judge_error` on 10/12 cells (rate-limit during the nested judge subprocess calls). The numbers above are therefore taken from the complete run-1 judging (`spike-driver/summary-run1.md`) and direct computation against the frozen baselines, not from that partial re-run. Re-run the command above when Opus quota is free to regenerate the `--baseline-dir` summary section across all 6 Tier-0 cells with the **locked** rubric.
