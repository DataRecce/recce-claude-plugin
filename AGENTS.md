# Agent Instructions

This project uses **bd** (beads) for issue tracking. Run `bd onboard` to get started.

## PR Impact Analysis (One-Sentence Trigger)

<!-- Codex AGENTS.md convention v2026-05 — pinned at cascade-003 implementation (R6) -->

Any of the following natural-language phrases SHOULD trigger the full
bootstrap-and-analysis flow below in a dbt project directory. Confirm intent
once with the user before running the **branch-mutating** steps in Step 3
(see "Confirmation gate" below) — do **not** proceed straight from a
trigger phrase into `git checkout` or `dbt build`.

**Canonical trigger phrases:**
- "summarize the impact of my changes"
- "summarize my PR impact"
- "what changed vs main"
- "data diff for this branch"
- "compare my branch to main"
- "what models did I change"
- "run recce"
- "check my dbt changes"

### Orchestration Steps (Codex path, mirrors recce-analyze.md steps 1–7)

`${CLAUDE_PLUGIN_ROOT}` below is the absolute path to this Claude Code plugin
on disk (e.g. `~/.claude/plugins/cache/recce-team/recce-quickstart/<ver>`).
Codex does not export this variable — substitute the literal path before
running the script.

**Step 1 — Prerequisites:**
```bash
ls dbt_project.yml          # must exist
dbt --version               # required
recce --version             # required
```
- Missing `dbt_project.yml` → tell the user this is not a dbt project root and stop.
- Missing `dbt` → guide adapter install (`pip install dbt-<adapter>`).
- Missing `recce` → `pip install recce`.

**Step 2 — Branch detection:**
```bash
git branch --show-current
git branch --list main master
```
- target = current branch.
- If current is `main`/`master`, ask the user which feature branch to compare against.
- Otherwise base = `main` or `master` (whichever exists).
- Confirm the detected target/base pair with the user before proceeding.

**Step 3 — Base strategy:**
```bash
recce check-base --format json
```
**Fallback:** If `recce check-base` exits non-zero, prints non-JSON, or
returns an unknown `recommendation`, tell the user to upgrade recce
(`pip install -U recce`) and fall back to the `full_build` path below
using the safe stash dance.

Parse `recommendation`:
- `reuse` → proceed to Step 4 (fast path; no branch mutation).
- `docs_generate` → warn verbatim
  _"⚠️ Base artifacts are stale. Refreshing with dbt docs generate…"_ (AC-3),
  then run `dbt docs generate --target-path target-base` **from the base
  branch** via the safe stash dance below.
- `full_build` → run `dbt build --target-path target-base` from the base
  branch via the safe stash dance below.

**Confirmation gate (REQUIRED for `docs_generate` and `full_build`):** Before
any `git checkout` or `dbt build`, print a one-line summary (base branch,
target branch, expected runtime) and ask the user to confirm with `y/N`.
Only proceed on explicit `y`.

**Safe stash dance** — naive `git stash; checkout; build; checkout; pop`
is unsafe (clean tree creates no stash entry; untracked files block checkout;
mid-flight failure strands the user on the base branch). Use the named-stash
+ trap pattern:

```bash
set -e
STASH_MSG="recce-analyze-$(date +%s)"
TARGET_BRANCH="$(git branch --show-current)"

cleanup() {
  git checkout "$TARGET_BRANCH" >/dev/null 2>&1 || true
  STASH_REF="$(git stash list | grep -F "$STASH_MSG" | head -n1 | cut -d: -f1)"
  if [ -n "$STASH_REF" ]; then
    git stash pop "$STASH_REF" || \
      echo "⚠️  Stash $STASH_REF could not be popped cleanly. Run: git stash list"
  fi
}
trap cleanup EXIT

git stash push --include-untracked -m "$STASH_MSG" || true
git checkout <base-branch>
# docs_generate:  dbt docs generate --target-path target-base
# full_build:     dbt build         --target-path target-base
```

**Step 4 — Target artifacts:**
```bash
ls target/manifest.json 2>/dev/null || echo MISSING
```
If missing → `dbt docs generate`.

**Step 5 — Start MCP server:**
```bash
bash ${CLAUDE_PLUGIN_ROOT}/scripts/start-mcp.sh
```
Verify `STATUS=STARTED` or `STATUS=ALREADY_RUNNING` before continuing.

**Step 6 — Analysis (call MCP tools in order):**
1. `mcp__recce__impact_analysis` — fast summary first.
2. `mcp__recce__lineage_diff` — model-level changes.
3. `mcp__recce__schema_diff` — column structure changes.
4. `mcp__recce__row_count_diff` with `select: "config.materialized:table"` — tables only.

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

### Error Recovery

- MCP server fails to start: `cat /tmp/recce-mcp-server.log`. Common
  causes — database connection errors (check `profiles.yml`), missing
  artifacts (re-run the matching artifact step), port conflicts (set
  `RECCE_MCP_PORT`).
- Stash unpopped after Step 3: `git stash list` to find the
  `recce-analyze-<ts>` entry, then `git stash pop stash@{<n>}`.
- `recce check-base` unavailable: upgrade recce or fall back to
  `dbt build --target-path target-base` from the base branch via the
  safe stash dance.

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
