# Fixture pr1-fix-clv — Restrict CLV to completed orders

- Tier-0 baseline (frozen): [../../fixtures/pr1-fix-clv/tier-0-baseline.md](../../fixtures/pr1-fix-clv/tier-0-baseline.md)
- Run date: 2026-06-09
- Agent / model: Claude Code / claude-opus-4-8
- Primary evidence tier + subset: 0 (Recce permitted at Tier-1 but **not invoked** — see lens 2)
- Binary catch (this run = Tier-1): catch
- Binary catch (Tier-0 baseline): catch
- Delta: catch → catch (**same**)

## Evidence Recce surfaced

None. At Tier-1 the agent invoked **no** Recce MCP tool. It reached its verdict from `diff.patch` + `compiled-{before,after}/` + `manifest-after.json` + `schema.yml`. It explicitly named the Recce evidence it *would* have wanted but could not run: "a Recce `value_diff` on `customers.customer_lifetime_value` … plus a `profile_diff` to see the NULL-rate and total-CLV shift" — the catalog is schema-only (zero rows) and no dev env was materialized.

## Conclusion the agent reached

Both tiers: **request-changes**. The one-line `where orders.status = 'completed'` silently narrows a published metric, introduces NULL CLV for customers with no completed orders, rebuckets `customer_segments.value_segment` downward (with the `accepted_values` test still green), and leaves `number_of_orders` vs `customer_lifetime_value` computed over inconsistent order populations.

## Delta vs Tier-0 baseline

No delta. Tier-1 reproduced the Tier-0 verdict and reasoning almost verbatim. Recce added nothing because it was not exercised (no materialized env, MCP not reachable). The decisive evidence the agent *wanted* (value/CLV magnitude) is a before/after data diff — single-env Recce cannot produce it without a base env (Tier 2).

## Notes

Tier-0 exceeded the fixture README's `partial` anchor (the README assumed the agent would hedge; Opus 4.8 reasoned to `catch` from artifacts). This is the friendliest fixture for Recce (preset `value_diff`/`query_diff` checks in `recce.yml`) yet the harness still surfaced no Recce evidence — see gap report W4/W6.
