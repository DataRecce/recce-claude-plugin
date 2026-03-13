#!/bin/bash
# show-history.sh — Display benchmark history as a markdown table
#
# Usage:
#   bash show-history.sh              # Show all runs
#   bash show-history.sh --limit 5    # Show last 5 runs
#   bash show-history.sh --flow-version 1.0.0  # Filter by flow version
#
# Output: Markdown table to stdout

set -euo pipefail

BENCHMARKS_DIR=".claude/recce/benchmarks"
LIMIT=0
FILTER_FV=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --limit)
            [[ $# -lt 2 ]] && { echo "ERROR=Missing value for --limit"; exit 1; }
            LIMIT="$2"; shift 2 ;;
        --flow-version)
            [[ $# -lt 2 ]] && { echo "ERROR=Missing value for --flow-version"; exit 1; }
            FILTER_FV="$2"; shift 2 ;;
        *) echo "ERROR=Unknown argument: $1"; exit 1 ;;
    esac
done

# ── Check directory exists ──
if [ ! -d "$BENCHMARKS_DIR" ]; then
    echo "NO_HISTORY=true"
    echo "MESSAGE=No benchmarks directory found at ${BENCHMARKS_DIR}"
    exit 0
fi

# ── Collect JSON files (newest first, exclude latest.json) ──
FILES=$(find "${BENCHMARKS_DIR}" -maxdepth 1 -name '*.json' -not -name 'latest.json' 2>/dev/null | sort -r)
if [ -z "$FILES" ]; then
    echo "NO_HISTORY=true"
    echo "MESSAGE=No benchmark files found"
    exit 0
fi

# ── Check jq availability ──
if ! command -v jq &>/dev/null; then
    echo "ERROR=jq is required for --history. Install with: brew install jq"
    exit 1
fi

# ── Build table ──
TABLE_HEADER="| # | Date | Flow Ver | Recce Ver | Tools | Tokens | Time | Risk | Verdict |
|---|------|----------|-----------|-------|--------|------|------|---------|"

COUNT=0
ROWS=""
while IFS= read -r f; do
    FV=$(jq -r '.flow_version // "?"' "$f")

    # Apply flow version filter
    if [ -n "$FILTER_FV" ] && [ "$FV" != "$FILTER_FV" ]; then
        continue
    fi

    COUNT=$((COUNT + 1))

    # Apply limit
    if [ "$LIMIT" -gt 0 ] && [ "$COUNT" -gt "$LIMIT" ]; then
        break
    fi

    TS=$(jq -r '.timestamp // "?"' "$f")
    RV=$(jq -r '.recce_version // "?"' "$f")
    TU=$(jq -r '.performance.tool_uses // "?"' "$f")
    TK=$(jq -r '.performance.total_tokens // "?"' "$f")
    DUR=$(jq -r '.performance.duration_s // "?"' "$f")
    RISK=$(jq -r '.risk_level // "?"' "$f")
    VERD=$(jq -r '.verdict // "?"' "$f")

    # Format date (extract date part from ISO timestamp)
    DATE=$(echo "$TS" | cut -c1-10)

    # Format duration
    if [ "$DUR" != "?" ] && [ "$DUR" -gt 60 ] 2>/dev/null; then
        MINS=$((DUR / 60))
        SECS=$((DUR % 60))
        DUR_FMT="${MINS}m${SECS}s"
    else
        DUR_FMT="${DUR}s"
    fi

    # Format tokens with comma
    if [ "$TK" != "?" ] && command -v printf &>/dev/null; then
        TK_FMT=$(printf "%'d" "$TK" 2>/dev/null || echo "$TK")
    else
        TK_FMT="$TK"
    fi

    ROWS="${ROWS}| ${COUNT} | ${DATE} | ${FV} | ${RV} | ${TU} | ${TK_FMT} | ${DUR_FMT} | ${RISK} | ${VERD} |
"
done <<< "$FILES"

# Output results — only emit HAS_HISTORY when rows exist
if [ "$COUNT" -eq 0 ]; then
    echo "NO_HISTORY=true"
    if [ -n "$FILTER_FV" ]; then
        echo "MESSAGE=No benchmarks found for flow version ${FILTER_FV}"
    else
        echo "MESSAGE=No benchmark files found"
    fi
else
    echo "HAS_HISTORY=true"
    echo "---TABLE_START---"
    echo "$TABLE_HEADER"
    printf "%s" "$ROWS"
    echo "---TABLE_END---"
    echo "TOTAL_RUNS=${COUNT}"
fi
