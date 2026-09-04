#!/bin/bash
# pre-commit-guard.sh -- PreToolUse Bash (synchronous)
# Non-blocking: always exit 0. Shows systemMessage warning if unreviewed changes.

command -v jq &>/dev/null || exit 0

INPUT=$(cat)

COMMAND=$(printf '%s' "$INPUT" | jq -r '.tool_input.command // empty')
CWD=$(printf '%s' "$INPUT" | jq -r '.cwd // empty')

if ! echo "$COMMAND" | grep -qE '(^|[;&|[:space:]])git[[:space:]]+commit([[:space:]]|$)'; then
    exit 0
fi

if command -v md5 >/dev/null 2>&1; then
    PROJECT_HASH=$(printf '%s' "${CWD:-$PWD}" | md5 | cut -c1-8)
else
    PROJECT_HASH=$(printf '%s' "${CWD:-$PWD}" | md5sum | cut -c1-8)
fi
CHANGES_FILE="/tmp/recce-changed-${PROJECT_HASH}.txt"

if [ ! -f "$CHANGES_FILE" ] || [ ! -s "$CHANGES_FILE" ]; then
    exit 0
fi

MODEL_COUNT=$(wc -l < "$CHANGES_FILE" | tr -d ' ')
MODEL_NAMES=$(while IFS= read -r f; do basename "$f" .sql; done < "$CHANGES_FILE" \
    | awk 'NR==1{printf "%s",$0; next} {printf ", %s",$0} END{print ""}')

MSG="${MODEL_COUNT} model change(s) not yet reviewed: ${MODEL_NAMES}. Consider running /recce-dev-review before committing."

jq -n --arg msg "$MSG" '{systemMessage: $msg}'

exit 0
