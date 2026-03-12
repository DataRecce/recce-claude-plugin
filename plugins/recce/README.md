# recce

Intelligent data review workflow for dbt developers.

## What it does

The recce plugin automatically tracks dbt model file changes and triggers progressive data validation using Recce. When you modify a dbt model, the plugin records the change. After your dbt run or build, it dispatches an agent that runs lineage diff, row count diff, and schema diff in sequence — producing an actionable summary with risk level before changes leave your machine.

## Components

- **Skill:** `/recce-review` — triggers the data review workflow; dispatches the recce-reviewer agent with tracked model context
- **Agent:** `recce-reviewer` — runs progressive diff analysis (lineage, row count, schema) and produces a risk-assessed summary
- **Hooks:**
  - `SessionStart` — detects dbt project environment and starts the Recce MCP server if prerequisites are met
  - `PostToolUse` — suggests `/recce-check` after dbt run/build commands
  - `PreToolUse` — tracks modified dbt model files before Write/Edit operations
- **MCP Servers:**
  - `recce` — Recce SSE server on `http://localhost:8081/sse` (local, project-scoped)
  - `recce-docs` — Recce documentation stdio server (local path, for doc lookups)

## Requirements

- **Recce >= 1.39.0** installed in the project's virtual environment (`pip install "recce>=1.39.0"`) — SSE transport (`--sse` flag) requires this version
- The virtual environment must be activated before starting a Claude Code session so `recce` is on PATH
- dbt project with two environments configured (base + target) for comparison diffs
- Base artifacts generated: `dbt docs generate --target-path target-base` on the comparison branch

## Known Limitations

- **Port hardcoded in `.mcp.json`**: The MCP server URL is `http://localhost:8081/sse`. If you override `mcp_port` in settings (e.g., `.claude/recce/settings.json`), the actual server starts on the configured port but `.mcp.json` still points to 8081. Claude Code MCP config is static — dynamic port resolution requires a future Claude Code feature.
- **Mid-session plugin install**: Installing the plugin mid-session does not activate hooks or MCP tools. Start a new Claude Code session after installation for full functionality.
- **recce-docs MCP path**: Uses a local symlink path (`../../packages/recce-docs-mcp/dist/cli.js`) that breaks after marketplace install. Deferred to v2 (MKTD-02).
- **HTTP-only MCP**: The `recce` MCP server uses `http://localhost:8081/sse` (not HTTPS). This is expected for a local SSE server.
