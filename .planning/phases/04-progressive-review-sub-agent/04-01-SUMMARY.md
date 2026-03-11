---
phase: 04-progressive-review-sub-agent
plan: 01
subsystem: agents
tags: [sub-agent, claude-code, mcp, dbt, recce, data-validation, progressive-review]

requires:
  - phase: 01-scaffold-and-mcp-lifecycle
    provides: recce-dev MCP server definition (.mcp.json with recce-dev SSE server on :8081)
  - phase: 03-two-tier-trigger-hooks
    provides: track-changes.sh writes /tmp/recce-changed-{hash}.txt that agent reads

provides:
  - plugins/recce-dev/agents/recce-reviewer.md — Progressive data review sub-agent definition
  - tests/smoke/test-reviewer-agent.sh — 21-assertion structural smoke test for agent file

affects:
  - phase 05-review-skill (dispatches recce-reviewer agent via /recce-review command)
  - phase 07-e2e-validation (validates agent behavior against live Recce MCP + dbt project)

tech-stack:
  added: []
  patterns:
    - "Claude Code sub-agent definition: YAML frontmatter with name/description/tools/mcpServers/model, then system prompt body"
    - "MCP server declaration in sub-agent frontmatter: mcpServers: [server-name] — sub-agents do NOT inherit parent MCP servers"
    - "MCP tool naming in sub-agent: mcp__{server-name}__{tool-name} format in tools list"
    - "Progressive review workflow: lineage_diff -> row_count_diff (tables only) -> schema_diff -> summary"
    - "Risk level derivation: HIGH=schema breaking change, MEDIUM=row count delta >10%, LOW=all deltas <10%"

key-files:
  created:
    - plugins/recce-dev/agents/recce-reviewer.md
    - tests/smoke/test-reviewer-agent.sh
  modified: []

key-decisions:
  - "Sub-agent includes Read and Bash tools in addition to MCP tools — agent reads /tmp/recce-changed-{hash}.txt and can compute PROJECT_HASH via Bash"
  - "mcpServers: [recce-dev] only — recce-docs excluded from agent to keep review focused (documentation lookup not part of review workflow)"
  - "assert_not_contains grep pattern uses -- flag to handle patterns starting with dashes cleanly"
  - "Smoke test assertion #10 changed from assert_not_contains '- recce' to assert_regex 'mcp__recce-dev__' — more precise and avoids false failure from recce-dev matching recce prefix"

patterns-established:
  - "Sub-agent smoke tests: extract frontmatter with awk between first two --- delimiters, extract body as everything after second ---"
  - "Smoke test assert helpers: assert_contains (grep -qF), assert_regex (grep -qE), assert_not_contains (grep -qF --)"

requirements-completed: [REVW-01, REVW-02, REVW-03, REVW-04, REVW-05]

duration: 3min
completed: 2026-03-11
---

# Phase 4 Plan 1: Progressive Review Sub-Agent Summary

**recce-reviewer sub-agent with 5-section system prompt encoding lineage->row_count->schema->summary workflow, view/single-env/error edge cases, and risk-level summary template — validated by 21/21 structural smoke test assertions**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-11T08:46:03Z
- **Completed:** 2026-03-11T08:48:39Z
- **Tasks:** 2
- **Files modified:** 2 created

## Accomplishments

- Created `plugins/recce-dev/agents/recce-reviewer.md` with correct YAML frontmatter (name, description, tools including 3 MCP tools, model: inherit, mcpServers: [recce-dev]) and a complete 5-section system prompt
- System prompt encodes: changed-model input via /tmp/recce-changed-{hash}.txt, progressive 4-step review workflow, 3 edge cases (views, single-env, permission errors), concrete summary template with risk level rules, and autonomy constraints
- Created `tests/smoke/test-reviewer-agent.sh` with 21 structural assertions covering frontmatter and body content — full suite 63/63 green (no regressions)

## Task Commits

Each task was committed atomically:

1. **Task 1: Create structural smoke test** - `e36b91d` (test)
2. **Task 2: Create recce-reviewer agent definition** - `64ffb23` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `plugins/recce-dev/agents/recce-reviewer.md` — Sub-agent definition with YAML frontmatter and complete progressive review system prompt
- `tests/smoke/test-reviewer-agent.sh` — 21-assertion structural smoke test; validates frontmatter fields, MCP tool names, and body content coverage

## Decisions Made

- **Read and Bash tools included**: Agent needs Read to access /tmp/recce-changed-{hash}.txt and Bash to compute PROJECT_HASH — both essential for the changed-models input section.
- **recce-docs excluded from mcpServers**: The review workflow only needs lineage/row_count/schema diff tools. Documentation lookup is out of scope per CONTEXT.md deferred items.
- **Smoke test assertion #10 design**: Changed from `assert_not_contains "- recce"` (which falsely matched `- recce-dev`) to `assert_regex "mcp__recce-dev__"` which precisely validates that MCP tools use the correct server prefix.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed grep pattern starting with dash in assert_not_contains**
- **Found during:** Task 1 (smoke test creation) — revealed when Task 2 made the test run for real
- **Issue:** `grep -qF "- recce"` interprets `-` prefix as flag causing grep error; test passed accidentally (error exit = no match = PASS). After adding `--`, the test correctly found `- recce-dev` as matching `- recce`.
- **Fix:** Redesigned assertion #10 from `assert_not_contains "- recce"` to `assert_regex "mcp__recce-dev__"` — more precise intent (verify correct server prefix in tool names)
- **Files modified:** tests/smoke/test-reviewer-agent.sh
- **Verification:** `bash tests/smoke/test-reviewer-agent.sh` — 21/21 pass, no grep warnings
- **Committed in:** 64ffb23 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - bug in test assertion logic)
**Impact on plan:** Fix improved test precision — the revised assertion catches both the intended positive case (tools use recce-dev) and is immune to grep flag interpretation issues.

## Issues Encountered

None beyond the auto-fixed grep assertion issue above.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- Agent definition complete and structurally validated; ready for Phase 5 to create `/recce-review` skill that dispatches this agent
- Behavioral validation (actual MCP tool calls, risk level calculation) deferred to Phase 7 E2E with jaffle_shop_golden
- Concern from STATE.md still valid: sub-agent `mcpServers` inheritance interaction is less-tested — Phase 7 E2E will confirm sub-agent actually receives recce-dev MCP tools

---
*Phase: 04-progressive-review-sub-agent*
*Completed: 2026-03-11*
