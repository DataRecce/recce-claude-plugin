# recce-dev

Internal development and testing tools for the Recce project.

## What it does

This plugin provides tools for Recce developers to validate the `recce` plugin's MCP integration, benchmark agent performance, and run E2E validation flows. It is **not** intended for end users of Recce.

## Components

- **Skill:** `/mcp-e2e-validate` — runs a full E2E validation of the `recce` plugin's event chain (SessionStart → model tracking → dbt suggestion → /recce-review → cleanup) and produces a performance benchmark report

## Requirements

- The `recce` plugin must be installed alongside this plugin
- A dbt project with Recce configured (same requirements as the `recce` plugin)
- Recce installed in the project's virtual environment
