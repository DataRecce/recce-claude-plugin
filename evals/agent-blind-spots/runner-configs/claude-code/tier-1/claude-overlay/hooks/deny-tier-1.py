#!/usr/bin/env python3
"""
Tier-1 PreToolUse hook for the /recce-verify v1 eval (v5 — bashlex).

Tier 1 = Tier 0 plus Recce CLI, Recce MCP, single-env warehouse
credentials. Recce MCP is intentionally not gated here.

Architecture:
  Parse the command with `bashlex` into an AST. Walk every node.
  Substitutions, ANSI-C quoting, parameter defaults, Bash keywords
  and command modifiers are handled by their AST shape, not by
  regex/shlex heuristics.

Two passes per command:
  1. WALK INTO every command substitution as if it were its own
     top-level command. This catches `$(sh -c "dbt run")` because
     the inner `sh -c "dbt run"` is itself denied.
  2. RESOLVE the head word of each command to its candidate output
     strings (literal text, ANSI-C decoded, parameter defaults,
     substitution payload words). If any candidate is a denied
     binary OR `dbt` with a denied subcommand visible anywhere in
     the args (including substitution payloads), deny.

Threat model:
  Adversarial agent reaches a denied binary via any Bash construct.
  Static AST walk catches each construct shape; cwd separation
  handles spoiler reads; recipe ensures no base/prod creds in env.

Fail-closed behavior:
  - Missing bashlex → exit 2 with install instructions.
  - `coproc` keyword (bashlex doesn't support it) → exit 2.
  - Other NotImplementedError from bashlex → exit 2.
  - Generic bash ParsingError → fail open (a quoting bug in a
    legitimate cell shouldn't brick the session).
"""
from __future__ import annotations

import json
import re
import sys
from os.path import basename
from typing import Iterable

try:
    import bashlex
    import bashlex.errors
except ImportError:
    print(
        "Tier-1 sandbox blocks: bashlex not installed. "
        "Install with `python3 -m pip install bashlex` in the eval-runner "
        "environment, then retry. Failing closed so bypasses can't slip "
        "through silently.",
        file=sys.stderr,
    )
    sys.exit(2)


# --- Policy ----------------------------------------------------------------

DENIED_BINS: frozenset[str] = frozenset(
    {"dbt", "duckdb", "psql", "snowsql", "bq"}
)

DBT_DENIED_SUBCOMMANDS: frozenset[str] = frozenset(
    {"run", "test", "parse", "compile", "docs", "seed", "snapshot",
     "build", "freshness", "run-operation", "debug", "source",
     "clone", "retry"}
)

SHELL_WRAPPERS: frozenset[str] = frozenset(
    {"sh", "bash", "zsh", "dash", "ash", "ksh"}
)

EXEC_WRAPPERS: frozenset[str] = frozenset(
    {"xargs", "time", "nice", "nohup", "setsid", "parallel",
     "exec", "timeout", "watch", "ionice", "chrt", "stdbuf"}
)

# `command`, `builtin` defeat alias/function shadowing — the actual
# binary is the next token. Walk past them transparently.
TRANSPARENT_PREFIXES: frozenset[str] = frozenset({"command", "builtin"})


# --- Output ---------------------------------------------------------------

def deny(reason: str) -> None:
    print(f"Tier-1 sandbox blocks: {reason}", file=sys.stderr)
    sys.exit(2)


# --- Word resolution ------------------------------------------------------

_ANSI_C_RE = re.compile(r"^\$'(.*)'$", re.DOTALL)


def _decode_ansi_c(inner: str) -> str:
    """Naive ANSI-C escape decode: drop backslashes that precede a
    char. `\\d\\b\\t` → `dbt`, which is the bypass we care about."""
    return re.sub(r"\\(.)", r"\1", inner)


