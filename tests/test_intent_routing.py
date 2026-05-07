"""
AC-5 — Phrase routing on both platforms.

For each canonical phrase in tests/fixtures/trigger_phrases.txt, assert that
the phrase is covered by the "Canonical Trigger Phrases" section in SKILL.md.
"""

from pathlib import Path

FIXTURE = Path(__file__).parent / "fixtures" / "trigger_phrases.txt"
SKILL_MD = (
    Path(__file__).parent.parent
    / "plugins"
    / "recce-quickstart"
    / "skills"
    / "recce-guide"
    / "SKILL.md"
)
AGENTS_MD = Path(__file__).parent.parent / "AGENTS.md"


def _load_phrases() -> list[str]:
    return [
        line.strip()
        for line in FIXTURE.read_text().splitlines()
        if line.strip() and not line.startswith("#")
    ]


def test_fixture_phrase_count():
    """
    Fixture must contain exactly 8 canonical trigger phrases (M4 v2).

    The original 10-phrase set included two ambiguous phrases — "review my
    changes" and "show me what broke" — that collide with non-Recce intents
    (general code review, test-failure triage). They were removed in
    response to PR #26 review feedback to narrow the auto-trigger surface.
    """
    phrases = _load_phrases()
    assert len(phrases) == 8, f"Expected 8 phrases, got {len(phrases)}: {phrases}"


def test_all_phrases_trigger_merged_command():
    """
    For each canonical phrase, verify it appears verbatim in the
    SKILL.md 'Canonical Trigger Phrases' section (AC-5 phrase routing).
    """
    skill_text = SKILL_MD.read_text()
    phrases = _load_phrases()

    missing = []
    for phrase in phrases:
        if phrase not in skill_text:
            missing.append(phrase)

    assert not missing, (
        "The following phrases from trigger_phrases.txt are NOT present in SKILL.md:\n"
        + "\n".join(f"  - {p}" for p in missing)
    )


def test_all_phrases_in_agents_md():
    """
    For each canonical phrase, verify it also appears in AGENTS.md Codex section (AC-8).
    """
    agents_text = AGENTS_MD.read_text()
    phrases = _load_phrases()

    missing = []
    for phrase in phrases:
        if phrase not in agents_text:
            missing.append(phrase)

    assert not missing, (
        "The following phrases from trigger_phrases.txt are NOT present in AGENTS.md:\n"
        + "\n".join(f"  - {p}" for p in missing)
    )


def test_recce_analyze_command_is_primary_in_skill():
    """SKILL.md must list /recce-analyze as the primary command (AC-5, M4)."""
    skill_text = SKILL_MD.read_text()
    assert "/recce-analyze" in skill_text, "SKILL.md must reference /recce-analyze"
    # Primary command appears before legacy commands
    primary_idx = skill_text.index("/recce-analyze")
    legacy_idx = skill_text.index("Legacy commands")
    assert primary_idx < legacy_idx, "/recce-analyze must appear before 'Legacy commands' section"
