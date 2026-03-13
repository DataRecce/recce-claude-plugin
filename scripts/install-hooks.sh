#!/usr/bin/env bash
# install-hooks.sh — copies git hooks from scripts/hooks/ to .git/hooks/
# Usage: bash scripts/install-hooks.sh
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"

install_hook() {
  local name="$1"
  local src="$REPO_ROOT/scripts/hooks/$name"
  local dest="$REPO_ROOT/.git/hooks/$name"

  if [ ! -f "$src" ]; then
    echo "ERROR: hook source not found: $src" >&2
    exit 1
  fi

  cp "$src" "$dest"
  chmod +x "$dest"
  echo "Installed $name hook -> $dest"
}

install_hook "pre-push"
echo "Done. Run 'git push' to test the hook."