def resolve_word(word_node, original_cmd: str) -> list[str]:
    """Return possible string values this word could resolve to.

    A bare `dbt` → ['dbt'].
    `$'dbt'` (ANSI-C) → ['dbt'] (detected via raw position because
    bashlex represents the construct as `$dbt` with a ParameterNode).
    `${a:-dbt}` → ['dbt'].
    `$(echo dbt)` → ['dbt', 'echo'] (each word inside the
    substitution is a candidate output; over-approximate but
    conservative for denial decisions).
    `` `cmd` `` → same as `$(cmd)`.
    """
    pos = getattr(word_node, 'pos', None)
    text = getattr(word_node, 'word', '') or ''

    # ANSI-C: check the raw source text because bashlex collapses
    # `$'dbt'` into word='$dbt' + ParameterNode.
    if pos and len(pos) == 2 and pos[1] > pos[0]:
        raw = original_cmd[pos[0]:pos[1]]
        m = _ANSI_C_RE.match(raw)
        if m:
            return [_decode_ansi_c(m.group(1))]

    parts = getattr(word_node, 'parts', []) or []
    if not parts:
        return [text]

    candidates: list[str] = []
    for part in parts:
        kind = getattr(part, 'kind', '')
        if kind == 'parameter':
            value = getattr(part, 'value', '') or ''
            if ':-' in value:
                candidates.append(value.split(':-', 1)[1])
            elif ':=' in value:
                candidates.append(value.split(':=', 1)[1])
            # Bare $VAR — unknown at static time. Don't speculate.
        elif kind == 'commandsubstitution':
            sub_cmd = getattr(part, 'command', None)
            if sub_cmd is not None:
                for sub_word in _walk_command_words(sub_cmd):
                    candidates.extend(resolve_word(sub_word, original_cmd))

    if not candidates:
        return [text]
    return candidates


def _walk_command_words(cmd_node) -> Iterable[object]:
    """Yield all WordNode descendants of a command/list/pipeline node."""
    kind = getattr(cmd_node, 'kind', '')
    if kind == 'word':
        yield cmd_node
        return
    for part in getattr(cmd_node, 'parts', []) or []:
        if not hasattr(part, 'kind'):
            continue
        if part.kind == 'word':
            yield part
        else:
            yield from _walk_command_words(part)


def _walk_substitutions(word_node, original_cmd: str, depth: int) -> None:
    """Walk INTO every command substitution found in this word as if
    it were a top-level command. Catches `$(sh -c "dbt run")` because
    the inner `sh -c "dbt run"` is itself denied.
    """
    for part in getattr(word_node, 'parts', []) or []:
        if getattr(part, 'kind', '') == 'commandsubstitution':
            sub_cmd = getattr(part, 'command', None)
            if sub_cmd is not None:
                walk(sub_cmd, original_cmd, depth + 1)


def _looks_like_executable(name: str) -> bool:
    if not name:
        return False
    if name in ("{}", "[]", ";", "+", "\\;"):
        return False
    if name.isdigit():
        return False
    stripped = name.replace("-", "").replace("_", "").replace(".", "")
    return stripped.isalnum()


# --- AST walk ------------------------------------------------------------

