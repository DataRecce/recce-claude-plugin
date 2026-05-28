# Codex — Tier-1 sandbox profile

Tier 1 = Tier 0 plus Recce CLI, Recce MCP, and single-env warehouse credentials (read-only on the dev environment). Base/prod environment access stays denied — Tier 2 territory, out of v1 scope.

## What changes from Tier 0

| Layer | Tier 0 | Tier 1 |
|---|---|---|
| Process sandbox | `--sandbox=read-only` | `--sandbox=workspace-write` (Recce writes to `~/.recce/`, log files, etc.) |
| MCP allowlist | empty `[mcp_servers]` | `[mcp_servers.recce]` registers the local Recce MCP server |
| PATH | scrub `recce` and `dbt` | scrub `dbt` only; keep `recce` reachable |
| Warehouse env | all credentials blanked | single-env credentials present (e.g., `SNOWFLAKE_*` for the dev account); base/prod credentials must be **absent** |
| `dbt` binary | not on PATH | not on PATH (Recce reads frozen artifacts; agent never needs to regenerate them) |

## Invocation recipe

```bash
SLUG="pr1-fix-clv"
WT_ROOT="$(git rev-parse --show-toplevel)"
FIXTURE_DIR="${WT_ROOT}/evals/agent-blind-spots/.tmp/sources/${SLUG}"

# Strip dbt only — recce stays on PATH for Tier 1.
SAFE_PATH="$(echo "$PATH" \
    | tr ':' '\n' \
    | grep -v -E '/dbt(/|$)' \
    | paste -sd: -)"

# Load dev-environment warehouse credentials here. Do NOT also export
# base/prod credentials in this shell — Tier 1 is single-env.
#   export SNOWFLAKE_USER=...
#   export SNOWFLAKE_PASSWORD=...
#   export SNOWFLAKE_ACCOUNT=...
#   (or equivalent for your warehouse)

cd "${FIXTURE_DIR}"

PATH="${SAFE_PATH}" \
codex exec \
    --sandbox=workspace-write \
    --ask-for-approval=never \
    --config "${WT_ROOT}/evals/agent-blind-spots/runner-configs/codex/tier-1/config.toml" \
    "<the prompt — see RUBRIC.md Tier-0 prompt-shape contract>"
```

## What's enforced vs. what's contract

| Concern | Enforced by | Notes |
|---|---|---|
| Cannot regenerate frozen artifacts | PATH scrub (no `dbt` binary) | Workspace-write would otherwise allow `target/` writes |
| Cannot reach a base/prod environment | No base/prod credentials exported in the eval shell | Contract-based; the runner must verify the shell env before launching Codex |
| Cannot read spoiler files | cwd at `.tmp/sources/<slug>/` | Same as Tier 0 |
| Recce MCP available | `config.toml` registers the local Recce MCP server | The exact `command`/`args` for the server are environment-specific; fill in the template before running |

## Verification check

After the run, inspect the agent transcript for:

- `mcp__recce__*` tool calls completed successfully → expected at Tier 1
- Any reference to a base/prod profile or to `target-base/` → leak; the agent constructed a Tier-2 path that should not be available
- Any `dbt` shell call → check exit was non-zero (PATH scrub)
- Any read of `../README.md` or `../../RUBRIC.md` → leak (cwd should prevent this)
