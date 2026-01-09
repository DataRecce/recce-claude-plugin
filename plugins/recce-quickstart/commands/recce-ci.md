---
name: recce-ci
description: Set up Recce Cloud CI/CD for GitHub Actions - generates PR review and main branch workflows
---

# Recce CI/CD Setup

You are helping the user set up Recce Cloud CI/CD for their dbt project. This command generates GitHub Actions workflows for automated data validation on pull requests.

## Prerequisites

Before starting, ensure:
- User is in a git repository
- User has a dbt project (dbt_project.yml exists)
- User has a GitHub repository

## Workflow Overview

This command will:
1. Detect dbt project location and warehouse adapter
2. Check for existing CI workflows
3. Remind user to create Recce Cloud Project
4. Generate workflow files (PR + Main branch)
5. Provide secrets configuration guidance
6. Optionally commit and push changes
