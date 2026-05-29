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

# Exec wrappers that run their argument as a new process. `xargs` and
# `find` are in the allowlist (legitimate dev-loop utilities), but
# they can launch any binary — including a denied one. Recurse into
# their wrapped command and re-check it against the allowlist.
#
# `time`, `nohup`, `nice`, `setsid`, etc. are NOT in the allowlist,
# so they're already denied head-of-token. Including them here is
# defensive: if a future version of this hook adds them to the
# allowlist, the recursion contract still holds.
EXEC_WRAPPERS: frozenset[str] = frozenset(
    {"xargs", "time", "nice", "nohup", "setsid", "parallel",
     "exec", "timeout", "watch", "ionice", "chrt", "stdbuf"}
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

    # Now split on command-boundary separators. Negative lookbehind on
    # `\\` keeps escaped separators (e.g. the `\;` that terminates
    # `find -exec`) attached to the same segment; shlex strips the
    # backslash later.
    parts = re.split(r"(?<!\\)[;&|()\n]+", cmd)
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


def looks_like_executable(name: str) -> bool:
    """Heuristic — does this token's basename look like it could be a
    binary the agent is actually invoking? Rules out numbers (timeout
    durations, chrt priorities), pure-symbol tokens (`{}`, `;`), and
    empty strings.
    """
    if not name:
        return False
    if name in ("{}", "[]", ";", "+", "\\;"):
        return False
    if name.isdigit():
        return False
    # Allow alphanumerics + `_`/`-`/`.` (binaries like `git-foo`,
    # `python3.11`, `recce-cli`). Anything else (e.g., a quoted-shell
    # construct that survived shlex) is treated as non-executable.
    stripped = name.replace("-", "").replace("_", "").replace(".", "")
    return stripped.isalnum()


def find_wrapped_command(wrapper_name: str, tokens: list[str]) -> list[str]:
    """For an exec wrapper at tokens[0], return the wrapped command's
    tokens.

    Different wrappers interleave their own positional args before the
    wrapped command (e.g., `timeout 30 CMD`, `chrt 0 5 CMD`,
    `ionice -c 2 CMD`). Hard-coding a per-wrapper arg parser is
    brittle. Instead, walk the args and return tokens starting at the
    first executable-shaped token. `find` is special because the
    wrapped command lives after a `-exec` / `-execdir` keyword.
    """
    if wrapper_name == "find":
        for keyword in ("-exec", "-execdir"):
            if keyword not in tokens:
                continue
            idx = tokens.index(keyword)
            end = len(tokens)
            for j in range(idx + 1, len(tokens)):
                if tokens[j] in (";", "+", "\\;"):
                    end = j
                    break
            return tokens[idx + 1:end]
        return []
    for i, tok in enumerate(tokens[1:], 1):
        if tok.startswith("-"):
            continue
        if not looks_like_executable(basename(tok)):
            continue
        return tokens[i:]
    return []


def check_segment_tokens(tokens: list[str], command: str, depth: int = 0) -> None:
    if depth > 4:
        return
    tokens = skip_leading_env(tokens)
    if not tokens:
        return
    name = basename(tokens[0])

    if name in SHELL_WRAPPERS:
        deny(
            f"shell wrapper '{name}' is banned at Tier 0 — the "
            f"agent has no legitimate reason to invoke a subshell "
            f"(matched in: {command!r})"
        )

    if not name:
        return

    # Exec wrappers in the allowlist (`xargs`, `find`) need recursion
    # so they can't smuggle a denied binary through. Wrappers NOT in
    # the allowlist (`time`, `nohup`, ...) are denied head-of-token
    # below, so the recursion is moot for them — but we still handle
    # them defensively in case the allowlist grows.
    if name in EXEC_WRAPPERS or name == "find":
        wrapped = find_wrapped_command(name, tokens)
        if wrapped:
            check_segment_tokens(wrapped, command, depth + 1)
        # If the wrapper itself isn't in the allowlist, fall through
        # to the allowlist check (will deny). If it IS allowlisted
        # (xargs / find), the wrapped check above is what enforces.
        if name in TIER_0_ALLOWLIST:
            return

    if name not in TIER_0_ALLOWLIST:
        deny(
            f"Bash executable '{name}' not in Tier-0 allowlist "
            f"(matched in: {command!r})"
        )


def check_bash_command(command: str) -> None:
    if not command.strip():
        return
    for segment in split_segments(command):
        check_segment_tokens(tokenize(segment), command)


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
