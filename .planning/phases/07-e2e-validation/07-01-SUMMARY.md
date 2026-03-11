---
phase: 07-e2e-validation
plan: 01
subsystem: testing
tags: [smoke-tests, e2e, bash, dotenv, mcp, recce-dev, snowflake]

# Dependency graph
requires:
  - phase: 06-plugin-forge-quality-validation
    provides: plugin-forge validated plugin structure including all scripts and manifests
provides:
  - .env credential passthrough fix for start-mcp.sh (Snowflake auth)
  - Standalone E2E scenario prompt for full plugin flow validation in jaffle_shop_golden
  - Automated marketplace install smoke test (VALD-03) for pre-E2E artifact verification
affects: [e2e-validation, phase-07-live-walkthrough]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "set -a; source .env; set +a idiom for dotenv variable export to child processes"
    - "Marketplace install smoke test validates source tree artifacts before live install"

key-files:
  created:
    - tests/e2e/e2e-scenario.md
    - tests/smoke/test-marketplace-install.sh
  modified:
    - plugins/recce-dev/scripts/start-mcp.sh

key-decisions:
  - ".env loading uses set -a/set +a before port resolution so RECCE_MCP_PORT in .env is honored"
  - "E2E scenario uses stg_orders.sql as edit target (reversible comment addition)"
  - "Marketplace install smoke test validates source tree artifacts, not a live install"
  - "servers/ excluded from broken symlink check for known MKTD-02 recce-docs PoC limitation"

patterns-established:
  - "E2E scenario format: pre-flight checklist + install steps + hook observations + pass criteria + cleanup + stale state check"
  - "Smoke test for install artifacts: assert_file_exists + assert_valid_json + assert_executable + assert_file_contains helpers"

requirements-completed: [VALD-02, VALD-03]

# Metrics
duration: 15min
completed: 2026-03-11
---

# Phase 7 Plan 01: E2E Validation Prep Summary

**.env credential passthrough fix for start-mcp.sh plus standalone E2E scenario and marketplace install smoke test (29 assertions) for jaffle_shop_golden Snowflake validation**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-03-11T22:20:00Z
- **Completed:** 2026-03-11T22:35:00Z
- **Tasks:** 3
- **Files modified:** 3 (1 modified, 2 created)

## Accomplishments

- Fixed confirmed Snowflake credential bug: `start-mcp.sh` now loads `.env` via `set -a; source .env; set +a` before port resolution, ensuring all env vars (including `RECCE_MCP_PORT`) are available when `recce mcp-server` spawns
- Created `tests/e2e/e2e-scenario.md` (335 lines): self-contained walkthrough covering pre-flight, install, SessionStart hook observation, model edit tracking, dbt run suggestion, `/recce-review` dispatch, pass criteria (row counts + risk level), cleanup, and stale state check
- Created `tests/smoke/test-marketplace-install.sh` (29 assertions): validates all 7 VALD-03 artifact categories — plugin.json, hooks.json, script executability, agents, skills, marketplace.json, and broken symlink detection — all passing on current plugin tree

## Task Commits

1. **Task 1: Fix .env credential loading** - `65d3a5c` (fix)
2. **Task 2: Create E2E scenario file** - `1d004bb` (feat)
3. **Task 3: Create marketplace install smoke test** - `a1d7a1e` (feat)

## Files Created/Modified

- `plugins/recce-dev/scripts/start-mcp.sh` - Added `.env` loading block between settings loading and port resolution (lines 31-37)
- `tests/e2e/e2e-scenario.md` - Standalone E2E validation prompt with 9 sections covering full plugin event chain
- `tests/smoke/test-marketplace-install.sh` - Automated VALD-03 smoke test with 29 assertions across 7 test groups

## Decisions Made

- `.env` loading placed BEFORE port resolution: `RECCE_MCP_PORT` in `.env` must be visible when `PORT=${RECCE_MCP_PORT:-$SETTINGS_PORT}` is evaluated
- E2E scenario targets `stg_orders.sql` with a reversible `-- recce-e2e-validation` comment to ensure the edit is safe and repeatable across multiple runs
- Marketplace smoke test validates source tree artifacts (not a live install) so it can run in CI without Claude Code
- `servers/` directory excluded from broken symlink check because the `recce-docs-mcp` symlink is an accepted PoC limitation (MKTD-02, deferred to v2)
- `servers/recce-docs-mcp` symlink status is reported informational (PASS either way) rather than failing the test

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None. All 5 smoke test suites passed before and after changes (84 pre-existing assertions unchanged, 29 new assertions added = 113 total).

## User Setup Required

None - no external service configuration required. The E2E scenario itself documents the pre-flight setup steps needed before running live validation.

## Next Phase Readiness

- All automated pre-E2E checks in place (smoke tests pass)
- `start-mcp.sh` will now correctly load Snowflake credentials from `.env` when run from `jaffle_shop_golden`
- `tests/e2e/e2e-scenario.md` is ready to paste into a Claude Code session in `jaffle_shop_golden` for live walkthrough
- Remaining Phase 7 work: run the live E2E walkthrough and document results

## Self-Check: PASSED

All created files verified present on disk. All 3 task commits verified in git log.

---
*Phase: 07-e2e-validation*
*Completed: 2026-03-11*
