# Gap Report — Eval Run `2026-06-09`

Action-prioritized shortlist from the v1 `/recce-verify` eval: **6 fixtures × Claude Code × {Tier-0, Tier-1}**, `claude-opus-4-8`, hand-graded against the locked rubric (DRC-3585). Receipts: `runs/2026-06-09/<pr-id>-scoring.md`, traces in `runs/2026-06-09/traces/`, frozen baselines in `fixtures/<id>/tier-0-baseline.md`, judge verdicts in `runs/2026-06-09/spike-driver/`.

> **Read this first — what the run actually measured.** Two structural findings reframe v1, and they change how the entries below should be read:
>
> 1. **The eval did not exercise Recce.** In every Tier-1 cell the agent invoked **zero** Recce tools — the driver's prompt is the neutral "review this PR" for both tiers (it never invokes `/recce-verify`), the Recce MCP server was permitted but **not configured/running** in the cells ("MCP isn't available", pr44/pr46 traces), and the fixtures carry **no materialized dev env** (built `--empty-catalog`). So measured **Tier-1 ≡ Tier-0**; no verdict change is attributable to Recce (waffle log W4/W6).
> 2. **The frontier agent alone clears the bar these fixtures set.** Opus 4.8 caught the decisive issue in **5.5 / 6** fixtures from static artifacts (diff + compiled SQL + manifest) — including the row-grain drop (`pr42`), the buried metric redefinition (`pr46`), and a real portability bug (`pr44`). On every fixture it *named* the Recce evidence it wanted (`value_diff`/`profile_diff`/`row_count`) and correctly noted it could not run it.
>
> **Therefore this is not yet a ranking of Recce *product* gaps** — the eval cannot produce that until it actually runs Recce against fixtures where the agent's own reasoning fails. The entries are ordered: fix the eval base first (1, 4, 5), then the genuine product signals the run did surface (2, 3).

## Prioritization criteria

Per `templates/gap-report.md`: judgment factors, not a formula — breadth across fixtures, whether a cheap fix exists, whether closing it would decisively change the agent's verdict, whether Super/205DataLab hit it on their first real PR. The "Cheapest fix" field is the dedup key; entries naming the same fix collapse.

## Entries

### 1. `eval-base-does-not-run-recce`

- Fixtures where this blocked the agent: **all 6** (every Tier-1 cell).
- Receipts: all six `*-scoring.md` ("Evidence Recce surfaced: None"); traces `pr1-fix-clv_claude_t1.txt`, `pr44-promotion-flags_claude_t1.txt` ("MCP isn't available"), `pr46-net-clv-segments_claude_t1.txt`.
- What the gap is, in plain terms: the eval never actually puts Recce in front of the agent, so it cannot measure whether Recce helps.
- Cheapest fix: **harness change** — (a) materialize a single-env dev DuckDB per fixture (`dbt seed && dbt run` at head) so Recce has data to introspect; (b) make the Tier-1 prompt invoke `/recce-verify`; (c) configure a reachable Recce MCP server in the Tier-1 cell. None is a Recce product change.
- Why this fix beats the others: until Tier-1 exercises Recce, **no** product-backend gap can be evidenced — this gates the entire DRC-3405 deliverable. It is the prerequisite, not a competing option.

### 2. `single-env-cannot-show-before-after-deltas`

- Fixtures where this blocked the agent: `pr1`, `pr42`, `pr46` (and `pr3` for downstream value impact).
- Receipts: `pr1-fix-clv-scoring.md`, `pr42-is-closed-filter-scoring.md`, `pr46-net-clv-segments-scoring.md` — in each the agent names the *magnitude* (rows dropped / CLV shift / segment migration) as the decisive missing evidence.
- What the gap is, in plain terms: the agents catch the *mechanism* of each regression from SQL, but the *magnitude* ("how many rows / how much value moved") needs a before-vs-after data comparison, which requires a base/prod environment.
- Cheapest fix: **honest single-env degradation** — `/recce-verify` should state plainly that single-env Recce surfaces CLL / AST / current-state profiling but **not** before/after deltas, and route magnitude questions to a base-env comparison. Over-promising a data diff it cannot produce is the failure mode.
- Why this fix beats the others: an MCP tool addition can't conjure a base env; building base-env comparison is the **v2 wedge** (Tier 2), explicitly out of v1 scope. The honest-degradation framing is the v1-shippable move and the clearest signal to route base-env comparison to the v2 / MCP-App backlog.

