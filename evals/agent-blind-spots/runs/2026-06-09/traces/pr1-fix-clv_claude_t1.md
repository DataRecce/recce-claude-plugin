# Cell: pr1-fix-clv · claude · tier-1
# model: claude-opus-4-8
# returncode: 0

## stdout
I now have everything I need. Both changed-file content and the frozen artifacts are clear. Let me write up the review.

## PR Review — `pr1-fix-clv`: filter `customer_payments` to completed orders

### What changed

A single line added to `models/customers.sql`, in the `customer_payments` CTE that feeds `customer_lifetime_value`:

```sql
 from payments
 left join orders on
      payments.order_id = orders.order_id

+    where orders.status = 'completed'
 group by orders.customer_id
```

Confirmed against `compiled-before/` vs `compiled-after/`: the *only* delta is the inserted `where orders.status = 'completed'`. No other models touched.

### Data-impact analysis

This is a semantic change to a headline business metric (CLV), and it is fully readable from the SQL even without row stats. Three distinct effects:

**1. CLV is silently narrowed to completed-order revenue.** `stg_orders.status` takes five values (`schema.yml` accepted_values: `placed, shipped, completed, return_pending, returned`). Before, `customer_lifetime_value` summed payments across *all* orders; now it counts **only `completed`**. That excludes `placed` and `shipped` orders — which are real, paid, in-flight revenue — not just refunded/returned ones. If the intent was "stop counting refunds," the correct predicate is `status not in ('returned','return_pending')`, not `status = 'completed'`. As written, the "fix" over-corrects and **under-counts** CLV.

**2. New NULLs in `customer_lifetime_value`.** `final` does `left join customer_payments`. Any customer whose orders are *all* non-completed now drops out of `customer_payments` entirely and gets `customer_lifetime_value = NULL` (previously a real number). This is a value→NULL transition for a subset of rows — exactly the kind of change downstream consumers and BI break on. Nothing guards it (see below).

**3. The metric is now internally inconsistent.** `number_of_orders`, `first_order`, and `most_recent_order` (from the `customer_orders` CTE) still span **all** orders, while `customer_lifetime_value` now spans **completed only**. After this PR a row can read `number_of_orders = 4` with `customer_lifetime_value = NULL`, or a CLV that reflects a different order population than the order counts beside it. That incoherence within a single table is a stronger defect than the filter itself, and it's not addressed.

(Side note — *not* a real effect here: putting a right-table predicate in the `WHERE` of a `LEFT JOIN` normally collapses it to an inner join. In this CTE the unmatched-payment rows landed in a `NULL` `customer_id` bucket that the downstream `final` left join already discarded, so the join-collapse changes nothing on its own. The material change is the status filter, not the join semantics. Worth not raising as the headline finding — it's a red herring.)

### Verification gap

- **No test covers this.** `manifest-after.json` shows the only tests touching `customers` are `unique`/`not_null` on `customer_id` and a `relationships` test from `orders`. There is **zero** coverage on `customer_lifetime_value`/`total_amount` — no `not_null`, no range/`accepted_values`. So the NULL introduction and the value drop pass CI silently.
- **Documentation is already loose:** `schema.yml` documents a column `total_order_amount`, but the model outputs `customer_lifetime_value`. Pre-existing, not introduced here, but it means there's no contract to anchor the metric's meaning.
- **I cannot quantify the impact from Tier-0 inputs.** `catalog-after.json` has empty `nodes`/`sources` (no row counts, no profiling), and the seed CSVs are stripped from the tree. So "how many customers lose value / go NULL, and by how much" is **not derivable** from what's frozen here. The right next step is a Recce data diff before merge: `value_diff` on `customers.customer_lifetime_value` (keyed by `customer_id`) plus a `profile_diff` to see the NULL-rate and total-CLV shift — that turns this from "looks risky" into a measured delta.

### Recommendation

**Request changes.** The change is plausibly motivated ("fix CLV") but the implementation has unintended breadth: it under-counts by excluding paid `placed`/`shipped` orders, introduces NULL CLV for customers with no completed orders, and leaves `number_of_orders` vs `customer_lifetime_value` computed on inconsistent order populations — all with no test guarding the metric. Before merge I'd want: (a) the intended CLV definition confirmed (why `= 'completed'` and not "exclude returns"?), (b) explicit NULL handling (`coalesce(..., 0)` or a `not_null` decision), (c) the order-population inconsistency resolved or justified, and (d) a Recce `value_diff`/`profile_diff` attached showing the actual row/value impact.

This defect is catchable from the SQL alone — the trap is reading "fix-clv" + a tidy one-line `where status = 'completed'` and rubber-stamping it. The data impact is real and unverified.

VERDICT: catch · request-changes


## stderr

