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
"""

from pathlib import Path

COMMAND_FILE = (
    Path(__file__).parent.parent
    / "plugins"
    / "recce-quickstart"
    / "commands"
    / "recce-analyze.md"
)

REQUIRED_SECTIONS = [
    "## Impact Summary",
    "## Lineage Changes",
    "## Schema Changes",
    "## Row Count Changes",
]


def _command_text() -> str:
    return COMMAND_FILE.read_text()


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
    AC-2 (structure proxy): Command file must reference the 120 s timing guard
    and include the 'reuse' (fast path) branch so pre-populated artifacts skip
    artifact generation.

    Full live-execution timing test (pytest-timeout=130) deferred to cascade-005.
    """
    text = _command_text()
    assert "120" in text, (
        "recce-analyze.md must reference the 120 s timing threshold (AC-2)"
    )
    assert "reuse" in text, (
        "recce-analyze.md must contain the 'reuse' fast-path branch (AC-2)"
    )


def test_stale_base_warning_in_output():
    """
    AC-3: Command file must instruct the agent to emit a staleness warning when
    recce check-base returns docs_generate recommendation.
    """
    text = _command_text()
    # Command should reference the staleness warning step
    assert "stale" in text.lower(), (
        "recce-analyze.md must mention staleness warning (AC-3)"
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
    tools = [
        "impact_analysis",
        "lineage_diff",
        "schema_diff",
        "row_count_diff",
    ]
    missing = [t for t in tools if t not in text]
    assert not missing, (
        f"recce-analyze.md must reference MCP tools: {missing}"
    )
