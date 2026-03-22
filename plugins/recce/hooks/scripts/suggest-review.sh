#!/bin/bash
# suggest-review.sh -- PostToolUse Bash (synchronous)
# Detects dbt run/build/test; suggests review with Recce MCP tools
# Output: JSON with additionalContext (or empty for non-dbt commands)

# Graceful degradation: require jq
command -v jq &>/dev/null || exit 0

INPUT=$(cat)

COMMAND=$(printf '%s' "$INPUT" | jq -r '.tool_input.command // empty')
CWD=$(printf '%s' "$INPUT" | jq -r '.cwd // empty')

# Fast path: only act on dbt run/build/test
if ! echo "$COMMAND" | grep -qE 'dbt (run|build|test)'; then
    exit 0
fi

# Compute project-scoped hash from cwd
PROJECT_HASH=$(printf '%s' "${CWD:-$PWD}" | md5 2>/dev/null | cut -c1-8 || printf '%s' "${CWD:-$PWD}" | md5sum | cut -c1-8)
CHANGES_FILE="/tmp/recce-changed-${PROJECT_HASH}.txt"

# Check if there are tracked model changes
if [ -f "$CHANGES_FILE" ] && [ -s "$CHANGES_FILE" ]; then
    MODEL_COUNT=$(wc -l < "$CHANGES_FILE" | tr -d ' ')
    MODEL_NAMES=$(while IFS= read -r f; do basename "$f" .sql; done < "$CHANGES_FILE" | paste -sd ', ' -)
    CTX="dbt execution completed. You changed ${MODEL_COUNT} model(s) since last review: ${MODEL_NAMES}. Run /recce-review to check for unexpected data changes. IMPORTANT: Before reporting which models are impacted, call lineage_diff to verify — the 'impacted' column shows which models are truly downstream of the change."
else
    # No tracked changes, but dbt ran — suggest using lineage_diff for impact verification
    CTX="dbt execution completed. If you need to assess which models are affected by code changes, call lineage_diff first — the 'impacted' column is authoritative for distinguishing downstream models from unrelated siblings sharing the same sources."
fi

jq -n --arg ctx "$CTX" \
    '{hookSpecificOutput: {hookEventName: "PostToolUse", additionalContext: $ctx}}'

exit 0
