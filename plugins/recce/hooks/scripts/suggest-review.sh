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
    CTX="dbt execution completed. You changed ${MODEL_COUNT} model(s) since last review: ${MODEL_NAMES}. MANDATORY: You MUST call impact_analysis before reporting impacted_models in your final output. Do NOT determine impact by reading code or ref() calls — this confuses upstream with downstream and produces false positives. impact_analysis returns the authoritative impacted_models and not_impacted_models lists."
else
    # No tracked changes, but dbt ran — mandate impact_analysis for impact verification
    CTX="dbt execution completed. MANDATORY: Before reporting which models are impacted by code changes, you MUST call impact_analysis. Do NOT infer impact from code reading — it confuses upstream dependencies with downstream impact. impact_analysis returns authoritative impacted_models and not_impacted_models lists."
fi

jq -n --arg ctx "$CTX" \
    '{hookSpecificOutput: {hookEventName: "PostToolUse", additionalContext: $ctx}}'

exit 0
