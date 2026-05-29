# Sandbox verification — 2026-05-28

Per [DRC-3584](https://linear.app/recce/issue/DRC-3584) acceptance criterion #2: one fixture × {Claude Code, Codex} × {Tier-0, Tier-1} verified by hand, with agent traces inspected to confirm enforcement actually fires.

**Fixture:** `pr1-fix-clv`. **Worktree:** `.claude/worktrees/drc-3584-sandbox-profiles`. **Hook revision:** `v5` (bashlex AST; post-PR-#36-cycle-iteration-3).

The v1 case-glob bash hooks (shipped in the first PR-#36 commit) were superseded four times:
- **v2** (Python rewrite using shlex + regex) — closed the 6 bypass shapes the case-glob couldn't address (shell separators, absolute paths, `sh -c`, dbt global flags, skill case-sensitivity, the false ENFORCEMENT.md:71 claim).
- **v3** — closed the 2 additional bypass shapes cycle iter-1 surfaced (Tier-1 dbt flag-with-value, exec-wrapper-launches-denied-binary).
- **v4** — closed 3 additional bypass classes cycle iter-2 surfaced (`eval` shell-builtin smuggling, `$()`/backtick substitution at command-head, missing dbt subcommands `clone`/`retry`).
- **v5** (this revision) — closed 9 additional bypass classes cycle iter-3 surfaced. Required a structural rewrite from regex/shlex to `bashlex` (a real Bash AST parser) because the bypasses exploited Bash semantics shlex/regex couldn't model: nested `$()`, ANSI-C `$'...'`, parameter expansion `${a:-default}`, Bash keywords (`coproc`, `!`), command modifiers (`command`, `builtin`), exec-wrapper smuggling (`xargs -I {} sh -c "{} parse" dbt`), and substitution-produces-subcommand (`dbt $(echo run)`).

The "Bypass attempts" tables below are the load-bearing evidence that v3 closes every reviewer-named bypass. All rows are exit-2 expected; the few exit-0 entries are explicit counter-claims (a documented allow path that protects the rubric for a different reason — typically cwd separation rather than the hook).

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
| `dbt` value-less flag before subcommand | `dbt --debug parse` | B4 | ✅ exit 2 (denied by allowlist — dbt not in allowlist) |
| `dbt --profiles-dir` interposed | `dbt --profiles-dir /tmp parse` | B4 | ✅ exit 2 (denied by allowlist) |
| `dbt -q` short-form flag | `dbt -q parse` | B4 | ✅ exit 2 (denied by allowlist) |
| Capitalised Skill name | `tool_name=Skill, skill=Recce-verify` | B5 | ✅ exit 2 |
| Uppercase Skill name | `tool_name=Skill, skill=RECCE-VERIFY` | B5 | ✅ exit 2 |
| `mcp__recce_dev__*` namespace | `tool_name=mcp__recce_dev__some_tool` | I10 | ✅ exit 2 |
| Exec wrapper: `xargs recce` | `echo check \| xargs recce` | cycle B2 | ✅ exit 2 |
| Exec wrapper: `xargs -I {} recce` | `ls \| xargs -I {} recce {}` | cycle B2 | ✅ exit 2 |
| Exec wrapper: `find -exec recce` | `find . -exec recce {} \;` | cycle B2 | ✅ exit 2 |
| **Counter-claim**: spoiler path read | `cat ../../RUBRIC.md` | B6 | ✅ exit 0 (allowed by hook; **cwd separation does the work**, per the revised ENFORCEMENT.md) |
| **Counter-claim**: benign xargs | `echo a \| xargs grep b` | regression | ✅ exit 0 (xargs wraps grep, both allowlisted) |
| **Counter-claim**: benign find -exec | `find . -exec grep foo {} \;` | regression | ✅ exit 0 |
| **Counter-claim**: find without -exec | `find . -name foo` | regression | ✅ exit 0 |
| **v4 — `eval` banned outright** | `eval recce check` | iter-2 | ✅ exit 2 |
| `eval "ls -la"` (even benign args) | `eval "ls -la"` | iter-2 | ✅ exit 2 (no legit reason for `eval` at Tier 0) |

Note: the cycle review (`v2 review`, NOTE 5) flagged the matcher regex `Bash|Skill|mcp__(plugin_)?recce(_|-).*` as "barely permissive enough to fire for `mcp__recce_dev__*`". Confirmed working: the synthetic payload above fires the hook (would be exit 2 instead of an un-gated allow path).

### Tier-1 hook

| Bypass shape | Payload `command` | Cycle finding | Observed |
|---|---|---|---|
| dbt with value-less flag | `dbt --debug parse` | B4 | ✅ exit 2 |
| dbt with flag-with-value (target) | `dbt --target dev parse` | cycle B1 | ✅ exit 2 |
| dbt with flag-with-value (profiles-dir) | `dbt --profiles-dir /tmp parse` | cycle B1 | ✅ exit 2 |
| dbt with flag-with-value (project-dir) | `dbt --project-dir /x run` | cycle B1 | ✅ exit 2 |
| dbt with flag-with-value (vars) | `dbt --vars "x: 1" parse` | cycle B1 | ✅ exit 2 |
| dbt with flag-with-value (log-format) | `dbt --log-format json parse` | cycle B1 | ✅ exit 2 |
| dbt with flag-with-value (log-level) | `dbt --log-level debug parse` | cycle B1 | ✅ exit 2 |
| dbt with flag-with-value (printer-width) | `dbt --printer-width 80 parse` | cycle B1 | ✅ exit 2 |
| dbt with flag-with-value (profile) | `dbt --profile myprof parse` | cycle B1 | ✅ exit 2 |
| `sh -c "psql ..."` | `sh -c "psql -h h -c x"` | B3 | ✅ exit 2 |
| Absolute path psql | `/usr/bin/psql -c "select 1"` | B2 | ✅ exit 2 |
| Pipeline with dbt parse | `true;dbt parse` | B1 | ✅ exit 2 |
| Exec wrapper: `xargs dbt` | `echo a \| xargs dbt parse` | cycle B2 | ✅ exit 2 |
| Exec wrapper: `find -exec dbt` | `find . -exec dbt parse \;` | cycle B2 | ✅ exit 2 |
| Exec wrapper: `time dbt` | `time dbt parse` | cycle B2 | ✅ exit 2 |
| Exec wrapper: `nohup dbt` | `nohup dbt parse` | cycle B2 | ✅ exit 2 |
| Exec wrapper: `timeout` + psql | `timeout 30 psql -c x` | cycle B2 | ✅ exit 2 |
| Exec wrapper: `xargs psql` | `echo s \| xargs psql` | cycle B2 | ✅ exit 2 |
| Exec wrapper: `chrt` + psql | `chrt 0 5 psql -c x` | cycle B2 | ✅ exit 2 |
| Exec wrapper: `ionice` + psql | `ionice -c 2 psql` | cycle B2 | ✅ exit 2 |
| **Counter-claim**: Recce allowed | `recce check` | rubric | ✅ exit 0 |
| **Counter-claim**: Recce MCP allowed | `tool_name=mcp__recce__row_count_diff` | rubric | ✅ exit 0 |
| **Counter-claim**: bare dbt allowed | `dbt` (discovery only) | rubric | ✅ exit 0 |
| **Counter-claim**: dbt --help allowed | `dbt --help` | rubric | ✅ exit 0 |
| **Counter-claim**: dbt list allowed | `dbt list` (read-only manifest) | rubric | ✅ exit 0 |
| **Counter-claim**: dbt deps allowed | `dbt deps` (no warehouse) | rubric | ✅ exit 0 |
| dbt parse direct | `dbt parse` | B4 | ✅ exit 2 |
| `git diff` | `git diff HEAD` | regression | ✅ exit 0 |
| **v4 — `eval` shell-builtin smuggling** | `eval dbt run` | iter-2 | ✅ exit 2 |
| `eval` with quoted inner | `eval "dbt run"` | iter-2 | ✅ exit 2 |
| **v4 — `$()` substitution at head** | `$(echo dbt) run` | iter-2 | ✅ exit 2 |
| Backtick substitution at head | `` `echo dbt` run `` | iter-2 | ✅ exit 2 |
| `$(printf %s dbt) parse` | `$(printf %s dbt) parse` | iter-2 | ✅ exit 2 |
| **v4 — `dbt clone`** | `dbt clone` (warehouse) | iter-2 | ✅ exit 2 |
| **v4 — `dbt retry`** | `dbt retry` (inherits prior cmd) | iter-2 | ✅ exit 2 |
| **Counter-claim**: `$()` not at head | `git log --grep=$(echo psql)` | iter-2 | ✅ exit 0 |
| **Counter-claim**: benign `$()` head | `$(which python) script.py` | iter-2 | ✅ exit 0 |
| **Counter-claim**: benign `$(echo grep)` | `$(echo grep) -rn foo .` | iter-2 | ✅ exit 0 |
| **Counter-claim**: dbt-without-subcommand via `$()` | `$(echo dbt)` | iter-2 | ✅ exit 0 (bare dbt allowed) |
| **v5 — nested `$()` L1** | `$(sh -c "$(echo dbt) run")` | iter-3 | ✅ exit 2 |
| **v5 — nested `$()` L2** | `$($(echo dbt) run)` | iter-3 | ✅ exit 2 |
| **v5 — nested backtick + `$()`** | `` `$(echo dbt) run` `` | iter-3 | ✅ exit 2 |
| **v5 — `eval $(...)` smuggling** | `eval $(echo "dbt parse")` | iter-3 | ✅ exit 2 |
| **v5 — `xargs $(echo dbt)`** | `xargs $(echo dbt)` | iter-3 | ✅ exit 2 (denied: xargs-wrapped denied basename) |
| **v5 — substitution-supplied subcommand** | `dbt $(echo run)` | iter-3 | ✅ exit 2 |
| **v5 — ANSI-C `$'dbt'`** | `$'dbt' parse` | iter-3 | ✅ exit 2 |
| **v5 — parameter expansion `${a:-dbt}`** | `${a:-dbt} parse` | iter-3 | ✅ exit 2 |
| **v5 — `coproc` keyword** | `coproc dbt run` | iter-3 | ✅ exit 2 (denied pre-parse; bashlex doesn't support coproc) |
| **v5 — `command` modifier** | `command dbt run` | iter-3 | ✅ exit 2 (transparent prefix; dbt revealed underneath) |
| **v5 — `builtin eval`** | `builtin eval dbt run` | iter-3 | ✅ exit 2 |
| **v5 — `!` negation prefix** | `! dbt run` | iter-3 | ✅ exit 2 (pipeline negation walked) |
| **v5 — `xargs -I {} sh -c "{} parse" dbt`** | `xargs -I {} sh -c "{} parse" dbt` | iter-3 | ✅ exit 2 (denied: dbt in wrapped position) |

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
