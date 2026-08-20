#!/usr/bin/env python3
"""check-artifacts.py -- Decide whether target/ still describes the working tree.

Used by /recce-dev-review before the upload decision.

The upload decision compares the session's timestamp against
target/manifest.json. That says nothing about whether the artifacts describe
the current source, or whether the warehouse was ever rebuilt -- both can be
stale while the manifest looks fresh. Uploading then reviews code the
developer no longer has.

Two mtime comparisons answer it, one per dbt command:

  models/<path>.sql  vs  target/manifest.json
      newer source means the artifacts predate the edit -> dbt docs generate

  models/<path>.sql  vs  target/run/<project>/<path>.sql
      target/run/ is written only by dbt run / dbt build, so a newer source
      (or a missing file) means the warehouse never got this version
      -> dbt run

target/run_results.json is not usable for the second check: `dbt docs
generate` rewrites it (args.which == "generate"), so its mtime says nothing
about a run.

Args:    [--target-path PATH]  (default: target)
Stdout:  ARTIFACTS=ok|stale_docs|stale_tables|stale_both
         STALE_MODELS=<comma+space separated names>   (omitted when ok)
Exit:    0 always. An unreadable or absent manifest reports ok -- the
         precondition step already owns the missing-artifacts case, and a
         second opinion here would contradict it.

mtime is not content: git checkout, a formatter, or touch moves it with no
real change, so this can ask for a rebuild that changes nothing. It never
reports fresh for a file that genuinely changed later, which is the
direction that matters.
"""

import argparse
import json
import os
import sys

# Ephemeral models are inlined into their consumers, so dbt run never writes a
# target/run file for them. Without this they would always look unbuilt.
NO_RUN_FILE = {"ephemeral"}


def main() -> int:
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("--target-path", default="target")
    ap.add_argument("-h", "--help", action="help")
    args = ap.parse_args()

    target = args.target_path
    manifest_path = os.path.join(target, "manifest.json")

    try:
        with open(manifest_path, "rb") as fh:
            manifest = json.load(fh)
        manifest_mtime = os.path.getmtime(manifest_path)
    except (OSError, ValueError):
        print("ARTIFACTS=ok")
        return 0

    project = (manifest.get("metadata") or {}).get("project_name") or ""
    stale_docs, stale_tables = [], []

    for node in (manifest.get("nodes") or {}).values():
        if node.get("resource_type") != "model":
            continue
        rel = node.get("original_file_path")
        if not rel:
            continue
        # original_file_path is relative to the package root, and a model from
        # an installed package is not this developer's source to rebuild.
        if node.get("package_name") and project and node["package_name"] != project:
            continue
        try:
            src_mtime = os.path.getmtime(rel)
        except OSError:
            continue

        name = node.get("name") or rel

        if src_mtime > manifest_mtime:
            stale_docs.append(name)

        if (node.get("config") or {}).get("materialized") in NO_RUN_FILE:
            continue
        run_path = os.path.join(target, "run", node.get("package_name") or project, rel)
        try:
            if src_mtime > os.path.getmtime(run_path):
                stale_tables.append(name)
        except OSError:
            # Never executed under this target path.
            stale_tables.append(name)

    if stale_docs and stale_tables:
        verdict = "stale_both"
    elif stale_docs:
        verdict = "stale_docs"
    elif stale_tables:
        verdict = "stale_tables"
    else:
        verdict = "ok"

    print(f"ARTIFACTS={verdict}")
    if verdict != "ok":
        names = sorted(set(stale_docs) | set(stale_tables))
        print("STALE_MODELS=" + ", ".join(names))
    return 0


if __name__ == "__main__":
    sys.exit(main())
