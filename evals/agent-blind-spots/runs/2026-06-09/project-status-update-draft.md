# DRAFT project status update — "Agent-blind spots: /recce-verify v1"
# (draft for Even to edit/post — not posted automatically)

**v1 eval chain complete (DRC-3585 + DRC-3405); rubric provisionally locked pending Andy's inter-rater pass.**

Ran the eval base end-to-end: 6 `jaffle_shop_golden` PR fixtures × Claude Code × {Tier-0, Tier-1}, hand-graded on `claude-opus-4-8`. Codex deferred for v1 (codex-cli 0.138.0 runner is broken; folded into the harness-fix item). Two structural findings reframe v1:

1. **The eval base doesn't yet exercise Recce.** Every Tier-1 cell ran with zero Recce tool calls — the driver prompt never invokes `/recce-verify`, the Recce MCP server isn't configured in the cells, and the fixtures have no materialized dev env. So measured Tier-1 ≡ Tier-0; no verdict shift is attributable to Recce yet. **This is gap-report item #1** and gates any product-backend ranking.

2. **A frontier agent already clears the bar these fixtures set.** Opus 4.8 caught the decisive issue in 5.5/6 fixtures from static artifacts alone (incl. the row-grain drop, the buried CLV redefinition, a real portability bug). On a 6-model project the agent out-traces single-env Recce by hand; Recce's value needs (a) realistically large fixtures where hand-tracing fails, and (b) base-env comparison (Tier 2) for the data-magnitude the agent keeps asking for — the v2 wedge.

**Shipped:**
- Rubric locked (provisionally): 4 rule clarifications + an 8-entry waffle log resolving every grading ambiguity (`RUBRIC.md`).
- 6 Tier-0 baselines frozen; 6 per-fixture case studies; 12 traces committed (`runs/2026-06-09/`).
- Ranked gap report (5 entries, eval-base fixes first, then the base-env/v2 signal) — the v1 conclusion + handoff doc.
- Inter-rater proxy: judge self-consistency catch 100% / tier 75% / delta 83%; judge–human catch 5/6. Judge can't replace human grading at the catch/partial boundary.

**Remaining for full lock:** Andy's independent second-grade on the 12 traces (≥90% agreement target) — packet ready at `runs/2026-06-09/andy-second-grader-packet.md`.

**Recommended next owner actions (post-handoff):** fix the eval base to actually run Recce (gap #1), add large-scale fixtures (gap #3), then re-run before deciding any backend additions. Base-env comparison + the data-magnitude value-add → route to the Recce MCP App / v2 backlog (per project cut), not v1.
