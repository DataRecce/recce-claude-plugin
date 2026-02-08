---
name: recce-ci
description: Set up Recce Cloud CI/CD for GitHub Actions - generates PR review and main branch workflows
---

# Recce CI/CD Setup

You are helping the user set up Recce Cloud CI/CD for their dbt project.
This command generates GitHub Actions workflows for automated data validation on pull requests.

## Prerequisites

Before starting, ensure:
- User is in a git repository
- User has a dbt project (dbt_project.yml exists)
- User has a GitHub repository

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

## Monorepo Guide

!`cat ${CLAUDE_PLUGIN_ROOT}/skills/recce-ci-setup/references/monorepo-guide.md`
