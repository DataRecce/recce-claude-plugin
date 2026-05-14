# Fixture `pr1-fix-clv` — Fix CLV to completed orders only

- Source PR: [DataRecce/jaffle_shop_golden#13](https://github.com/DataRecce/jaffle_shop_golden/pull/13)
- Base SHA: `f09861a39b314907719260f19f7d6ef2fd347ab0`
- Head SHA: `2abf877ec9d067f2169d1b690aefdd54a2b3d205`
- Verification class: **semantic**
- Models touched: `customers` (1 file, 1 line added)

## What the PR does

Adds `where orders.status = 'completed'` to the `customer_payments` CTE in `models/customers.sql`. The author frames it as a bugfix: previously, `customer_lifetime_value` summed payment amounts from *all* orders (including `placed`, `shipped`, `return_pending`, `returned`). With the fix it only counts payments tied to completed orders.

## Why this is a "semantic" case

The diff is one line, syntactically valid, and the schema (column names, types) is unchanged. An agent reading only manifest + git diff sees a filter being added inside a CTE. The intent — "should non-completed orders' payments count toward lifetime value?" — is a business semantic question, not a SQL correctness question. Whether this is a **fix** or a **regression** depends on the business definition of CLV, and on whether downstream consumers depended on the previous (looser) value.

## Expected agent verdict — Tier 0 (no Recce)

Anchor — what the Tier-0 baseline run *should* look like; not a live run record.

- Likely catch quality: **partial**.
- The agent will spot the new `where` clause from the diff and correctly identify it narrows the set of payments aggregated. It can describe the semantic change in prose.
- But without measuring rows or values it cannot say:
  - How many customers see their CLV change.
  - How big the per-customer value delta is.
  - Whether any customer's CLV drops to NULL because they have no completed orders.
- The agent is therefore likely to hedge ("this could be a bugfix or a behavior change depending on intent") rather than commit to a verdict.

## Expected agent verdict — with Recce

- Likely catch quality: **catch**.
- Evidence Recce should surface:
  - **Row-count diff on `customers`** — unchanged (every customer still appears; left joins preserve rows).
  - **Value diff on `customer_lifetime_value`** — non-trivial mismatch percentage; some customers' CLV drops, none rises.
  - **Query diff** on average CLV per first-order week (the preset check in `recce.yml`) — values shift downward.
- Expected conclusion: "The change reduces CLV for customers whose orders include non-completed statuses. This is intentional per the PR title but is a behavior change; downstream consumers of `customer_lifetime_value` should be notified."

## Caveats

- The PR's compiled `.sql` for `customers.sql` is the only file that changes; nothing in the manifest schema changes.
- `recce.yml` already defines `value_diff` and `query_diff` preset checks on `customer_lifetime_value`, which makes this fixture an unusually friendly target for Recce. Other fixtures will not have this advantage.
- Reproducible without warehouse: yes. `compiled-before`/`compiled-after` SQL diff captures the substantive change.
