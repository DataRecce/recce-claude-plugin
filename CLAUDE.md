# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Claude Code plugin marketplace repository for [Recce](https://datarecce.io) — a data validation and diff tool for dbt developers.

**Plugins in this repo:**

| Plugin | Description |
|--------|-------------|
| **recce** | Daily dbt workflow plugin — auto-tracks model changes, triggers progressive data validation via MCP |
| **recce-dev** | Internal E2E validation plugin for Recce project developers |
| **recce-quickstart** | Guided onboarding for new Recce users (`/recce-setup`, `/recce-pr`, `/recce-check`) |

## Repository Structure

```
recce-claude-plugin/
├── .claude-plugin/          # Marketplace definition
├── .github/workflows/       # CI guards (bundle freshness)
├── packages/
│   └── recce-docs-mcp/      # MCP docs server source + build
├── plugins/
│   ├── recce/               # Daily dbt workflow plugin
│   ├── recce-dev/           # Internal E2E validation
│   └── recce-quickstart/    # Guided onboarding
├── scripts/                 # Developer setup (install-hooks.sh)
└── tests/                   # Test suite
```

## Key Concepts

### Marketplace vs Plugin Structure

- **Root `.claude-plugin/marketplace.json`**: Required for Claude Code to recognize this repo as a marketplace. The `source` field in each plugins entry points to a subdirectory (e.g., `./plugins/recce`, `./plugins/recce-quickstart`).
- **Plugin `plugin.json`**: Defines plugin metadata inside `plugins/<name>/.claude-plugin/`.

### MCP Server Integration

The `recce` and `recce-quickstart` plugins use Recce's MCP server (HTTP/SSE transport) for data validation tools:
- Default port: 8081 (configurable via `RECCE_MCP_PORT`)
- SSE health checks use HTTP status code (`curl -w "%{http_code}"`) because SSE connections stay open
- Scripts: `start-mcp.sh`, `stop-mcp.sh`, `check-mcp.sh` inside each plugin's `scripts/` dir

### Hook Types

- **SessionStart**: Runs `check-dbt-project.sh` to detect dbt environment
- **PostToolUse** (Bash matcher): Suggests `/recce-check` after dbt commands

### Plugin Component Conventions

**Commands (`commands/*.md`)**: YAML frontmatter with `name` and `description`, followed by markdown instructions for Claude.

**Skills (`skills/*/SKILL.md`)**: Must be named `SKILL.md` (not README.md). Auto-triggers based on description keywords.

**Hooks (`hooks/hooks.json`)**: Use `${CLAUDE_PLUGIN_ROOT}` for portable paths in hook commands.

## Rebuilding the Bundled MCP Server

Each plugin ships `servers/recce-docs-mcp/dist/cli.js` — a self-contained CJS bundle committed directly to the repo (not a symlink). This file must be present for marketplace install to work offline.

**Rebuild after source changes:**

```bash
cd packages/recce-docs-mcp && npm run build:bundle
```

This outputs the bundle to both `plugins/recce/servers/recce-docs-mcp/dist/cli.js` and `plugins/recce-dev/servers/recce-docs-mcp/dist/cli.js`.

**Developer setup** (install pre-push staleness guard):

```bash
bash scripts/install-hooks.sh
```

**CI guard**: `.github/workflows/bundle-freshness.yml` fails the build if the committed bundle is stale relative to source.

## Development Commands

### Testing a Plugin Locally

```bash
# Add as local marketplace in Claude Code
/plugin marketplace add /path/to/recce-claude-plugin

# Install a plugin
/plugin install recce@recce-claude-plugin
/plugin install recce-quickstart@recce-claude-plugin

# Verify installation
/plugin  # Check Installed tab
```

### Testing MCP Server Scripts

```bash
cd /path/to/dbt-project
source .venv/bin/activate  # Recce must be in PATH

# Test start/stop (adjust plugin name as needed)
RECCE_MCP_PORT=8085 bash plugins/<name>/scripts/start-mcp.sh
bash plugins/<name>/scripts/check-mcp.sh
bash plugins/<name>/scripts/stop-mcp.sh
```

### Testing Hook Scripts

```bash
cd /path/to/dbt-project
bash plugins/<name>/hooks/scripts/check-dbt-project.sh
```

## Issue Tracking

This project uses **bd** (beads) for issue tracking. See AGENTS.md for workflow.
