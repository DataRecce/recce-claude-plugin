"""
AC-1 + AC-2 + AC-3 integration tests for the /recce-analyze merged command.

These tests validate the command file structure and key behavioral properties:
  - AC-1: test_recce_analyze_output_sections — command file requires all four output headers
  - AC-2: test_recce_analyze_timing_fast_path — timing guard (structure-level assertion;
           full timing CI test deferred to cascade-005 E2E suite)
  - AC-3: test_stale_base_warning_in_output — staleness warning instruction present in command

Note on test_recce_analyze_timing_fast_path:
  The design specifies a pytest-timeout=130 decorator for a live-execution test.
  The full end-to-end timing test requires a real dbt project, running MCP server,
  and live warehouse credentials — deferred to cascade-005 (E2E suite). This file
  provides a structure-level proxy: assert the command file mentions the 120 s threshold
  and contains the fast-path (reuse) branch, confirming the command would take the
  fast path when artifacts are pre-populated.

Parity tests (added in response to PR #26 review):
  - test_stale_warning_parity_claude_codex — full warning sentence appears in both files
  - test_mcp_tool_names_parity — `mcp__recce__*` prefix used consistently in both files
  - test_safe_stash_dance_in_both_paths — named-stash pattern present in both files
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent

COMMAND_FILE = (
    REPO_ROOT
    / "plugins"
    / "recce-quickstart"
    / "commands"
    / "recce-analyze.md"
)

AGENTS_FILE = REPO_ROOT / "AGENTS.md"

REQUIRED_SECTIONS = [
    "## Impact Summary",
    "## Lineage Changes",
    "## Schema Changes",
    "## Row Count Changes",
]

# The full canonical staleness warning sentence (AC-3). Both /recce-analyze
# and the AGENTS.md Codex orchestration MUST emit this verbatim, so the
# parity test diffs the exact substring rather than a loose token.
STALE_WARNING_SENTENCE = (
    "⚠️ Base artifacts are stale. Refreshing with dbt docs generate…"
)

# The four MCP tools that Step 6 must invoke. Both files use the
# `mcp__recce__` namespace because that is the actual tool name exposed
# by the Recce MCP server through Claude Code / Codex MCP integration.
MCP_TOOLS = [
    "mcp__recce__impact_analysis",
    "mcp__recce__lineage_diff",
    "mcp__recce__schema_diff",
    "mcp__recce__row_count_diff",
]


def _command_text() -> str:
    return COMMAND_FILE.read_text()


def _agents_text() -> str:
    return AGENTS_FILE.read_text()


def test_recce_analyze_command_file_exists():
    """recce-analyze.md must exist at the expected path (M1, R7 name confirmed)."""
    assert COMMAND_FILE.exists(), f"Command file not found: {COMMAND_FILE}"


def test_recce_analyze_output_sections():
    """
    AC-1: Command file must instruct the agent to render all four required
    section headers in the output markdown.
    """
    text = _command_text()
    missing = [s for s in REQUIRED_SECTIONS if s not in text]
    assert not missing, (
        f"recce-analyze.md is missing required output section(s): {missing}"
    )


def test_recce_analyze_timing_fast_path():
    """
    AC-2 (structure proxy): Command file must reference the 120 s timing
    guard and include the 'reuse' (fast path) branch so pre-populated
    artifacts skip artifact generation.

    The 120 s reference is anchored — the previous loose `"120" in text`
    assertion would pass on incidental occurrences like "120 lines of
    code" in narrative prose. This anchored regex requires the threshold
    to appear next to a `s` (seconds) marker.
    """
    text = _command_text()
    assert re.search(r"\b120\s*s\b", text), (
        "recce-analyze.md must reference the 120 s timing threshold (AC-2). "
        "Look for an anchored '120 s' (with optional whitespace), not just "
        "the bare token '120'."
    )
    assert "`reuse`" in text or "'reuse'" in text or '"reuse"' in text or (
        "reuse" in text and "fast path" in text.lower()
    ), (
        "recce-analyze.md must contain the 'reuse' fast-path branch (AC-2)"
    )


def test_stale_base_warning_in_output():
    """
    AC-3: Command file must instruct the agent to emit the canonical
    staleness warning sentence when recce check-base returns
    docs_generate. Tightened from the loose `"stale" in text.lower()`
    proxy (which passed on the word "stalemate") to an exact substring
    match on the full warning sentence.
    """
    text = _command_text()
    assert STALE_WARNING_SENTENCE in text, (
        "recce-analyze.md must contain the verbatim staleness warning "
        f"sentence (AC-3): {STALE_WARNING_SENTENCE!r}"
    )
    assert "recce check-base" in text, (
        "recce-analyze.md must invoke recce check-base (M2 integration)"
    )


def test_recce_analyze_frontmatter():
    """Command file must have correct YAML frontmatter with approved name."""
    text = _command_text()
    assert "name: recce-analyze" in text, (
        "recce-analyze.md must have 'name: recce-analyze' in frontmatter (R7)"
    )


def test_four_mcp_tools_referenced():
    """AC-1: Command must reference all four MCP analysis tools."""
    text = _command_text()
    missing = [t for t in MCP_TOOLS if t not in text]
    assert not missing, (
        f"recce-analyze.md must reference MCP tools: {missing}"
    )


# ---------------------------------------------------------------------------
# Parity tests — added in response to PR #26 review.
# AGENTS.md (Codex orchestration) drifted from recce-analyze.md (Claude Code
# orchestration) on warning text, plugin-root variable, and MCP tool names.
# These tests catch that drift in CI.
# ---------------------------------------------------------------------------


def test_stale_warning_parity_claude_codex():
    """
    The verbatim staleness warning sentence must appear in BOTH
    recce-analyze.md and AGENTS.md, so the Claude Code and Codex paths
    surface identical text to the user.
    """
    cmd = _command_text()
    agents = _agents_text()
    assert STALE_WARNING_SENTENCE in cmd, (
        "recce-analyze.md is missing the canonical staleness warning"
    )
    assert STALE_WARNING_SENTENCE in agents, (
        "AGENTS.md is missing the canonical staleness warning — drift "
        "from recce-analyze.md will surface different text to Codex users"
    )


def test_mcp_tool_names_parity():
    """
    AGENTS.md must reference all four MCP tools using the same
    `mcp__recce__*` namespace as recce-analyze.md. Bare names (e.g.
    `impact_analysis` without prefix) drift from the Claude Code path.
    """
    agents = _agents_text()
    missing = [t for t in MCP_TOOLS if t not in agents]
    assert not missing, (
        f"AGENTS.md must reference MCP tools with the canonical prefix: {missing}"
    )


def test_no_codex_plugin_root_in_agents_md():
    """
    AGENTS.md must NOT reference `${CODEX_PLUGIN_ROOT}` — it is not a real
    environment variable. Use `${CLAUDE_PLUGIN_ROOT}` (the actual var
    exported by Claude Code) and instruct Codex users to substitute the
    literal path.
    """
    agents = _agents_text()
    assert "${CODEX_PLUGIN_ROOT}" not in agents, (
        "AGENTS.md references ${CODEX_PLUGIN_ROOT}, which is not a real env var. "
        "Use ${CLAUDE_PLUGIN_ROOT} or a literal path."
    )


def test_safe_stash_dance_in_both_paths():
    """
    Both recce-analyze.md and AGENTS.md must use the safe stash dance
    (named stash + trap), not the unsafe `git stash; checkout; ...; pop`
    sequence. Detected by presence of the named-stash marker plus a trap.
    """
    for label, text in [("recce-analyze.md", _command_text()), ("AGENTS.md", _agents_text())]:
        assert "git stash push --include-untracked -m" in text, (
            f"{label} still uses the unsafe stash dance — must call "
            "`git stash push --include-untracked -m <named-stash>` to capture a stable id."
        )
        assert "trap" in text, (
            f"{label} stash dance must wrap with `trap` so the user is "
            "always returned to the target branch on failure."
        )


def test_agents_md_has_prereq_and_branch_detection():
    """
    PR #26 BLOCKER 2: AGENTS.md must include explicit prereq + branch
    detection steps so the trigger-phrase entry point doesn't jump
    straight into `recce check-base` on a fresh project.
    """
    agents = _agents_text()
    assert "Step 1 — Prerequisites" in agents, (
        "AGENTS.md must define a prereq step (dbt/recce/dbt_project.yml checks)"
    )
    assert "Step 2 — Branch detection" in agents, (
        "AGENTS.md must define a branch detection step before running recce check-base"
    )


def test_agents_md_has_error_recovery_section():
    """
    AGENTS.md must include an Error Recovery section to match
    recce-analyze.md and give Codex users a recovery path for stash
    or MCP-server failures.
    """
    agents = _agents_text()
    assert "Error Recovery" in agents, (
        "AGENTS.md is missing an Error Recovery section (parity with recce-analyze.md)"
    )


# ---------------------------------------------------------------------------
# Round-2 review tests — added in response to PR #26 round-2 review
# (issuecomment-4386104070). The first asserts the trap-scope defect cannot
# silently regress; the next two close the test-coverage gaps the reviewer
# flagged as NOTEs.
# ---------------------------------------------------------------------------


def _exec_lines(body: str) -> str:
    """Drop blank lines and comment-only lines so substring assertions
    cannot pass on documentation comments alone.

    Round-3 review found the round-2 test passed on `AGENTS.md` even when
    the only dbt references inside the trap fence were `# docs_generate:
    dbt docs generate ...` comments — comments that an agent running the
    block verbatim would never execute. Filtering to executable lines
    forces the substring check to find a real command (or the explicit
    `<chosen build command>` placeholder), not just a `#`-prefixed hint.
    """
    return "\n".join(
        line
        for line in body.splitlines()
        if line.strip() and not line.strip().startswith("#")
    )


def test_build_inside_trap_scope():
    """
    Round-2 ISSUE 1: the dbt build command MUST appear inside the same
    fenced bash block as ``trap cleanup EXIT`` — and as an EXECUTABLE
    line, not as a comment that an agent might never substitute.

    Each fenced bash block is an isolated subprocess (per
    ``recce-setup.md:212-213``). When the block ends, the trap fires and
    returns the user to the target branch *before* any build command in a
    later, separate shell can run on the base branch. A build outside the
    fence therefore writes target-branch SQL into ``target-base/`` and the
    MCP diff tools return empty diffs (silent wrong-answer). This test
    fails on that exact structural defect.

    Round-3 review tightened the scan: ``_exec_lines`` strips comments and
    blanks before the substring check so the AGENTS.md
    "comments-inside-fence-with-no-executable-line" variant of the
    round-2 ISSUE 1 cannot regress past the test (the round-2 version
    passed against that variant because ``# dbt docs generate …`` matched
    the substring).
    """
    for label, text in [
        ("recce-analyze.md", _command_text()),
        ("AGENTS.md", _agents_text()),
    ]:
        found_trap_fence = False
        for block in re.finditer(r"```bash\s*(.*?)```", text, re.DOTALL):
            body = block.group(1)
            if "trap cleanup EXIT" not in body:
                continue
            found_trap_fence = True
            exec_text = _exec_lines(body)
            assert (
                "dbt docs generate" in exec_text
                or "dbt build" in exec_text
                or "<chosen build command>" in exec_text
            ), (
                f"{label}: trap-protected fence must contain an "
                "EXECUTABLE dbt command or the `<chosen build command>` "
                "placeholder. Comments documenting which command to run "
                "do not satisfy — Codex/Claude running the block "
                "verbatim would no-op."
            )
            break
        assert found_trap_fence, (
            f"{label}: no fenced bash block containing `trap cleanup EXIT` "
            "found — the safe stash dance must be wrapped in a trap."
        )


def test_build_inside_trap_scope_catches_pre_fix_agents_variant():
    """
    Empirical proof that the tightened ``test_build_inside_trap_scope``
    catches the pre-fix AGENTS.md variant of round-2 ISSUE 1.

    Constructs the exact fence body that lived in AGENTS.md before the
    round-2 fix — comment-only dbt references, no executable build line —
    and asserts the executable-line filter rejects it. Round-3 review
    flagged that the round-2 test passed against this body because the
    raw substring check matched ``# docs_generate: dbt docs generate
    --target-path target-base``. With ``_exec_lines`` filtering the
    comments out, only ``git stash push …`` and ``git checkout
    <base-branch>`` survive — neither contains a dbt command nor the
    placeholder, so the assertion is expected to fail.
    """
    pre_fix_agents_fence_body = """
