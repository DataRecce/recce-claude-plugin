# Fixture `pr42-is-closed-filter` — Add `is_closed` and filter orders

- Source PR: [DataRecce/jaffle_shop_golden#14](https://github.com/DataRecce/jaffle_shop_golden/pull/14)
- Base SHA: `62d6dc9367cb6a35fc56942ad437900f9c1fd8cb`
- Head SHA: `d2be60a0f338ef6bf5e1dcf143c5bc0a17a55060`
- Verification class: **row-grain**
- Models touched: `orders`, `stg_orders` (2 files)

## What the PR does

Two changes packaged together:

1. `stg_orders.sql` adds a new derived column `is_closed`, computed as `status = 'completed'`.
2. `orders.sql` (a) surfaces `is_closed` in the model's output, then (b) adds `where is_closed = true` at the bottom of the final CTE.

The net effect on `orders`: every row whose status is anything other than `completed` is dropped. The row grain of `orders` changes from "one row per order" to "one row per **completed** order." A new column also appears in the schema.

## Why this is a "row-grain" case

Both changes are syntactically clean. The compiled-after SQL still reads naturally. The verification question — "does the agent notice that the model now drops ~half the rows?" — depends on whether the agent reasons about set semantics from the new `where` clause, not on a SQL parse error.

Adding the `is_closed` column to the schema is a separate concern (downstream consumers that `select *` from `orders` now have an extra column). The row drop is the more dangerous of the two.

## Expected agent verdict — Tier 0 (no Recce)

Anchor — what the Tier-0 baseline run *should* look like; not a live run record.

- Likely catch quality: **partial** (best case) or **miss** (typical).
- An attentive agent reading the diff will see the new `where is_closed = true` and flag it. A less careful agent will frame the change as "adds an `is_closed` indicator," focusing on the schema addition and treating the filter as obvious / intentional.
- Without row counts the agent has no way to quantify the impact ("filters down to maybe 30% of orders? 90%?") and cannot point to a downstream consumer that breaks.

## Expected agent verdict — with Recce

- Likely catch quality: **catch**.
- Evidence Recce should surface:
  - **Row-count diff on `orders`** — large negative delta (every non-completed order is dropped).
  - **Schema diff** — new column `is_closed` on both `stg_orders` and `orders`.
  - **Lineage** — any model downstream of `orders` that depends on non-completed orders now silently sees fewer rows.
- Expected conclusion: "This PR drops X% of rows from `orders` because of the new `where is_closed = true` filter. The `is_closed` column itself is fine; the filter is the model-wide change. Either remove the filter or update the model's contract."

## Caveats

- Base SHA for this PR is `62d6dc936...`, an older `main` head before `f09861a` (`feat: add avg_order_amount to orders_daily_summary`). That earlier merge added two columns to `orders_daily_summary` that are absent in this fixture's base manifest. The other five fixtures use `f09861a` as base.
- Reproducible without warehouse: yes. The compiled SQL and the source diff make the filter visible.
