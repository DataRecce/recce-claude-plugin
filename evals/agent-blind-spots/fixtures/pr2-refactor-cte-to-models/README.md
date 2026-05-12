# Fixture `pr2-refactor-cte-to-models` — Refactor CTEs into intermediate models

- Source PR: [DataRecce/jaffle_shop_golden#15](https://github.com/DataRecce/jaffle_shop_golden/pull/15)
- Base SHA: `f09861a39b314907719260f19f7d6ef2fd347ab0`
- Head SHA: `9c386b453ba7f5317784dc5c6ec03e48af0d4903`
- Verification class: **refactor (behavior-preserving, equality expected)**
- Models touched: `customers` (rewritten), `int_customer_orders` (new), `int_customer_payments` (new)

## What the PR does

Refactors `customers.sql` by extracting the two inline CTEs (`customer_orders` and `customer_payments`) into two new standalone intermediate models (`int_customer_orders.sql`, `int_customer_payments.sql`). The body of `customers.sql` is reduced from a ~70-line `with ... select` chain to a single 16-line `select ... left join ref(int_*) ...`.

No filters added, no columns added or removed, no aggregation logic changed. The DAG gets two new nodes between the staging layer and `customers`.

## Why this is a "refactor / equality-expected" case

This fixture is the **negative control** for the eval. A Recce-aware agent should *approve* this PR with high confidence and cite evidence that the refactor preserves behavior. A Recce-aware agent that flags this PR as risky has either misread the lineage change or is generating false alarms.

The verification question: can the agent (with Recce) confidently conclude "behavior preserved"?

## Expected agent verdict — Tier 0 (no Recce)

Anchor — what the Tier-0 baseline run *should* look like; not a live run record.

- Likely catch quality: **catch** (the easiest verdict in the fixture set, but for the wrong reason — usually pattern-matching on "refactor" in the commit message rather than verifying equivalence).
- The agent will recognize the structural rewrite from the diff and the manifest's new node count and assume behavior preservation based on shape alone. It cannot prove equivalence without comparing values.

## Expected agent verdict — with Recce

- Likely catch quality: **catch**.
- Evidence Recce should surface:
  - **Lineage diff** — two new nodes appear (`int_customer_orders`, `int_customer_payments`); `customers` now depends on them rather than directly on staging.
  - **Schema diff on `customers`** — unchanged columns.
  - **Row-count diff on `customers`** — unchanged.
  - **Value diff on `customer_lifetime_value`** — 100% match (the preset check in `recce.yml`).
- Expected conclusion: "Behavior-preserving refactor. Two intermediate models added; downstream `customers` is bit-for-bit identical. Approve."

## Caveats

- This fixture exercises the rubric's `catch → catch` "same" delta bucket, where the case-study Notes should record *what Recce showed that the Tier-0 verdict couldn't* — namely value-level equivalence. If both runs say "catch" but only the with-Recce run produces a 100% match receipt, that's the differentiating signal even though the binary catch didn't move.
- Reproducible without warehouse: yes.
