#!/bin/bash
# Clone a dbt project repo and bootstrap for eval.
# Usage: bash setup-v2-project.sh --repo <owner/name> --ref <branch|tag|sha>
# Output: PROJECT_DIR=/tmp/recce-eval-XXXX
set -euo pipefail

REPO="" REF="main"
while [[ $# -gt 0 ]]; do
    case "$1" in
        --repo) REPO="$2"; shift 2 ;;
        --ref)  REF="$2";  shift 2 ;;
        *) echo "ERROR: Unknown argument: $1" >&2; exit 1 ;;
    esac
done

if [ -z "$REPO" ]; then
    echo "ERROR: --repo is required" >&2
    exit 1
fi

PROJECT_DIR=$(mktemp -d "/tmp/recce-eval-XXXXXXXX")

echo "Cloning ${REPO}@${REF} into ${PROJECT_DIR}..." >&2
git clone --branch "$REF" --depth 1 "https://github.com/${REPO}.git" "$PROJECT_DIR" >&2

cd "$PROJECT_DIR"

echo "Creating venv and installing dbt + recce..." >&2
python3 -m venv .venv
source .venv/bin/activate
pip install --quiet dbt-core dbt-duckdb recce

echo "Installing dbt packages..." >&2
dbt deps --quiet

echo "Seeding data..." >&2
dbt seed --full-refresh --vars '{"load_source_data": true}' --quiet

echo "PROJECT_DIR=$PROJECT_DIR"
