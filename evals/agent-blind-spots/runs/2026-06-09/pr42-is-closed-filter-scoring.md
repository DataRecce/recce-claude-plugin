# Fixture pr42-is-closed-filter — Add is_closed and filter orders (row-grain)

- Tier-0 baseline (frozen): [../../fixtures/pr42-is-closed-filter/tier-0-baseline.md](../../fixtures/pr42-is-closed-filter/tier-0-baseline.md)
- Run date: 2026-06-09
- Agent / model: Claude Code / claude-opus-4-8
- Primary evidence tier + subset: 0 (Recce permitted at Tier-1 but not invoked)
- Binary catch (this run = Tier-1): catch
- Binary catch (Tier-0 baseline): catch
- Delta: catch → catch (**same**)

## Evidence Recce surfaced

None. Both tiers caught the silent row drop from the compiled-SQL `where is_closed = true` + the `accepted_values` status domain (only 1 of 5 statuses survives), and confirmed `orders` is a terminal mart via the manifest `child_map`. Both explicitly noted the magnitude needs a Recce `row_count`/`profile_diff` that they could not run.

## Conclusion the agent reached

Both tiers: **request-changes**. The `where is_closed = true` silently drops every non-completed order from a published mart; `dbt test` stays green (accepted_values passes on the subset; not_null/unique survive a smaller set); intent (expose-flag vs redefine-mart) is ambiguous and needs author confirmation.

## Delta vs Tier-0 baseline

No delta. Recce was not exercised. Notably the agent reached `catch` at Tier-0 — the row-drop **direction and mechanism** are determinable from static evidence; only the **magnitude** needs Recce, and magnitude did not change the verdict here.

## Notes

This is the cleanest case for the central finding: the row-grain blind-spot the fixture was built to expose is caught by Opus 4.8 from artifacts alone. Recce's row-count diff would add the quantified magnitude, not the catch. (Uses an older base SHA `62d6dc9` than the rest — see fixtures README.)
