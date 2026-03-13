#!/usr/bin/env bash
# build-bundle.sh — Bundles recce-docs-mcp into a self-contained CLI for plugin distribution.
#
# Format: CJS (not ESM)
# Reason: safer-buffer (cheerio transitive dep via iconv-lite) calls require('buffer')
# at module load. esbuild's ESM polyfill cannot route built-in module calls, causing
# "Dynamic require of 'buffer' is not supported" at runtime. CJS handles this natively.
#
# The --banner and --define flags polyfill import.meta.url for CJS context because
# server.ts uses import.meta.url (ESM idiom) for __dirname resolution.
#
# Empirically verified: 2026-03-12 with esbuild 0.27.3

set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
PKG="$REPO_ROOT/packages/recce-docs-mcp"
BUNDLE_DIR="$PKG/dist-bundle"

mkdir -p "$BUNDLE_DIR"

echo "Building bundle..."
"$PKG/node_modules/.bin/esbuild" "$PKG/src/cli.ts" \
  --bundle \
  --platform=node \
  --format=cjs \
  --target=node20 \
  --minify \
  '--banner:js=const _importMetaUrl=require("url").pathToFileURL(__filename).href;' \
  '--define:import.meta.url=_importMetaUrl' \
  --outfile="$BUNDLE_DIR/cli.js"

echo "Bundle size: $(du -h "$BUNDLE_DIR/cli.js" | cut -f1)"

echo "Copying to plugins..."
for plugin in recce recce-quickstart; do
  DEST="$REPO_ROOT/plugins/$plugin/servers/recce-docs-mcp/dist"
  mkdir -p "$DEST"
  cp "$BUNDLE_DIR/cli.js" "$DEST/cli.js"
  chmod +x "$DEST/cli.js"
  echo "Copied to $plugin"
done

echo "Verifying copies are identical..."
diff -q \
  "$REPO_ROOT/plugins/recce/servers/recce-docs-mcp/dist/cli.js" \
  "$REPO_ROOT/plugins/recce-quickstart/servers/recce-docs-mcp/dist/cli.js" \
  && echo "Verified: both dist/cli.js files are byte-for-byte identical" \
  || { echo "ERROR: dist/cli.js files differ!"; exit 1; }

echo "Done."
