# Fixture pr44-promotion-flags — Promotion flags (schema-expansion; head state)

- Tier-0 baseline (frozen): [../../fixtures/pr44-promotion-flags/tier-0-baseline.md](../../fixtures/pr44-promotion-flags/tier-0-baseline.md)
- Run date: 2026-06-09
- Agent / model: Claude Code / claude-opus-4-8
- Primary evidence tier + subset: 0 (Recce permitted at Tier-1 but not invoked)
- Binary catch (this run = Tier-1): catch
- Binary catch (Tier-0 baseline): catch
- Delta: catch → catch (binary), but **action flipped request-changes → approve — confounded (run variance — no Recce evidence cited)**

## Evidence Recce surfaced

None. Tier-1 stated outright "MCP isn't available"; both tiers reasoned from the diff + compiled SQL + manifest.

## Conclusion the agent reached

- **Tier-0: request-changes** — assumed **DuckDB** → `boolor_agg` is a Snowflake-only function → "the model will fail at `dbt run`". A genuine portability bug, but a *different* issue than the fixture's schema-expansion intent.
- **Tier-1: approve** — assumed **Snowflake** → `boolor_agg` valid → clean additive feature, existing columns untouched, downstream unaffected.

Both verdicts are internally correct **for their assumed adapter**; there is no single ground truth for the head state (W8).

## Delta vs Tier-0 baseline

Binary catch is `catch → catch`, but the recommended action flipped (`request-changes → approve`) on the dialect assumption — **not** Recce. Recorded as confounded per the lens-3 attribution rule.

## Notes

**Default cell evaluates the BENIGN head** (two new columns, no filter). The fixture's intended blind-spot — the `where has_promoted_orders = true` row filter at intermediate commit `23b96ca` — is **not staged by the default `diff.patch`** and was not exercised here (waffle point W2). Exercising it requires a `pr44-intermediate` cell staging `diff-from-base-to-intermediate.patch` + `artifacts/intermediate-commit-23b96ca/` → flagged in the gap report.
