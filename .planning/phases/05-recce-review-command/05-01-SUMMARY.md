---
phase: 05-recce-review-command
plan: 01
subsystem: skills
tags: [skill, mcp, sub-agent, orchestration, recce-review]

requires:
  - phase: 04-progressive-review-sub-agent
    provides: recce-reviewer sub-agent definition that this skill dispatches

provides:
  - /recce-review skill at plugins/recce-dev/skills/recce-review/SKILL.md
  - Structural smoke test at tests/smoke/test-recce-review-skill.sh

affects: [06-plugin-forge-validation, 07-e2e-validation]

tech-stack:
  added: []
  patterns:
    - "Thin skill orchestration: SKILL.md routes to existing scripts and sub-agent, no logic duplication"
    - "7-step skill structure: health-check, auto-start, re-check, model-scope, dispatch, cleanup, risk-next-steps"
    - "Conditional cleanup: rm -f tracked file only fires when agent output contains '## Data Review Summary'"

key-files:
  created:
    - plugins/recce-dev/skills/recce-review/SKILL.md
    - tests/smoke/test-recce-review-skill.sh
  modified: []

key-decisions:
  - "Skill does not gate on tracked file presence — state:modified+ fallback ensures CMD-04 manual escape hatch always works"
  - "Cleanup conditional on '## Data Review Summary' header — preserves tracked file for retry on incomplete reviews"
  - "Risk-based next steps use HIGH/MEDIUM/LOW parsed from agent summary — no hardcoded model logic in skill"

patterns-established:
  - "Smoke test mirrors test-reviewer-agent.sh pattern exactly: assert helpers, frontmatter/body awk extraction, PASS/FAIL counters"
  - "SKILL.md uses ## Step N: Name headings for numbered orchestration steps"

requirements-completed: [CMD-01, CMD-02, CMD-03, CMD-04]

duration: 6min
completed: 2026-03-11
---

# Phase 5 Plan 01: Recce Review Skill Summary

**7-step /recce-review skill orchestrating MCP health check, auto-start recovery, tracked model handoff, recce-reviewer dispatch, conditional cleanup, and risk-based next steps**

## Performance

- **Duration:** 6 min
- **Started:** 2026-03-11T09:41:41Z
- **Completed:** 2026-03-11T09:47:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Created `plugins/recce-dev/skills/recce-review/SKILL.md` with full 7-step orchestration flow covering MCP health check through risk-based next steps
- Created `tests/smoke/test-recce-review-skill.sh` with 21 assertions validating CMD-01 through CMD-04 requirements
- Full 4-suite smoke test suite passes (84 total assertions, 0 failures)

## Task Commits

1. **Task 1: Structural smoke test for SKILL.md** - `5259643` (test)
2. **Task 2: Create /recce-review SKILL.md** - `1f71fa8` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `plugins/recce-dev/skills/recce-review/SKILL.md` - 7-step skill orchestrating MCP lifecycle, tracked model injection, sub-agent dispatch, cleanup, and risk-based guidance
- `tests/smoke/test-recce-review-skill.sh` - 21-assertion structural smoke test validating CMD-01 through CMD-04

## Decisions Made

- Skill does not abort when tracked changes file is absent — falls back to `state:modified+` (CMD-04 manual escape hatch)
- Post-review cleanup (`rm -f`) is gated on `## Data Review Summary` presence in agent output — tracked file preserved on incomplete reviews
- Risk level guidance uses HIGH/MEDIUM/LOW parsed from agent summary rather than hardcoded logic

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `/recce-review` skill is ready for plugin-forge validation (Phase 6)
- All 4 smoke test suites green — no regressions introduced
- Full plugin structure (MCP scripts, hooks, reviewer agent, review skill) is now complete

---
*Phase: 05-recce-review-command*
*Completed: 2026-03-11*
