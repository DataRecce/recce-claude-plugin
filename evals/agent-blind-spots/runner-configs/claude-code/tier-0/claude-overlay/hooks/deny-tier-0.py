#!/usr/bin/env python3
"""
Tier-0 PreToolUse hook for the /recce-verify v1 eval.

Belt-and-suspenders alongside `permissions.deny` in ../settings.json
(see DRC-3584 issue body: hooks are more reliable than deny rules per
open Claude Code issue #6699).

Tier 0 is a **positive allowlist** for Bash, with Recce MCP / Recce
skill denial layered on top. Anything outside the allowlist exits 2.

The case-glob version of this hook (deny-tier-0.sh, removed in PR #36's
v2 commit) was bypassed by:
  * `true;recce check`, `true|recce`, `(recce check)`, `$(recce ls)` —
    shell separators that aren't `[[:space:]]`
  * `/usr/local/bin/recce check` — absolute path on the executable
  * `sh -c "recce check"`, `bash -lc "..."` — wrapper hiding inner cmd
  * `dbt --debug parse` — global flag interposed before subcommand
  * `Recce-verify`, `RECCE-VERIFY` — skill case-insensitivity
  * `mcp__recce_dev__*` — MCP namespace shape not in the prior regex

This rewrite tokenises by shell metacharacters (not just whitespace),
basenames each executable token (so paths don't help), recurses into
`sh -c` arg, and lowercases the skill name before matching.
"""
from __future__ import annotations

import json
import re
import shlex
import sys
from os.path import basename

# Bash commands a Tier-0 agent legitimately needs. Anything else denied.
# Per RUBRIC.md Tier-0 runtime contract: file read, grep/ripgrep, jq,
# git log/diff/show. The list below is that contract plus standard
# POSIX text-processing utilities for evidence analysis.
TIER_0_ALLOWLIST: frozenset[str] = frozenset({
    "git", "grep", "rg", "jq", "ls", "cat", "head", "tail", "wc", "find",
    "echo", "true", "false", "awk", "sed", "sort", "uniq", "comm", "diff",
    "basename", "dirname", "readlink", "pwd", "file", "stat", "test", "[",
    "printf", "tr", "cut", "xargs", "tee", "less", "more",
})

# Shell wrappers that take `-c <command>`. Banned outright at Tier 0 —
# refusing to interpret them is simpler than recursing, and an agent
# with a positive allowlist has no legitimate reason to invoke a shell.
SHELL_WRAPPERS: frozenset[str] = frozenset(
    {"sh", "bash", "zsh", "dash", "ash", "ksh"}
)

# Recce MCP namespaces. Covers mcp__recce__*, mcp__plugin_recce_*,
# mcp__recce_dev__*, and any future Recce-shaped namespace.
MCP_RECCE_RE = re.compile(r"^mcp__(plugin_)?recce(_|-|$)", re.IGNORECASE)

# Recce skill prefix — `recce-verify`, `recce:recce-review`, etc.
RECCE_SKILL_RE = re.compile(r"^recce[-:]", re.IGNORECASE)


def deny(reason: str) -> None:
    print(f"Tier-0 sandbox blocks: {reason}", file=sys.stderr)
    sys.exit(2)


def split_segments(cmd: str) -> list[str]:
    """Split a shell command into segments by separators that introduce
    a new command boundary: `;`, `&`, `|`, `(`, `)`, newline. Also
    extract `$(...)` and backtick subshells as their own segments —
    they let the agent smuggle a command past a leading `echo`.
    """
    segments: list[str] = []

    # Extract command substitutions first (they could nest, but a
    # single-level extraction defeats the obvious bypass and matches
    # the threat model: an LLM is unlikely to construct deep nesting
    # specifically to evade us).
    for sub in re.findall(r"\$\(([^()]*)\)", cmd):
        segments.extend(split_segments(sub))
    cmd = re.sub(r"\$\([^()]*\)", "", cmd)
    for sub in re.findall(r"`([^`]*)`", cmd):
        segments.extend(split_segments(sub))
    cmd = re.sub(r"`[^`]*`", "", cmd)

    # Now split on command-boundary separators.
    parts = re.split(r"[;&|()\n]+", cmd)
    for part in parts:
        if part.strip():
            segments.append(part.strip())
    return segments


def tokenize(segment: str) -> list[str]:
    try:
        return shlex.split(segment)
    except ValueError:
        # Unbalanced quotes — treat as one opaque token. Whatever the
        # agent meant, it's not a clean invocation; let the allowlist
        # check it as-is.
        return [segment]


def skip_leading_env(tokens: list[str]) -> list[str]:
    """Skip `VAR=value` env assignments and `env [args] CMD ...` so the
    executable check lands on the real command.
    """
    i = 0
    while i < len(tokens) and "=" in tokens[i] and not tokens[i].startswith("="):
        i += 1
    if i >= len(tokens):
        return []
    if basename(tokens[i]) == "env":
        i += 1
        # env [-i] [-u VAR ...] [NAME=value ...] command ...
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


def check_bash_command(command: str) -> None:
    if not command.strip():
        return
    for segment in split_segments(command):
        tokens = skip_leading_env(tokenize(segment))
        if not tokens:
            continue
        name = basename(tokens[0])
        if name in SHELL_WRAPPERS:
            deny(
                f"shell wrapper '{name}' is banned at Tier 0 — the "
                f"agent has no legitimate reason to invoke a subshell "
                f"(matched in: {command!r})"
            )
        if not name:
            continue
        if name not in TIER_0_ALLOWLIST:
            deny(
                f"Bash executable '{name}' not in Tier-0 allowlist "
                f"(matched in: {command!r})"
            )


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        # Malformed payload — fail open so a single bad invocation
        # doesn't break the whole session. The matcher in settings.json
        # narrows what we see; nothing legitimate arrives malformed.
        return

    tool_name = payload.get("tool_name", "") or ""
    tool_input = payload.get("tool_input", {}) or {}

    if MCP_RECCE_RE.match(tool_name):
        deny(f"Recce MCP tool '{tool_name}' (Tier-0 disallows Recce)")

    skill = tool_input.get("skill", "") or ""
    if RECCE_SKILL_RE.match(skill):
        deny(f"Recce skill '{skill}' (Tier-0 disallows /recce-* skills)")

    if tool_name == "Bash":
        check_bash_command(tool_input.get("command", "") or "")


if __name__ == "__main__":
    main()
