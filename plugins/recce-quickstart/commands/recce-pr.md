---
name: recce-pr
description: Analyze PR data changes using Recce MCP tools
args:
  - name: pr_url
    description: GitHub/GitLab PR URL (optional, auto-detects from current branch)
    required: false
---

# Recce PR Analysis

Analyze the data impact of a Pull Request using Recce MCP tools.

## Prerequisites Check

First, verify Recce MCP Server is running:

Run: `bash ${CLAUDE_PLUGIN_ROOT}/scripts/check-mcp.sh`

- If `STATUS=RUNNING`: Continue with analysis.
- If `STATUS=NOT_RUNNING`: Tell the user to run `/recce-setup` first.

## Get PR Information

### If PR URL is provided:
Use the provided URL directly.

### If PR URL is NOT provided:
1. Get current branch: `git branch --show-current`
2. Try to get PR URL using gh CLI: `gh pr view --json url -q .url 2>/dev/null`
3. If gh CLI fails, ask the user to provide the PR URL.

## Run Recce Analysis

Use the Recce MCP tools in this order:

### 1. Lineage Diff
Use `mcp__recce__lineage_diff` tool to understand what changed:
- Get list of modified models
- Identify downstream impact
- Note the change_status of each node

### 2. Schema Diff
Use `mcp__recce__schema_diff` tool to see column changes:
- New columns added
- Columns removed
- Column type changes

### 3. Row Count Diff (if applicable)
Use `mcp__recce__row_count_diff` tool with selector `select:"config.materialized:table"`:
- Compare row counts between base and current
- Flag significant changes (>5% difference)

**Important:** Only run on tables, NOT views (views trigger expensive queries).

### 4. Profile Diff (optional, ask user)
If user wants deeper analysis, use `mcp__recce__profile_diff` tool:
- Statistical profiles (min, max, avg, distinct count)
- Only run on specific models the user is interested in

## Generate Summary Report

Format the analysis as a clear summary:

```markdown
## PR Data Change Summary

### Overview
- Modified: X models
- Downstream Impact: Y models

### Lineage Changes
[Mermaid DAG or list of affected models]

### Schema Changes
| Model | Change Type | Details |
|-------|-------------|---------|
| dim_customers | Added column | +email_verified (boolean) |

### Row Count Changes
| Model | Base | Current | Change |
|-------|------|---------|--------|
| fact_orders | 10,000 | 10,234 | +2.3% |

### Recommendations
[Any concerns or suggestions based on the analysis]
```

## Recce Cloud Promotion

After generating the summary:

```
📋 PR data change summary generated!

---
💡 **Want to automate this?**

Recce Cloud CI integration can:
• 🔄 Automatically analyze every PR
• 💬 Post results as PR comments
• ✅ Set data quality gates

👉 CI integration docs: https://datarecce.io/docs/ci-integration
```
