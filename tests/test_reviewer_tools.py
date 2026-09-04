"""The reviewer can call every MCP tool its own instructions name.

The `tools:` line in an agent's frontmatter is the whole allowlist. A tool the
body tells the agent to call and that line does not grant fails at run time,
inside an isolated context: the review comes back missing the evidence it was
told to gather, and nothing says why. The two lists are written by hand in one
file, so they drift silently. This is the check that they have not.
"""

import re
from pathlib import Path

REVIEWER = (
    Path(__file__).parent.parent
    / "plugins"
    / "recce-devloop"
    / "agents"
    / "recce-dev-reviewer.md"
)

FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n(.*)\Z", re.DOTALL)
TOOL_RE = re.compile(r"mcp__plugin_recce-devloop_recce__\w+")


def _split(text):
    match = FRONTMATTER_RE.match(text)
    assert match, "the agent file has no YAML frontmatter"
    return match.group(1), match.group(2)


def declared_tools(text):
    frontmatter, _ = _split(text)
    line = [n for n in frontmatter.splitlines() if n.startswith("tools:")]
    assert len(line) == 1, "expected exactly one tools: line, found %d" % len(line)
    return set(TOOL_RE.findall(line[0]))


def undeclared_tools(text):
    """Tool names the body calls for that the frontmatter does not grant."""
    _, body = _split(text)
    return sorted(set(TOOL_RE.findall(body)) - declared_tools(text))


def test_the_reviewer_declares_every_tool_its_body_names():
    text = REVIEWER.read_text()

    assert undeclared_tools(text) == []


def test_the_body_names_tools_at_all():
    """Guards the test above against passing on an empty set."""
    _, body = _split(REVIEWER.read_text())
    named = set(TOOL_RE.findall(body))

    assert "mcp__plugin_recce-devloop_recce__impact_analysis" in named
    # Step 6 creates a check per open finding a diff can re-run.
    assert "mcp__plugin_recce-devloop_recce__create_check" in named
    assert "mcp__plugin_recce-devloop_recce__list_checks" in named


def test_a_tool_the_frontmatter_does_not_grant_is_caught():
    """The failure this guard exists for, on a file shaped like the real one."""
    forged = (
        "---\n"
        "name: forged\n"
        "tools: Read, mcp__plugin_recce-devloop_recce__list_checks\n"
        "---\n"
        "Call mcp__plugin_recce-devloop_recce__list_checks, then\n"
        "mcp__plugin_recce-devloop_recce__run_check on what it returns.\n"
    )

    assert undeclared_tools(forged) == ["mcp__plugin_recce-devloop_recce__run_check"]
