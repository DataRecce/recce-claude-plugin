# Eval — Agent Blind Spots / `/recce-verify` v1

Qualitative case-study eval for the `/recce-verify` skill v1.

## What this is

Six PR fixtures from `DataRecce/jaffle_shop_golden` exercising distinct verification classes (semantic, row-grain, refactor, type, schema-expansion, multi-model). Each fixture produces one structured case study viewed through three lenses (binary catch, primary evidence tier, counterfactual delta against a frozen agent-only baseline) — these are observation axes, not metrics; **do not aggregate them**. Output is an action-prioritized gap report (target ≤5 entries, with an overflow path) that gates v1 backend additions.

## Why qualitative, not quantitative

N=6 PRs is too small for statistics. The eval is a **named-case narrative**, not a leaderboard. Presenting it as "X% accuracy" or "Y% improvement" overstates rigor and breaks credibility with Super / 205DataLab. The rubric is built around case studies; resist the temptation to aggregate.

## Layout

```
evals/agent-blind-spots/
├── README.md            ← this file
├── RUBRIC.md            ← scoring rules; read before adding or scoring fixtures
├── build_fixtures.sh    ← rebuilds the gitignored artifacts/ per fixture (DRC-3402)
├── fixtures/            ← one directory per PR fixture
│   ├── README.md               ← fixture-set caveats + build instructions
│   └── <pr-id-slug>/
│       ├── README.md           ← what the PR does + expected verdicts
│       ├── tier-0-baseline.md  ← frozen agent-only verdict (template in templates/)
│       ├── commits.txt         ← base + head SHAs read by build_fixtures.sh
│       ├── diff.patch          ← small source-models diff base..head (committed)
│       └── artifacts/          ← gitignored; produced by build_fixtures.sh
├── templates/
│   ├── tier-0-baseline.md      ← per-fixture frozen baseline template
│   └── gap-report.md           ← gap-report template (target ≤5 entries)
└── runs/
    └── <YYYY-MM-DD>/
        ├── gap-report.md           ← filled gap report for the run
        └── <pr-id>-scoring.md      ← per-fixture scoring per RUBRIC.md
```

Before any eval run, build the gitignored artifacts:

```bash
cd evals/agent-blind-spots && ./build_fixtures.sh
```

See [`fixtures/README.md`](./fixtures/README.md) for the full per-fixture caveats (PR #16 merge head, PR #20 intermediate trap, PR #46 stress test, empty-DuckDB catalog stats, PR #14 older base) and pinned versions.

## How to run

1. Pick a fixture in `fixtures/`.
2. If `tier-0-baseline.md` is missing, run the agent in Tier-0 mode (no Recce) and capture the verdict per the template. The baseline file is **frozen at commit**: the commander commits it (per the workspace's normal change-control flow) before authorizing the with-Recce run, and the baseline must not be edited afterwards even if later evidence suggests revision.
3. Run the agent with `/recce-verify` available.
4. Score the run in `runs/<YYYY-MM-DD>/<pr-id>-scoring.md` using `RUBRIC.md`.
5. Once all six fixtures are scored, fill `runs/<YYYY-MM-DD>/gap-report.md` (action-prioritized; target ≤5 entries, exceed-with-rationale allowed).

## References

- Project: [Agent-blind spots: /recce-verify v1](https://linear.app/recce/project/agent-blind-spots-recce-verify-v1-d2bb2d77bff8)
- Rubric source: [DRC-3403](https://linear.app/recce/issue/DRC-3403)
- Fixture set: [DRC-3402](https://linear.app/recce/issue/DRC-3402)
- Skill: [DRC-3404](https://linear.app/recce/issue/DRC-3404)
- Notion: [Single-env Capability Breakdown](https://www.notion.so/35a79451d357807ba2befc365cb74217)
