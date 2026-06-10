# Fixture pr2-refactor-cte-to-models — Refactor CTEs into intermediate models (negative control)

- Tier-0 baseline (frozen): [../../fixtures/pr2-refactor-cte-to-models/tier-0-baseline.md](../../fixtures/pr2-refactor-cte-to-models/tier-0-baseline.md)
- Run date: 2026-06-09
- Agent / model: Claude Code / claude-opus-4-8
- Primary evidence tier + subset: 0 (Recce permitted at Tier-1 but not invoked)
- Binary catch (this run = Tier-1): catch
- Binary catch (Tier-0 baseline): catch
- Delta: catch → catch (**same**)

## Evidence Recce surfaced

None. Both tiers proved behaviour preservation by tracing `compiled-before/` vs `compiled-after/` (byte-equivalent join logic, preserved grain, preserved NULL behaviour). Tier-1 noted a Recce `value_diff` as optional "belt-and-suspenders" but did not run it.

## Conclusion the agent reached

Both tiers: **approve**. Behaviour-preserving refactor; `customers` and all downstream tables produce identical data. Non-blocking nits: the new `int_*` models materialise as `table` (consider `ephemeral`); no tests/docs on the new models.

## Delta vs Tier-0 baseline

No delta. The negative control passed at both tiers — **no false alarm**. The rubric's intended differentiator for this fixture (a with-Recce 100% value-match receipt) was never produced because Recce was not exercised.

## Notes

Opus 4.8 independently flagged the materialisation-as-table consequence, beyond the fixture spec — evidence the agent reasons past the obvious "looks equivalent → approve" skim on its own.
