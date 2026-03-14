---
name: readme-refresh
description: This skill should be used when the user asks to "update readme", "review readme", "refresh readme", "audit readme", "fix the main readme", "改 readme", "檢查 readme", or when the root README.md needs to reflect new plugin changes, version bumps, or feature additions.
---

# README Refresh

Audit and update the marketplace README.md to maximize value for prospective users while keeping internal details out.

## Core Principle

The README is a **storefront**, not a technical spec. Every section must answer one question: **"Why should a dbt developer install this?"**

## Process

### Step 1: Read Current State

Read the root `README.md` and gather context:

- Read the root README.md
- Read CLAUDE.md for the plugin inventory and project conventions
- Read each plugin's `plugin.json` for current version and description

### Step 2: Audit Against Checklist

Evaluate every section using the value audit checklist in `references/audit-checklist.md`. Flag sections that fail any check.

Present findings as a structured report:

```
## README Audit

| Section | Status | Issue |
|---------|--------|-------|
| Intro   | PASS   | —     |
| Plugins table | WARN | Lists internal plugin visible to public |
| recce details | FAIL | Exposes agent names, MCP port numbers |
| Requirements | FAIL | Lists Recce prereqs, not plugin prereqs |

Proposed changes:
1. Remove recce-dev from plugins table
2. Replace implementation details with user-facing behavior
3. ...
```

**GATE — Wait for user confirmation before editing.**

### Step 3: Rewrite

Apply the writing principles from `references/audit-checklist.md`:

- Lead with the pain point → solution arc
- Describe behavior from the user's perspective ("Claude auto-tracks your changes")
- Link to external docs instead of duplicating content
- Keep Getting Started to 3 steps max

### Step 4: Verify

After editing, re-run the audit checklist to confirm all sections pass. Read the final README end-to-end and check:

- No orphaned links
- No version numbers without a verifiable source
- No internal terminology (agent names, script names, port numbers)
- Word count under 300 for any single section

## Anti-Patterns

| Pattern | Why it's wrong | Fix |
|---------|---------------|-----|
| Listing agent/hook/script names | Users don't invoke these directly | Describe the behavior they enable |
| Hardcoding MCP tool list | Tools change across Recce versions | Link to Recce docs |
| Documenting Installation Scopes | Generic Claude Code knowledge | Remove or link to Claude Code docs |
| Mixing product prereqs with plugin prereqs | Confuses what to install | Plugin needs Recce; Recce needs Python/dbt — link to Recce install guide |
| Internal plugins in public README | Noise for external visitors | Move to CLAUDE.md or plugin's own README |
| Troubleshooting with implementation details | Couples README to internals | Keep plugin-level issues only, link elsewhere for product issues |
| Fabricating version pins | Cannot be verified, erodes trust | Describe capability requirement instead; link to install guide |

## Additional Resources

### Reference Files

- **`references/audit-checklist.md`** — Section-by-section audit criteria and writing principles for value-focused README content.
