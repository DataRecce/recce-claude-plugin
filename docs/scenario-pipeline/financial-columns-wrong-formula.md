---
id: "003"
title: "Financial Columns: wrong gross_profit formula"
status: draft
assignee:
source: commission seed
started:
completed:
verdict:
score: 0.6
worktree:
issue:
pr:
jaffle_issue: 6
patch_file:
scenario_yaml:
prompt_file:
---

## Bug Variant

**Source issue**: jaffle-shop-simulator#6 — Accounting Manager requests audit-compliant financial_orders model with proper terminology.

**Plausible bug**: Calculate `gross_profit = revenue_excl_tax - tax_collected` instead of `gross_profit = revenue_excl_tax - cost_of_goods_sold`. The formula subtracts tax instead of COGS — a classic accounting error that produces a number that looks like a margin but is completely wrong.

**PR description**: "Add financial_orders mart with audit-compliant columns — gross profit computed as revenue minus tax"

**Why it's subtle**: The PR creates a new model (not modifying existing ones), so there's no baseline to compare against. The formula `revenue - tax` produces positive numbers that look like reasonable margins. You need to know that gross_profit should use COGS, not tax.

**Detection requires**: Domain knowledge that gross_profit = revenue - COGS, then comparing against the correct calculation using supply_cost data. This scenario tests whether the agent applies accounting domain knowledge, not just data comparison.