def walk(node, original_cmd: str, depth: int = 0) -> None:
    if depth > 8:
        return
    kind = getattr(node, 'kind', '')

    if kind in ('list', 'pipeline', 'compound', 'if', 'for', 'while',
                'until', 'function', 'case'):
        for child in getattr(node, 'parts', []) or []:
            if hasattr(child, 'kind'):
                walk(child, original_cmd, depth + 1)
        return

    if kind != 'command':
        return

    words = [p for p in (node.parts or []) if getattr(p, 'kind', '') == 'word']
    if not words:
        return

    # Pass 1: walk INTO every substitution in every word. Catches
    # bypasses where a substitution payload is itself a denied
    # command (e.g., `$(sh -c "dbt run")` — even though the outer
    # head is the substitution, the inner sh -c "dbt run" is a real
    # denied call that bash will execute).
    for w in words:
        _walk_substitutions(w, original_cmd, depth)

    # Pass 2: head + args check on the current command.
    idx = 0

    # Skip transparent prefixes (`command`, `builtin`).
    while idx < len(words):
        cands = resolve_word(words[idx], original_cmd)
        names = {basename(c) for c in cands}
        if names & TRANSPARENT_PREFIXES:
            idx += 1
            continue
        # `env [-i] [-u VAR] [VAR=val ...] CMD ...` — skip env args.
        if "env" in names and idx + 1 < len(words):
            idx += 1
            while idx < len(words):
                t = words[idx].word or ''
                if t in ("-i", "-0", "--null"):
                    idx += 1
                    continue
                if t in ("-u", "--unset"):
                    idx += 2
                    continue
                if "=" in t and not t.startswith("="):
                    idx += 1
                    continue
                break
            continue
        break

    if idx >= len(words):
        return

    head_word = words[idx]
    head_candidates = resolve_word(head_word, original_cmd)
    head_names = {basename(c) for c in head_candidates}
    arg_words = words[idx + 1:]

    # --- Shell wrappers (sh -c, bash -lc, ...) ---
    if head_names & SHELL_WRAPPERS:
        for j in range(len(arg_words) - 1):
            arg_text = arg_words[j].word or ''
            if arg_text in ("-c", "-lc", "-ic"):
                # Re-parse the LITERAL word text (with substitutions
                # intact) instead of its substitution candidates. The
                # candidates form `['echo', 'dbt']` for
                # `$(echo dbt) run` and lose the ` run` suffix; using
                # the literal `$(echo dbt) run` lets bashlex reparse
                # it as the inner CommandNode with $() head + `run`
                # arg, which the recursive walk catches.
                inner_literal = arg_words[j + 1].word or ''
                _reparse_and_walk(inner_literal, original_cmd, depth + 1)
                return
        return

    # --- eval ARGS... ---
    # Inputs can be literal words OR substitution outputs. For each
    # candidate "inner command", re-parse and walk. Substitution
    # payloads are also independently walked by Pass 1 above.
    if "eval" in head_names:
        # Literal-word form: `eval foo bar baz` → "foo bar baz".
        literal_parts: list[str] = []
        for arg in arg_words:
            if not (getattr(arg, 'parts', None) or []):
                literal_parts.append(arg.word or '')
        if literal_parts:
            _reparse_and_walk(" ".join(literal_parts), original_cmd, depth + 1)
        # Substitution-form: `eval $(echo "dbt parse")` — each
        # substitution candidate could be the eval'd command.
        for arg in arg_words:
            if getattr(arg, 'parts', None):
                for cand in resolve_word(arg, original_cmd):
                    _reparse_and_walk(cand, original_cmd, depth + 1)
        return

    # --- Exec wrappers (xargs / time / nohup / find -exec / ...) ---
    if head_names & EXEC_WRAPPERS or "find" in head_names:
        wrapped = _find_exec_target(head_names, arg_words)
        if wrapped:
            # CRITICAL: scan EVERY wrapped-command word's candidates
            # for a denied binary. Exec wrappers supply args from
            # stdin / find-output, so we can't trust a "bare dbt is
            # allowed" reasoning here — any dbt invocation under an
            # exec wrapper is suspect because the subcommand could
            # come from the wrapper's dynamic args.
            for w in wrapped:
                for cand in resolve_word(w, original_cmd):
                    name = basename(cand)
                    if name in DENIED_BINS:
                        deny(
                            f"denied binary '{name}' as exec-wrapped "
                            f"command (matched in: {original_cmd!r})"
                        )
            # Also re-parse to catch nested wrappers.
            head_cands = resolve_word(wrapped[0], original_cmd)
            if head_cands:
                rest = " ".join((w.word or '') for w in wrapped[1:])
                synth = (head_cands[0] + " " + rest).strip()
                if synth:
                    _reparse_and_walk(synth, original_cmd, depth + 1)
        return

    # --- dbt ---
    if "dbt" in head_names:
        if _dbt_args_have_denied(arg_words, original_cmd):
            deny(
                "dbt subcommand regenerates frozen artifacts or hits a "
                f"warehouse (matched in: {original_cmd!r})"
            )
        return

    # --- Direct denied bin (psql / duckdb / snowsql / bq) ---
    direct_denied = (head_names & DENIED_BINS) - {"dbt"}
    if direct_denied:
        name = next(iter(direct_denied))
        deny(
            f"Direct SQL client '{name}' — use Recce MCP query instead "
            f"(matched in: {original_cmd!r})"
        )


