# Fixture `pr44-promotion-flags` — Add promotion payment flag + customer has-promotion flag

- Source PR: [DataRecce/jaffle_shop_golden#20](https://github.com/DataRecce/jaffle_shop_golden/pull/20)
- Base SHA: `f09861a39b314907719260f19f7d6ef2fd347ab0`
- Head SHA: `bd407ac2a40ce52cc24ee9c40393e9412706c4e3`
- Verification class: **schema-expansion + (intermediate row-filter accident)**
- Models touched: `stg_payments`, `customers` (2 files at head)

## What the PR does (head state)

Two schema additions at head:

1. `stg_payments` gains an `is_promotion` column derived as `payment_method = 'coupon'`.
2. `customers` gains a `has_promoted_orders` column, computed via `boolor_agg(is_promotion)` in the `customer_payments` CTE, surfaced in the final select.

At head, no row filter is present in `customers.sql`. Schema and lineage both expand; no rows are dropped.

## The intermediate-commit accident (the interesting bit)

PR #20 has four commits. The interesting case for this eval is **not** the head state — it is the state after commit `23b96ca02b` ("Add promotion information"), which:

- Added the two schema columns as described above.
- **Also added** `where has_promoted_orders = true` at the bottom of the `customers.sql` final CTE.

That `where` clause means: only customers with at least one coupon-paid order remain in the `customers` model. Every customer who paid by card / bank-transfer / gift-card with no coupon ever is dropped.

Commit `1500eb444c` ("Remove where condition") reverted the filter — but only because the author re-read their own diff. An agent reviewing commit-by-commit (or any reviewer who looks only at the first commit's preview before more were pushed) would face the same row-filter trap as `pr42-is-closed-filter`, packaged inside what looks like a benign schema-expansion PR.

Artifacts for both states are produced by `build_fixtures.sh` (not committed):

- `artifacts/manifest-after.json` + `artifacts/compiled-after/` — head (`bd407ac`). Schema expansion only, no row drop.
- `artifacts/intermediate-commit-23b96ca/` — the problematic intermediate. Same schema additions **plus** the row filter.
- `diff-from-base-to-intermediate.patch` (committed, top-level) — the diff `base..23b96ca` so the eval can present the intermediate commit as if it were the PR head.

## Why this is a "schema-expansion + accidental row filter" case

The dangerous pattern is the *combination*. A new column is a low-stakes change; reviewers tend to approve it on diff alone. Wrapping a row filter inside the same commit hides the filter behind the schema noise. Recce's row-count diff is the cheap, decisive signal that catches it.

## Expected agent verdict — Tier 0 (no Recce)

Anchor — what the Tier-0 baseline run *should* look like; not a live run record. **Run separately against each of the two artifact snapshots; the headline finding is the contrast between them.**

### Against head (`bd407ac`)

- Likely catch quality: **catch** (correctly approves schema expansion).
- Reasoning: agent sees two new columns, no `where` clause introduced, approves with a note about new columns.

### Against intermediate (`23b96ca`)

- Likely catch quality: **miss** or **partial**.
- The agent sees a schema-expansion diff that *also* contains `where has_promoted_orders = true`. Diligent agents catch the filter; many will read the diff as "adds promotion flags" and miss the trailing two lines.
- Without row counts they cannot quantify impact.

## Expected agent verdict — with Recce

### Against head (`bd407ac`)

- Likely catch quality: **catch**.
- Evidence Recce should surface: schema diff showing two new columns, row count unchanged.
- Conclusion: "Approve — schema expansion, no row impact."

### Against intermediate (`23b96ca`)

- Likely catch quality: **catch**.
- Evidence Recce should surface: schema diff (new columns) **and** row-count diff on `customers` showing a large drop.
- Conclusion: "Block — accidental row filter introduced in the same commit as the schema expansion. Either remove `where has_promoted_orders = true` or scope the new column to a separate downstream model."

## Caveats

- The PR has **four commits**, not one. Per the spec, the row-filter case lives in the middle. The eval runner has the choice to (a) treat `head` as the canonical PR (clean schema expansion, no row drop) or (b) replay commit `23b96ca` as the PR head to exercise the row-filter case. The author of the spec wanted **both**.
- Tier-2 (base comparison) gives the cleanest evidence, but the row-filter trap is also visible from single-env Recce: a row count of `customers` against the dev environment's prior state would surface the drop. Whether the agent can construct that comparison without a base env is itself a case-study question.
- `boolor_agg` is a Snowflake function. The fixture build pipeline overrides the dbt profile to DuckDB for offline compile; DuckDB accepts `bool_or` as the canonical aggregate. The compiled SQL captured in `compiled-after/` will show `boolor_agg` as written in source — note this in the agent prompt if the eval runs a DuckDB-backed Recce.
- Reproducible without warehouse: yes for compile artifacts. Schema diff and lineage diff are visible; row-count diff requires a live env, which v1 Tier-1 single-env Recce can do against any dev DB.
