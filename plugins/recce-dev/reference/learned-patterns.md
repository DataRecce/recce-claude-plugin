# Learned Patterns

Cross-project patterns accumulated during recce-dev operations.

Curate periodically and PR valuable entries back to the origin repo.

---

### [2026-03-22] Forge — Plugin agents in skill subdirectories are not auto-discovered

**Pattern**: Agent `.md` files placed in `skills/<name>/agents/` instead of the plugin root `agents/` directory are not registered in Claude Code's subagent type registry. Dispatching via `Agent` tool with `subagent_type: "plugin:agent-name"` fails with "agent type not found". The agent must be dispatched as a general-purpose agent with the full rubric inlined in the prompt.
**Applies to**: Any plugin with agents defined inside skill subdirectories
**Action**: Place agents in plugin root `agents/` for auto-discovery, or document that skill-scoped agents require manual dispatch with inlined instructions
**Resolution**: eval-judge.md moved to plugin root `agents/` (commit 909dba3)

---

### [2026-03-22] Re-verification — dbt Cloud CLI shadows dbt-core in PATH

**Pattern**: `/opt/homebrew/bin/dbt` is the dbt Cloud CLI (requires `dbt_cloud.yml`), not dbt-core. Scripts that check `command -v dbt` find the Cloud CLI first and skip venv activation, causing `dbt run` to fail with "dbt_cloud.yml credentials file not found".
**Applies to**: Any script that auto-detects dbt via PATH before activating venv
**Action**: Always activate the local venv (venv/ or .venv/) unconditionally if it exists, rather than gating activation on `command -v dbt` absence.

---

### [2026-03-22] Re-verification — Claude Code v0.2.x vs v2.x CLI binary conflict

**Pattern**: Multiple `claude` binaries on PATH. `/usr/local/bin/claude` (v0.2.45) is stale and lacks `--output-format`, `--max-budget-usd`, `--mcp-config`, `--plugin-dir`. `~/.local/bin/claude` and `~/.npm-global/bin/claude` (v2.1.81) have the full flag set.
**Applies to**: Scripts that invoke `claude -p` with headless flags
**Action**: Resolve the claude binary by checking `~/.local/bin/claude` first (standard install location), falling back to PATH.