def _find_exec_target(head_names: set[str], arg_words: list) -> list:
    """Return the wrapped command's word list. For `find`, that's
    the tokens after `-exec`/`-execdir` up to `;` / `+`. For other
    wrappers, walk past flags and placeholders to the first
    executable-shaped word."""
    if "find" in head_names:
        for i, w in enumerate(arg_words):
            if (w.word or '') in ("-exec", "-execdir"):
                end = len(arg_words)
                for j in range(i + 1, len(arg_words)):
                    if (arg_words[j].word or '') in (";", "+", "\\;"):
                        end = j
                        break
                return arg_words[i + 1:end]
        return []
    for i, w in enumerate(arg_words):
        text = w.word or ''
        if text.startswith("-"):
            continue
        # Word might be a substitution — _looks_like_executable on
        # the raw text says False, but the substitution's payload
        # could include a real binary. Either way we return from
        # here and let the caller scan candidates.
        if _looks_like_executable(basename(text)):
            return arg_words[i:]
        # Special: if the word is a substitution (has parts), it
        # could resolve to a binary at runtime. Treat it as the
        # wrapped-target so DENIED_BINS scan can catch it.
        if getattr(w, 'parts', None):
            return arg_words[i:]
    return []


def _dbt_args_have_denied(arg_words: list, original_cmd: str) -> bool:
    """True if any resolved value of any arg (including substitution
    payloads, ANSI-C decoded, parameter defaults) is a banned
    dbt subcommand."""
    for arg in arg_words:
        for cand in resolve_word(arg, original_cmd):
            if cand in DBT_DENIED_SUBCOMMANDS:
                return True
    return False


def _reparse_and_walk(inner: str, original_cmd: str, depth: int) -> None:
    if depth > 8 or not inner.strip():
        return
    try:
        trees = bashlex.parse(inner)
    except (bashlex.errors.ParsingError, NotImplementedError):
        # Unparseable inner — fall back to literal token scan.
        for tok in inner.split():
            base = basename(tok)
            if base in DENIED_BINS or base in SHELL_WRAPPERS or base in EXEC_WRAPPERS:
                deny(
                    f"unparseable inner command contains denied "
                    f"basename '{base}' (matched in: {original_cmd!r})"
                )
        return
    for tree in trees:
        walk(tree, original_cmd, depth)


# --- Entry point ---------------------------------------------------------

def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return
    if payload.get("tool_name") != "Bash":
        return
    cmd = (payload.get("tool_input") or {}).get("command") or ""
    if not cmd.strip():
        return

    # `coproc` is a Bash keyword bashlex can't parse. A Tier-1 agent
    # has no legitimate reason for it; deny outright before the parser
    # raises NotImplementedError.
    if re.search(r"\bcoproc\b", cmd):
        deny(f"`coproc` keyword is not allowed at Tier 1 (matched in: {cmd!r})")

    try:
        trees = bashlex.parse(cmd)
    except NotImplementedError as e:
        deny(
            f"bash construct not supported by parser ({e}); "
            f"failing closed (matched in: {cmd!r})"
        )
    except bashlex.errors.ParsingError:
        return

    for tree in trees:
        walk(tree, cmd, 0)


if __name__ == "__main__":
    main()
