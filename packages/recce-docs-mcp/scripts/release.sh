#!/usr/bin/env bash
# release.sh — Cut a release of @datarecce/docs-mcp.
#
# Usage:
#   bash scripts/release.sh <patch|minor|major|x.y.z> [--dry-run]
#
# What it does:
#   1. Sanity-checks: clean working tree, on main, logged into npm.
#   2. Runs tests + build.
#   3. Bumps version in package.json (no git tag — we create our own).
#   4. Shows tarball contents via `npm pack --dry-run`.
#   5. Asks for confirmation, then:
#        - commits the version bump
#        - tags it as docs-mcp-v<version>
#        - publishes to npm
#        - pushes commit + tag
#
# With --dry-run: stops before publishing, just shows what would happen.

set -euo pipefail

if [ "$#" -lt 1 ]; then
  echo "Usage: bash scripts/release.sh <patch|minor|major|x.y.z> [--dry-run]"
  exit 1
fi

BUMP="$1"
DRY_RUN="${2:-}"

PKG_DIR="$(cd "$(dirname "$0")/.." && pwd)"
REPO_ROOT="$(git -C "$PKG_DIR" rev-parse --show-toplevel)"
cd "$PKG_DIR"

echo "==> Pre-flight checks"

if [ -n "$(git -C "$REPO_ROOT" status --porcelain)" ]; then
  echo "ERROR: working tree is not clean. Commit or stash changes first."
  git -C "$REPO_ROOT" status --short
  exit 1
fi

BRANCH="$(git -C "$REPO_ROOT" rev-parse --abbrev-ref HEAD)"
if [ "$BRANCH" != "main" ]; then
  echo "WARN: not on main (current: $BRANCH). Continue? [y/N]"
  read -r ans
  [ "$ans" = "y" ] || [ "$ans" = "Y" ] || { echo "Aborted."; exit 1; }
fi

if ! npm whoami >/dev/null 2>&1; then
  echo "ERROR: not logged into npm. Run: npm login"
  exit 1
fi
echo "  npm user: $(npm whoami)"

echo "==> Installing dependencies"
npm ci

echo "==> Running tests"
npm test

echo "==> Building"
npm run build

echo "==> Bumping version ($BUMP)"
# --no-git-tag-version: we manage the tag ourselves with our scoped prefix.
NEW_VERSION="$(npm version "$BUMP" --no-git-tag-version | tr -d 'v')"
TAG="docs-mcp-v${NEW_VERSION}"
echo "  new version: $NEW_VERSION"
echo "  git tag:     $TAG"

echo "==> Tarball preview"
npm pack --dry-run

echo ""
echo "About to:"
echo "  1. git commit -m 'chore(docs-mcp): release v${NEW_VERSION}'"
echo "  2. git tag ${TAG}"
echo "  3. npm publish  (access=public, provenance via CI only)"
echo "  4. git push && git push origin ${TAG}"
echo ""

if [ "$DRY_RUN" = "--dry-run" ]; then
  echo "Dry run — reverting version bump and exiting."
  git -C "$REPO_ROOT" checkout -- "$PKG_DIR/package.json" "$PKG_DIR/package-lock.json" 2>/dev/null || true
  exit 0
fi

echo "Continue? [y/N]"
read -r ans
[ "$ans" = "y" ] || [ "$ans" = "Y" ] || {
  echo "Aborted. Reverting version bump."
  git -C "$REPO_ROOT" checkout -- "$PKG_DIR/package.json" "$PKG_DIR/package-lock.json" 2>/dev/null || true
  exit 1
}

echo "==> Committing + tagging"
git -C "$REPO_ROOT" add "$PKG_DIR/package.json" "$PKG_DIR/package-lock.json"
git -C "$REPO_ROOT" commit -m "chore(docs-mcp): release v${NEW_VERSION}"
git -C "$REPO_ROOT" tag -a "$TAG" -m "@datarecce/docs-mcp v${NEW_VERSION}"

echo "==> Publishing to npm"
# Provenance requires OIDC, which is only available in CI — omit locally.
npm publish --access public

echo "==> Pushing commit + tag"
git -C "$REPO_ROOT" push
git -C "$REPO_ROOT" push origin "$TAG"

echo ""
echo "Released @datarecce/docs-mcp@${NEW_VERSION}"
echo "  https://www.npmjs.com/package/@datarecce/docs-mcp"
