# Recce Plugins for Claude Code

Official [Recce](https://datarecce.io) plugins for Claude Code — bringing data validation into your dbt development workflow.

## Why?

dbt developers modify models, run `dbt run`, and hope nothing breaks downstream. Recce plugins let Claude Code **automatically detect what changed and validate the data impact** — so you catch row count drops, schema drift, and query differences before they reach production.

## Plugins

| Plugin | Who it's for | Install |
|--------|-------------|---------|
| **recce-quickstart** | New Recce users getting started | `/plugin install recce-quickstart@recce-claude-plugin` |
| **recce** | dbt developers using Recce daily | `/plugin install recce@recce-claude-plugin` |

### recce-quickstart

Guided onboarding for first-time users:

| Command | What it does |
|---------|-------------|
| `/recce-setup` | Walks you through environment setup — installs dependencies, generates artifacts, starts the MCP server |
| `/recce-pr [url]` | Analyzes data changes in a pull request |
| `/recce-check [type] [selector]` | Runs a specific data validation (row-count, schema, profile, query-diff) |
| `/recce-ci` | Sets up Recce Cloud CI/CD for GitHub Actions |

### recce

Automated data review for daily development. Once installed:

- Claude **auto-tracks** which model files you edit
- After `dbt run`, Claude **suggests** a data review based on tracked changes
- `/recce-review` validates impacted models and produces a **risk-assessed summary**

## Getting Started

**Step 1: Install Recce** (see [Recce installation guide](https://datarecce.io/docs))

**Step 2: Add the marketplace**

```
/plugin marketplace add DataRecce/recce-claude-plugin
```

**Step 3: Install a plugin**

```
/plugin install recce-quickstart@recce-claude-plugin
```

Start a new Claude Code session in your dbt project directory, then type `/recce-setup`.

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Plugin not showing up | Check `/plugin` → **Installed** tab. If missing, reinstall. |
| Plugin errors after install | Check `/plugin` → **Errors** tab. |
| Commands not available | Restart Claude Code — hooks and MCP tools activate on session start. |

For Recce-specific issues (MCP server, dbt connection, environment setup), see the [Recce documentation](https://datarecce.io/docs).

## Links

- [Recce Documentation](https://datarecce.io/docs)
- [Recce GitHub](https://github.com/DataRecce/recce)
- [Recce Cloud](https://cloud.datarecce.io)
- [Report Plugin Issues](https://github.com/DataRecce/recce-claude-plugin/issues)

## License

MIT
