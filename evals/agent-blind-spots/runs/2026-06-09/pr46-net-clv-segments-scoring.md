# Fixture pr46-net-clv-segments — Net revenue / net CLV / segments (multi-model stress test)

- Tier-0 baseline (frozen): [../../fixtures/pr46-net-clv-segments/tier-0-baseline.md](../../fixtures/pr46-net-clv-segments/tier-0-baseline.md)
- Run date: 2026-06-09
- Agent / model: Claude Code / claude-opus-4-8
- Primary evidence tier + subset: 0 (Recce permitted at Tier-1 but not invoked)
- Binary catch (this run = Tier-1): catch
- Binary catch (Tier-0 baseline): catch
- Delta: catch → catch (**same**)

## Evidence Recce surfaced

None. Both tiers identified the issues from the diff + compiled SQL + manifest and noted Recce/MCP unavailable; both named `value_diff` on `customer_lifetime_value` + a `value_segment` distribution diff as the unrun validation.

## Conclusion the agent reached

Both tiers: **request-changes** on the **decisive issue** — the in-place redefinition of the public `customer_lifetime_value` (now completed-orders-only + `amount > 0`), smuggled into an additive-looking PR, with misleading column docs and a downstream `value_segment` shift. Both also flagged the LEFT-JOIN-filter anti-pattern, the fragile `finance_revenue` `not_null` tests, and the copy-pasted net thresholds.

## Delta vs Tier-0 baseline

No delta. The stress-test fixture's decisive blind-spot (a buried metric redefinition the README expected the agent to miss) was caught at **both** tiers from static evidence. Recce was not exercised.

## Notes

Defines the lens-1 decisive-issue anchor for this fixture: catching the `customer_lifetime_value` redefinition = `catch`; catching only the additive surface while missing the redefinition = `partial`. Opus 4.8 caught the redefinition plus all secondary issues — the strongest single demonstration that a frontier agent clears the bar these fixtures set, from artifacts alone.
