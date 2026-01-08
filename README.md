# Recce Quickstart Plugin for Claude Code

A Claude Code plugin that helps dbt users quickly onboard to [Recce](https://datarecce.io) - the open-source data validation and diff tool for dbt.

## Features

- 🚀 **Guided Setup** - `/recce-setup` walks you through environment configuration
- 📊 **PR Analysis** - `/recce-pr` analyzes data impact of pull requests
- ✅ **Data Checks** - `/recce-check` runs validation checks between environments
- 🤖 **Smart Guidance** - Automatic suggestions when working with dbt projects

## Installation

### From Claude Code Marketplace (Coming Soon)
```
/install recce-quickstart
```

### Manual Installation
1. Clone this repository
2. In Claude Code, add the plugin path to your settings

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

- Python 3.8+
- dbt (any adapter)
- Git

## How It Works

This plugin:
1. Detects when you're in a dbt project
2. Helps you set up base and current dbt artifacts
3. Starts a Recce MCP server for AI-powered analysis
4. Provides Claude with tools to analyze data changes

## Recce Cloud

Want to automate data validation in CI/CD? [Recce Cloud](https://cloud.datarecce.io) offers:
- Automatic PR analysis
- Data quality gates
- Team collaboration
- Historical tracking

## Links

- [Recce Documentation](https://datarecce.io/docs)
- [Recce GitHub](https://github.com/DataRecce/recce)
- [Recce Cloud](https://cloud.datarecce.io)

## License

MIT
