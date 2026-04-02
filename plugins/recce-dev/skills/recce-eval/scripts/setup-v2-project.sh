#!/bin/bash
# Clone a dbt project repo and bootstrap for eval.
# Usage: bash setup-v2-project.sh --repo <owner/name> --ref <branch|tag|sha>
# Output: PROJECT_DIR=$TMPDIR/XXXXXXXX/recce-eval
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

WORK_DIR=$(mktemp -d "${TMPDIR:-/tmp}/XXXXXXXX")
PROJECT_DIR="$WORK_DIR/recce-eval"

# Always output both dirs so the caller can clean up on failure.
# Clean up WORK_DIR (parent) to avoid leaving empty temp directories.
trap 'echo "PROJECT_DIR=$PROJECT_DIR"; echo "WORK_DIR=$WORK_DIR"' EXIT

echo "Cloning ${REPO}@${REF} into ${PROJECT_DIR}..." >&2
# --branch works for branches/tags but not raw SHAs.
# Detect SHA refs (40-char hex) and use fetch+checkout instead.
if [[ "$REF" =~ ^[0-9a-f]{40}$ ]]; then
    git clone --depth 1 "https://github.com/${REPO}.git" "$PROJECT_DIR" >&2
    git -C "$PROJECT_DIR" fetch --depth 1 origin "$REF" >&2
    git -C "$PROJECT_DIR" checkout "$REF" >&2
else
    git clone --branch "$REF" --depth 1 "https://github.com/${REPO}.git" "$PROJECT_DIR" >&2
fi

cd "$PROJECT_DIR"

echo "Creating venv and installing dbt + recce..." >&2
python3 -m venv .venv >&2
source .venv/bin/activate
pip install --quiet dbt-core dbt-duckdb recce >&2

echo "Installing dbt packages..." >&2
dbt deps --quiet >&2

echo "Seeding data..." >&2
dbt seed --full-refresh --vars "{\"load_source_data\": true}" --quiet >&2
