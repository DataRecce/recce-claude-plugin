# recce-dev

Intelligent data review workflow for dbt developers.

## What it does

recce-dev automatically tracks dbt model file changes and triggers progressive data validation using Recce. When you modify a dbt model, the plugin records the change. After your dbt run or build, it dispatches an agent that runs lineage diff, row count diff, and schema diff in sequence — producing an actionable summary with risk level before changes leave your machine.

## Components

- **Skill:** `/recce-review` — triggers the data review workflow; dispatches the recce-reviewer agent with tracked model context
- **Agent:** `recce-reviewer` — runs progressive diff analysis (lineage, row count, schema) and produces a risk-assessed summary
- **Hooks:**
  - `SessionStart` — detects dbt project environment and starts the Recce MCP server if prerequisites are met
  - `PostToolUse` — suggests `/recce-check` after dbt run/build commands
  - `PreToolUse` — tracks modified dbt model files before Write/Edit operations
- **MCP Servers:**
  - `recce-dev` — Recce SSE server on `http://localhost:8081/sse` (local, project-scoped)
  - `recce-docs` — Recce documentation stdio server (local path, for doc lookups)

## Requirements

- Recce installed in the active virtual environment (`pip install recce`)
- dbt project with two environments configured (base + target) for comparison diffs
- Recce server running before dispatching the review agent (`recce server`)

## Known Limitations

- The `recce-docs` MCP server uses a local symlink path (`../../packages/recce-docs-mcp/dist/cli.js`). This path is relative to the plugin root and resolves correctly in development but will break after marketplace install. Resolving this is deferred to v2 (tracked as MKTD-02).
- The `recce-dev` MCP server uses `http://localhost:8081/sse` (HTTP, not HTTPS). This is expected for a local SSE server and is intentional — no fix needed.
