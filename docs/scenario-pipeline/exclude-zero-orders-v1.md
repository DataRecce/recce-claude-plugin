---
id: "001"
title: "Exclude $0 Orders: filter on subtotal"
status: integrated
assignee: kent
source: commission seed
started: 2026-03-30T16:00:00+08:00
completed: 2026-03-30T18:00:00+08:00
verdict: PASSED
score: 0.8
worktree:
issue:
pr:
jaffle_issue: 8
patch_file: plugins/recce-dev/skills/recce-eval/scenarios/v2/patches/r8-exclude-zero-orders-wrong-column.patch
scenario_yaml: plugins/recce-dev/skills/recce-eval/scenarios/v2/r8-exclude-zero-orders-wrong-column.yaml
prompt_file:
---

## Bug Variant

**Source issue**: jaffle-shop-simulator#8 — VP of Operations requests excluding complimentary ($0) orders from all mart models.

**Plausible bug**: Filter on `WHERE subtotal > 0` instead of `WHERE order_total > 0` in stg_orders. The PR uses the wrong column — subtotal (pre-tax item total) instead of order_total (amount charged). With current data both produce identical results (all 4,155 zero-total orders also have zero subtotal), making it a semantic/spec deviation bug.

**PR description**: "Filter out $0 comp orders at staging layer — add WHERE subtotal > 0 to stg_orders for clean downstream metrics"

**Why it's hard**: Data comparison shows correct results. The bug is a specification deviation, not a data correctness issue. Agent must compare PR code against the issue spec to catch the wrong column.

**Ground truth**: 4,155 rows filtered. stg_orders/orders lose rows. customers affected (236 have lower count_lifetime_orders). order_items unchanged (comp orders have no line items). Dashboard impacted (AOV changes).

**Difficulty**: hard — detection requires spec comparison, not just data comparison.
