#!/bin/bash
# load-baseline.sh — Load baseline benchmark for comparison
#
# Usage:
#   bash load-baseline.sh                          # Load latest.json
#   bash load-baseline.sh --timestamp 2026-03-13T041957  # Load specific run
#   bash load-baseline.sh --flow-version 1.0.0     # Load latest with matching flow version
#
# Output: KEY=VALUE lines
#   BASELINE_FOUND=true|false
#   BASELINE_FILE=/path/to/file.json
#   FLOW_VERSION=1.0.0
#   TOOL_USES=29
#   TOTAL_TOKENS=23821
#   DURATION_S=3862
#   RECCE_VERSION=1.40.0.dev0
#   VERDICT=PASS

set -euo pipefail

BENCHMARKS_DIR=".claude/recce/benchmarks"
TARGET_TIMESTAMP=""
TARGET_FLOW_VERSION=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --timestamp)
            [[ $# -lt 2 ]] && { echo "ERROR=Missing value for --timestamp"; exit 1; }
            TARGET_TIMESTAMP="$2"; shift 2 ;;
        --flow-version)
            [[ $# -lt 2 ]] && { echo "ERROR=Missing value for --flow-version"; exit 1; }
            TARGET_FLOW_VERSION="$2"; shift 2 ;;
        *) echo "ERROR=Unknown argument: $1"; exit 1 ;;
    esac
done

# ── Resolve target file ──
BASELINE_FILE=""

if [ -n "$TARGET_TIMESTAMP" ]; then
    # Specific timestamp
    CANDIDATE="${BENCHMARKS_DIR}/${TARGET_TIMESTAMP}.json"
    if [ -f "$CANDIDATE" ]; then
        BASELINE_FILE="$CANDIDATE"
    fi
elif [ -n "$TARGET_FLOW_VERSION" ]; then
    # Find latest benchmark with matching flow_version
    if command -v jq &>/dev/null; then
        for f in $(find "${BENCHMARKS_DIR}" -maxdepth 1 -name '*.json' -not -name 'latest.json' 2>/dev/null | sort -r); do
            FV=$(jq -r '.flow_version // ""' "$f" 2>/dev/null)
            if [ "$FV" = "$TARGET_FLOW_VERSION" ]; then
                BASELINE_FILE="$f"
                break
            fi
        done
    else
        echo "WARNING=jq is required for --flow-version filter; falling back to no baseline"
    fi
else
    # Default: latest.json
    CANDIDATE="${BENCHMARKS_DIR}/latest.json"
    if [ -f "$CANDIDATE" ]; then
        BASELINE_FILE="$CANDIDATE"
    fi
fi

# ── Output ──
if [ -z "$BASELINE_FILE" ] || [ ! -f "$BASELINE_FILE" ]; then
    echo "BASELINE_FOUND=false"
    exit 0
fi

echo "BASELINE_FOUND=true"
echo "BASELINE_FILE=${BASELINE_FILE}"

if command -v jq &>/dev/null; then
    echo "FLOW_VERSION=$(jq -r '.flow_version // "unknown"' "$BASELINE_FILE")"
    echo "TOOL_USES=$(jq -r '.performance.tool_uses // 0' "$BASELINE_FILE")"
    echo "TOTAL_TOKENS=$(jq -r '.performance.total_tokens // 0' "$BASELINE_FILE")"
    echo "DURATION_S=$(jq -r '.performance.duration_s // 0' "$BASELINE_FILE")"
    echo "RECCE_VERSION=$(jq -r '.recce_version // "unknown"' "$BASELINE_FILE")"
    echo "VERDICT=$(jq -r '.verdict // "unknown"' "$BASELINE_FILE")"
    echo "TIMESTAMP=$(jq -r '.timestamp // "unknown"' "$BASELINE_FILE")"
else
    # Fallback: grep-based extraction
    echo "FLOW_VERSION=$(grep -o '"flow_version"[[:space:]]*:[[:space:]]*"[^"]*"' "$BASELINE_FILE" | head -1 | sed 's/.*: *"//' | tr -d '"')"
    echo "TOOL_USES=$(grep -o '"tool_uses"[[:space:]]*:[[:space:]]*[0-9]*' "$BASELINE_FILE" | head -1 | sed 's/.*: *//')"
    echo "TOTAL_TOKENS=$(grep -o '"total_tokens"[[:space:]]*:[[:space:]]*[0-9]*' "$BASELINE_FILE" | head -1 | sed 's/.*: *//')"
    echo "DURATION_S=$(grep -o '"duration_s"[[:space:]]*:[[:space:]]*[0-9]*' "$BASELINE_FILE" | head -1 | sed 's/.*: *//')"
    echo "RECCE_VERSION=$(grep -o '"recce_version"[[:space:]]*:[[:space:]]*"[^"]*"' "$BASELINE_FILE" | head -1 | sed 's/.*: *"//' | tr -d '"')"
    echo "VERDICT=$(grep -o '"verdict"[[:space:]]*:[[:space:]]*"[^"]*"' "$BASELINE_FILE" | head -1 | sed 's/.*: *"//' | tr -d '"')"
    echo "TIMESTAMP=$(grep -o '"timestamp"[[:space:]]*:[[:space:]]*"[^"]*"' "$BASELINE_FILE" | head -1 | sed 's/.*: *"//' | tr -d '"')"
fi
