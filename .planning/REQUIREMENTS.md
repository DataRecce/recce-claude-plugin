# Requirements: recce-dev Plugin

**Defined:** 2026-03-11
**Core Value:** When a data engineer modifies a dbt model, the plugin ensures data impact is reviewed before changes leave the developer's machine.

## v1 Requirements

### Plugin Scaffold

- [x] **SCAF-01**: Plugin loads in Claude Code without errors (plugin.json, directory structure)
- [x] **SCAF-02**: `.mcp.json` configures recce MCP (SSE) and recce-docs MCP (stdio) servers
- [x] **SCAF-03**: MCP lifecycle scripts (start/stop/check) manage recce server with project-scoped PID
- [x] **SCAF-04**: All hook/MCP scripts use `${CLAUDE_PLUGIN_ROOT}` for portable paths
- [x] **SCAF-05**: All scripts have executable bit set in git

### Settings

- [x] **SETT-01**: Settings system reads global config (`~/.claude/plugins/recce-dev/settings.json`)
- [x] **SETT-02**: Project-level config (`.claude/recce-dev/settings.json`) overrides global
- [x] **SETT-03**: Default settings template included in plugin (`settings/defaults.json`)
- [x] **SETT-04**: Settings control trigger behavior (`on_dbt_execution`, `on_pre_commit`, `on_model_edit`)

### Hooks — SessionStart

- [x] **HOOK-01**: SessionStart hook detects dbt project (finds `dbt_project.yml`)
- [x] **HOOK-02**: SessionStart checks recce installation and dbt artifacts
- [x] **HOOK-03**: SessionStart starts MCP server on configured port (default 8081)
- [x] **HOOK-04**: SessionStart outputs structured KEY=VALUE state to Claude context

### Hooks — Two-Tier Trigger

- [x] **TRIG-01**: PostToolUse (Write/Edit) silently tracks model file changes to temp file
- [x] **TRIG-02**: Tracking uses project-scoped temp file (e.g., `/tmp/recce-changed-${project_hash}.txt`)
- [x] **TRIG-03**: PostToolUse (Bash) detects `dbt run/build/test` completion
- [x] **TRIG-04**: After dbt execution, suggests review if tracked models exist ("You changed N models. Run data review?")
- [x] **TRIG-05**: Pre-commit hook warns about unreviewed model changes (non-blocking, exit 0)

### Review Sub-Agent

- [x] **REVW-01**: Progressive review agent follows lineage → row_count → schema → summary flow
- [x] **REVW-02**: Agent uses Recce MCP tools (lineage_diff, row_count_diff, schema_diff)
- [x] **REVW-03**: Agent produces actionable summary (changed models, row count impact, schema changes, risk level)
- [x] **REVW-04**: Agent handles edge cases (views with row_count, single-env _warning, permission errors)
- [x] **REVW-05**: Agent definition declares MCP servers explicitly in frontmatter

### Review Command

- [ ] **CMD-01**: `/recce-review` skill invokes the review sub-agent
- [ ] **CMD-02**: Skill checks MCP server is running before dispatching agent
- [ ] **CMD-03**: Skill passes tracked changed models list if available
- [ ] **CMD-04**: Skill works as manual escape hatch even without tracked changes

### Documentation MCP

- [x] **DOCS-01**: recce-docs MCP configured as stdio server in `.mcp.json`
- [x] **DOCS-02**: Path references local build (`packages/recce-docs-mcp/dist/index.js`)
- [x] **DOCS-03**: Docs MCP provides Recce documentation search capability to the agent

### Validation

- [ ] **VALD-01**: Plugin passes `/kc-plugin-forge` quality audit (structure, conventions, best practices)
- [ ] **VALD-02**: Full install → review → feedback E2E flow validated
- [ ] **VALD-03**: Plugin installable via local marketplace (`/plugin marketplace add`)

## v2 Requirements

### Marketplace Distribution

- **MKTD-01**: Register recce-dev in root `marketplace.json`
- **MKTD-02**: Resolve recce-docs MCP path for marketplace install (symlink or bundle strategy)
- **MKTD-03**: Plugin installable via public marketplace (`claude plugins install recce-dev`)

### UX Polish

- **UXPL-01**: `on_model_edit` option for user-visible suggestion on each edit (power users)
- **UXPL-02**: Contextual guidance skill (`recce-dev-guide`) for onboarding help

## Out of Scope

| Feature | Reason |
|---------|--------|
| CI/CD integration commands | Stays in `recce-quickstart`, not `recce-dev` |
| Auto-run dbt | Production safety risk — only suggest |
| Auto-run profile_diff/query_diff on all models | Cost/latency — only recommended when anomalies detected |
| Real-time MCP streaming | Standard SSE polling sufficient for PoC |
| Consolidation with recce-quickstart | PoC first, merge decision after validation |
| Mobile/web UI | CLI plugin only |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| SCAF-01 | Phase 1 | Complete |
| SCAF-02 | Phase 1 | Complete |
| SCAF-03 | Phase 1 | Complete |
| SCAF-04 | Phase 1 | Complete |
| SCAF-05 | Phase 1 | Complete |
| SETT-01 | Phase 1 | Complete |
| SETT-02 | Phase 1 | Complete |
| SETT-03 | Phase 1 | Complete |
| SETT-04 | Phase 1 | Complete |
| DOCS-01 | Phase 1 | Complete |
| DOCS-02 | Phase 1 | Complete |
| DOCS-03 | Phase 1 | Complete |
| HOOK-01 | Phase 2 | Complete |
| HOOK-02 | Phase 2 | Complete |
| HOOK-03 | Phase 2 | Complete |
| HOOK-04 | Phase 2 | Complete |
| TRIG-01 | Phase 3 | Complete |
| TRIG-02 | Phase 3 | Complete |
| TRIG-03 | Phase 3 | Complete |
| TRIG-04 | Phase 3 | Complete |
| TRIG-05 | Phase 3 | Complete |
| REVW-01 | Phase 4 | Complete |
| REVW-02 | Phase 4 | Complete |
| REVW-03 | Phase 4 | Complete |
| REVW-04 | Phase 4 | Complete |
| REVW-05 | Phase 4 | Complete |
| CMD-01 | Phase 5 | Pending |
| CMD-02 | Phase 5 | Pending |
| CMD-03 | Phase 5 | Pending |
| CMD-04 | Phase 5 | Pending |
| VALD-01 | Phase 6 | Pending |
| VALD-02 | Phase 7 | Pending |
| VALD-03 | Phase 7 | Pending |

**Coverage:**
- v1 requirements: 33 total
- Mapped to phases: 33
- Unmapped: 0

---
*Requirements defined: 2026-03-11*
*Last updated: 2026-03-11 after roadmap creation — all 33 requirements mapped to phases 1-7*
