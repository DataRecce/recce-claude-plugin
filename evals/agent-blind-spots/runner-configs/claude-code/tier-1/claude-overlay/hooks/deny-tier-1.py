#!/usr/bin/env python3
"""
Tier-1 PreToolUse hook for the /recce-verify v1 eval.

Tier 1 = Tier 0 plus Recce CLI, Recce MCP, single-env warehouse
credentials (read-only on the dev environment). Base/prod environment
access stays denied — Tier 2 territory, out of v1 scope. Recce MCP is
**intentionally not gated** here — the rubric explicitly allows it.

Tier 1 denies (relative to Tier 0):
  * dbt subcommands that regenerate frozen artifacts or hit a
    warehouse directly (`dbt run|test|parse|compile|docs`). Recce
    reads the frozen artifacts; the agent never needs to regenerate
    them, and dbt invocations would let the agent bypass Recce's
    structured query surfaces.
  * Direct SQL clients (`duckdb`, `psql`, `snowsql`, `bq`) — at Tier 1
    warehouse access is mediated through Recce MCP tools (e.g.
    `mcp__recce__query`), never raw shell.
  * `sh -c "<denied>"`, `bash -c …`, `zsh -c …` wrappers that smuggle
    a denied binary past a shallow check.

This is a denylist (Tier 0 was an allowlist) because Tier 1's
legitimate command surface is large — the agent can invoke arbitrary
git, grep, recce-*, and other dev-loop utilities. Tokenisation +
basename + `sh -c` recursion catch the bypass shapes the prior
case-glob version missed.
"""
from __future__ import annotations

import json
import re
import shlex
import sys
from os.path import basename

# Binaries the Tier-1 agent must not invoke directly.
DENIED_BINS: frozenset[str] = frozenset(
    {"dbt", "duckdb", "psql", "snowsql", "bq"}
)

# dbt subcommands that either regenerate frozen Tier-0 inputs or hit a
# warehouse directly. `dbt` alone (no subcommand) and `dbt --help` are
# allowed — they're discovery-only.
DBT_DENIED_SUBCOMMANDS: frozenset[str] = frozenset(
    {"run", "test", "parse", "compile", "docs", "seed", "snapshot",
     "build", "freshness"}
)

SHELL_WRAPPERS: frozenset[str] = frozenset(
    {"sh", "bash", "zsh", "dash", "ash", "ksh"}
)


def deny(reason: str) -> None:
    print(f"Tier-1 sandbox blocks: {reason}", file=sys.stderr)
    sys.exit(2)


def split_segments(cmd: str) -> list[str]:
    segments: list[str] = []
    for sub in re.findall(r"\$\(([^()]*)\)", cmd):
        segments.extend(split_segments(sub))
    cmd = re.sub(r"\$\([^()]*\)", "", cmd)
    for sub in re.findall(r"`([^`]*)`", cmd):
        segments.extend(split_segments(sub))
    cmd = re.sub(r"`[^`]*`", "", cmd)
    for part in re.split(r"[;&|()\n]+", cmd):
        if part.strip():
            segments.append(part.strip())
    return segments


def tokenize(segment: str) -> list[str]:
    try:
        return shlex.split(segment)
    except ValueError:
        return [segment]


def skip_leading_env(tokens: list[str]) -> list[str]:
    i = 0
    while i < len(tokens) and "=" in tokens[i] and not tokens[i].startswith("="):
        i += 1
    if i >= len(tokens):
        return []
    if basename(tokens[i]) == "env":
        i += 1
        while i < len(tokens):
            t = tokens[i]
            if t in ("-i", "-0", "--null"):
                i += 1
                continue
            if t in ("-u", "--unset"):
                i += 2
                continue
            if "=" in t and not t.startswith("="):
                i += 1
                continue
            break
    return tokens[i:]


def has_denied_dbt_subcommand(tokens: list[str]) -> bool:
    # Walk past `dbt` and look for the first positional (non-flag) token.
    for tok in tokens[1:]:
        if tok.startswith("-"):
            continue
        return tok in DBT_DENIED_SUBCOMMANDS
    return False


def check_tokens(tokens: list[str], command_str: str) -> None:
    tokens = skip_leading_env(tokens)
    if not tokens:
        return
    name = basename(tokens[0])

    if name in SHELL_WRAPPERS:
        # Find the -c / -lc arg and recurse into its content.
        for j in range(1, len(tokens) - 1):
            if tokens[j] in ("-c", "-lc", "-ic"):
                inner = tokens[j + 1]
                for inner_segment in split_segments(inner):
                    check_tokens(tokenize(inner_segment), command_str)
                return
        # A bare `sh`/`bash` interactive subshell with no -c arg is
        # not a denied command on its own.
        return

    if name == "dbt":
        if has_denied_dbt_subcommand(tokens):
            deny(
                "dbt subcommand regenerates frozen artifacts or hits a "
                f"warehouse (matched in: {command_str!r})"
            )
        return

    if name in DENIED_BINS:
        deny(
            f"Direct SQL client '{name}' — use Recce MCP query instead "
            f"(matched in: {command_str!r})"
        )


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return

    if payload.get("tool_name", "") != "Bash":
        return

    command = (payload.get("tool_input", {}) or {}).get("command", "") or ""
    if not command.strip():
        return

    for segment in split_segments(command):
        check_tokens(tokenize(segment), command)


if __name__ == "__main__":
    main()
