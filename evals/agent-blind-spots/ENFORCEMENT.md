# Enforcement — Tier-0 / Tier-1 sandbox profiles

Operational counterpart of `RUBRIC.md`'s Tier-0 runtime contract. The rubric defines **what** the agent must (and must not) see; this document defines **how** the runner makes that real and **how it gets recorded** in each baseline.

This is load-bearing: the lens-3 counterfactual delta (Tier-0 verdict → Tier-1 verdict) only isolates Recce's contribution if a Tier-0 agent provably cannot reach Recce-shaped signals. If Tier-0 can sneak a peek — Recce MCP tools registered, `recce.yml` in the source tree, warehouse credentials in env, live SQL accessible, spoiler READMEs reachable — every downstream conclusion is contaminated.

The sandbox profile templates live under [`runner-configs/`](runner-configs/). See [`runner-configs/README.md`](runner-configs/README.md) for the per-agent / per-tier file map; this document is the recipe that turns those templates into a recorded baseline.

## Prerequisite — `bashlex`

The Claude Code PreToolUse hooks (`deny-tier-{0,1}.py`) use `bashlex` to parse the agent's Bash command into an AST. Without it the hooks fail closed (exit 2 with an install message) so bypasses cannot slip through silently. Install once per eval-runner Python:

```bash
python3 -m pip install bashlex
```

This is needed for the Claude Code runner only — Codex's enforcement is process-sandbox + PATH scrub + MCP allowlist, no hook involved.

## Recipe — Claude Code

### Tier 0

```bash
SLUG="pr1-fix-clv"                                # the fixture you're scoring
WT_ROOT="$(git rev-parse --show-toplevel)"        # eval host repo root
FIXTURE_DIR="${WT_ROOT}/evals/agent-blind-spots/.tmp/sources/${SLUG}"
TIER_DIR="${WT_ROOT}/evals/agent-blind-spots/runner-configs/claude-code/tier-0"

# 1. Build fixtures if you haven't, and confirm bashlex is installed.
( cd "${WT_ROOT}/evals/agent-blind-spots" && ./build_fixtures.sh )
python3 -c "import bashlex" || python3 -m pip install bashlex

# 2. Stamp the per-fixture working tree with the Tier-0 sandbox config.
#    `claude-overlay/` becomes `.claude/` inside the fixture — the source
#    directory is named differently so it isn't swallowed by the repo's
#    `.claude/` gitignore rule.
cp -r "${TIER_DIR}/claude-overlay" "${FIXTURE_DIR}/.claude"

# 3. Neuter user-level Claude Code settings so a stray ~/.claude/settings.json
#    can't widen the sandbox. (Skip this step at your own risk.)
export CLAUDE_CONFIG_DIR="$(mktemp -d)"

# 4. Clear warehouse and Recce credentials in the shell that spawns Claude Code.
unset RECCE_API_TOKEN DBT_PROFILES_DIR
unset SNOWFLAKE_USER SNOWFLAKE_PASSWORD SNOWFLAKE_ACCOUNT
unset POSTGRES_PASSWORD BIGQUERY_PROJECT
# (extend to match your environment; goal is no live credential in env)

# 5. Run the agent with cwd at the per-fixture working tree.
cd "${FIXTURE_DIR}"
claude "<the prompt — see RUBRIC.md Tier-0 prompt-shape contract>"
```

