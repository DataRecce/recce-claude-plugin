# Cell: pr44-promotion-flags · claude · tier-1
# model: claude-opus-4-8
# returncode: 0

## stdout
I now have a complete picture. Let me synthesize the review.

## PR Review: promotion flags (`is_promotion` / `has_promoted_orders`)

### What the PR does
Two additive changes, Snowflake adapter (`JAFFLE_SHOP_GOLDEN`):

| Model | Change |
|---|---|
| `stg_payments` | New boolean `is_promotion` = `payment_method = 'coupon'` |
| `customers` | New boolean `has_promoted_orders` = `boolor_agg(is_promotion)` rolled up per customer (+ a cosmetic blank-line removal in the join) |

No existing column is modified — `customer_lifetime_value`, `number_of_orders`, etc. are byte-for-byte unchanged in the compiled SQL.

### Correctness (static — there is no row data to profile)
The catalogs are empty (`"nodes": {}`) and row stats are zero, so I can't empirically diff distributions. Reasoning from the diff + compiled SQL + manifest:

- **Compiles on Snowflake.** `boolor_agg`, the `::bigint` cast, and the boolean comparison are all valid Snowflake. Compiled SQL shows the expressions pass through verbatim (no macro). `'coupon'` is in the `accepted_values` test for `payment_method`, so the predicate is meaningful (not dead).
- **Unqualified refs resolve cleanly.** In `customer_payments`, `is_promotion` and `amount` exist only on the `payments` side (not `stg_orders`), so the unqualified references are unambiguous.
- **No new fan-out.** `payments LEFT JOIN orders ON order_id` is 1:1 per payment; `boolor_agg` aggregates within the existing customer grouping. The new column inherits the model's established grain.

### Downstream impact — safe
`customers` feeds `customer_segments` and `customer_order_pattern`. Both select **explicit columns** (not `select *`) and consume only untouched fields. No enforced contracts anywhere, no exposures. The new columns are **not yet consumed** by anything. → Zero regression risk to current consumers.

### Non-blocking observations
1. **NULL vs FALSE.** `has_promoted_orders` is `NULL` (not `FALSE`) for customers with no payments — `boolor_agg` over an empty/all-null group yields NULL, and the left-join also misses no-payment customers. This *mirrors* the existing `customer_lifetime_value` NULL behavior, so it's consistent with the model's convention — but a boolean "flag" consumed later with `WHERE NOT has_promoted_orders` would silently drop those rows (three-valued logic). Worth confirming intent; `coalesce(..., false)` if FALSE is desired.
2. **Grain/naming.** The flag is derived from *payment method* (`coupon`) aggregated to the *customer*, but is named `has_promoted_orders` ("orders"). It means "customer made ≥1 coupon payment," not an order-level promotion. Loose, not wrong.
3. **Docs/tests not updated.** Neither `is_promotion` nor `has_promoted_orders` is added to `schema.yml`. (Pre-existing, unrelated drift: `customers` schema.yml still documents `total_order_amount` while the model emits `customer_lifetime_value`.)

### Validation gap
A complete data review would `profile_diff`/`value_diff` the new flag to confirm it isn't 100% NULL/FALSE (which would signal a broken predicate or absent coupon data). The frozen inputs carry no data and MCP isn't available, so that empirical step can't be run here — the static evidence is what supports the verdict.

### Recommendation
This is a clean, additive feature: existing columns untouched, downstream models unaffected, SQL valid for the target. The three observations above are clarifications/nits, not regressions — none justifies blocking. **Approve**, with the NULL-vs-FALSE intent and the missing docs noted as follow-ups.

VERDICT: catch · approve


## stderr

