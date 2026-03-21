# recce-dev

Internal development and testing tools for the Recce project.

## What it does

This plugin provides tools for Recce developers to validate the `recce` plugin's MCP integration, benchmark agent performance, and run E2E validation flows. It is **not** intended for end users of Recce.

## Components

### Skills

| Skill | Description |
|-------|-------------|
| `/mcp-e2e-validate` | Full E2E validation of the `recce` plugin's event chain (SessionStart → model tracking → dbt suggestion → /recce-review → cleanup) with performance benchmarking |
| `/recce-eval` | A/B evaluation framework — runs headless Claude Code sessions with and without the Recce plugin, scores results against ground truth using deterministic checks and an LLM judge |
| `/readme-refresh` | Audit and update the marketplace root README.md to reflect current plugin state |

### Agents

| Agent | Description |
|-------|-------------|
| `recce-dev:eval-judge` | LLM-as-judge for recce-eval — scores reasoning quality, evidence quality, fix quality, false positive discipline, and completeness |

### Scripts

- `scripts/resolve-recce-root.sh` — locates the sibling `recce` plugin across monorepo and cache install layouts

## Requirements

- The `recce` plugin must be installed alongside this plugin
- A dbt project with Recce configured (same requirements as the `recce` plugin)
- Recce installed in the project's virtual environment
- Claude Code CLI v2.x+ (for `recce-eval` headless sessions)
