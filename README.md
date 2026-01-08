# Recce Quickstart Plugin for Claude Code

A Claude Code plugin that helps dbt users quickly onboard to [Recce](https://datarecce.io) - the open-source data validation and diff tool for dbt.

## Features

- **Guided Setup** - `/recce-setup` walks you through environment configuration
- **PR Analysis** - `/recce-pr` analyzes data impact of pull requests
- **Data Checks** - `/recce-check` runs validation checks between environments
- **Smart Guidance** - Automatic suggestions when working with dbt projects

## Installation

### Method 1: From GitHub Marketplace (Recommended)

**Step 1: Add the Recce marketplace to Claude Code**

In Claude Code, run:
```
/plugin marketplace add DataRecce/recce-claude-plugin
```

**Step 2: Install the plugin**
```
/plugin install recce-quickstart@recce-claude-plugin
```

Or use the interactive installer:
```
/plugin
```
Then navigate to **Discover** tab, find `recce-quickstart`, and press Enter to install.

### Method 2: Local Installation (For Development)

**Step 1: Clone the repository**
```bash
git clone https://github.com/DataRecce/recce-claude-plugin.git
cd recce-claude-plugin
```

**Step 2: Add as local marketplace**

In Claude Code, run:
```
/plugin marketplace add /path/to/recce-claude-plugin
```

**Step 3: Install the plugin**
```
/plugin install recce-quickstart@recce-claude-plugin
```

### Installation Scopes

You can install the plugin at different scopes:

| Scope | Command | Description |
|-------|---------|-------------|
| User (default) | `/plugin install ...` | Available across all your projects |
| Project | `/plugin install ... --scope project` | Shared with team via `.claude/settings.json` |
| Local | `/plugin install ... --scope local` | Only for current repository, not shared |

### Verify Installation

After installation, verify the plugin is working:
```
/plugin
```
Navigate to the **Installed** tab to see `recce-quickstart`.

## Quick Start

1. Navigate to your dbt project directory
2. Run `/recce-setup` to configure your environment
3. Use `/recce-pr` or `/recce-check` to analyze data changes

## Commands

| Command | Description |
|---------|-------------|
| `/recce-setup` | Guided environment setup (installs dependencies, generates artifacts, starts MCP server) |
| `/recce-pr [url]` | Analyze PR data changes (auto-detects PR from current branch) |
| `/recce-check [type] [selector]` | Run data validation checks (row-count, schema, profile, query-diff) |

## Requirements

- **Python 3.8+**
- **dbt** (any adapter: duckdb, postgres, bigquery, snowflake, etc.)
- **Git**

The plugin will guide you to install these if missing:
- `pip install recce` - Recce CLI
- `pip install 'recce[mcp]'` - Recce MCP Server (for AI-powered analysis)

## How It Works

This plugin:
1. **Detects** when you're in a dbt project (via `dbt_project.yml`)
2. **Guides** you to set up base and current dbt artifacts
3. **Starts** a Recce MCP server for AI-powered analysis
4. **Provides** Claude with tools to analyze data changes

### MCP Server Tools

When the Recce MCP server is running, Claude has access to these tools:

| Tool | Description |
|------|-------------|
| `lineage_diff` | Compare data lineage between environments |
| `schema_diff` | Detect schema changes (columns, types) |
| `row_count_diff` | Compare row counts between environments |
| `profile_diff` | Statistical profiling comparison |
| `query_diff` | Run custom SQL queries for comparison |

## Managing the Plugin

**Disable the plugin:**
```
/plugin disable recce-quickstart@recce-claude-plugin
```

**Re-enable the plugin:**
```
/plugin enable recce-quickstart@recce-claude-plugin
```

**Uninstall the plugin:**
```
/plugin uninstall recce-quickstart@recce-claude-plugin
```

**Update marketplace:**
```
/plugin marketplace update recce-claude-plugin
```

## Recce Cloud

Want to automate data validation in CI/CD? [Recce Cloud](https://cloud.datarecce.io) offers:
- Automatic PR analysis
- Data quality gates
- Team collaboration
- Historical tracking

## Troubleshooting

### Plugin not loading?
1. Verify Claude Code version is 1.0.33 or higher: `claude --version`
2. Check plugin is installed: `/plugin` → **Installed** tab
3. Check for errors: `/plugin` → **Errors** tab

### MCP server not starting?
1. Ensure you're in a dbt project directory (has `dbt_project.yml`)
2. Verify Recce is installed: `pip install 'recce[mcp]'`
3. Check if port 8081 is available (or set `RECCE_MCP_PORT=8085`)
4. Run the setup command: `/recce-setup`

### Commands not recognized?
1. Ensure plugin is enabled: `/plugin` → **Installed** tab → check status
2. Restart Claude Code to reload plugins

## Links

- [Recce Documentation](https://datarecce.io/docs)
- [Recce GitHub](https://github.com/DataRecce/recce)
- [Recce Cloud](https://cloud.datarecce.io)
- [Report Issues](https://github.com/DataRecce/recce-claude-plugin/issues)

## License

MIT
