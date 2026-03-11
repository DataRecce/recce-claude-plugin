---
phase: 03-two-tier-trigger-hooks
plan: "01"
subsystem: hooks
tags: [bash, hooks, post-tool-use, pre-tool-use, dbt, git, smoke-tests]

requires:
  - phase: 02-sessionstart-hook
    provides: session-start.sh hook pattern and test runner conventions

provides:
  - Two-tier trigger hook system: silent Tier 1 tracking + Tier 2 review suggestion
  - track-changes.sh: PostToolUse Write|Edit silent model file tracker
  - suggest-review.sh: PostToolUse Bash dbt execution review suggester
  - pre-commit-guard.sh: PreToolUse Bash non-blocking git commit warning
  - hooks.json with SessionStart + PostToolUse x2 + PreToolUse registrations
  - Smoke test suite with 11 test cases (test-trigger-hooks.sh)
  - 6 JSON fixtures for hook input simulation

affects:
  - 04-recce-reviewer-subagent
  - 05-commands-and-skills
  - 07-e2e-validation

tech-stack:
  added: []
  patterns:
    - "Project-scoped temp file via md5 hash of $CWD: /tmp/recce-changed-{hash}.txt"
    - "jq -r '.field // empty' for safe JSON extraction with graceful fallback"
    - "Deduplication via grep -qxF before appending to temp file"
    - "macOS paste -sd ', ' - requires explicit - for stdin (not portable default)"
    - "async: true in hooks.json for fire-and-forget PostToolUse hooks"
    - "Smoke test run_hook() helper substitutes {{CWD}} placeholder via sed"

key-files:
  created:
    - plugins/recce-dev/hooks/scripts/track-changes.sh
    - plugins/recce-dev/hooks/scripts/suggest-review.sh
    - plugins/recce-dev/hooks/scripts/pre-commit-guard.sh
    - tests/smoke/test-trigger-hooks.sh
    - tests/fixtures/fake-hook-inputs/write-model.json
    - tests/fixtures/fake-hook-inputs/write-readme.json
    - tests/fixtures/fake-hook-inputs/edit-model.json
    - tests/fixtures/fake-hook-inputs/bash-dbt-run.json
    - tests/fixtures/fake-hook-inputs/bash-git-status.json
    - tests/fixtures/fake-hook-inputs/bash-git-commit.json
  modified:
    - plugins/recce-dev/hooks/hooks.json

key-decisions:
  - "paste -sd ', ' - (explicit dash) required on macOS for stdin piping — discovered via Rule 1 auto-fix during test run"
  - "Temp file deduplication via grep -qxF avoids repeated tracking of same model on multiple edits"
  - "pre-commit-guard always exits 0 — exit 2 would block the commit, which is not the desired behavior"
  - "async: true on track-changes.sh ensures Tier 1 never adds latency to Write/Edit tool calls"

patterns-established:
  - "Hook scripts: read full JSON stdin into variable, then jq-extract fields — avoids piping issues"
  - "Graceful degradation: all scripts exit 0 immediately if jq is absent"
  - "Smoke test isolation: unique mktemp -d per scenario + cleanup of /tmp/recce-changed-*.txt"

requirements-completed: [TRIG-01, TRIG-02, TRIG-03, TRIG-04, TRIG-05]

duration: 4min
completed: "2026-03-11"
---

# Phase 3 Plan 01: Two-Tier Trigger Hooks Summary

**Three bash hook scripts implementing silent model tracking, post-dbt review suggestion, and non-blocking pre-commit warning via project-scoped /tmp temp file**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-11T08:04:54Z
- **Completed:** 2026-03-11T08:08:41Z
- **Tasks:** 3
- **Files modified:** 11

## Accomplishments

- track-changes.sh silently tracks edited models/*.sql paths to /tmp/recce-changed-{hash}.txt with deduplication
- suggest-review.sh detects dbt run/build/test and emits additionalContext JSON with model names when models tracked
- pre-commit-guard.sh warns about unreviewed models on git commit via systemMessage JSON, always exits 0
- hooks.json updated with all four event types: SessionStart, PostToolUse x2, PreToolUse x1
- 11/11 smoke tests pass; 21/21 Phase 2 regression tests still pass

## Task Commits

Each task was committed atomically:

1. **Task 1: Create smoke test fixtures and test runner** - `220549e` (test)
2. **Task 2: Create track-changes.sh, suggest-review.sh, pre-commit-guard.sh** - `42f67ee` (feat)
3. **Task 3: Register all three hooks in hooks.json** - `159e705` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `plugins/recce-dev/hooks/scripts/track-changes.sh` - PostToolUse Write|Edit: silent model file tracker
- `plugins/recce-dev/hooks/scripts/suggest-review.sh` - PostToolUse Bash: dbt execution review suggester
- `plugins/recce-dev/hooks/scripts/pre-commit-guard.sh` - PreToolUse Bash: non-blocking git commit warning
- `plugins/recce-dev/hooks/hooks.json` - Extended with PostToolUse x2 and PreToolUse x1 registrations
- `tests/smoke/test-trigger-hooks.sh` - 11 test cases covering TRIG-01 through TRIG-05
- `tests/fixtures/fake-hook-inputs/*.json` - 6 fixture files for Write/Edit/Bash hook inputs

## Decisions Made

- `paste -sd ', ' -` (explicit dash) required on macOS for stdin — discovered via Rule 1 auto-fix during test run
- Temp file deduplication via `grep -qxF` avoids tracking same model multiple times
- pre-commit-guard always exits 0; exit 2 would block git commit (not the intended behavior)
- `async: true` on track-changes.sh ensures Tier 1 never adds latency to Write/Edit calls

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed paste stdin compatibility on macOS**
- **Found during:** Task 2 (suggest-review.sh and pre-commit-guard.sh)
- **Issue:** `paste -sd ', '` without explicit `-` for stdin produces empty output on macOS — it waits for a file argument rather than reading stdin
- **Fix:** Changed to `paste -sd ', ' -` in both suggest-review.sh and pre-commit-guard.sh
- **Files modified:** plugins/recce-dev/hooks/scripts/suggest-review.sh, plugins/recce-dev/hooks/scripts/pre-commit-guard.sh
- **Verification:** Scenario 7 (model names in output) and Scenario 10 (model name in warning) both pass after fix
- **Committed in:** 42f67ee (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug - cross-platform paste compatibility)
**Impact on plan:** Essential fix for macOS. No scope creep.

## Issues Encountered

None beyond the paste compatibility fix above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Two-tier trigger system complete and tested
- hooks.json registers all four event types; session-start.sh unaffected (regression confirmed)
- Phase 4 (recce-reviewer subagent) can rely on /tmp/recce-changed-{hash}.txt being populated by track-changes.sh
- No blockers for next phase

## Self-Check: PASSED

All files confirmed present:
- plugins/recce-dev/hooks/scripts/track-changes.sh
- plugins/recce-dev/hooks/scripts/suggest-review.sh
- plugins/recce-dev/hooks/scripts/pre-commit-guard.sh
- plugins/recce-dev/hooks/hooks.json
- tests/smoke/test-trigger-hooks.sh
- .planning/phases/03-two-tier-trigger-hooks/03-01-SUMMARY.md

All task commits confirmed: 220549e, 42f67ee, 159e705

---
*Phase: 03-two-tier-trigger-hooks*
*Completed: 2026-03-11*
