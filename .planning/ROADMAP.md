# Roadmap: recce-dev Plugin

## Overview

Build the `recce-dev` Claude Code plugin in seven phases, each delivering a verified capability that the next phase depends on. The sequence follows strict component dependencies: scaffold and MCP lifecycle must work before hooks, hooks must track changes before the sub-agent can use that state, the sub-agent must exist before the command can dispatch it, and quality validation runs last on the complete plugin. Phases 1–5 use `/plugin-dev` skills for plugin development. Phase 6 uses `/kc-plugin-forge` to audit overall quality. Phase 7 validates the end-to-end install-and-review flow.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Scaffold and MCP Lifecycle** - Plugin loads cleanly; MCP scripts manage server with project-scoped PIDs; settings system scaffolded; docs MCP configured (completed 2026-03-11)
- [x] **Phase 2: SessionStart Hook** - Session-start script detects dbt environment, checks artifacts, and auto-starts MCP; Claude receives structured KEY=VALUE context at session open (completed 2026-03-11)
- [x] **Phase 3: Two-Tier Trigger Hooks** - Tier 1 silently tracks edited model files; Tier 2 suggests data review after dbt run/build/test completes; pre-commit guard warns about unreviewed changes (completed 2026-03-11)
- [ ] **Phase 4: Progressive Review Sub-Agent** - `agents/recce-reviewer.md` drives lineage → row_count → schema → summary workflow in isolated context using Recce MCP tools
- [ ] **Phase 5: /recce-review Command** - Skill dispatches review sub-agent; checks MCP health before launch; passes tracked model list when available; works as manual escape hatch
- [ ] **Phase 6: Plugin-Forge Quality Validation** - `/kc-plugin-forge` audits plugin structure, conventions, and best practices; all issues resolved
- [ ] **Phase 7: E2E Validation** - Full install-to-review flow validated; plugin installable via local marketplace

## Phase Details

### Phase 1: Scaffold and MCP Lifecycle
**Goal**: The plugin loads in Claude Code without errors and the MCP server lifecycle is fully managed
**Depends on**: Nothing (first phase)
**Requirements**: SCAF-01, SCAF-02, SCAF-03, SCAF-04, SCAF-05, SETT-01, SETT-02, SETT-03, SETT-04, DOCS-01, DOCS-02, DOCS-03
**Success Criteria** (what must be TRUE):
  1. Running `/plugin install recce-dev` in Claude Code produces no errors and the plugin appears in the Installed tab
  2. `start-mcp.sh` starts the Recce MCP server and writes a project-scoped PID file; `check-mcp.sh` returns healthy; `stop-mcp.sh` stops the server and removes the PID file
  3. Two dbt projects open simultaneously each manage independent MCP server processes (no PID collisions)
  4. Settings from `~/.claude/plugins/recce-dev/settings.json` are read; a project-level `.claude/recce-dev/settings.json` overrides global values
  5. The recce-docs MCP server is declared in `.mcp.json` and Claude can invoke a docs search tool
**Plans:** 2/2 plans complete

Plans:
- [ ] 01-01-PLAN.md — Plugin directory scaffold, configs (plugin.json, marketplace, .mcp.json, hooks.json, defaults.json, recce-docs symlink)
- [ ] 01-02-PLAN.md — MCP lifecycle scripts (start/stop/check) with project-scoped PID and integrated settings loading

### Phase 2: SessionStart Hook
**Goal**: Claude receives structured environment context at every session open in a dbt project
**Depends on**: Phase 1
**Requirements**: HOOK-01, HOOK-02, HOOK-03, HOOK-04
**Success Criteria** (what must be TRUE):
  1. Opening Claude Code in a directory containing `dbt_project.yml` causes the session-start hook to emit `DBT_PROJECT=true` and the project name into Claude's context
  2. Opening Claude Code in a non-dbt directory causes the hook to emit `DBT_PROJECT=false` and the plugin stays silent
  3. When dbt artifacts (`manifest.json`) exist, the hook starts the MCP server automatically on the configured port and emits `MCP_STARTED=true`
  4. When recce is not installed, the hook emits `RECCE_INSTALLED=false` and Claude surfaces a clear setup message instead of silently failing
**Plans:** 2/2 plans complete

Plans:
- [ ] 02-01-PLAN.md — Modify start-mcp.sh for single-env mode, create session-start.sh with dbt detection and MCP delegation, register SessionStart hook in hooks.json
- [ ] 02-02-PLAN.md — Smoke test runner for session-start.sh output validation + human checkpoint for MCP auto-start in real dbt project

### Phase 3: Two-Tier Trigger Hooks
**Goal**: Model file changes are silently tracked; review is suggested at the right moment; pre-commit guard catches unreviewed changes
**Depends on**: Phase 2
**Requirements**: TRIG-01, TRIG-02, TRIG-03, TRIG-04, TRIG-05
**Success Criteria** (what must be TRUE):
  1. Editing `models/stg_bookings.sql` with Write/Edit causes the file path to appear in a project-scoped temp file without any message in the conversation
  2. After `dbt run` completes, Claude surfaces "You changed N models. Run data review?" with the specific model names listed
  3. Running `dbt run` in a session where no model files were edited produces no review suggestion
  4. Running `git commit` with tracked unreviewed changes causes a non-blocking warning ("N model changes not yet reviewed") and the commit proceeds normally (exit 0)
