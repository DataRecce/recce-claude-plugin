# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Claude Code plugin marketplace repository containing the `recce-quickstart` plugin, which helps dbt users onboard to Recce - a data validation and diff tool for dbt.

## Repository Structure

```
recce-claude-plugin/
├── .claude-plugin/
│   └── marketplace.json      # Marketplace definition (required for /plugin marketplace add)
├── plugins/
│   └── recce-quickstart/     # The actual plugin
│       ├── .claude-plugin/
│       │   └── plugin.json   # Plugin manifest
│       ├── .mcp.json         # MCP server configuration (Recce SSE server)
│       ├── commands/         # Slash commands (/recce-setup, /recce-pr, /recce-check)
│       ├── skills/           # Auto-triggering skills (recce-guide)
│       ├── hooks/            # Event hooks (SessionStart, PostToolUse)
│       │   ├── hooks.json
│       │   └── scripts/      # Hook scripts (check-dbt-project.sh)
│       └── scripts/          # MCP server management (start-mcp.sh, stop-mcp.sh)
└── docs/plans/               # Design documents (gitignored)
```

## Key Concepts

### Marketplace vs Plugin Structure

- **Root `.claude-plugin/marketplace.json`**: Required for Claude Code to recognize this repo as a marketplace. The `source` field in plugins array must point to a subdirectory (e.g., `./plugins/recce-quickstart`).
- **Plugin `plugin.json`**: Defines the plugin metadata inside `plugins/<name>/.claude-plugin/`.

### MCP Server Integration

The plugin uses Recce's MCP server (HTTP/SSE transport) for data validation tools:
- Default port: 8081 (configurable via `RECCE_MCP_PORT`)
- SSE health checks use HTTP status code (`curl -w "%{http_code}"`) because SSE connections stay open
- Scripts: `start-mcp.sh`, `stop-mcp.sh`, `check-mcp.sh`

### Hook Types

- **SessionStart**: Runs `check-dbt-project.sh` to detect dbt environment
- **PostToolUse** (Bash matcher): Suggests `/recce-check` after dbt commands

## Development Commands

### Testing the Plugin Locally

```bash
# Add as local marketplace in Claude Code
/plugin marketplace add /path/to/recce-claude-plugin

# Install the plugin
/plugin install recce-quickstart@recce-plugins

# Verify installation
/plugin  # Check Installed tab
```

### Testing MCP Server Scripts

```bash
cd /path/to/dbt-project
source .venv/bin/activate  # Recce must be in PATH

# Test start/stop
RECCE_MCP_PORT=8085 bash plugins/recce-quickstart/scripts/start-mcp.sh
bash plugins/recce-quickstart/scripts/check-mcp.sh
bash plugins/recce-quickstart/scripts/stop-mcp.sh
```

### Testing Hook Scripts

```bash
cd /path/to/dbt-project
bash plugins/recce-quickstart/hooks/scripts/check-dbt-project.sh
```

## Plugin Component Conventions

### Commands (commands/*.md)

YAML frontmatter with `name` and `description`, followed by markdown instructions for Claude.

### Skills (skills/*/SKILL.md)

Must be named `SKILL.md` (not README.md). Auto-triggers based on description keywords.

### Hooks (hooks/hooks.json)

Use `${CLAUDE_PLUGIN_ROOT}` for portable paths in hook commands.

## Issue Tracking

This project uses **bd** (beads) for issue tracking. See AGENTS.md for workflow.
