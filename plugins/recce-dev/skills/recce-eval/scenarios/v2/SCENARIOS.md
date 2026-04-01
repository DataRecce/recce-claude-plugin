# Eval V2 Scenarios

All scenarios are based on the [jaffle-shop-simulator](https://github.com/DataRecce/jaffle-shop-simulator) repository.

## Naming Convention

Scenario IDs follow the pattern: `{detection}-{NNN}-{bug-slug}`

- **detection**: `data` (requires data comparison to detect) or `code` (requires code review against spec)
- **NNN**: sequential number within each detection category
- **bug-slug**: human-readable description of the bug

## Evaluation Flow

Each scenario follows this flow:

1. **Base state** — clean repo with correct code → `dbt run` → correct data
2. **Apply patch in reverse** — introduces the bug (simulates a teammate's PR)
3. **Current state** — `dbt run` with buggy code → buggy data
4. **Agent reviews** the code diff + data diff between base and current
5. **Agent reports** findings as structured JSON

---

## data-001: Subtotal Tax Deduction

**GitHub Issue**: [#2 — Add Tax Summary Report and Cost Accounting Breakdown](https://github.com/DataRecce/jaffle-shop-simulator/issues/2)

**Story**: Accounting Manager asks to standardize subtotal as pre-tax. A teammate modifies `stg_orders.sql` to compute `subtotal - tax_paid`, claiming raw data includes tax in subtotal.

**Init state (buggy PR)**:
```sql
-- stg_orders.sql
{{ cents_to_dollars('subtotal') }} - {{ cents_to_dollars('tax_paid') }} as subtotal
```

**The bug**: Raw `subtotal` is **already pre-tax** (`order_total = subtotal + tax_paid`). Subtracting tax again double-deducts it, making subtotal systematically too low.

**What we expect the agent to find**:
- Issue found: **yes** — data drift
- Root cause: double tax deduction on an already pre-tax column
- Impacted: `stg_orders`, `orders`, `customers` (lifetime_spend_pretax uses subtotal)
- Not impacted: `order_items`, `products`
- Affected rows: **654,502** (all orders with non-zero tax)
- Dashboard impact: **yes** (subtotal is an Executive Dashboard column)
- Detection requires: **data comparison** — code looks mathematically reasonable

**Difficulty**: easy

---

## data-002: COGS Miscalculation

**GitHub Issue**: [#2 — Add Tax Summary Report and Cost Accounting Breakdown](https://github.com/DataRecce/jaffle-shop-simulator/issues/2)

**Story**: VP of Operations asks to review COGS accuracy. A teammate "optimizes" the order_items_summary CTE in `orders.sql` to only sum supply_cost for food items.

**Init state (buggy PR)**:
```sql
-- orders.sql
sum(case when is_food_item then supply_cost else 0 end) as order_cost
```

**The bug**: Drink supply costs account for **~59% of total COGS**. Filtering to food-only makes `order_cost` systematically too low for nearly all orders.

**What we expect the agent to find**:
- Issue found: **yes** — data drift
- Root cause: `order_cost` excludes drink supply costs due to `is_food_item` filter
- Impacted: `orders`
- Not impacted: `customers` (doesn't use order_cost), `order_items`
- Affected rows: **643,875** (98% — all orders with at least one drink item)
- Dashboard impact: **no** (order_cost is not an Executive Dashboard column)
- Detection requires: **data comparison**

**Difficulty**: medium

---

## data-003: Store Performance Order Count Fan-out

**GitHub Issue**: [#3 — Add Store Performance Metrics and Operational Efficiency Model](https://github.com/DataRecce/jaffle-shop-simulator/issues/3)

**Story**: Store Operations Manager requests per-location KPIs. A teammate creates a new `store_performance` mart that joins `orders` with `order_items` for product mix data, then aggregates by location.

**Init state (buggy PR)** — new file `models/marts/store_performance.sql`:
```sql
-- Joins orders ↔ order_items (one-to-many), then:
count(order_details.order_id) as total_orders           -- counts order_items rows!
sum(order_details.order_total) / nullif(count(...), 0)  -- deflated AOV
count(...) / nullif(days_since_opening, 0)              -- inflated orders_per_day
```

**The bug**: Classic **grain mismatch**. After joining orders with order_items (avg ~1.47 items/order), `count(order_id)` counts one row per order_item, not per order. This inflates `total_orders` ~47%, inflates `orders_per_day`, and deflates `avg_order_value`. Note: `sum(order_total)` and `count(distinct customer_id)` are unaffected by fan-out.

**What we expect the agent to find**:
- Issue found: **yes** — data drift
- Root cause: `count(order_id)` inflated by order_items join fan-out; needs `count(distinct order_id)`
- Impacted: `store_performance` (new model)
- Not impacted: all existing models (`orders`, `customers`, etc.)
- Dashboard impact: **no** (new model, not read by Executive Dashboard)
- Detection requires: **data comparison**

**Difficulty**: medium

---

## data-004: Supply Cost Perishable Ratio — Count vs Cost

**GitHub Issue**: [#4 — Add Supply Cost Analysis and Perishable Inventory Tracking](https://github.com/DataRecce/jaffle-shop-simulator/issues/4)

**Story**: Purchasing Manager requests supply cost analysis with perishable risk scoring — what percentage of supply **cost** is perishable per product.

**Init state (buggy PR)** — new file `models/marts/supply_analysis.sql`:
```sql
-- Named "perishable_cost_pct" but computed as:
sum(case when is_perishable_supply then 1 else 0 end)::float
    / nullif(count(*), 0) as perishable_cost_pct
```

**The bug**: The column is named `perishable_cost_pct` and the stakeholder asked for **cost percentage**, but the formula computes **item-count percentage** (number of perishable supply line items / total supply line items). Since perishable and non-perishable supplies have different cost distributions, the two metrics diverge significantly. The correct formula is `sum(perishable_cost) / sum(total_cost)`.

**What we expect the agent to find**:
- Issue found: **yes** — data drift
- Root cause: uses `count(*)` ratio instead of `sum(supply_cost)` ratio
- Impacted: `supply_analysis` (new model)
- Not impacted: all existing models
- Dashboard impact: **no**
- Detection requires: **data comparison** (compare count-based vs cost-based ratios)

**Difficulty**: medium

---

## data-005: Customer Segmentation — Broken Recency Logic

**GitHub Issue**: [#5 — Add Customer Segmentation and Engagement Analytics](https://github.com/DataRecce/jaffle-shop-simulator/issues/5)

**Story**: Marketing Manager requests customer segmentation with recency classification (Active ≤30d, At-risk 31–90d, Churned >90d since last order).

**Init state (buggy PR)** — new file `models/marts/customer_segments.sql`:
```sql
{{ dbt.datediff("customers.last_ordered_at", dbt.current_timestamp(), "day") }} as days_since_last_order
```

**The bug**: The dataset is **historical/simulated** — the most recent orders are months or years in the past. Using `current_timestamp` makes `days_since_last_order` hundreds of days for **every** customer, so all are classified as `"churned"`. Spend tiers and frequency segments are correct — only recency is broken. The correct approach is to use `max(ordered_at)` as the reference date.

**What we expect the agent to find**:
- Issue found: **yes** — data drift
- Root cause: `current_date` produces unrealistic recency on historical data; all customers are "churned"
- Impacted: `customer_segments` (new model)
- Not impacted: all existing models
- Dashboard impact: **no**
- Detection requires: **data comparison** (notice 100% churned distribution)

**Difficulty**: easy

---

## data-006: Financial Orders — Gross Profit Uses Tax Instead of COGS

**GitHub Issue**: [#6 — Rename Financial Columns in Orders Mart for Audit Compliance](https://github.com/DataRecce/jaffle-shop-simulator/issues/6)

**Story**: Accounting Manager (P1) requests a `financial_orders` audit mart with renamed columns and derived `gross_profit` (revenue − COGS) and `gross_margin_pct`.

**Init state (buggy PR)** — new file `models/marts/financial_orders.sql`:
```sql
-- Column renames are correct:
subtotal as revenue_excl_tax,
tax_paid as tax_collected,
order_total as total_incl_tax,
order_cost as cost_of_goods_sold,

-- But derived columns use wrong source:
subtotal - tax_paid as gross_profit,           -- should be: subtotal - order_cost
(subtotal - tax_paid) / nullif(subtotal, 0) as gross_margin_pct
```

**The bug**: Developer confused the renamed columns. `gross_profit` computes `revenue − tax` instead of `revenue − COGS`. This produces a completely different metric — margins appear inflated for low-cost products and deflated for high-cost products. Auditors would see wrong profitability numbers.

**What we expect the agent to find**:
- Issue found: **yes** — data drift
- Root cause: `gross_profit` uses `tax_paid` instead of `order_cost` (COGS)
- Impacted: `financial_orders` (new model)
- Not impacted: existing `orders` mart, `customers`, etc.
- Dashboard impact: **no** (Executive Dashboard reads from `orders`, not `financial_orders`)
- Detection requires: **data comparison**

**Difficulty**: easy

---

## code-001: Exclude $0 Orders — Wrong Column

**GitHub Issue**: [#8 — Exclude Complimentary ($0) Orders from All Mart Models](https://github.com/DataRecce/jaffle-shop-simulator/issues/8)

**Story**: VP of Operations escalates that ~4,155 complimentary orders inflate counts and dilute AOV. A teammate adds a `WHERE subtotal > 0` filter to `stg_orders.sql`.

**Init state (buggy PR)**:
```sql
-- stg_orders.sql (appended)
where subtotal > 0
```

**The bug**: The issue specification says `WHERE order_total > 0`, but the PR uses `subtotal > 0`. In the **current dataset**, `subtotal = 0 ↔ order_total = 0` for all rows, so data results are **identical**. The bug is purely **semantic** — wrong column choice that could silently break with future data (e.g., fully discounted orders with tax credit where subtotal != 0 but order_total = 0).

**Data impact**:
- stg_orders: 658,657 → 654,502 (−4,155 rows)
- orders: 658,657 → 654,502 (−4,155 rows)
- order_items: unchanged (comp orders have no line items)
- customers: same count, but 236 customers have lower `count_lifetime_orders`
- AOV: 10.9178 → 10.9871 (+0.63%)

**What we expect the agent to find**:
- Issue found: **yes** — spec deviation
- Root cause: filter uses `subtotal` instead of `order_total` as specified in the issue
- Impacted: `stg_orders`, `orders`, `customers`
- Not impacted: `order_items`, `products`
- Affected rows: **4,155**
- Dashboard impact: **yes** (order counts and AOV change)
- Detection requires: **code review** (data is identical between subtotal>0 and order_total>0)

**Difficulty**: hard — the agent must compare PR code against the issue spec, not just validate data correctness

---

## Summary Matrix

| ID | Bug Type | Modified/New | Difficulty | Detection | Dashboard? | Affected Rows |
|----|----------|-------------|------------|-----------|------------|--------------|
| data-001 | Double tax deduction | Modified `stg_orders` | easy | data comparison | yes | 654,502 |
| data-002 | Food-only COGS | Modified `orders` | medium | data comparison | no | 643,875 |
| data-003 | Join fan-out inflates counts | New `store_performance` | medium | data comparison | no | all rows |
| data-004 | Count ratio vs cost ratio | New `supply_analysis` | medium | data comparison | no | all rows |
| data-005 | current_date on historical data | New `customer_segments` | easy | data comparison | no | all rows |
| data-006 | Tax instead of COGS in formula | New `financial_orders` | easy | data comparison | no | all rows |
| code-001 | Wrong filter column (spec deviation) | Modified `stg_orders` | hard | code review | yes | 4,155 |
