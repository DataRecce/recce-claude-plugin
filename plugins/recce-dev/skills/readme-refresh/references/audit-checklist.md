# README Audit Checklist

Section-by-section criteria for evaluating marketplace README quality. Each check is PASS/WARN/FAIL.

## Section Audits

### 1. Opening (Title + Intro)

| Check | Criteria |
|-------|----------|
| Value signal | First sentence states what the user gains, not what the repo contains |
| Audience clarity | Target user (dbt developer) is named within first two lines |
| No jargon | Avoids internal terms (MCP, progressive validation) without context |

**Good:** "Bringing data validation into your dbt development workflow"
**Bad:** "Plugins providing MCP-based progressive data diff tools"

### 2. Why Section

| Check | Criteria |
|-------|----------|
| Pain → solution | States the problem before the solution |
| Concrete | Mentions specific outcomes (catch row count drops, schema drift) |
| Brief | Under 80 words |

A README without a "Why" section jumps straight to features, which assumes the reader already wants the product.

### 3. Plugins Table

| Check | Criteria |
|-------|----------|
| Public only | No internal/dev-only plugins listed |
| User-facing descriptions | Describes what the user gets, not how it works internally |
| Install command | Each row has a copy-pasteable install command |

### 4. Plugin Details

| Check | Criteria |
|-------|----------|
| User perspective | Describes behavior ("Claude auto-tracks changes"), not implementation ("PostToolUse hook fires on bash matcher") |
| No internal names | Does not mention agent names, script names, hook types, or MCP port numbers |
| Slash commands prominent | Primary interaction (slash commands) is the first thing listed |
| Discoverable | Each plugin section is scannable in <15 seconds |

### 5. Getting Started

| Check | Criteria |
|-------|----------|
| 3 steps max | Numbered steps, each with one action |
| Prereqs first | Links to Recce installation before plugin steps |
| Ends with action | Final step tells user what to type next |

### 6. Requirements

| Check | Criteria |
|-------|----------|
| Plugin-scoped | Lists only what the plugin needs (Recce installed) |
| No product prereqs | Python, dbt, Git are Recce's requirements — link to Recce docs |
| No fabricated versions | Version numbers must have a verifiable source |

### 7. Troubleshooting

| Check | Criteria |
|-------|----------|
| Plugin-level only | Covers "plugin not loading" and "commands not available" |
| No implementation details | Does not mention MCP ports, dbt_project.yml paths, or pip commands |
| Links out | Points to Recce docs for product-level issues |

### 8. Links

| Check | Criteria |
|-------|----------|
| All links valid | Point to known valid targets or existing repository paths |
| Issue link points to plugin repo | Not the main Recce repo |
| No redundant links | Each link serves a distinct purpose |

---

## Writing Principles

### 1. Storefront Rule

Every sentence must help the reader decide whether to install. If it doesn't, it belongs in CLAUDE.md, the plugin's own README, or Recce docs.

### 2. Behavior Over Implementation

| Instead of | Write |
|-----------|-------|
| "PostToolUse hook suggests review after dbt commands" | "After `dbt run`, Claude suggests a data review" |
| "recce-reviewer agent runs progressive diff analysis" | "`/recce-review` validates your changes and produces a risk summary" |
| "MCP server on localhost:8081 (SSE transport)" | (omit — user doesn't configure this) |

### 3. Link, Don't Duplicate

Content that lives in another repo will drift out of sync. Instead:

- MCP tool list → link to Recce docs
- Python/dbt installation → link to Recce install guide
- Claude Code plugin mechanics → link to Claude Code docs

### 4. Version Discipline

Never write a specific version number (e.g., `>= 0.41.0`) without a verifiable source. Describe the capability instead:

- **Bad:** "Requires Recce >= 0.41.0"
- **Good:** "Requires a version of Recce that supports `recce mcp-server --sse`"
- **Best:** "Requires Recce with MCP support — see [installation guide](link)"

### 5. Scanability

- Sections under 300 words
- Tables over prose for comparisons
- Code blocks for anything the user types
- One action per numbered step
