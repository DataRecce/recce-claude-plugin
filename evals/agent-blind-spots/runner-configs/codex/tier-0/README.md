# Codex — Tier-0 sandbox profile

Codex (OpenAI CLI) does not load `.claude/settings.json`. Enforcement at Tier 0 is a combination of:

1. **Process sandbox** via `--sandbox=read-only` — blocks any write the agent attempts outside the workspace, which already blocks `dbt run`/`test`/`parse`/`compile`/`docs generate` (all write `target/`) and any `recce` invocation that wants to mutate state under `~/.recce/`.
2. **MCP allowlist** — invoke Codex with a `config.toml` that registers zero MCP servers (see `config.toml` in this directory). The Recce MCP server is not reachable to the agent.
3. **PATH scrub** — run Codex with a sanitised `PATH` so Recce-related binaries are not on it. This catches read-only Recce CLI calls (e.g., `recce list`) that the process sandbox would otherwise allow.
4. **Per-fixture working directory** — Codex runs with cwd at `.tmp/sources/<slug>/` (per-fixture standalone repo from `build_fixtures.sh`). Sibling fixtures, `evals/agent-blind-spots/RUBRIC.md`, and `fixtures/<slug>/README.md` are outside the workspace and not in `cwd`, so file reads can't reach them. Make sure you do **not** launch Codex from the eval repo root.

## Invocation recipe

```bash
SLUG="pr1-fix-clv"
WT_ROOT="$(git rev-parse --show-toplevel)"
FIXTURE_DIR="${WT_ROOT}/evals/agent-blind-spots/.tmp/sources/${SLUG}"

# Strip Recce + dbt binaries from PATH so even read-only CLI calls fail.
SAFE_PATH="$(echo "$PATH" \
    | tr ':' '\n' \
    | grep -v -E '/recce(/|$)|/dbt(/|$)|\.recce' \
    | paste -sd: -)"

cd "${FIXTURE_DIR}"

PATH="${SAFE_PATH}" \
RECCE_API_TOKEN="" \
DBT_PROFILES_DIR="" \
codex exec \
    --sandbox=read-only \
    --ask-for-approval=never \
    --config "${WT_ROOT}/evals/agent-blind-spots/runner-configs/codex/tier-0/config.toml" \
    "<the prompt — see RUBRIC.md Tier-0 prompt-shape contract>"
```

`RECCE_API_TOKEN=""` and `DBT_PROFILES_DIR=""` are explicit even though they look redundant — leaving real values in the parent shell silently grants the sandbox more reach than intended. Make the empty-string assignments part of the invocation.

## What's enforced vs. what's contract

| Concern | Enforced by | Notes |
|---|---|---|
| Cannot regenerate frozen artifacts (`manifest`, `compiled`, `catalog`) | `--sandbox=read-only` (no `target/` writes) + PATH scrub (no `dbt` binary) | Belt-and-suspenders |
| Cannot reach Recce MCP | `config.toml` registers zero MCP servers | The `mcp_servers` table is intentionally empty in `config.toml` |
| Cannot invoke `recce` CLI | PATH scrub | Process sandbox alone doesn't help for read-only Recce calls |
| Cannot reach a warehouse | No warehouse credentials in the eval shell + read-only sandbox + PATH scrub of SQL clients | Recipe should never `export SNOWFLAKE_PASSWORD=...` for Tier 0 |
| Cannot read spoiler files (`fixtures/<slug>/README.md`, `RUBRIC.md`, sibling fixtures) | cwd at `.tmp/sources/<slug>/` (a separate git repo from the eval host) | Out-of-workspace paths are not in the read sandbox |

## Verification check

After the run, inspect the agent transcript for:

- Any `mcp__recce__*` tool reference → leak (should not appear; MCP server isn't registered)
- Any `recce` shell call → check exit was non-zero (PATH scrub)
- Any read of `../README.md` or `../../RUBRIC.md` → leak (cwd should prevent this)
- Any `dbt` shell call → check exit was non-zero
