#!/usr/bin/env python3
"""
Tier-1 PreToolUse hook for the /recce-verify v1 eval.

Tier 1 = Tier 0 plus Recce CLI, Recce MCP, single-env warehouse
credentials (read-only on the dev environment). Base/prod environment
access stays denied — Tier 2 territory, out of v1 scope. Recce MCP is
**intentionally not gated** here — the rubric explicitly allows it.

Tier 1 denies (relative to Tier 0):
  * dbt subcommands that regenerate frozen artifacts or hit a
    warehouse directly (`dbt run|test|parse|compile|docs|seed|...`).
    Recce reads the frozen artifacts; the agent never needs to
    regenerate them, and dbt invocations would let the agent bypass
    Recce's structured query surfaces.
  * Direct SQL clients (`duckdb`, `psql`, `snowsql`, `bq`) — at Tier 1
    warehouse access is mediated through Recce MCP tools (e.g.
    `mcp__recce__query`), never raw shell.
  * `sh -c "<denied>"`, `bash -c …`, `zsh -c …` wrappers that smuggle
    a denied binary past a shallow check.
  * Exec wrappers (`xargs`, `find -exec`, `time`, `nohup`, …) that
    launch a denied binary as a child process — same bypass class as
    `sh -c`, different syntactic shape.

This is a denylist (Tier 0 is an allowlist) because Tier 1's
legitimate command surface is large — the agent can invoke arbitrary
git, grep, recce-*, and other dev-loop utilities. Tokenisation +
basename + wrapper recursion catch the bypass shapes the prior
case-glob and v2 hooks missed.
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

# dbt subcommands that regenerate frozen Tier-0 inputs or hit a
# warehouse directly. `dbt` alone (no subcommand), `dbt --help`,
# `dbt --version`, `dbt list` / `dbt ls`, `dbt deps`, `dbt clean` are
# allowed because they don't regenerate artifacts or touch the
# warehouse.
#
# `dbt clone` (dbt-core ≥1.6) materialises cloned models in the
# warehouse. `dbt retry` re-executes whatever the previous failed
# invocation was — if that was `dbt run`, retry re-runs it, so the
# deny semantics must inherit at the retry call.
DBT_DENIED_SUBCOMMANDS: frozenset[str] = frozenset(
    {"run", "test", "parse", "compile", "docs", "seed", "snapshot",
     "build", "freshness", "run-operation", "debug", "source",
     "clone", "retry"}
)

SHELL_WRAPPERS: frozenset[str] = frozenset(
    {"sh", "bash", "zsh", "dash", "ash", "ksh"}
)

# `eval` is a shell builtin that concatenates its args and
# re-evaluates them as a command. Same threat surface as `sh -c` but
# with no `-c` flag — the inner command is just the joined positional
# args. Handled as a special case alongside SHELL_WRAPPERS.

# Exec wrappers that run their argument as a new process. If the
# wrapped command is a denied binary, the hook would otherwise see
# only the wrapper and let the call through. We recurse into the
# wrapped command for each.
#
# `find` is handled separately because its wrapped command lives
# after a `-exec` / `-execdir` keyword, not at a fixed position.
EXEC_WRAPPERS: frozenset[str] = frozenset(
    {"xargs", "time", "nice", "nohup", "setsid", "parallel",
     "exec", "timeout", "watch", "ionice", "chrt", "stdbuf"}
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
    # Negative lookbehind on `\\` keeps escaped separators (e.g. the
    # `\;` that terminates `find -exec`) attached to the same segment;
    # shlex strips the backslash later.
    for part in re.split(r"(?<!\\)[;&|()\n]+", cmd):
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
    """True if any token after `dbt` is a banned subcommand.

    Earlier versions tried to find the "first positional" by skipping
    leading flags. That broke on `dbt --target dev parse` — `dev` (the
    value of `--target`) became the first positional and `parse` was
    never inspected. Scanning every token after `dbt` instead is both
    simpler and more robust: a false positive requires the agent to
    pass a literal banned-subcommand name as a flag value (e.g.
    `--target parse`), which is perverse and would deserve denial
    anyway since the agent shouldn't be invoking dbt at Tier 1.
    """
    return any(tok in DBT_DENIED_SUBCOMMANDS for tok in tokens[1:])


def find_wrapped_command_after_exec(tokens: list[str]) -> list[str]:
    """For `find` with `-exec` / `-execdir`, return the wrapped command
    tokens. Returns [] when `find` has no `-exec` — plain `find` is
    safe and doesn't need recursion.
    """
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
    # construct that survived shlex) is treated as non-executable so
    # we don't spuriously deny.
    stripped = name.replace("-", "").replace("_", "").replace(".", "")
    return stripped.isalnum()


def find_wrapped_command(wrapper_name: str, tokens: list[str]) -> list[str]:
    """For an exec wrapper at tokens[0], return the wrapped command's
    tokens.

    Different wrappers interleave their own positional args before the
    wrapped command (e.g., `timeout 30 CMD`, `chrt 0 5 CMD`,
    `ionice -c 2 CMD`). Hard-coding a per-wrapper arg parser is
    brittle. Instead, walk the args and return tokens starting at the
    first executable-shaped token — that's the wrapped command in
    practice. `find` is special because the wrapped command lives
    after a `-exec` / `-execdir` keyword.
    """
    if wrapper_name == "find":
        return find_wrapped_command_after_exec(tokens)
    for i, tok in enumerate(tokens[1:], 1):
        if tok.startswith("-"):
            continue
        if not looks_like_executable(basename(tok)):
            continue
        return tokens[i:]
    return []


def check_tokens(tokens: list[str], command_str: str, depth: int = 0) -> None:
    """Inspect a token list. Recurses one level for shell wrappers and
    exec wrappers. `depth` guards against pathological deep recursion.
    """
    if depth > 4:
        return
    tokens = skip_leading_env(tokens)
    if not tokens:
        return
    name = basename(tokens[0])

    # Shell wrapper with -c — recurse into its argument.
    if name in SHELL_WRAPPERS:
        for j in range(1, len(tokens) - 1):
            if tokens[j] in ("-c", "-lc", "-ic"):
                inner = tokens[j + 1]
                for inner_segment in split_segments(inner):
                    check_tokens(tokenize(inner_segment), command_str, depth + 1)
                return
        # A bare `sh` / `bash` interactive subshell with no -c arg is
        # not a denied command on its own.
        return

    # `eval ARGS...` concatenates its positional args and re-evaluates
    # them as a new command. Same threat surface as `sh -c` but with
    # the inner command spread across positional args instead of a
    # single `-c` value.
    if name == "eval":
        inner = " ".join(tokens[1:])
        for inner_segment in split_segments(inner):
            check_tokens(tokenize(inner_segment), command_str, depth + 1)
        return

    # Exec wrapper (xargs / time / nohup / find -exec / ...).
    if name in EXEC_WRAPPERS or name == "find":
        wrapped = find_wrapped_command(name, tokens)
        if wrapped:
            check_tokens(wrapped, command_str, depth + 1)
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


def check_substitution_at_head(cmd: str) -> None:
    """Detect `$()` / backtick substitutions at command-head position
    that smuggle a denied binary.

    `$(echo dbt) run` evaluates to `dbt run` at bash runtime — the
    substitution provides the head binary, which the regular
    check_tokens path can't see because the substitution's content
    has already been stripped from the outer segment. This pass walks
    the original command and looks for substitutions at the head of
    each segment.

    The check is conservative — false positives only occur if the
    agent legitimately has a denied-binary basename appear in a
    substitution at command-head, which is the threat we're guarding
    against and has no benign use at Tier 1.
    """
    # Segment on true command separators only — don't split on `(`/`)`
    # because that would shred `$(...)` into pieces (we want it intact
    # to detect it as a head substitution). `split_segments` upstream
    # uses parens too because it has already extracted `$()` before
    # splitting; this pass works on the raw command.
    for raw_seg in re.split(r"(?<!\\)[;&|\n]+", cmd):
        seg = raw_seg.strip()
        if not seg:
            continue
        m = re.match(r"^(\$\(([^()]*)\)|`([^`]*)`)", seg)
        if not m:
            continue
        payload = (m.group(2) or m.group(3) or "").strip()
        outer_rest = seg[m.end():].strip()
        try:
            payload_tokens = shlex.split(payload) if payload else []
        except ValueError:
            payload_tokens = [payload]
        try:
            outer_tokens = shlex.split(outer_rest) if outer_rest else []
        except ValueError:
            outer_tokens = [outer_rest]
        for i, tok in enumerate(payload_tokens):
            sub_name = basename(tok)
            if sub_name == "dbt":
                combined = payload_tokens[i + 1:] + outer_tokens
                if any(t in DBT_DENIED_SUBCOMMANDS for t in combined):
                    deny(
                        "dbt smuggled via substitution at command-head "
                        f"with denied subcommand (matched in: {cmd!r})"
                    )
            elif sub_name in DENIED_BINS:
                deny(
                    f"denied binary '{sub_name}' smuggled via "
                    f"substitution at command-head "
                    f"(matched in: {cmd!r})"
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

    # Pre-check for `$()` / backtick substitutions at command-head
    # position that smuggle a denied binary (e.g., `$(echo dbt) run`).
    # split_segments extracts the substitution's content as its own
    # segment, so the outer post-substitution segment loses the head
    # binary — check_tokens alone can't see it. This pre-check fills
    # that gap.
    check_substitution_at_head(command)

    for segment in split_segments(command):
        check_tokens(tokenize(segment), command)


if __name__ == "__main__":
    main()
