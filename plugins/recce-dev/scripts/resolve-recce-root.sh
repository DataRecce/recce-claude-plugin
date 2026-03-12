#!/bin/bash
# resolve-recce-root.sh — Locate the sibling 'recce' plugin root directory.
#
# Supports two installation layouts:
#   1. Monorepo:  plugins/recce-dev/  ←→  plugins/recce/
#   2. Cache:     {marketplace}/recce-dev/{ver}/  ←→  {marketplace}/recce/{ver}/
#
# Output: KEY=VALUE lines on stdout.
#   Success: RECCE_PLUGIN_ROOT=/path/to/recce  LAYOUT=monorepo|cache
#   Failure: ERROR=<message>  TRIED=<paths>
#
# Usage:
#   source this file (sets RECCE_PLUGIN_ROOT variable), or
#   eval "$(bash resolve-recce-root.sh)"

SELF_ROOT="${CLAUDE_PLUGIN_ROOT:-${1:-$(cd "$(dirname "$0")/.." && pwd)}}"
TRIED=""

# --- Probe 1: Monorepo layout (../recce/scripts/) ---
CANDIDATE="${SELF_ROOT}/../recce"
TRIED="${CANDIDATE}"
if [ -d "${CANDIDATE}/scripts" ]; then
    echo "RECCE_PLUGIN_ROOT=$(cd "${CANDIDATE}" && pwd)"
    echo "LAYOUT=monorepo"
    exit 0
fi

# --- Probe 2: Cache layout (../../recce/*/scripts/) ---
# Cache structure: {marketplace}/{plugin}/{version}/
# From recce-dev/{ver}/, go up 2 levels to {marketplace}/, then into recce/{ver}/
CACHE_PARENT="${SELF_ROOT}/../.."
CANDIDATE_DIR="${CACHE_PARENT}/recce"
TRIED="${TRIED}, ${CANDIDATE_DIR}/*"

if [ -d "${CANDIDATE_DIR}" ]; then
    # Find the latest version directory that contains scripts/
    LATEST=$(ls -d "${CANDIDATE_DIR}/"*/scripts 2>/dev/null | sort -V | tail -1)
    if [ -n "${LATEST}" ]; then
        RESOLVED=$(cd "${LATEST}/.." && pwd)
        echo "RECCE_PLUGIN_ROOT=${RESOLVED}"
        echo "LAYOUT=cache"
        exit 0
    fi
fi

# --- Failure ---
echo "ERROR=recce plugin not found"
echo "TRIED=${TRIED}"
echo "SELF_ROOT=${SELF_ROOT}"
exit 1
