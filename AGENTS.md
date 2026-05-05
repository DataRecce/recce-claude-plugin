# Agent Instructions

This project uses **bd** (beads) for issue tracking. Run `bd onboard` to get started.

## PR Impact Analysis (One-Sentence Trigger)

<!-- Codex AGENTS.md convention v2026-05 — pinned at cascade-003 implementation (R6) -->

Any of the following natural-language phrases MUST trigger the full
bootstrap-and-analysis flow below. Execute immediately without asking for
confirmation when one of these phrases is detected in a dbt project directory.

**Canonical trigger phrases:**
- "summarize the impact of my changes"
- "summarize my PR impact"
- "what changed vs main"
- "data diff for this branch"
- "review my changes" (in dbt project context)
- "show me what broke"
- "compare my branch to main"
- "what models did I change"
- "run recce"
- "check my dbt changes"

### Orchestration Steps (Codex path, mirrors recce-analyze.md steps 3–7)

Assumes prerequisites (dbt, recce installed; dbt_project.yml present) and branch
detection are already satisfied. Adapt `${CLAUDE_PLUGIN_ROOT}` to the Codex
equivalent plugin root path.

**Step 3 — Base strategy:**
```bash
recce check-base --format json
```
Parse `recommendation`:
- `reuse` → proceed to Step 4.
- `docs_generate` → warn "_⚠️ Base artifacts are stale. Refreshing…_" (AC-3);
  run `dbt docs generate --target-path target-base`; proceed to Step 4.
- `full_build` → `git stash; git checkout <base>; dbt build --target-path target-base; git checkout <target>; git stash pop`.

**Step 4 — Target artifacts:**
```bash
ls target/manifest.json 2>/dev/null || echo MISSING
```
If missing → `dbt docs generate`.

**Step 5 — Start MCP server:**
```bash
bash ${CODEX_PLUGIN_ROOT}/scripts/start-mcp.sh
```
Verify `STATUS=STARTED` or `STATUS=ALREADY_RUNNING` before continuing.

**Step 6 — Analysis (call MCP tools in order):**
1. `impact_analysis` — fast summary first.
2. `lineage_diff` — model-level changes.
3. `schema_diff` — column structure changes.
4. `row_count_diff` with `select: "config.materialized:table"` — tables only.

**Step 7 — Output:**
Render a four-section markdown report:
```
## Impact Summary        ← narrative from impact_analysis
## Lineage Changes       ← from lineage_diff
## Schema Changes        ← table from schema_diff
## Row Count Changes     ← table from row_count_diff
```
All four sections MUST appear. Write _"No changes detected."_ for empty
sections. Log elapsed time; warn if > 120 s.

## Quick Reference

```bash
bd ready              # Find available work
bd show <id>          # View issue details
bd update <id> --status in_progress  # Claim work
bd close <id>         # Complete work
bd sync               # Sync with git
```

## Landing the Plane (Session Completion)

**When ending a work session**, you MUST complete ALL steps below. Work is NOT complete until `git push` succeeds.

**MANDATORY WORKFLOW:**

1. **File issues for remaining work** - Create issues for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **PUSH TO REMOTE** - This is MANDATORY:
   ```bash
   git pull --rebase
   bd sync
   git push
   git status  # MUST show "up to date with origin"
   ```
5. **Clean up** - Clear stashes, prune remote branches
6. **Verify** - All changes committed AND pushed
7. **Hand off** - Provide context for next session

**CRITICAL RULES:**
- Work is NOT complete until `git push` succeeds
- NEVER stop before pushing - that leaves work stranded locally
- NEVER say "ready to push when you are" - YOU must push
- If push fails, resolve and retry until it succeeds

