# Fixture `pr3-amount-double-to-decimal` — Change payment amount from double to decimal

- Source PR: [DataRecce/jaffle_shop_golden#16](https://github.com/DataRecce/jaffle_shop_golden/pull/16)
- Base SHA: `f09861a39b314907719260f19f7d6ef2fd347ab0`
- Head SHA: `1c56861bf11eb1449eb6d357596d8ff015678c5b` (includes a `main` merge commit on top of `6ffc23f` — see drift note below)
- Verification class: **type / rounding drift**
- Models touched: `stg_payments` (1 file, 1 line)

## What the PR does

In `models/staging/stg_payments.sql`, replaces:

```sql
amount / 100 as amount
```

with:

```sql
(amount / 100)::DECIMAL(10,2) amount
```

The previous expression yields a floating-point type (Snowflake `NUMBER(38,4)` on integer division, but for the original raw cents column behaves like double). The new expression coerces to `DECIMAL(10,2)`.

## Why this is a "type / rounding" case

Three distinct sub-issues, none catastrophic individually:

1. **Precision narrowing.** `DECIMAL(10,2)` only fits values up to `99,999,999.99`. Any payment whose dollar value exceeds that overflows and the result is implementation-dependent (Snowflake errors; DuckDB may also error).
2. **Rounding behavior.** Casting `amount / 100` (e.g., `1234 / 100` in integer arithmetic) to `DECIMAL(10,2)` produces `12.34` instead of `12` or `12.3400000`. Whether this is the desired result depends on the upstream type of `amount`.
3. **Missing `as`.** The new statement is `(amount / 100)::DECIMAL(10,2) amount` — no `as`. Snowflake accepts an alias without `as`; this is a stylistic quirk, not a bug.

The downstream effect propagates through `customer_payments`/`gross_amount`/`customer_lifetime_value`. CLV is cast to `::bigint` further downstream, which truncates fractional cents — so the visible delta in CLV may be small or zero, masking the upstream type change.

## Expected agent verdict — Tier 0 (no Recce)

Anchor — what the Tier-0 baseline run *should* look like; not a live run record.

- Likely catch quality: **partial** or **miss**.
- A diligent agent will spot the type cast and may comment on rounding / overflow possibilities. The agent will *not* know:
  - The actual maximum payment amount in the data (and therefore overflow risk).
  - Whether any downstream computation changes value because of the cast.
  - Whether the `::bigint` cast downstream hides the precision change entirely.
- Most agents will pattern-match on "type change" → "may affect downstream" and hedge.

## Expected agent verdict — with Recce

- Likely catch quality: **partial** at best on a *single dev environment* (Tier 1).
- Evidence Recce should surface:
  - **Schema diff** — column type for `amount` on `stg_payments` changed to `DECIMAL(10,2)`.
  - **Query diff** for `select max(amount) from stg_payments` — same value, but now bounded by precision.
- What single-env Recce **cannot** surface:
  - Whether the change introduces overflow on production-scale data (no base env to compare against).
  - Whether `customer_lifetime_value` shifts on any customer (requires Tier-2 base comparison; the ::bigint cast may absorb the difference anyway).
- Expected conclusion: "Type narrowed to DECIMAL(10,2). Potential overflow if any payment exceeds 99,999,999.99 dollars. Downstream impact unknown without a base comparison."

## Caveats

- **PR has evolved beyond the spec.** Head SHA includes a merge commit (`1c56861`) that brings `main` into the PR branch. The substantive change is at `6ffc23f`; the merge is mechanical. We use the merge head as the fixture head because it is what reviewers see when the PR is opened.
- This fixture is the clearest example in the set where **single-env Tier-1 Recce is honestly degraded** vs Tier-2 (data-diff). The case study should call this out — it's the most useful kind of signal for the gap report.
- Reproducible without warehouse: yes. The type change is visible in the source diff and the `catalog-*.json` files; without real data the empty catalogs will not show realistic precision behavior, so the eval runner should not rely on `catalog-*.json` numbers for this fixture.