### 3. `single-env-recce-redundant-with-agent-hand-tracing-at-toy-scale`

- Fixtures where this blocked the agent: all 6 (it's why Tier-1 would likely ≈ Tier-0 even after fixing entry 1).
- Receipts: `pr1` (agent hand-traced the full downstream `customer_segments` rebucketing), `pr42` (agent walked the manifest `child_map` to prove `orders` is terminal), `pr2` (agent proved equivalence by tracing compiled SQL) — all the lineage/CLL work Recce's `1a`/`1b` would automate, done by hand.
- What the gap is, in plain terms: on a 6-model project a frontier agent can read every model and trace lineage by hand, so Recce's column-lineage / AST capabilities are redundant; their value only appears at a scale where hand-tracing breaks down.
- Cheapest fix: **skill-side prompt change + fixture scale** — scope `/recce-verify`'s value proposition to what Recce does *more reliably than hand-tracing at scale* (deterministic CLL across hundreds of models), and add eval fixtures from a realistically large project so the agent's own tracing fails. The current `jaffle_shop_golden` fixtures (6 models) structurally under-represent Recce's value.
- Why this fix beats the others: no MCP tool addition changes the outcome on toy fixtures; the binding constraint is fixture scale, not a missing capability.

### 4. `fixture-dialect-ambiguity-breaks-grading`

- Fixtures where this blocked the agent: `pr3`, `pr44`.
- Receipts: `pr3-amount-double-to-decimal-scoring.md` (t0 approve/Snowflake vs t1 request-changes/DuckDB), `pr44-promotion-flags-scoring.md` (t0 request-changes/DuckDB vs t1 approve/Snowflake).
- What the gap is, in plain terms: each fixture ships the upstream **Snowflake** `profiles.yml` next to **DuckDB**-compiled artifacts, so the agent's verdict flips depending on which it believes — there is no single correct answer to grade against.
- Cheapest fix: **fixture hygiene** — make each per-fixture tree internally dialect-consistent (drop/replace `profiles.yml` in `.tmp/sources/`, or state the dialect in the prompt).
- Why this fix beats the others: it is the root cause of the run-variance that confounds the lens-3 delta (waffle log W7/W8); no skill or backend change addresses it.

### 5. `pr44-intermediate-blind-spot-not-exercised`

- Fixtures where this blocked the agent: `pr44`.
- Receipts: `pr44-promotion-flags-scoring.md` Notes; `fixtures/pr44-promotion-flags/diff-from-base-to-intermediate.patch` (committed but unused).
- What the gap is, in plain terms: `pr44` was built to test a row-filter accident hidden in a schema-expansion PR, but the default cell reviews the benign head where the filter was already reverted — the actual blind-spot is never shown to the agent.
- Cheapest fix: **harness change** — add a `pr44-intermediate` cell that stages `diff-from-base-to-intermediate.patch` + `artifacts/intermediate-commit-23b96ca/`.
- Why this fix beats the others: the evidence already exists on disk (built by `build_fixtures.sh`); only the driver wiring to stage it is missing.

## Not promoted to this report

- **A specific new MCP tool (e.g. `warehouse_introspect`, `preview_diff`).** Not blocking any fixture *in this run* — the eval never reached the point of needing one because Recce wasn't exercised (entry 1). Reconsider after entry 1 lands. (Explicitly out of v1 per the project description.)
- **PostToolUse / Edit hooks, dry-run/cost preview (Layers 5/6).** Deferred to v2 — out of v1 scope; nothing in this run pointed at them.
- **Judge reliability hardening.** The Claude-as-judge was unreliable on the evidence-tier axis (75% self-consistency, < 80% bar) and over-credited `partial` cases as `catch` (judge said `catch` for `pr3` Tier-0; human graded `partial` → judge–human catch agreement 5/6 = 83%). This is why DRC-3585 gates DRC-3405 with human grading — captured in the rubric waffle log, not a product gap.
- **Codex coverage.** v1 shipped Claude-Code-only (decision 2026-06-09). The codex-cli runner is broken on 0.138.0 (`--ask-for-approval` removed; `--config` now takes `key=value` not a file path → use `CODEX_HOME`; new trusted-dir check needs `--skip-git-repo-check`). Subsumed by entry 1 (same harness-fix pass); not an independent product gap.
