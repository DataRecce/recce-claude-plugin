---
id: "002"
title: "Tax Summary: wrong tax base"
status: draft
assignee:
source: commission seed
started:
completed:
verdict:
score: 0.7
worktree:
issue:
pr:
jaffle_issue: 2
patch_file:
scenario_yaml:
prompt_file:
---

## Bug Variant

**Source issue**: jaffle-shop-simulator#2 — Accounting Manager requests a tax summary report with tax rate validation.

**Plausible bug**: Calculate effective tax rate as `tax_paid / order_total` instead of `tax_paid / subtotal`. Since `order_total = subtotal + tax_paid`, using order_total as the denominator systematically understates the tax rate (e.g., 6% appears as ~5.66%). The formula is mathematically valid — it's just dividing by the wrong base.

**PR description**: "Add tax rate validation — compute effective rate as tax collected divided by order total"

**Why it's subtle**: `tax_paid / order_total` is a reasonable-looking formula. The error is a common confusion between tax-inclusive and tax-exclusive bases. The resulting rates are close to correct (off by ~0.3pp) — easy to miss without comparing against expected rates.

**Detection requires**: Compare computed tax rate against expected rate per location, or verify that `tax_paid / subtotal` matches while `tax_paid / order_total` doesn't.
