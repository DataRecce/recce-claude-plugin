#!/bin/bash
# List eval scenarios from a version directory.
# Usage: bash list-scenarios.sh --version <v1|v2> [--base-dir <path>]
# Output: pipe-delimited rows: id|name|case_type|difficulty
set -euo pipefail

VERSION="v2" BASE_DIR=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --version)  VERSION="$2";  shift 2 ;;
        --base-dir) BASE_DIR="$2"; shift 2 ;;
        *) echo "ERROR: Unknown argument: $1" >&2; exit 1 ;;
    esac
done

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BASE_DIR="${BASE_DIR:-$(dirname "$SCRIPT_DIR")}"
SCENARIO_DIR="$BASE_DIR/scenarios/$VERSION"

if [ ! -d "$SCENARIO_DIR" ]; then
    echo "ERROR: Scenario directory not found: $SCENARIO_DIR" >&2
    exit 1
fi

yq eval-all -r -o=json \
    '[.] | .[] | select(.id) | (.id + "|" + .name + "|" + .case_type + "|" + (.difficulty // "-"))' \
    "$SCENARIO_DIR"/*.yaml
