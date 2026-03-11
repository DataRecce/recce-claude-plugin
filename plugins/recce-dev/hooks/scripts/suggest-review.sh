#!/bin/bash
# suggest-review.sh -- PostToolUse Bash (synchronous)
# Detects dbt run/build/test; suggests review if tracked models exist
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

# Silent if no tracked models
if [ ! -f "$CHANGES_FILE" ] || [ ! -s "$CHANGES_FILE" ]; then
    exit 0
fi

# Count and list changed models
MODEL_COUNT=$(wc -l < "$CHANGES_FILE" | tr -d ' ')
MODEL_NAMES=$(while IFS= read -r f; do basename "$f" .sql; done < "$CHANGES_FILE" | paste -sd ', ' -)

CTX="dbt execution completed. You changed ${MODEL_COUNT} model(s) since last review: ${MODEL_NAMES}. Consider running data review to check for unexpected changes (row counts, schema diffs). Run /recce-review or ask me to start a review."

jq -n --arg ctx "$CTX" \
    '{hookSpecificOutput: {hookEventName: "PostToolUse", additionalContext: $ctx}}'

exit 0