set -e
STASH_MSG="recce-analyze-$(date +%s)"
TARGET_BRANCH="$(git branch --show-current)"

cleanup() {
  git checkout "$TARGET_BRANCH" >/dev/null 2>&1 || true
  STASH_REF="$(git stash list | grep -F "$STASH_MSG" | head -n1 | cut -d: -f1)"
  if [ -n "$STASH_REF" ]; then
    git stash pop "$STASH_REF" || \
      echo "⚠️  Stash $STASH_REF could not be popped cleanly. Run: git stash list"
  fi
}
trap cleanup EXIT

git stash push --include-untracked -m "$STASH_MSG" || true
git checkout <base-branch>
# docs_generate:  dbt docs generate --target-path target-base
# full_build:     dbt build         --target-path target-base
"""
    exec_text = _exec_lines(pre_fix_agents_fence_body)
    assert "dbt docs generate" not in exec_text
    assert "dbt build" not in exec_text
    assert "<chosen build command>" not in exec_text
    # Sanity: the surviving lines should be the executable ones only.
    assert "git stash push --include-untracked" in exec_text
    assert "git checkout <base-branch>" in exec_text


def test_timing_threshold_parity_claude_codex():
    """
    Round-2 NOTE 1: the 120 s timing threshold (AC-2) is referenced in
    both files, but no test pinned them together — a future edit could
    drift one to e.g. 180 s and CI would not notice. Anchored regex
    requires "120 s" (with optional whitespace) so incidental "120 lines"
    in prose does not satisfy the assertion.
    """
    for label, text in [
        ("recce-analyze.md", _command_text()),
        ("AGENTS.md", _agents_text()),
    ]:
        assert re.search(r"\b120\s*s\b", text), (
            f"{label}: missing the canonical 120 s timing threshold "
            "(AC-2). Drift from the parity file will surface different "
            "fast-path semantics to Claude vs Codex users."
        )


def test_confirmation_gate_parity_claude_codex():
    """
    Round-2 NOTE 2: the Y/N confirmation gate is the central safety stop
    that the trigger-phrase entry point relies on. Without a parity test,
    a future refactor could remove it from one file and CI would not
    notice. Both files must mention "Confirmation gate" in their
    instructions.
    """
    for label, text in [
        ("recce-analyze.md", _command_text()),
        ("AGENTS.md", _agents_text()),
    ]:
        assert "Confirmation gate" in text, (
            f"{label}: missing the 'Confirmation gate' safety stop. "
            "The trigger-phrase entry point relies on this gate to "
            "prevent unattended `git checkout` / `dbt build` runs."
        )
