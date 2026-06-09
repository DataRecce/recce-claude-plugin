# Fixture `pr46-net-clv-segments` — Net revenue, net CLV, customer segments

- Source PR: [DataRecce/jaffle_shop_golden#2](https://github.com/DataRecce/jaffle_shop_golden/pull/2)
- Base SHA: `f09861a39b314907719260f19f7d6ef2fd347ab0`
- Head SHA: `297eb54e868f7f6070cc1d2bb6a46aade7cc97b1`
- Verification class: **multi-model semantic**
- Models touched: `stg_payments`, `customers`, `customer_segments`, `finance_revenue` (new), schema YAML (2 files)

## What the PR does

The most behavior-rich PR in the fixture set. Multiple co-changed models, each with its own semantic concern:

1. **`stg_payments`** gains a `coupon_amount` column: `(payment_method = 'coupon')::int * (amount / 100)`. Pure schema add — no row impact.

2. **`customers`** is rewritten more than the diff suggests:
   - The intermediate `customer_payments` CTE renames `total_amount` → `gross_amount` and adds `net_amount = sum(amount - coupon_amount)`.
   - The join is qualified with `and orders.status = 'completed'` — silently introducing the same "completed-only" semantic as PR #13 but inside the join condition (not a `where`).
   - Adds `where payments.amount is not null and payments.amount > 0` — two row filters on the payments side of the join, before aggregation.
   - The final select **renames** the user-visible `customer_lifetime_value` to be sourced from `gross_amount` (was `total_amount`), and adds `net_customer_lifetime_value` from `net_amount`. The column name `customer_lifetime_value` is preserved at the model boundary; its definition changed underneath.

3. **`customer_segments`** adds `net_customer_lifetime_value` and a new `net_value_segment` column with the same threshold logic as the existing `value_segment` but on the net value. Also adds several `not_null`, `accepted_values`, and `relationships` tests.

4. **`finance_revenue`** (new model) — per-order gross and net revenue, joined with stg_orders.

5. **`schema.yml` (root and staging)** — extensive column/test additions to match new schema.

## Why this is a "multi-model semantic" case

Four distinct semantic risks, all in one PR, all packaged with new columns that look like additive schema expansion:

| Risk | Where it lives | Cheap detection |
|------|----------------|------------------|
| `customer_lifetime_value` redefined (now gross, only on completed orders) | `customers.customer_payments` CTE | value diff on `customer_lifetime_value` (preset check exists) |
| Negative / null amount payments dropped | `customers.customer_payments` CTE `where` clause | row count diff on `customers` if any negatives exist |
| New downstream `net_value_segment` thresholds copy-pasted from gross thresholds | `customer_segments` | semantic question — thresholds may not be appropriate for net |
| `finance_revenue` new model leaks into the DAG with no row-count check | new file | new node in lineage diff |

Several of these are easy to miss because the diff *looks like* "additive net-metrics feature" but contains in-place redefinitions of existing public columns.

## Expected agent verdict — Tier 0 (no Recce)

Anchor — what the Tier-0 baseline run *should* look like; not a live run record.

- Likely catch quality: **partial** (best case) or **miss** (typical).
- An agent will probably catch the new column / new model surface area and the obvious schema additions. It is unlikely to notice:
  - That `customer_lifetime_value` is a renamed alias of `gross_amount`, which itself is computed differently from `total_amount` because of the `orders.status = 'completed'` join filter and the `where amount > 0`.
  - That copying thresholds 1500 / 4000 from `value_segment` to `net_value_segment` is a semantic decision, not a mechanical one.
- The PR description (if the agent reads it) frames the work as "net CLV metrics," nudging the agent toward an approve.

## Expected agent verdict — with Recce

- Likely catch quality: **catch** if the agent specifically queries `customer_lifetime_value` value-diff; **partial** otherwise.
- Evidence Recce should surface:
  - **Schema diff** — new columns on `customers`, `customer_segments`, `stg_payments`; new model `finance_revenue`.
  - **Value diff on `customer_lifetime_value`** — mismatched (it now reflects gross-of-coupons on completed orders only). This is the decisive piece of evidence; the preset check in `recce.yml` already targets it.
  - **Row-count diff on `customers`** — unchanged (left join preserves rows).
  - **Lineage diff** — new node `finance_revenue` appears but has no downstream consumers in this PR.
- Expected conclusion: "Net-CLV addition is fine; the redefinition of `customer_lifetime_value` is the column change for downstream consumers. Request changes: either keep `customer_lifetime_value` semantics stable and name the new column distinctly, or version the column and bump the contract."

## Caveats

- This fixture is the **stress test** for the rubric's "binary catch" lens — it has at least three distinct issues, so `partial` is a likely verdict for both Tier-0 and with-Recce runs. The case-study Notes should enumerate which of the issues the agent caught, not collapse to a single verdict.
- The preset `value_diff` check in `recce.yml` covers `customer_lifetime_value` — Recce has a friendly target here.
- Reproducible without warehouse: yes. Compiled SQL diff captures all four model changes.
