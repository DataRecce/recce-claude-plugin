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
if command -v md5 >/dev/null 2>&1; then
    PROJECT_HASH=$(printf '%s' "${CWD:-$PWD}" | md5 | cut -c1-8)
else
    PROJECT_HASH=$(printf '%s' "${CWD:-$PWD}" | md5sum | cut -c1-8)
fi
CHANGES_FILE="/tmp/recce-changed-${PROJECT_HASH}.txt"

# Check if there are tracked model changes
if [ -f "$CHANGES_FILE" ] && [ -s "$CHANGES_FILE" ]; then
    MODEL_COUNT=$(wc -l < "$CHANGES_FILE" | tr -d ' ')
    MODEL_NAMES=$(while IFS= read -r f; do basename "$f" .sql; done < "$CHANGES_FILE" \
        | awk 'NR==1{printf "%s",$0; next} {printf ", %s",$0} END{print ""}')
    CTX="dbt execution completed. You changed ${MODEL_COUNT} model(s) since last review: ${MODEL_NAMES}. MANDATORY: You MUST call impact_analysis to get the authoritative impacted_models and not_impacted_models lists. Do NOT determine model impact from ref() calls alone — this confuses upstream with downstream. Use data evidence from impact_analysis for impact classification, and read model SQL to understand root causes. When data_impact is 'confirmed', investigate what code change caused it. When value_diff.rows_changed is present, use it as the affected row count."
else
    # No tracked changes, but dbt ran — mandate impact_analysis for impact verification
    CTX="dbt execution completed. MANDATORY: You MUST call impact_analysis to get the authoritative impacted_models and not_impacted_models lists. Do NOT determine model impact from ref() calls alone — this confuses upstream with downstream. Use data evidence from impact_analysis for impact classification, and read model SQL to understand root causes. When data_impact is 'confirmed', investigate what code change caused it. When value_diff.rows_changed is present, use it as the affected row count."
fi

jq -n --arg ctx "$CTX" \
    '{hookSpecificOutput: {hookEventName: "PostToolUse", additionalContext: $ctx}}'

exit 0
