#!/bin/bash
# pre-commit-guard.sh -- PreToolUse Bash (synchronous)
# Non-blocking: always exit 0. Shows systemMessage warning if unreviewed changes.

# Graceful degradation: require jq
command -v jq &>/dev/null || exit 0

INPUT=$(cat)

COMMAND=$(printf '%s' "$INPUT" | jq -r '.tool_input.command // empty')
CWD=$(printf '%s' "$INPUT" | jq -r '.cwd // empty')

# Only act on git commit commands
if ! echo "$COMMAND" | grep -qE 'git commit'; then
    exit 0
fi

# Compute project-scoped hash from cwd
if command -v md5 >/dev/null 2>&1; then
    PROJECT_HASH=$(printf '%s' "${CWD:-$PWD}" | md5 | cut -c1-8)
else
    PROJECT_HASH=$(printf '%s' "${CWD:-$PWD}" | md5sum | cut -c1-8)
fi
CHANGES_FILE="/tmp/recce-changed-${PROJECT_HASH}.txt"

# Silent if no tracked models
if [ ! -f "$CHANGES_FILE" ] || [ ! -s "$CHANGES_FILE" ]; then
    exit 0
fi

# Count and list changed models
MODEL_COUNT=$(wc -l < "$CHANGES_FILE" | tr -d ' ')
MODEL_NAMES=$(while IFS= read -r f; do basename "$f" .sql; done < "$CHANGES_FILE" | paste -sd ', ' -)

MSG="${MODEL_COUNT} model change(s) not yet reviewed: ${MODEL_NAMES}. Consider running /recce-review before committing."

jq -n --arg msg "$MSG" '{systemMessage: $msg}'

# CRITICAL: always exit 0 -- never use exit 2 (that would block the commit)
exit 0
