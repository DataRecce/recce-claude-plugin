#!/bin/bash
# track-changes.sh -- PostToolUse Write|Edit (async: true)
# Silent: no stdout, always exit 0
# Tracks model SQL file edits to project-scoped temp file

# Graceful degradation: require jq
command -v jq &>/dev/null || exit 0

INPUT=$(cat)

FILE_PATH=$(printf '%s' "$INPUT" | jq -r '.tool_input.file_path // empty')
CWD=$(printf '%s' "$INPUT" | jq -r '.cwd // empty')

# Only track model SQL files (support nested dirs: models/staging/stg_foo.sql)
if [[ ! "$FILE_PATH" =~ /models/.*\.sql$ ]]; then
    exit 0
fi

# Compute project-scoped hash from cwd
PROJECT_HASH=$(printf '%s' "${CWD:-$PWD}" | md5 2>/dev/null | cut -c1-8 || printf '%s' "${CWD:-$PWD}" | md5sum | cut -c1-8)
CHANGES_FILE="/tmp/recce-changed-${PROJECT_HASH}.txt"

# Append with deduplication
if ! grep -qxF "$FILE_PATH" "$CHANGES_FILE" 2>/dev/null; then
    echo "$FILE_PATH" >> "$CHANGES_FILE"
fi

# Critical: no stdout (async hook must be silent)
exit 0
