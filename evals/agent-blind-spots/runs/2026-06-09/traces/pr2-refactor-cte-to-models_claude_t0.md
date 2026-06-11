# Cell: pr2-refactor-cte-to-models · claude · tier-0
# model: claude-opus-4-8
# returncode: 0

## stdout
The after-catalog is empty (no nodes) — consistent with the note that catalog is schema-only and `dbt docs generate` wasn't run against a live warehouse (`TARGET_EXISTS=false`). So the **compiled SQL is the authoritative evidence**, and I've fully traced it. I have everything I need.

## Review: `pr2-refactor-cte-to-models`

### What the PR does
Extracts two CTEs out of `models/customers.sql` into standalone models and re-points `customers` at them via `ref()`:
- `customer_orders` CTE → `models/int_customer_orders.sql`
- `customer_payments` CTE → `models/int_customer_payments.sql`
- `customers.sql` collapses to a thin `select ... from stg_customers left join int_customer_orders left join int_customer_payments`.

### Correctness — behavior-preserving (verified)
I traced the compiled SQL before/after rather than trusting the source diff:

- **`customers` output is logically identical.** Before, `final` was `customers ⟕ customer_orders ⟕ customer_payments`; after, the same three relations are joined in the same order on the same keys, projecting the same 7 columns in the same order (`customer_id, first_name, last_name, first_order, most_recent_order, number_of_orders, customer_lifetime_value`). Compiled SQL confirms byte-equivalent join logic.
- **The extracted models are exact lifts of the CTEs.** `int_customer_orders` = the `min/max/count … group by customer_id` aggregation over `stg_orders`; `int_customer_payments` = `sum(amount)::bigint … stg_payments ⟕ stg_orders group by customer_id`. The original CTEs read from `orders`/`payments` aliases that were themselves `select * from stg_orders`/`stg_payments`, so pointing directly at the staging models is equivalent.
- **No grain/fan-out risk introduced.** Both int models group by `customer_id` (unique grain), so the left joins from `customers` can't fan out — same as the original CTEs.
- **Downstream is safe.** The only consumers of `customers` are `customer_segments` (reads `number_of_orders`, `customer_lifetime_value`) and `customer_order_pattern` (reads `first_order`, `most_recent_order`, `number_of_orders`). All those columns survive unchanged, and neither downstream model is in the diff.

A row-level / value diff on `customers` would show **zero change** — which is exactly why this PR is a blind-spot trap: the data is safe, but the diff is not a no-op on the warehouse.

### The real side effect a careful reviewer should flag
- **The two new `int_*` models materialize as `table`, not ephemeral.** `dbt_project.yml` sets `models: jaffle_shop: materialized: table` for everything outside `staging/`, and neither new file carries a `{{ config(...) }}` override. So a refactor that *looks* purely logical actually adds **two new physical tables** to the warehouse and two extra build steps. If the intent was a pure logical decomposition (the usual reason to "CTE → model"), these should likely be `materialized: ephemeral` (compiles back inline, zero warehouse footprint) — or at minimum a deliberate choice. This is the consequence that a static "looks equivalent → approve" skim misses.
- **No tests or docs for the new models.** `schema.yml` was not touched, so `int_customer_orders` / `int_customer_payments` ship with no `unique`/`not_null` on `customer_id` and no descriptions. Promoting CTEs to first-class models is the moment to add at least grain tests. (Caveat: the original CTEs weren't tested either, so this is a missed-opportunity, not a regression.)
- **Minor convention nit:** `int_`-prefixed models sitting in `models/` root rather than an `intermediate/` subdirectory.

### Recommendation
The change is correct and behavior-preserving — `customers` and all downstream tables produce identical data. The findings (materialization-as-table, missing tests/docs) are convention/quality, not correctness, and don't block. **Approve** with non-blocking suggestions: set the int models to `ephemeral` (or confirm table is intended) and add minimal `unique`/`not_null` grain tests on their `customer_id`.

One honesty caveat on evidence: the catalog artifacts are empty/schema-only and no warehouse run was available, so I'm asserting equivalence from compiled-SQL tracing, not from an executed value diff. For a deterministic aggregation+join like this, logical equivalence of compiled SQL is sufficient; if you want belt-and-suspenders, a Recce `value_diff` on `customers` post-build would empirically confirm zero rows changed.

VERDICT: catch · approve


## stderr
[33mPermission deny rule "MultiEdit" matches no known tool — check for typos.[39m

