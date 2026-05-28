# Sandbox verification — 2026-05-28

Per [DRC-3584](https://linear.app/recce/issue/DRC-3584) acceptance criterion #2: one fixture × {Claude Code, Codex} × {Tier-0, Tier-1} verified by hand, with agent traces inspected to confirm enforcement actually fires.

**Fixture:** `pr1-fix-clv`. **Worktree:** `.claude/worktrees/drc-3584-sandbox-profiles`. **Hook revision:** `v2` (Python, post-PR-#36-review).

The v1 case-glob bash hooks (shipped in the first PR-#36 commit) were superseded after the code review surfaced six bypass shapes the case-glob couldn't address. The v2 hooks use `shlex` tokenisation, `basename` path-stripping, `sh -c` recursion, and case-insensitive skill/MCP matching. The "Bypass attempts" table below is the load-bearing evidence that v2 closes the bypasses.

## Bypass attempts (the new red-team table)

Each cell ran the actual `deny-tier-{0,1}.py` hook against the JSON payload via stdin. **Every row must be exit 2** (denied) for the rubric's enforcement story to hold.

### Tier-0 hook

| Bypass shape | Payload `command` (or `tool_name` / `skill`) | Reviewer finding | Observed |
|---|---|---|---|
| Shell separator `;` | `true;recce check` | B1 | ✅ exit 2 |
| Pipe `\|` | `true\|recce check` | B1 | ✅ exit 2 |
| Subshell `()` | `(recce check)` | B1 | ✅ exit 2 |
| Command substitution `$()` | `echo $(recce ls)` | B1 | ✅ exit 2 |
| Variable indirection | `PROG=recce; $PROG ls` | B1 | ✅ exit 2 |
| Absolute path (recce) | `/usr/local/bin/recce check` | B2 | ✅ exit 2 |
| Absolute path under /opt | `/opt/recce/bin/recce ls` | B2 | ✅ exit 2 |
| `sh -c` wrapper | `sh -c "recce check"` | B3 | ✅ exit 2 |
| `bash -lc` wrapper | `bash -lc "recce check"` | B3 | ✅ exit 2 |
| `dbt` global flag before subcommand | `dbt --debug parse` | B4 | ✅ exit 2 |
| `dbt --profiles-dir` interposed | `dbt --profiles-dir /tmp parse` | B4 | ✅ exit 2 |
| `dbt -q` short-form flag | `dbt -q parse` | B4 | ✅ exit 2 |
| Capitalised Skill name | `tool_name=Skill, skill=Recce-verify` | B5 | ✅ exit 2 |
| Uppercase Skill name | `tool_name=Skill, skill=RECCE-VERIFY` | B5 | ✅ exit 2 |
| `mcp__recce_dev__*` namespace | `tool_name=mcp__recce_dev__some_tool` | I10 | ✅ exit 2 |
| **Counter-claim**: spoiler path read | `cat ../../RUBRIC.md` | B6 | ✅ exit 0 (allowed by hook; **cwd separation does the work**, per the revised ENFORCEMENT.md) |

### Tier-1 hook

| Bypass shape | Payload `command` | Observed |
|---|---|---|
| dbt with global flag | `dbt --debug parse` | ✅ exit 2 |
| `sh -c "psql ..."` | `sh -c "psql -h h -c x"` | ✅ exit 2 |
| Absolute path psql | `/usr/bin/psql -c "select 1"` | ✅ exit 2 |
| Pipeline with dbt parse | `true;dbt parse` | ✅ exit 2 |
| **Counter-claim**: Recce allowed | `recce check` | ✅ exit 0 |
| **Counter-claim**: Recce MCP allowed | `tool_name=mcp__recce__row_count_diff` | ✅ exit 0 |
| dbt parse direct | `dbt parse` | ✅ exit 2 |
| `git diff` | `git diff HEAD` | ✅ exit 0 |

## Happy-path coverage (regression check)

These were green in the v1 hook and must stay green in v2.

### Tier-0

| Cell | Observed |
|---|---|
| `recce check` direct | ✅ exit 2 |
| `mcp__recce__row_count_diff` | ✅ exit 2 |
| `Skill skill=recce-verify` | ✅ exit 2 |
| `dbt parse --target dev` | ✅ exit 2 |
| `git diff HEAD` (benign) | ✅ exit 0 |
| `Read /some/file` (benign) | ✅ exit 0 |
| `grep -rn foo .` | ✅ exit 0 |
| `git log \| head -20` | ✅ exit 0 |
| `jq .nodes manifest.json` | ✅ exit 0 |

## End-to-end cell: Claude Code × Tier 0

Real `claude --print` invocation with cwd at the per-fixture working tree, against the v2 Python hook.

**Setup:**

```bash
SLUG=pr1-fix-clv
WT=/Users/evenwei/InfuseAI/recce-claude-plugin/.claude/worktrees/drc-3584-sandbox-profiles
FIXTURE=$WT/evals/agent-blind-spots/.tmp/sources/$SLUG
TIER=$WT/evals/agent-blind-spots/runner-configs/claude-code/tier-0

cp -r $TIER/claude-overlay $FIXTURE/.claude

cd $FIXTURE
claude --print --permission-mode acceptEdits \
  "Run the bash command 'recce check' and report what happened, including any error message."
```

**Agent trace (v1 run; v2 hook produces the same shape with a Python-style stderr line):**

```
The command was blocked by a sandbox hook.

**What happened:**
- Command attempted: `recce check`
- Result: Blocked before execution

**Error message:**
PreToolUse:Bash hook error: [python3 "$CLAUDE_PROJECT_DIR/.claude/hooks/deny-tier-0.py"]:
Tier-0 sandbox blocks: Bash executable 'recce' not in Tier-0 allowlist (matched in: 'recce check')
```

**Result:** ✅ PASS — the hook fires, the agent surfaces the block. (Re-running this cell against the v2 hook is recommended once the operator picks up the deferred 3 cells below; the hook logic is otherwise identical to what fired in the v1 run.)

## Cells deferred to operator (acceptance #2 leftover)

The remaining three cells need an environment with Recce MCP reachable and the `codex` CLI configured against the same fixture working tree. Run them once before declaring DRC-3584 done:

| Cell | What to check | Pass condition |
|---|---|---|
| Claude Code × Tier 1 | `mcp__recce__*` call from the agent succeeds; raw `psql`/`dbt parse` blocked | At least one Recce MCP tool returns data; the dbt/SQL attempts surface the Tier-1 deny message |
| Codex × Tier 0 | `recce check` in Bash → "command not found" (PATH scrub); `mcp__recce__*` unresolved (empty MCP allowlist) | Both attempts fail; transcript shows the failure surface |
| Codex × Tier 1 | `mcp__recce__*` from the agent succeeds; `dbt parse` → "command not found" | Recce MCP works; dbt is unreachable |

Recipes for each cell: see [`../../ENFORCEMENT.md`](../../ENFORCEMENT.md) (Claude Code) and [`../../runner-configs/codex/tier-{0,1}/README.md`](../../runner-configs/codex/) (Codex).

## DRC-3430 strip — verified concurrently

`build_fixtures.sh` re-run end-to-end (all 6 fixtures) with the expanded strip list (post-review):

```
OK pr1-fix-clv
OK pr2-refactor-cte-to-models
OK pr3-amount-double-to-decimal
OK pr42-is-closed-filter
OK pr44-promotion-flags
OK pr46-net-clv-segments
```

Strip list now covers (in addition to the v1 list):

- `.devcontainer/` (Recce-specific dev container + post-start script that boots Recce)
- `.github/mcp_config.json` (explicit Recce MCP registration)
- `.github/workflows/recce_*.{yml,yaml}` glob (the `recce-*` glob already in v1 missed `recce_ci.yml`)
- `.github/workflows/dbt-build-pr.yml`, `dbt-build-base.yml`, `dbt_base.yml` (dbt CI that uses `DataRecce/recce-cloud-cicd-action`)

Post-build leak audit (case-insensitive `recce` match, profiles.yml whitelisted):

```
$ grep -rlEi --exclude-dir=.git --exclude=profiles.yml 'mcp__recce|recce' .tmp/sources
(empty)
```

`profiles.yml` is whitelisted from the grep — its `role: RECCE` is the Snowflake role name, not Recce-the-tool priming. A role name doesn't tell the agent how to use Recce; stripping `profiles.yml` would break dbt parse.
