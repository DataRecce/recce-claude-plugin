#!/usr/bin/env bash
# check-bundle-freshness.sh — runs the same check as CI bundle-freshness job, locally.
# Usage: bash scripts/check-bundle-freshness.sh
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"

echo "Installing packages/recce-docs-mcp dependencies..."
npm ci --prefix "$REPO_ROOT/packages/recce-docs-mcp"

echo "Rebuilding bundle..."
bash "$REPO_ROOT/packages/recce-docs-mcp/scripts/build-bundle.sh"

echo "Checking freshness..."
DIFF_LINES=$(git -C "$REPO_ROOT" diff --ignore-space-at-eol --text -- \
  "plugins/*/servers/recce-docs-mcp/dist/cli.js" | wc -l)
if [ "$DIFF_LINES" -gt "0" ]; then
  echo "FAIL: bundle is stale"
  git -C "$REPO_ROOT" diff --stat -- "plugins/*/servers/recce-docs-mcp/dist/cli.js"
  exit 1
fi
echo "PASS: bundle is fresh (zero diff)"