**Plans:** 2 plans

Plans:
- [ ] 03-01-PLAN.md — Test infrastructure + all three hook scripts (track-changes.sh, suggest-review.sh, pre-commit-guard.sh) + hooks.json registration
- [ ] 03-02-PLAN.md — Human verification checkpoint for runtime hook behavior in Claude Code

### Phase 4: Progressive Review Sub-Agent
**Goal**: The review sub-agent drives a complete lineage → row_count → schema → summary workflow in isolated context using Recce MCP tools
**Depends on**: Phase 1, Phase 3
**Requirements**: REVW-01, REVW-02, REVW-03, REVW-04, REVW-05
**Success Criteria** (what must be TRUE):
  1. Invoking the review sub-agent on `stg_bookings` produces a lineage diff first, then row count diff on affected downstream models, then schema diff — in that order — without prompting
  2. The sub-agent produces a final summary naming changed models, row count delta (e.g., "-12% rows in fct_bookings"), schema changes, and a risk level (low/medium/high)
  3. When a view model is encountered, the sub-agent skips `row_count_diff` for that model and notes the skip in the summary
  4. The sub-agent runs in an isolated context (no output visible in main conversation until summary is complete)
  5. When invoked in a single-environment setup, the sub-agent emits a clear warning and continues with available data
**Plans**: TBD

Plans:
- [ ] 04-01: `agents/recce-reviewer.md` with MCP server declarations in frontmatter and progressive review workflow
- [ ] 04-02: Edge case handling (views, single-env, permission errors) and actionable summary format

### Phase 5: /recce-review Command
**Goal**: The `/recce-review` skill dispatches the review sub-agent and works as a reliable manual escape hatch
**Depends on**: Phase 4
**Requirements**: CMD-01, CMD-02, CMD-03, CMD-04
**Success Criteria** (what must be TRUE):
  1. Typing `/recce-review` in Claude Code launches the review sub-agent and returns a summary
  2. Running `/recce-review` when the MCP server is not running surfaces a clear error ("MCP server not running — start with `start-mcp.sh`") instead of a silent failure
  3. Running `/recce-review` after editing model files passes those specific model names to the sub-agent for scoped review
  4. Running `/recce-review` in a fresh session with no tracked changes still launches a full review across all modified models (detected via `git diff --name-only`)
**Plans**: TBD

Plans:
- [ ] 05-01: `skills/recce-dev/SKILL.md` with MCP health check, tracked model injection, and sub-agent dispatch

### Phase 6: Plugin-Forge Quality Validation
**Goal**: The complete plugin passes `/kc-plugin-forge` quality audit with all issues resolved
**Depends on**: Phase 5
**Requirements**: VALD-01
**Success Criteria** (what must be TRUE):
  1. Running `/kc-plugin-forge` on the `recce-dev` plugin produces a passing audit report with no critical or high-severity findings
  2. All plugin conventions are met: SKILL.md naming, `${CLAUDE_PLUGIN_ROOT}` paths, executable bits set in git, hooks.json structure, agent frontmatter completeness
  3. Any findings from the audit are fixed and the audit re-run confirms resolution
**Plans**: TBD

Plans:
- [ ] 06-01: Run `/kc-plugin-forge` audit, triage findings, apply fixes, and re-validate

### Phase 7: E2E Validation
**Goal**: The full install-to-review workflow is validated end-to-end against `jaffle_shop_golden` (Snowflake) and the plugin is installable via local marketplace
**Depends on**: Phase 6
**Requirements**: VALD-02, VALD-03
**Test Environment**: `/Users/kent/Project/recce/jaffle_shop_golden` — dbt project with Snowflake warehouse configured
**Success Criteria** (what must be TRUE):
  1. A fresh Claude Code session in `jaffle_shop_golden/` with the plugin installed via `/plugin marketplace add` completes the full flow: session opens → dbt project detected → MCP starts → model edit tracked → `dbt run` triggers suggestion → `/recce-review` produces summary with real Snowflake row counts
  2. The plugin installs cleanly from the local marketplace with no path errors or missing files
  3. Uninstalling and reinstalling the plugin leaves no stale state (PID files, temp tracking files, stale `CLAUDE_PLUGIN_ROOT`)
**Plans**: TBD

Plans:
- [ ] 07-01: E2E flow walkthrough in `jaffle_shop_golden` (Snowflake): install plugin → edit a model → dbt run → review → validate summary accuracy

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6 → 7

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Scaffold and MCP Lifecycle | 2/2 | Complete   | 2026-03-11 |
| 2. SessionStart Hook | 2/2 | Complete   | 2026-03-11 |
| 3. Two-Tier Trigger Hooks | 2/2 | Complete   | 2026-03-11 |
| 4. Progressive Review Sub-Agent | 0/2 | Not started | - |
| 5. /recce-review Command | 0/1 | Not started | - |
| 6. Plugin-Forge Quality Validation | 0/1 | Not started | - |
| 7. E2E Validation | 0/1 | Not started | - |
