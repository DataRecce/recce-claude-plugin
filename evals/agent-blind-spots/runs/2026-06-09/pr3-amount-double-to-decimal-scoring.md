# Fixture pr3-amount-double-to-decimal — Money column DOUBLE → DECIMAL(10,2)

- Tier-0 baseline (frozen): [../../fixtures/pr3-amount-double-to-decimal/tier-0-baseline.md](../../fixtures/pr3-amount-double-to-decimal/tier-0-baseline.md)
- Run date: 2026-06-09
- Agent / model: Claude Code / claude-opus-4-8
- Primary evidence tier + subset: 0 (Recce permitted at Tier-1 but not invoked)
- Binary catch (this run = Tier-1): catch
- Binary catch (Tier-0 baseline): partial
- Delta: partial → catch — **confounded (run variance — no Recce evidence cited)**

## Evidence Recce surfaced

None. Neither tier invoked Recce. Both named `value_diff`/`profile_diff` as the validation they could not run (catalog schema-only, no dev env, MCP unavailable).

## Conclusion the agent reached

- **Tier-0: approve** — assumed the **Snowflake** dialect (read `profiles.yml`), reasoned the cast is value-preserving, flagged only an overflow bound and an `as` style nit. Graded **partial** (missed the downstream incremental schema-drift risk).
- **Tier-1: request-changes** — assumed the **DuckDB** dialect (read the compiled SQL's `DATEDIFF` + 3-part identifiers), found the `orders_daily_summary` incremental schema-drift footgun and the `sum(...)::bigint` rounding-boundary effect on `value_segment`. Graded **catch**.

## Delta vs Tier-0 baseline

The verdict moved `partial → catch`, **but this is not Recce-attributable** (Recce was invoked in neither run). The shift is driven by the two runs anchoring on different dialects (W8) — a stochastic run-variance artifact (W7). Per the lens-3 Recce-attribution rule, recorded as **confounded**.

## Notes

This fixture is the clearest demonstration that, at N=1 run per cell, a lens-3 delta cannot be attributed to Recce without the with-Recce run citing Recce evidence. It is also the honest-degradation exemplar: the decisive question (does the type change shift any downstream value?) requires a base comparison = Tier 2, out of v1 scope.
