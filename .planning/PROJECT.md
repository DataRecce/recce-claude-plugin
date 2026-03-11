# recce-dev Plugin — Complete Data Review Workflow

## What This Is

A new Claude Code plugin (`recce-dev`) that provides an intelligent data review workflow for dbt developers. It silently tracks model changes during editing, suggests data review at meaningful checkpoints (after `dbt run/build`, before commit), and drives a progressive review flow via Recce MCP tools — from lineage diff to actionable summary. This is a PoC to validate the generate-review cycle with coding agents.

## Core Value

When a data engineer modifies a dbt model, the plugin ensures data impact is reviewed before changes leave the developer's machine — catching issues like "row count dropped 12%" at the right moment, not after deployment.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Plugin scaffold loads in Claude Code without errors
- [ ] Settings system supports global + project-level layered config
- [ ] SessionStart hook detects dbt environment and starts MCP server
- [ ] PostToolUse hook silently tracks model file changes (Tier 1)
- [ ] PostToolUse hook suggests review after dbt execution (Tier 2)
- [ ] Pre-commit hook warns about unreviewed model changes
- [ ] Progressive data review sub-agent (lineage → row_count → schema → summary)
- [ ] `/recce-review` command for manual review invocation
- [ ] MCP config supports recce SSE + recce-docs stdio
- [ ] Marketplace registration and installable via plugin marketplace
- [ ] Plugin passes `/kc-plugin-forge` quality validation

### Out of Scope

- Consolidation with `recce-quickstart` — PoC first, merge later
- `on_model_edit` user-visible suggestion — too noisy, off by default
- `auto_run_dbt` — never auto-run dbt (production risk), only suggest
- Real-time MCP streaming — standard SSE polling is sufficient for PoC
- query_diff / profile_diff auto-execution — only recommended when anomalies detected
- CI/CD integration — stays in `recce-quickstart`

## Context

### Design Persona

Airbnb data engineer modifying `stg_bookings.sql` (JOIN condition change). Their PR requires external audit. They use Recce + Claude Code during development.

**What they don't want:** Review suggestions after every file save (too noisy), or no hint until after commit when discovering row count dropped 12% (too late).

**What they want:** Silent tracking → smart suggestions at meaningful checkpoints → progressive review → actionable summary.

### Architecture: Two-Tier Trigger System

**Tier 1 — Silent tracking** (PostToolUse on Write/Edit):
Agent notes model file changes without interrupting. Maintains internal "changed models" list.

**Tier 2 — Smart suggestion** at key moments:

| Trigger | Condition | Behavior |
|---------|-----------|----------|
| dbt execution | Bash matches `dbt (run\|build\|test)` | "dbt finished. You changed N models. Run data review?" |
| Pre-commit | Pre-commit hook fires | "N model changes not yet reviewed. Check before committing?" |
| Manual | User runs `/recce-review` | Always available |

### Plugin Component Pattern: Thin Skill + Heavy Subagent

- Skill (SKILL.md) handles auto-trigger detection and lightweight routing
- Subagent handles progressive data review (isolated context, no main conversation pollution)
- `/recce-review` command dispatches the subagent directly

### Existing Reference Code

- `recce-quickstart` plugin: commands, skills, hooks, MCP scripts (patterns to adapt, not reuse directly)
- `packages/recce-docs-mcp/`: docs MCP server (local build, not npm published)
- Recce OSS MCP server: 8 tools (lineage_diff, row_count_diff, schema_diff, query_diff, profile_diff, etc.)

### Coordination

- DRC-2919 (Kent Huang): Recce MCP tool enhancements — need response format alignment
- DRC-2920 (Kent Huang): E2E validation — install → review → feedback
- DRC-2921 (KC): Phase 2 Technical Design

## Constraints

- **Plugin system**: Must follow Claude Code plugin conventions (plugin.json, hooks.json, SKILL.md naming, `${CLAUDE_PLUGIN_ROOT}` paths)
- **MCP transport**: Recce MCP uses HTTP/SSE (not stdio); recce-docs MCP uses stdio (local build)
- **recce-docs path**: Relative path `../../packages/recce-docs-mcp/dist/index.js` — fragile for marketplace install, flagged for Phase 5
- **No auto-dbt**: Never auto-run `dbt run/build` — suggest only (production safety)
- **Repo scope**: Plugin lives in `recce-claude-plugin/plugins/recce-dev/`; GSD plan stays local (not pushed)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Separate plugin from recce-quickstart | PoC validation first, consolidate after | — Pending |
| recce-docs MCP via local build | Not published to npm yet | — Pending |
| Thin skill + heavy subagent | Skill for trigger detection, subagent for isolated progressive review | — Pending |
| MCP scripts: copy from recce-quickstart | Adapt existing patterns to new settings system | — Pending |
| Plugin-forge validation as final phase | Validate overall quality after all features complete | — Pending |
| GSD plan local-only | `.planning/` in `.gitignore`, not pushed to remote | — Pending |
| Progressive review depth default | lineage → row_count → schema → summary, deeper only if needed | — Pending |

---
*Last updated: 2026-03-11 after initialization*
