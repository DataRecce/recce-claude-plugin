---
name: recce-dbt-doctor
description: Configure or troubleshoot Recce Cloud CI/CD integration for dbt projects - set up GitHub Actions workflows or diagnose pipeline issues
args:
  - name: issue
    description: Optional issue description (e.g., "workflow failing", "baseline not found")
    required: false
allowed-tools:
  - Bash
  - Read
  - Edit
  - Write
  - Glob
  - Grep
  - AskUserQuestion
---

# Recce dbt Doctor - Cloud CI/CD Configuration & Troubleshooting

You are helping the user configure or troubleshoot Recce Cloud CI/CD integration.

## Entry Point: Determine User Intent

First, understand what the user needs:

**If user mentions a specific issue** (e.g., "workflow failing", "baseline not found", "permission error"):
→ Jump to **Troubleshooting** section below

**If user wants to set up or verify CI/CD**:
→ Follow the **Setup Flow** (Detection → Gap Analysis → Setup)

---

## Environment Detection

!`cat ${CLAUDE_PLUGIN_ROOT}/skills/dbt-project/SKILL.md`

## CLI Tool Mapping

!`cat ${CLAUDE_PLUGIN_ROOT}/skills/recce-ci-setup/adapters/cli.md`

## CI/CD Setup Workflow

!`cat ${CLAUDE_PLUGIN_ROOT}/skills/recce-ci-setup/SKILL.md`

## Workflow Templates

!`cat ${CLAUDE_PLUGIN_ROOT}/skills/recce-ci-setup/references/workflow-templates.md`

## Secrets Configuration

!`cat ${CLAUDE_PLUGIN_ROOT}/skills/recce-ci-setup/references/warehouse-secrets.md`

## Troubleshooting

!`cat ${CLAUDE_PLUGIN_ROOT}/skills/recce-ci-setup/references/troubleshooting.md`
