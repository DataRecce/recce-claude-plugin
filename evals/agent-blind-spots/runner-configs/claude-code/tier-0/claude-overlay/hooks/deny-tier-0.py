#!/usr/bin/env python3
"""
Tier-0 PreToolUse hook for the /recce-verify v1 eval (v5 — bashlex).

Tier 0 is a positive allowlist for Bash plus Recce MCP / Recce skill
denial. Anything outside the allowlist exits 2.

Architecture: see deny-tier-1.py (same bashlex-based AST walk shape).
Tier-0-specific differences:
  * Bash head must be in TIER_0_ALLOWLIST (positive policy) instead
    of "not in DENIED_BINS".
  * Shell wrappers are banned outright (no `-c` recursion); a Tier-0
    agent has no legitimate reason to spawn a subshell.
  * `eval` is banned outright as a shell builtin.
  * `xargs` and `find` ARE in the allowlist but recurse-check their
    wrapped command against the allowlist.
  * MCP-Recce namespaces and Recce-* skills are denied at the tool
    level before we ever look at the command.

Fail-closed behavior: missing bashlex → exit 2.
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
        "Tier-0 sandbox blocks: bashlex not installed. "
        "Install with `python3 -m pip install bashlex` in the eval-runner "
        "environment, then retry. Failing closed so bypasses can't slip "
        "through silently.",
        file=sys.stderr,
    )
    sys.exit(2)


# --- Policy ----------------------------------------------------------------

# Bash commands the Tier-0 agent legitimately needs. Anything else is
# denied. Per RUBRIC.md Tier-0 runtime contract: file read, grep /
# ripgrep, jq, git log/diff/show. Augmented with standard POSIX
# text-processing utilities.
TIER_0_ALLOWLIST: frozenset[str] = frozenset({
    "git", "grep", "rg", "jq", "ls", "cat", "head", "tail", "wc", "find",
    "echo", "true", "false", "awk", "sed", "sort", "uniq", "comm", "diff",
    "basename", "dirname", "readlink", "pwd", "file", "stat", "test", "[",
    "printf", "tr", "cut", "xargs", "tee", "less", "more",
})

# Shell wrappers and `eval` are banned outright at Tier 0.
SHELL_WRAPPERS: frozenset[str] = frozenset(
    {"sh", "bash", "zsh", "dash", "ash", "ksh", "eval"}
)

# Exec wrappers in the allowlist (`xargs`, `find`) need recursion
# checks; non-allowlisted wrappers (`time`, `nohup`, etc.) are denied
# by the head check anyway. Listed defensively in case the allowlist
# grows later.
EXEC_WRAPPERS: frozenset[str] = frozenset(
    {"xargs", "time", "nice", "nohup", "setsid", "parallel",
     "exec", "timeout", "watch", "ionice", "chrt", "stdbuf"}
)

TRANSPARENT_PREFIXES: frozenset[str] = frozenset({"command", "builtin"})

# Recce MCP namespaces. Covers mcp__recce__*, mcp__plugin_recce_*,
# mcp__recce_dev__*, and any future Recce-shaped namespace.
MCP_RECCE_RE = re.compile(r"^mcp__(plugin_)?recce(_|-|$)", re.IGNORECASE)

# Recce skill prefix — `recce-verify`, `recce:recce-review`, etc.
RECCE_SKILL_RE = re.compile(r"^recce[-:]", re.IGNORECASE)

# Overlay-leak guard. The Tier-0 enforcement overlay itself names Recce
# (settings.json deny rules, deny-tier-0.py vocabulary). `cat` is in
# the allowlist, so a bare `cat .claude/settings.json` would otherwise
# turn the enforcement file into a Recce-shaped spoiler. Block any Bash
# command argument that references `.claude/` or the `.claude`
# directory itself. The Read/Glob/Grep tool paths are blocked
# separately via permissions.deny in settings.json (deny rules apply
# even with --dangerously-skip-permissions).
_CLAUDE_DIR_RE = re.compile(r"(?:^|[/=])\.claude(?:/|$)")


# --- Output ---------------------------------------------------------------

def deny(reason: str) -> None:
    print(f"Tier-0 sandbox blocks: {reason}", file=sys.stderr)
    sys.exit(2)


# --- Word resolution ------------------------------------------------------

_ANSI_C_RE = re.compile(r"^\$'(.*)'$", re.DOTALL)
_BRACE_LITERAL_RE = re.compile(r"^([^{},\s]*)\{([^{}]+)\}([^{}]*)$")

# Parameters that at runtime resolve to a shell name. We can't predict
# which shell, so treat them as if they were a shell wrapper.
_SHELL_NAME_PARAMS: frozenset[str] = frozenset(
    {"0", "BASH", "SHELL", "BASH_SOURCE"}
)


def _decode_ansi_c(inner: str) -> str:
    try:
        import codecs
        return codecs.decode(inner, 'unicode_escape')
    except (UnicodeDecodeError, ValueError):
        return re.sub(r"\\(.)", r"\1", inner)


def _expand_brace_literal(text: str) -> list[str] | None:
    m = _BRACE_LITERAL_RE.match(text)
    if not m:
        return None
    prefix, inner, suffix = m.group(1), m.group(2), m.group(3)
    parts = [p.strip() for p in inner.split(",")]
    if len(parts) < 2:
        return None
    return [f"{prefix}{p}{suffix}" for p in parts]


def resolve_word(word_node, original_cmd: str) -> list[str]:
    """Return possible string values this word could resolve to.
    See deny-tier-1.py for the rules."""
    pos = getattr(word_node, 'pos', None)
    text = getattr(word_node, 'word', '') or ''

    if pos and len(pos) == 2 and pos[1] > pos[0]:
        raw = original_cmd[pos[0]:pos[1]]
        m = _ANSI_C_RE.match(raw)
        if m:
            return [_decode_ansi_c(m.group(1))]

    parts = getattr(word_node, 'parts', []) or []
    if not parts:
        expanded = _expand_brace_literal(text)
        if expanded is not None:
            return expanded
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
            elif value in _SHELL_NAME_PARAMS:
                candidates.append("sh")
        elif kind == 'commandsubstitution':
            sub_cmd = getattr(part, 'command', None)
            if sub_cmd is not None:
                for sub_word in _walk_command_words(sub_cmd):
                    candidates.extend(resolve_word(sub_word, original_cmd))
        elif kind == 'processsubstitution':
            sub_cmd = getattr(part, 'command', None)
            if sub_cmd is not None:
                for sub_word in _walk_command_words(sub_cmd):
                    candidates.extend(resolve_word(sub_word, original_cmd))

    if not candidates:
        expanded = _expand_brace_literal(text)
        if expanded is not None:
            return expanded
        return [text]
    return candidates


def _walk_command_words(cmd_node) -> Iterable[object]:
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
    for part in getattr(word_node, 'parts', []) or []:
        kind = getattr(part, 'kind', '')
        if kind in ('commandsubstitution', 'processsubstitution'):
            sub_cmd = getattr(part, 'command', None)
            if sub_cmd is not None:
                walk(sub_cmd, original_cmd, depth + 1)


def _looks_like_executable(name: str) -> bool:
    if not name:
        return False
    if name in ("{}", "[]", ";", "+", "\\;", "[[", "]]", ";;", "&&", "||"):
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
        # CompoundNode uses `.list`, other containers use `.parts`.
        children = (getattr(node, 'list', None)
                    or getattr(node, 'parts', None) or [])
        for child in children:
            if hasattr(child, 'kind'):
                walk(child, original_cmd, depth + 1)
        return

    if kind != 'command':
        return

    words = [p for p in (node.parts or []) if getattr(p, 'kind', '') == 'word']
    if not words:
        return

    # Pass 0: overlay-leak guard. Any word argument that references
    # `.claude/` (the directory holding the Tier-0 enforcement overlay
    # itself) is denied at Tier 0 — its contents name Recce vocabulary
    # and reading it would defeat the "agent cannot reach Recce-shaped
    # signals" contract. Read/Glob/Grep tool kinds are blocked
    # separately by permissions.deny in settings.json.
    #
    # This intentionally catches the non-adversarial shape — a normal
    # agent inspecting cwd via `cat .claude/...`, `ls .claude/`,
    # `cat < .claude/...`, `find .claude`, etc. The interpreter-shell-out
    # bypass class (awk/python -c "...cat .claude/...") is out of scope
    # per ENFORCEMENT.md § "Threat model — non-adversarial code agent".
    for w in words:
        for cand in resolve_word(w, original_cmd):
            if cand and _CLAUDE_DIR_RE.search(cand):
                deny(
                    f"argument '{cand}' references the Tier-0 enforcement "
                    f"overlay at .claude/, which names Recce vocabulary "
                    f"(matched in: {original_cmd!r})"
                )

    # Redirect targets (`cat < .claude/settings.json`,
    # `grep recce < .claude/...`) bypass the words pass because
    # `<file` is parsed as a redirect node, not a positional word.
    for p in (node.parts or []):
        if getattr(p, 'kind', '') != 'redirect':
            continue
        out = getattr(p, 'output', None)
        if out is None or getattr(out, 'kind', '') != 'word':
            continue
        for cand in resolve_word(out, original_cmd):
            if cand and _CLAUDE_DIR_RE.search(cand):
                deny(
                    f"redirect target '{cand}' references the Tier-0 "
                    f"enforcement overlay at .claude/, which names Recce "
                    f"vocabulary (matched in: {original_cmd!r})"
                )

    # Pass 1: walk INTO every substitution so the inner is independently
    # checked against Tier-0 allowlist.
    for w in words:
        _walk_substitutions(w, original_cmd, depth)

    # Pass 1b: redirect targets can be process substitutions
    # (`echo x 2> >(recce check)`); walk those too.
    for p in (node.parts or []):
        if getattr(p, 'kind', '') == 'redirect':
            out = getattr(p, 'output', None)
            if out is not None and getattr(out, 'kind', '') == 'word':
                _walk_substitutions(out, original_cmd, depth)

    # Pass 2: head check.
    idx = 0
    while idx < len(words):
        cands = resolve_word(words[idx], original_cmd)
        names = {basename(c) for c in cands}
        if names & TRANSPARENT_PREFIXES:
            idx += 1
            continue
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

    # Shell wrappers and `eval` banned outright at Tier 0.
    if head_names & SHELL_WRAPPERS:
        bad = next(iter(head_names & SHELL_WRAPPERS))
        deny(
            f"shell wrapper '{bad}' is banned at Tier 0 — the agent "
            f"has no legitimate reason to invoke a subshell "
            f"(matched in: {original_cmd!r})"
        )

    # Exec wrappers (`xargs`, `find`) ARE in the allowlist, but we
    # must recurse-check what they spawn so the allowlist isn't
    # bypassed via `xargs recce`.
    if head_names & EXEC_WRAPPERS or "find" in head_names:
        wrapped = _find_exec_target(head_names, arg_words)
        if wrapped:
            for w in wrapped:
                for cand in resolve_word(w, original_cmd):
                    name = basename(cand)
                    if not name or name.startswith("-"):
                        continue
                    if not _looks_like_executable(name):
                        continue
                    if name not in TIER_0_ALLOWLIST:
                        deny(
                            f"Bash executable '{name}' (wrapped by "
                            f"'{next(iter(head_names))}') not in "
                            f"Tier-0 allowlist (matched in: "
                            f"{original_cmd!r})"
                        )
                # First wrapped-position word checked; stop after first
                # candidate set so multi-arg commands like
                # `xargs grep foo` don't false-positive on 'foo'.
                break
            # Also re-parse to catch nested constructs.
            head_cands = resolve_word(wrapped[0], original_cmd)
            if head_cands:
                rest = " ".join((w.word or '') for w in wrapped[1:])
                synth = (head_cands[0] + " " + rest).strip()
                if synth:
                    _reparse_and_walk(synth, original_cmd, depth + 1)
        # If wrapper itself is in the allowlist, fall through to the
        # allowlist check (which allows). If not, the head-check
        # below denies.
        if head_names & TIER_0_ALLOWLIST:
            return

    # Head must be in the allowlist. When the head resolves to
    # multiple candidates (e.g., from a `$(echo dbt)` substitution),
    # ALL must be allowed — any one being out of allowlist is a
    # potential bypass at runtime because that candidate could be
    # the actual head bash exec's.
    out_of_allowlist = head_names - TIER_0_ALLOWLIST
    if out_of_allowlist:
        name = next(iter(out_of_allowlist))
        deny(
            f"Bash executable '{name}' not in Tier-0 allowlist "
            f"(matched in: {original_cmd!r})"
        )


def _find_exec_target(head_names: set[str], arg_words: list) -> list:
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
        if _looks_like_executable(basename(text)):
            return arg_words[i:]
        if getattr(w, 'parts', None):
            return arg_words[i:]
    return []


def _reparse_and_walk(inner: str, original_cmd: str, depth: int) -> None:
    if depth > 8 or not inner.strip():
        return
    try:
        trees = bashlex.parse(inner)
    except (bashlex.errors.ParsingError, NotImplementedError):
        for tok in inner.split():
            base = basename(tok)
            if base and not base.startswith("-") and _looks_like_executable(base):
                if base not in TIER_0_ALLOWLIST:
                    deny(
                        f"unparseable inner command head '{base}' not "
                        f"in Tier-0 allowlist (matched in: {original_cmd!r})"
                    )
                # Only inspect the first looks-like-executable token.
                return
        return
    for tree in trees:
        walk(tree, original_cmd, depth)


# --- Entry point ---------------------------------------------------------

def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return

    tool_name = payload.get("tool_name", "") or ""
    tool_input = payload.get("tool_input", {}) or {}

    # MCP-Recce check (any namespace shape).
    if MCP_RECCE_RE.match(tool_name):
        deny(f"Recce MCP tool '{tool_name}' (Tier-0 disallows Recce)")

    # Skill check (case-insensitive).
    skill = tool_input.get("skill", "") or ""
    if RECCE_SKILL_RE.match(skill):
        deny(f"Recce skill '{skill}' (Tier-0 disallows /recce-* skills)")

    if tool_name != "Bash":
        return

    cmd = tool_input.get("command", "") or ""
    if not cmd.strip():
        return

    try:
        trees = bashlex.parse(cmd)
    except NotImplementedError as e:
        msg = str(e).lower()
        if 'coproc' in msg:
            deny(
                f"`coproc` keyword is not allowed at Tier 0 "
                f"(matched in: {cmd!r})"
            )
        # Other unsupported constructs (arithmetic expansion, select,
        # etc.) fall open — they're legitimate Bash idioms; the rest
        # of the sandbox catches denied binaries.
        return
    except bashlex.errors.ParsingError:
        return

    for tree in trees:
        walk(tree, cmd, 0)


if __name__ == "__main__":
    main()
