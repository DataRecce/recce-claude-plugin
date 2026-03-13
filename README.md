# Recce Plugins for Claude Code

Official [Recce](https://datarecce.io) plugins for Claude Code — data validation and diff tools for dbt developers.

## Plugins

| Plugin | Description | Audience |
|--------|-------------|----------|
| **recce-quickstart** | Guided onboarding — `/recce-setup`, `/recce-pr`, `/recce-check`, `/recce-ci` | New Recce users |
| **recce** | Intelligent data review workflow — auto-tracks model changes, triggers progressive validation via MCP | dbt developers using Recce daily |
| **recce-dev** | Internal MCP E2E validation and benchmarking (`/mcp-e2e-validate`) | Recce project developers |

## Installation

### From GitHub Marketplace (Recommended)

**Step 1: Add the Recce marketplace to Claude Code**

```
/plugin marketplace add DataRecce/recce-claude-plugin
```

**Step 2: Install a plugin**

```
/plugin install recce-quickstart@recce-claude-plugin
/plugin install recce@recce-claude-plugin
```

Or use the interactive installer:
```
/plugin
```
Then navigate to **Discover** tab and select the plugin to install.

### Local Installation (For Development)

```bash
git clone https://github.com/DataRecce/recce-claude-plugin.git
cd recce-claude-plugin
```

In Claude Code:
```
/plugin marketplace add /path/to/recce-claude-plugin
/plugin install recce@recce-claude-plugin
```

### Installation Scopes

| Scope | Command | Description |
|-------|---------|-------------|
| User (default) | `/plugin install ...` | Available across all your projects |
| Project | `/plugin install ... --scope project` | Shared with team via `.claude/settings.json` |
| Local | `/plugin install ... --scope local` | Only for current repository, not shared |

## Plugin Details

### recce-quickstart

Guided setup for new Recce users:

| Command | Description |
|---------|-------------|
| `/recce-setup` | Environment setup (installs dependencies, generates artifacts, starts MCP server) |
| `/recce-pr [url]` | Analyze PR data changes (auto-detects PR from current branch) |
| `/recce-check [type] [selector]` | Run data validation checks (row-count, schema, profile, query-diff) |
| `/recce-ci` | Set up Recce Cloud CI/CD for GitHub Actions |

### recce

Automated data review workflow for daily dbt development:

- **Skill:** `/recce-review` — dispatches the recce-reviewer agent with tracked model context
- **Agent:** `recce-reviewer` — runs progressive diff analysis (lineage, row count, schema) and produces a risk-assessed summary
- **Hooks:** auto-tracks model file changes, suggests review after `dbt run`, warns before unreviewed commits
- **MCP Servers:** `recce` (SSE, localhost:8081), `recce-docs` (stdio)

### recce-dev

Internal tools for Recce project developers:

- **Skill:** `/mcp-e2e-validate` — full event chain validation + benchmark report
- **Script:** `resolve-recce-root.sh` — cross-plugin path resolution (monorepo + cache layouts)
- **Requires:** the `recce` plugin installed alongside

## Requirements

- **Python** (version compatible with your Recce installation)
- **dbt** (any adapter: duckdb, postgres, bigquery, snowflake, etc.)
- **Git**
- **Recce with MCP server support** — `pip install 'recce[mcp]'` (requires a version that supports `recce mcp-server --sse`)

## MCP Server Tools

When the Recce MCP server is running, Claude has access to:

| Tool | Description |
|------|-------------|
| `lineage_diff` | Compare data lineage between environments |
| `schema_diff` | Detect schema changes (columns, types) |
| `row_count_diff` | Compare row counts between environments |
| `profile_diff` | Statistical profiling comparison |
| `query_diff` | Run custom SQL queries for comparison |

## Troubleshooting

### Plugin not loading?
1. Verify Claude Code is up to date: `claude --version`
2. Check plugin is installed: `/plugin` → **Installed** tab
3. Check for errors: `/plugin` → **Errors** tab

### MCP server not starting?
1. Ensure you're in a dbt project directory (has `dbt_project.yml`)
2. Verify Recce is installed: `pip install 'recce[mcp]'`
3. Check if port 8081 is available (or set `RECCE_MCP_PORT=8085`)

### Mid-session plugin install?
Hooks and MCP tools require a fresh session to activate. Restart Claude Code after installing plugins.

## Links

- [Recce Documentation](https://datarecce.io/docs)
- [Recce GitHub](https://github.com/DataRecce/recce)
- [Recce Cloud](https://cloud.datarecce.io)
- [Report Issues](https://github.com/DataRecce/recce-claude-plugin/issues)

## License

MIT
