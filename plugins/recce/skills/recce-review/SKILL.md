---
name: recce-review
description: >
  Review dbt model data changes using Recce. Triggers when: user asks to review
  data changes, check data impact, run recce review, or validate model changes
  before committing.
---

# /recce-review — Data Review Orchestration

This skill orchestrates MCP health checks, auto-start recovery, tracked model handoff, sub-agent dispatch, post-review cleanup, and risk-based next-step suggestions.

Follow these steps in order.

---

## Step 1: MCP Health Check

Run:

```bash
bash ${CLAUDE_PLUGIN_ROOT}/scripts/check-mcp.sh
```

Parse the KEY=VALUE output:
- If `RUNNING=true` — MCP server is healthy. Skip to **Step 4**.
- If `RUNNING=false` — MCP server is not running. Proceed to **Step 2**.

---

## Step 2: Auto-Start MCP Server

Run:

```bash
bash ${CLAUDE_PLUGIN_ROOT}/scripts/start-mcp.sh
```

Parse the KEY=VALUE output:
- If `STATUS=STARTED` or `STATUS=ALREADY_RUNNING` — proceed to **Step 3**.
- If `ERROR=` appears in output — abort. Show the `ERROR`, `MESSAGE`, and `FIX` lines verbatim. Tell the user: "MCP server failed to start. Fix the issue above, then re-run /recce-review."

---

## Step 3: Re-Check MCP After Auto-Start

> Note: Skip this step if Step 1 already returned `RUNNING=true`.

Run:

```bash
bash ${CLAUDE_PLUGIN_ROOT}/scripts/check-mcp.sh
```

Parse the KEY=VALUE output:
- If `RUNNING=true` — proceed to **Step 4**.
- If `RUNNING=false` — abort. Tell the user: "MCP server started but health check failed. Check logs and try `bash ${CLAUDE_PLUGIN_ROOT}/scripts/check-mcp.sh` manually."

---

## Step 4: Determine Model Scope

Run:

```bash
PROJECT_HASH=$(printf '%s' "$PWD" | md5 2>/dev/null | cut -c1-8 || printf '%s' "$PWD" | md5sum | cut -c1-8)
CHANGES_FILE="/tmp/recce-changed-${PROJECT_HASH}.txt"
if [ -f "$CHANGES_FILE" ] && [ -s "$CHANGES_FILE" ]; then
    echo "TRACKED=true"
    echo "MODEL_COUNT=$(wc -l < "$CHANGES_FILE" | tr -d ' ')"
    echo "MODELS=$(while IFS= read -r f; do basename "$f" .sql; done < "$CHANGES_FILE" | paste -sd ', ' -)"
else
    echo "TRACKED=false"
fi
```

Parse the output:
- If `TRACKED=true` — record the `MODELS` value (comma-separated model names). Use these in Step 5.
- If `TRACKED=false` — no tracked changes file exists. Do **not** abort. Do **not** ask the user for model names. The agent will use `state:modified+` as a fallback selector.

---

## Step 5: Dispatch Review Agent

Use the `agent:` tool to dispatch `recce-reviewer`.

**If tracked models were found (Step 4 returned TRACKED=true):**
Include in the dispatch context:
> "Changed models (from tracked file): {MODELS}. Focus review on these models using selector: {model1}+ {model2}+ (one per model from the list)."

**If no tracked models (Step 4 returned TRACKED=false):**
Include in the dispatch context:
> "No tracked changes file found. Use state:modified+ as the default selector to review all modified models."

**Context passthrough:** If the user's request includes any of the following, include it in the dispatch message so the reviewer can validate findings against intent:
- **Stakeholder request** (who asked for the change and what they asked for)
- **PR description** (what the change claims to do)
- **Change rationale** (why the change was made)

Format: `Context: [stakeholder] requested '[request]'. PR says: '[description]'.`

This enables the reviewer's context validation step (Step 4 in the agent workflow).

Wait for the agent to complete and capture its full output.

---

## Step 6: Post-Review Cleanup (on success only)

Check if the agent's output contains `## Data Review Summary`.

**If YES** (successful review):

Run:

```bash
PROJECT_HASH=$(printf '%s' "$PWD" | md5 2>/dev/null | cut -c1-8 || printf '%s' "$PWD" | md5sum | cut -c1-8)
rm -f "/tmp/recce-changed-${PROJECT_HASH}.txt"
```

This clears tracked changes so the pre-commit guard no longer warns about already-reviewed models.

**If NO** (agent error or incomplete review):

Do **not** delete the file. Tell the user: "Review did not complete successfully. Tracked changes preserved for retry. Run /recce-review again." Then **STOP** — do not proceed to Step 7.

---

## Step 7: Next Steps Based on Risk Level

> Skip this step if the review did not complete successfully (no `## Data Review Summary` found in Step 6).

Parse the risk level from the agent's summary output (look for `Risk level: HIGH`, `Risk level: MEDIUM`, or `Risk level: LOW`).

- **HIGH**: "Schema breaking changes detected. Consider running `/recce-check` for detailed profile and query analysis before committing."
- **MEDIUM**: "Row count changes detected. Review the deltas above, then commit when satisfied."
- **LOW**: "No significant data impact detected. Looks safe to commit."
