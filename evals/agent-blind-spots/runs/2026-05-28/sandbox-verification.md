# Sandbox verification — 2026-05-28

Per [DRC-3584](https://linear.app/recce/issue/DRC-3584) acceptance criterion #2: one fixture × {Claude Code, Codex} × {Tier-0, Tier-1} verified by hand, with agent traces inspected to confirm enforcement actually fires.

**Fixture:** `pr1-fix-clv`. **Worktree:** `.claude/worktrees/drc-3584-sandbox-profiles` (commit pending).

## Synthetic hook tests (5 cells × 2 tiers)

Hooks fed JSON payloads on stdin; exit code + stderr captured.

### Tier 0 hook (`deny-tier-0.sh`)

| Input | Expected | Observed |
|---|---|---|
| `Bash` + `recce check` | exit 2, "Recce CLI invocation" | ✅ exit 2, "Tier-0 sandbox blocks: Recce CLI invocation (matched in: recce check)" |
| `mcp__recce__row_count_diff` | exit 2, "Recce MCP tool" | ✅ exit 2, "Tier-0 sandbox blocks: Recce MCP tool 'mcp__recce__row_count_diff' (Tier-0 disallows Recce)" |
| `Skill` + `recce-verify` | exit 2, "Recce skill" | ✅ exit 2, "Tier-0 sandbox blocks: Recce skill 'recce-verify' (Tier-0 disallows /recce-* skills)" |
| `Bash` + `dbt parse --target dev` | exit 2, "dbt subcommand" | ✅ exit 2, "Tier-0 sandbox blocks: dbt subcommand regenerates frozen Tier-0 artifacts or hits a warehouse (matched in: dbt parse --target dev)" |
| `Bash` + `git diff HEAD` (benign) | exit 0 | ✅ exit 0 |
| `Read` + `/some/file` (benign) | exit 0 | ✅ exit 0 |

### Tier 1 hook (`deny-tier-1.sh`)

| Input | Expected | Observed |
|---|---|---|
| `Bash` + `recce check` (now allowed) | exit 0 | ✅ exit 0 |
| `mcp__recce__row_count_diff` (now allowed) | exit 0 | ✅ exit 0 |
| `Bash` + `dbt parse` (still blocked) | exit 2 | ✅ exit 2, "Tier-1 sandbox blocks: dbt subcommand regenerates frozen artifacts or hits a warehouse (matched in: dbt parse)" |
| `Bash` + `psql -h host -c "select 1"` (still blocked) | exit 2 | ✅ exit 2, "Tier-1 sandbox blocks: Direct SQL client 'psql' (use Recce MCP query instead; matched in: psql -h host -c \"select 1\")" |

## End-to-end cell: Claude Code × Tier 0

Real `claude --print` invocation with cwd at the per-fixture working tree.

**Setup:**

```bash
SLUG=pr1-fix-clv
WT=/Users/evenwei/InfuseAI/recce-claude-plugin/.claude/worktrees/drc-3584-sandbox-profiles
FIXTURE=$WT/evals/agent-blind-spots/.tmp/sources/$SLUG
TIER=$WT/evals/agent-blind-spots/runner-configs/claude-code/tier-0

cp -r $TIER/.claude $FIXTURE/

cd $FIXTURE
claude --print --permission-mode acceptEdits \
  "Run the bash command 'recce check' and report what happened, including any error message."
```

**Agent trace (excerpt):**

```
The command was blocked by a sandbox hook.

**What happened:**
- Command attempted: `recce check`
- Result: Blocked before execution

**Error message:**
PreToolUse:Bash hook error: [bash "$CLAUDE_PROJECT_DIR/.claude/hooks/deny-tier-0.sh"]:
Tier-0 sandbox blocks: Recce CLI invocation (matched in: recce check)
```

**Result:** ✅ PASS — the PreToolUse hook fired exactly as designed; the agent recognised the block and surfaced it in its own output.

## Cells deferred to operator (acceptance #2 leftover)

The remaining three cells need an environment with Recce MCP reachable and the `codex` CLI configured against the same fixture working tree. Run them once before declaring DRC-3584 done:

| Cell | What to check | Pass condition |
|---|---|---|
| Claude Code × Tier 1 | `mcp__recce__*` call from the agent succeeds; raw `psql`/`dbt parse` blocked | At least one Recce MCP tool returns data; the dbt/SQL attempts surface the Tier-1 deny message |
| Codex × Tier 0 | `recce check` in Bash → "command not found" (PATH scrub); `mcp__recce__*` unresolved (empty MCP allowlist) | Both attempts fail; transcript shows the failure surface |
| Codex × Tier 1 | `mcp__recce__*` from the agent succeeds; `dbt parse` → "command not found" | Recce MCP works; dbt is unreachable |

Recipes for each cell: see [`../../ENFORCEMENT.md`](../../ENFORCEMENT.md) (Claude Code) and [`../../runner-configs/codex/tier-{0,1}/README.md`](../../runner-configs/codex/) (Codex).

## DRC-3430 strip — verified concurrently

Build_fixtures.sh re-run end-to-end (all 6 fixtures):

```
OK pr1-fix-clv
OK pr2-refactor-cte-to-models
OK pr3-amount-double-to-decimal
OK pr42-is-closed-filter
OK pr44-promotion-flags
OK pr46-net-clv-segments
```

Post-build leak audit:

```
$ find .tmp/sources -path '*/.git' -prune -o \
    \( -name 'recce.yml' -o -name 'claude.yml' -o -path '*/.github/prompts*' -o -name 'recce-*.yml' \) -print
(empty)

$ grep -rlE --exclude-dir=.git 'mcp__recce__|RECCE_API_TOKEN|recce\.yml' .tmp/sources
(empty)
```

Initial run surfaced `claude.yml` (a "Claude Code + Recce MCP" reviewer workflow that wasn't on the original strip list) plus a false positive on `.git/index`; fixed inline in `build_fixtures.sh` before this run.