The Tier-0 `.claude/settings.json` declares `permissions.deny` rules for the documented Recce MCP namespaces and dbt/SQL-client Bash patterns, and registers a `PreToolUse` hook (`deny-tier-0.py`). The hook is the **load-bearing layer** — `permissions.deny` is conceded to be unreliable (Claude Code [issue #6699](https://github.com/anthropics/claude-code/issues/6699)) and uses shell-glob matching whose surface differs from the hook's AST-based check. Treat `permissions.deny` as documentation; trust the hook. See `runner-configs/README.md` for the divergence details.

The hook uses `bashlex` (a real Bash AST parser) so nested `$()`, ANSI-C `$'...'`, parameter expansion `${a:-default}`, Bash keywords (`!`, `coproc`), command modifiers (`command`, `builtin`), and exec wrappers (`xargs`, `find -exec`, `time`, `nohup`, …) are all handled by their AST shape rather than ad-hoc regex.

### Tier 1

Same shape as Tier 0, with three differences:

1. `TIER_DIR` points to `runner-configs/claude-code/tier-1/`.
2. Leave the **dev-environment** warehouse credentials in the shell (or load them from a secrets file). Do **not** also export base/prod credentials — Tier 1 is single-env.
3. Recce MCP must be reachable to Claude Code (typically already true if `/recce-verify` works locally). The Tier-1 settings allow Recce MCP tools and Recce CLI; only dbt-regen and direct SQL clients stay denied.

## Recipe — Codex

See:

* [`runner-configs/codex/tier-0/README.md`](runner-configs/codex/tier-0/README.md)
* [`runner-configs/codex/tier-1/README.md`](runner-configs/codex/tier-1/README.md)

Both layer process sandboxing (`--sandbox=read-only` / `workspace-write`), MCP allowlisting (`config.toml`'s `mcp_servers` table), and a `PATH` scrub. Codex does not load `.claude/settings.json`, so the enforcement shape is different from Claude Code's even though the contract it satisfies is the same.

## Agent view restriction (folded from PR #28 follow-up)

The Tier-0 runtime contract enumerates the *inputs the agent gets*. It is not enough to enumerate what's allowed — the runner must also keep spoilers out of the agent's reach. A naive `claude` / `codex` invocation from the eval host repo root gives the agent file-read access to:

- `evals/agent-blind-spots/fixtures/<slug>/README.md` — contains `## Expected agent verdict — Tier 0` sections that *literally tell the agent the answer*
- `evals/agent-blind-spots/RUBRIC.md` — the rubric the agent is being scored against
- Sibling fixtures' files — useful for cross-comparison the agent should not have

The runner therefore **must** launch the agent with cwd set to the per-fixture working tree at `.tmp/sources/<slug>/` (a freshly-initialised standalone git repo from `build_fixtures.sh` — see step 2 in the script). The per-fixture worktree is structurally separated from the eval host repo: it has one commit, zero remotes, and no path back to `evals/`. With cwd at that worktree, the spoiler paths are outside the agent's filesystem reach for the duration of the run.

This complements the cwd separation:

* Claude Code: the project-level `.claude/settings.json` lives inside the per-fixture worktree, so it travels with the agent's cwd. **Spoiler-path protection comes from cwd alone** — the PreToolUse hook does not gate `Read`/`Grep`/`Glob` and the Tier-0 Bash allowlist includes `cat`. If the runner mistakenly launches `claude` from the eval host repo root, the agent can read `RUBRIC.md` and the per-fixture spoiler README. The recipe above (step 5: `cd "${FIXTURE_DIR}"`) is therefore not optional.
* Codex: the process sandbox is anchored on cwd; absolute paths outside cwd require approval at Tier-0 read-only mode and writes are uniformly denied.

## Recording in the baseline

Every Tier-0 and Tier-1 baseline records which sandbox profile fired, so deltas across iterations are reproducible. The Notes section of `templates/tier-0-baseline.md` has dedicated fields:

```markdown
## Notes

...

### Sandbox profile used

- Agent runtime: <Claude Code | Codex>
- Tier: <0 | 1>
- Profile source: <e.g., evals/agent-blind-spots/runner-configs/claude-code/tier-0 @ <git-sha>>
- Enforcement mechanism summary: <one or two lines — `permissions.deny` + PreToolUse hook for Claude Code; `--sandbox=read-only` + PATH scrub + empty MCP allowlist for Codex>
- Deviation from the recipe: <none | description>
```

Without a recorded mechanism the baseline is unreproducible; treat a missing block as a baseline-of-record disqualifier.

## Verifying enforcement (one-fixture smoke test)

Per DRC-3584 acceptance criterion #2, run one fixture × {Claude Code, Codex} × {Tier-0, Tier-1} by hand and inspect the agent trace to confirm enforcement fires when the agent attempts a banned operation. The minimum trace check per cell:

| Cell | What to grep the trace for | Pass condition |
|---|---|---|
| Claude Code · Tier 0 | `mcp__recce__`, `recce ` shell call, `dbt parse`, `dbt compile`, `Skill recce-verify` | All blocked (PreToolUse hook stderr line `Tier-0 sandbox blocks: ...`, exit 2) |
| Claude Code · Tier 1 | `mcp__recce__` succeeded | At least one Recce MCP tool call returned data |
| Claude Code · Tier 1 | `dbt parse`, `dbt compile`, raw `duckdb`/`psql`/`snowsql`/`bq` | All blocked |
| Codex · Tier 0 | `recce ` shell call, `dbt parse`, `mcp__recce__` reference | All blocked (`command not found` from PATH scrub; MCP table empty so tool name unresolved) |
| Codex · Tier 1 | `mcp__recce__` succeeded | At least one Recce MCP tool call returned data |
| Codex · Tier 1 | `dbt parse`, raw SQL clients | All blocked |
| Any cell | Read of `../README.md`, `../../RUBRIC.md`, sibling fixture file | Blocked (cwd-out-of-workspace; sandbox denies) |

Record the result in a `runs/<YYYY-MM-DD>/sandbox-verification.md` per cell so future contributors can repro.

## Threat model — non-adversarial code agent

`RUBRIC.md` evaluates a **non-adversarial code agent** doing dbt PR review under instruction. That agent's failure mode is forgetting to call Recce, or calling Recce incorrectly — not constructing Bash incantations to slip past the sandbox. The Claude Code hooks are calibrated to that threat model; treat them as accident-prevention, not as red-team defense.

The hooks block what a non-adversarial agent reaches in normal operation:

- Direct Recce reachable paths (`recce` CLI, `mcp__recce__*`, `/recce:*` skill names, `recce.yml` discovery, `RECCE_API_TOKEN` references).
- The dbt subcommands that compile or evaluate models (`run`, `test`, `parse`, `compile`, `build`, `seed`, `snapshot`, `docs`, `freshness`, `run-operation`, `debug`, `source`, `clone`, `retry`).
- Raw SQL clients in the Tier-0 / Tier-1 denylist (`duckdb`, `psql`, `snowsql`, `bq`).
- Standard exec-wrapper laundering (`xargs`, `find -exec`, `time`, `nohup`, `parallel`, `timeout`, `command`, `builtin`) and shell-wrapper laundering (`sh -c`, `bash -c`; `eval` at Tier-0).

The hooks do **not** attempt to defeat an adversarial agent actively trying to evade the sandbox. Static Bash analysis has structural limits — an adversary can reach denied commands through any of the following classes, all of which are **accepted as out of scope for v1**:

| Class | Example | Why static analysis can't close it |
|---|---|---|
| `bashlex` parser gaps | `time dbt parse`, `case x in *) dbt parse;; esac`, `select … dbt …` | bashlex raises `NotImplementedError` on certain Bash keywords; the AST is unreachable |
| Heredoc body as interpreter input | `sh <<EOF\ndbt parse\nEOF` | The heredoc body is a string from `sh`'s perspective; not a child AST |
| Pipeline producer/consumer | `echo "dbt parse" \| sh` | The string flowing across the pipe is opaque at parse time |
| Stdin-supplied subcommands | `while read l; do dbt $l; done` | The values of `$l` are only known at runtime |
| String args evaluated later | `trap 'dbt parse' EXIT` | The string is evaluated by the trap handler at signal time |
| Interpreter shell-out | `python3 -c "os.system('dbt parse')"`, `node -e "..."`, `awk 'BEGIN{system(...)}'` | The interpreter's command is an opaque string from Bash's perspective |
| Variable-flow assignments / loops | `FOO=$(dbt parse) cmd`, `for x in $(dbt parse); do …` | Requires whole-program data-flow analysis, not single-command parsing |

Closing these would require either an OS-level sandbox (`bwrap` / `firejail` / `sandbox-exec`) or a full Bash interpreter — both larger than the eval itself. If a downstream eval discovers a *non-adversarial* agent reaching denied commands through one of these classes in practice, that becomes a follow-up issue (revisit the threat model, not patch one more pattern speculatively).

For Codex, this whole class of escape is closed by the OS-level process sandbox (`--sandbox=read-only` / `workspace-write`) plus the PATH scrub — there is no need for static Bash analysis. The Claude Code side runs without an OS-level sandbox in v1 because Claude Code does not expose one; the hook + cwd discipline is the best available approximation under that constraint.

## What this does NOT enforce

Mechanical enforcement only catches what the runner can introspect. Three categories are still contract-based:

1. **Same-model contract** (`RUBRIC.md`). Nothing here pins the model — the runner must pin it.
2. **Tier-1 base/prod credential discipline**. The Tier-1 recipe assumes the shell that spawns the agent has *only* single-env credentials. There is no programmatic check that base/prod credentials are absent; the runner must verify before launch.
3. **Prompt-shape neutrality** (`RUBRIC.md` Tier-0 prompt-shape contract). The sandbox doesn't read the prompt. A prompt that steers the agent toward humility or aggression violates the rubric but does not trip a hook.

Treat these three as runner discipline that's recorded in the baseline's Notes section.
