"""findings.py -- the record that carries findings between review rounds.

Covers the contract the agent and the skill both depend on: what a valid block
produces, what is rejected (and that nothing is written when it is), and the
new / open / resolved split across two rounds.
"""

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

SCRIPT = (
    Path(__file__).parent.parent
    / "plugins"
    / "recce-devloop"
    / "skills"
    / "recce-dev-review"
    / "scripts"
    / "findings.py"
)


def _load():
    spec = importlib.util.spec_from_file_location("findings", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


findings = _load()


def _run(args, stdin=""):
    """Run the script as the skill runs it: a subprocess, with a real stdin."""
    return subprocess.run(
        [sys.executable, str(SCRIPT)] + args,
        input=stdin,
        capture_output=True,
        text=True,
    )


def _project(tmp_path):
    """A directory with the two model files the fixtures name."""
    (tmp_path / "models" / "staging").mkdir(parents=True)
    (tmp_path / "models" / "customers.sql").write_text("select 1\n")
    (tmp_path / "models" / "schema.yml").write_text("version: 2\n")
    (tmp_path / "models" / "staging" / "stg_payments.sql").write_text("select 1\n")
    return tmp_path


ROUND_1 = """```recce-findings
F1 open customers.customer_lifetime_value:doc_mismatch models/schema.yml
F2 open customers.customer_lifetime_value:null_introduced models/customers.sql
- verified customers.customer_lifetime_value:value_shift models/customers.sql
- verified stg_payments.coupon_amount:schema_add models/staging/stg_payments.sql
```
"""


def test_valid_block_writes_the_record(tmp_path):
    project = _project(tmp_path)
    record = tmp_path / "record.json"

    result = _run(
        ["write", "--record", str(record), "--project-dir", str(project)],
        stdin=ROUND_1,
    )

    assert result.returncode == 0, result.stderr
    assert "ROUND=1" in result.stdout
    assert "FINDINGS=4" in result.stdout
    assert "NEW=4" in result.stdout
    assert "RESOLVED=0" in result.stdout

    written = json.loads(record.read_text())
    assert written["version"] == findings.RECORD_VERSION
    assert written["round"] == 1
    assert written["project"] == str(project)
    keys = [f["key"] for f in written["findings"]]
    assert keys == [
        "customers.customer_lifetime_value:doc_mismatch",
        "customers.customer_lifetime_value:null_introduced",
        "customers.customer_lifetime_value:value_shift",
        "stg_payments.coupon_amount:schema_add",
    ]
    assert written["findings"][3]["ordinal"] is None
    assert all(f["first_seen"] == 1 and f["last_seen"] == 1 for f in written["findings"])


def test_block_is_extracted_from_a_whole_summary(tmp_path):
    """The skill pipes the agent's output as-is, fence and prose included."""
    project = _project(tmp_path)
    record = tmp_path / "record.json"
    summary = "## Data Review Summary\n\n**Data status:** measured\n\n" + ROUND_1

    result = _run(
        ["write", "--record", str(record), "--project-dir", str(project)],
        stdin=summary,
    )

    assert result.returncode == 0, result.stderr
    assert "FINDINGS=4" in result.stdout


def test_second_round_splits_new_open_and_resolved(tmp_path):
    project = _project(tmp_path)
    record = tmp_path / "record.json"
    _run(["write", "--record", str(record), "--project-dir", str(project)], stdin=ROUND_1)

    # doc_mismatch stays, null_introduced was fixed, join_shape is new.
    round_2 = """```recce-findings
F1 open customers.customer_lifetime_value:doc_mismatch models/schema.yml
F2 open customers:join_shape models/customers.sql
- verified customers.customer_lifetime_value:value_shift models/customers.sql
- verified stg_payments.coupon_amount:schema_add models/staging/stg_payments.sql
```
"""
    result = _run(
        ["write", "--record", str(record), "--project-dir", str(project)],
        stdin=round_2,
    )

    assert result.returncode == 0, result.stderr
    assert "ROUND=2" in result.stdout
    assert "FINDINGS=4" in result.stdout
    assert "NEW=1" in result.stdout
    assert "CARRIED=3" in result.stdout
    assert "RETURNED=0" in result.stdout
    assert "RESOLVED=1" in result.stdout
    assert (
        "RESOLVED_KEY=customers.customer_lifetime_value:null_introduced"
        in result.stdout
    )

    written = json.loads(record.read_text())
    by_key = {f["key"]: f for f in written["findings"]}
    # A carried finding keeps the round it was first seen in.
    assert by_key["customers.customer_lifetime_value:doc_mismatch"]["first_seen"] == 1
    assert by_key["customers.customer_lifetime_value:doc_mismatch"]["last_seen"] == 2
    assert by_key["customers:join_shape"]["first_seen"] == 2
    # The resolved finding stays, with last_seen behind the round. Deleting it
    # would make a later return indistinguishable from a first sighting.
    gone = by_key["customers.customer_lifetime_value:null_introduced"]
    assert gone["last_seen"] == 1
    assert written["round"] == 2
    # It gave up its ordinal: this round's F2 belongs to another finding.
    assert gone["ordinal"] is None
    # Open ordinals only: every verified finding carries None, which collides.
    live_open = [
        f["ordinal"]
        for f in written["findings"]
        if f["last_seen"] == 2 and f["group"] == "open"
    ]
    assert len(live_open) == len(set(live_open)), "an ordinal is ambiguous"
    assert [f["ordinal"] for f in written["findings"] if f["group"] == "verified"] == [
        None,
        None,
    ]


def test_read_reports_the_prior_round_and_always_the_concerns(tmp_path):
    project = _project(tmp_path)
    record = tmp_path / "record.json"

    first = _run(["read", "--record", str(record), "--project-dir", str(project)])
    assert "PRIOR_ROUND=0" in first.stdout
    # The agent needs the words to build keys even with no prior round.
    assert "CONCERNS=" in first.stdout

    _run(["write", "--record", str(record), "--project-dir", str(project)], stdin=ROUND_1)
    second = _run(["read", "--record", str(record), "--project-dir", str(project)])

    assert "PRIOR_ROUND=1" in second.stdout
    assert "customers.customer_lifetime_value:doc_mismatch" in second.stdout
    assert "verified " in second.stdout
    assert "CONCERNS=" in second.stdout


ROUND_2_WITHOUT_NULLS = """```recce-findings
F1 open customers.customer_lifetime_value:doc_mismatch models/schema.yml
- verified customers.customer_lifetime_value:value_shift models/customers.sql
- verified stg_payments.coupon_amount:schema_add models/staging/stg_payments.sql
```
"""


def test_read_hides_findings_that_are_already_resolved(tmp_path):
    project = _project(tmp_path)
    record = tmp_path / "record.json"
    _run(["write", "--record", str(record), "--project-dir", str(project)], stdin=ROUND_1)
    _run(
        ["write", "--record", str(record), "--project-dir", str(project)],
        stdin=ROUND_2_WITHOUT_NULLS,
    )

    result = _run(["read", "--record", str(record), "--project-dir", str(project)])

    assert "PRIOR_ROUND=2" in result.stdout
    # Check the finding lines only: every concern word, null_introduced
    # included, also appears on the CONCERNS= line.
    listed = [
        line
        for line in result.stdout.splitlines()
        if line.startswith(("open ", "verified "))
    ]
    assert any("doc_mismatch" in line for line in listed)
    # It is in the record, and the reviewer must not be told to look at it.
    assert not any("null_introduced" in line for line in listed)


def test_a_finding_that_comes_back_is_reported_as_returned(tmp_path):
    project = _project(tmp_path)
    record = tmp_path / "record.json"
    _run(["write", "--record", str(record), "--project-dir", str(project)], stdin=ROUND_1)
    _run(
        ["write", "--record", str(record), "--project-dir", str(project)],
        stdin=ROUND_2_WITHOUT_NULLS,
    )

    # Round 3: the same problem is back after being fixed in round 2.
    result = _run(
        ["write", "--record", str(record), "--project-dir", str(project)],
        stdin=ROUND_1,
    )

    assert result.returncode == 0, result.stderr
    assert "ROUND=3" in result.stdout
    assert "RETURNED=1" in result.stdout
    assert (
        "RETURNED_KEY=customers.customer_lifetime_value:null_introduced"
        in result.stdout
    )
    # It is not new: the record remembers when it was first seen.
    assert "NEW=0" in result.stdout
    written = json.loads(record.read_text())
    came_back = {f["key"]: f for f in written["findings"]}[
        "customers.customer_lifetime_value:null_introduced"
    ]
    assert came_back["first_seen"] == 1
    assert came_back["last_seen"] == 3


def test_a_resolved_finding_is_reported_once_only(tmp_path):
    project = _project(tmp_path)
    record = tmp_path / "record.json"
    _run(["write", "--record", str(record), "--project-dir", str(project)], stdin=ROUND_1)

    first = _run(
        ["write", "--record", str(record), "--project-dir", str(project)],
        stdin=ROUND_2_WITHOUT_NULLS,
    )
    second = _run(
        ["write", "--record", str(record), "--project-dir", str(project)],
        stdin=ROUND_2_WITHOUT_NULLS,
    )

    assert "RESOLVED=1" in first.stdout
    assert "RESOLVED=0" in second.stdout, "reported a second time"
    assert "RESOLVED_KEY=" not in second.stdout


TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def test_the_record_carries_utc_timestamps(tmp_path):
    project = _project(tmp_path)
    record = tmp_path / "record.json"

    _run(["write", "--record", str(record), "--project-dir", str(project)], stdin=ROUND_1)

    written = json.loads(record.read_text())
    assert TIMESTAMP.match(written["updated_at"]), written["updated_at"]
    for finding in written["findings"]:
        assert TIMESTAMP.match(finding["first_seen_at"])
        assert TIMESTAMP.match(finding["last_seen_at"])


def test_a_carried_finding_keeps_the_time_it_was_first_seen(tmp_path):
    project = _project(tmp_path)
    record = tmp_path / "record.json"
    _run(["write", "--record", str(record), "--project-dir", str(project)], stdin=ROUND_1)

    # Backdate round 1 so the check does not depend on the clock ticking.
    written = json.loads(record.read_text())
    for finding in written["findings"]:
        finding["first_seen_at"] = "2026-01-01T00:00:00Z"
        finding["last_seen_at"] = "2026-01-01T00:00:00Z"
    record.write_text(json.dumps(written))

    _run(["write", "--record", str(record), "--project-dir", str(project)], stdin=ROUND_1)

    after = {f["key"]: f for f in json.loads(record.read_text())["findings"]}
    kept = after["customers.customer_lifetime_value:doc_mismatch"]
    assert kept["first_seen_at"] == "2026-01-01T00:00:00Z"
    assert kept["last_seen_at"] != "2026-01-01T00:00:00Z"


def test_a_record_without_timestamps_reports_unknown_not_now(tmp_path):
    """Filling a missing time with now would claim this round first saw it."""
    project = _project(tmp_path)
    record = tmp_path / "record.json"
    _run(["write", "--record", str(record), "--project-dir", str(project)], stdin=ROUND_1)

    written = json.loads(record.read_text())
    written.pop("updated_at")
    for finding in written["findings"]:
        finding.pop("first_seen_at")
        finding.pop("last_seen_at")
    record.write_text(json.dumps(written))

    _run(["write", "--record", str(record), "--project-dir", str(project)], stdin=ROUND_1)

    after = {f["key"]: f for f in json.loads(record.read_text())["findings"]}
    assert after["customers.customer_lifetime_value:doc_mismatch"]["first_seen_at"] is None


def test_an_open_finding_must_carry_an_ordinal(tmp_path):
    """The summary prints it, so it has to be there."""
    project = _project(tmp_path)
    record = tmp_path / "record.json"
    block = """```recce-findings
- open customers.clv:doc_mismatch models/schema.yml
```
"""

    result = _run(
        ["write", "--record", str(record), "--project-dir", str(project)],
        stdin=block,
    )

    assert result.returncode == 2
    assert "An open finding needs a number" in result.stderr
    assert not record.exists()


def test_a_verified_finding_must_not_carry_an_ordinal(tmp_path):
    """A number on a verified line means the summary printed one."""
    project = _project(tmp_path)
    record = tmp_path / "record.json"
    block = """```recce-findings
F1 open customers.clv:doc_mismatch models/schema.yml
F2 verified stg_payments.coupon_amount:schema_add models/staging/stg_payments.sql
```
"""

    result = _run(
        ["write", "--record", str(record), "--project-dir", str(project)],
        stdin=block,
    )

    assert result.returncode == 2
    assert "never numbers a verified bullet" in result.stderr
    assert not record.exists()


def test_open_ordinals_are_numbered_independently_of_verified(tmp_path):
    """Verified findings take no number, so the open ones stay F1..Fn."""
    project = _project(tmp_path)
    record = tmp_path / "record.json"
    block = """```recce-findings
F1 open customers.clv:doc_mismatch models/schema.yml
- verified stg_payments.coupon_amount:schema_add models/staging/stg_payments.sql
F2 open customers.clv:null_introduced models/customers.sql
```
"""

    result = _run(
        ["write", "--record", str(record), "--project-dir", str(project)],
        stdin=block,
    )

    assert result.returncode == 0, result.stderr
    written = json.loads(record.read_text())
    by_key = {f["key"]: f for f in written["findings"]}
    assert by_key["customers.clv:doc_mismatch"]["ordinal"] == "F1"
    assert by_key["customers.clv:null_introduced"]["ordinal"] == "F2"
    assert by_key["stg_payments.coupon_amount:schema_add"]["ordinal"] is None


def test_a_gap_in_the_ordinals_is_rejected(tmp_path):
    project = _project(tmp_path)
    record = tmp_path / "record.json"
    block = """```recce-findings
F1 open customers.clv:doc_mismatch models/schema.yml
F3 open customers.clv:null_introduced models/customers.sql
```
"""

    result = _run(
        ["write", "--record", str(record), "--project-dir", str(project)],
        stdin=block,
    )

    assert result.returncode == 2
    assert "expected F1..F2" in result.stderr
    assert not record.exists()


def test_a_repeated_ordinal_is_rejected(tmp_path):
    project = _project(tmp_path)
    record = tmp_path / "record.json"
    block = """```recce-findings
F1 open customers.clv:doc_mismatch models/schema.yml
F1 open customers.clv:null_introduced models/customers.sql
```
"""

    result = _run(
        ["write", "--record", str(record), "--project-dir", str(project)],
        stdin=block,
    )

    assert result.returncode == 2
    assert not record.exists()


def test_a_verified_finding_dropping_out_is_not_reported_as_resolved(tmp_path):
    """Nothing was fixed: a new column is still there, the agent just moved on."""
    project = _project(tmp_path)
    record = tmp_path / "record.json"
    _run(["write", "--record", str(record), "--project-dir", str(project)], stdin=ROUND_1)

    # Round 2 keeps the open findings and drops the verified ones.
    round_2 = """```recce-findings
F1 open customers.customer_lifetime_value:doc_mismatch models/schema.yml
F2 open customers.customer_lifetime_value:null_introduced models/customers.sql
```
"""
    result = _run(
        ["write", "--record", str(record), "--project-dir", str(project)],
        stdin=round_2,
    )

    assert result.returncode == 0, result.stderr
    assert "RESOLVED=0" in result.stdout
    assert "RESOLVED_KEY=" not in result.stdout
    # Still recorded, so its key stays stable for later rounds.
    keys = {f["key"] for f in json.loads(record.read_text())["findings"]}
    assert "stg_payments.coupon_amount:schema_add" in keys


def test_a_verified_finding_coming_back_is_not_reported_as_returned(tmp_path):
    project = _project(tmp_path)
    record = tmp_path / "record.json"
    _run(["write", "--record", str(record), "--project-dir", str(project)], stdin=ROUND_1)
    # Drop only the verified findings. Both open ones stay, so nothing that
    # returns here was ever open.
    _run(
        ["write", "--record", str(record), "--project-dir", str(project)],
        stdin="""```recce-findings
F1 open customers.customer_lifetime_value:doc_mismatch models/schema.yml
F2 open customers.customer_lifetime_value:null_introduced models/customers.sql
```
""",
    )

    result = _run(
        ["write", "--record", str(record), "--project-dir", str(project)],
        stdin=ROUND_1,
    )

    assert result.returncode == 0, result.stderr
    assert "RETURNED=0" in result.stdout, "a verified finding is not tracked"
    assert "RETURNED_KEY=" not in result.stdout


def test_an_all_fixed_round_is_recorded_and_reports_the_fixes(tmp_path):
    """The best outcome in the loop used to be the one path that crashed."""
    project = _project(tmp_path)
    record = tmp_path / "record.json"
    _run(["write", "--record", str(record), "--project-dir", str(project)], stdin=ROUND_1)

    result = _run(
        ["write", "--record", str(record), "--project-dir", str(project)],
        stdin="```recce-findings\nnone\n```\n",
    )

    assert result.returncode == 0, result.stderr
    assert "ROUND=2" in result.stdout
    assert "FINDINGS=0" in result.stdout
    assert "RESOLVED=2" in result.stdout
    assert "RESOLVED_KEY=customers.customer_lifetime_value:doc_mismatch" in result.stdout
    written = json.loads(record.read_text())
    assert written["round"] == 2
    assert all(f["last_seen"] == 1 for f in written["findings"])


def test_an_empty_block_is_still_an_error(tmp_path):
    """A forgotten block must not look like an all-fixed round."""
    project = _project(tmp_path)
    record = tmp_path / "record.json"

    result = _run(
        ["write", "--record", str(record), "--project-dir", str(project)],
        stdin="```recce-findings\n```\n",
    )

    assert result.returncode == 2
    assert "the block is empty" in result.stderr
    assert not record.exists()


def test_a_record_from_another_branch_is_ignored(tmp_path):
    project = _project(tmp_path)
    subprocess.run(["git", "init", "-q"], cwd=project, check=True)
    subprocess.run(["git", "checkout", "-q", "-b", "feature/one"], cwd=project, check=True)
    record = tmp_path / "record.json"
    _run(["write", "--record", str(record), "--project-dir", str(project)], stdin=ROUND_1)

    assert "PRIOR_ROUND=1" in _run(
        ["read", "--record", str(record), "--project-dir", str(project)]
    ).stdout

    subprocess.run(["git", "checkout", "-q", "-b", "feature/two"], cwd=project, check=True)
    moved = _run(["read", "--record", str(record), "--project-dir", str(project)])

    assert "PRIOR_ROUND=0" in moved.stdout


def test_a_record_from_another_project_is_ignored(tmp_path):
    project = _project(tmp_path)
    other = _project(tmp_path / "other")
    record = tmp_path / "record.json"
    _run(["write", "--record", str(record), "--project-dir", str(project)], stdin=ROUND_1)

    result = _run(["read", "--record", str(record), "--project-dir", str(other)])

    assert "PRIOR_ROUND=0" in result.stdout


BAD_BLOCKS = {
    "unknown_concern": "F1 open customers.clv:doc_missmatch models/schema.yml",
    "bad_ordinal": "X1 open customers.clv:doc_mismatch models/schema.yml",
    "no_ordinal": "- open customers.clv:doc_mismatch models/schema.yml",
    "numbered_verified": "F1 verified customers.clv:value_shift models/customers.sql",
    "bad_group": "F1 maybe customers.clv:doc_mismatch models/schema.yml",
    "no_colon": "F1 open customers.clv.doc_mismatch models/schema.yml",
    "missing_file": "F1 open customers.clv:doc_mismatch models/nope.sql",
    "absolute_file": "F1 open customers.clv:doc_mismatch /etc/passwd",
    "escaping_file": "F1 open customers.clv:doc_mismatch ../outside.sql",
    "wrong_field_count": "F1 open customers.clv:doc_mismatch",
}


def test_each_malformed_line_is_rejected(tmp_path):
    project = _project(tmp_path)
    for name, line in BAD_BLOCKS.items():
        record = tmp_path / ("%s.json" % name)
        block = "```recce-findings\n%s\n```\n" % line

        result = _run(
            ["write", "--record", str(record), "--project-dir", str(project)],
            stdin=block,
        )

        assert result.returncode == 2, "%s was accepted: %s" % (name, result.stdout)
        assert "ERROR=" in result.stderr, name
        # The rejection has to teach the shape, or the agent cannot correct it.
        assert "Expected form" in result.stderr, name
        assert not record.exists(), "%s wrote a record anyway" % name


def test_the_rejection_names_the_valid_concern_words(tmp_path):
    project = _project(tmp_path)
    block = "```recce-findings\nF1 open customers.clv:not_a_word models/schema.yml\n```\n"

    result = _run(
        ["write", "--record", str(tmp_path / "r.json"), "--project-dir", str(project)],
        stdin=block,
    )

    assert result.returncode == 2
    for word in findings.CONCERNS:
        assert word in result.stderr


def test_a_duplicate_key_is_rejected(tmp_path):
    project = _project(tmp_path)
    record = tmp_path / "record.json"
    block = """```recce-findings
F1 open customers.clv:doc_mismatch models/schema.yml
- verified customers.clv:doc_mismatch models/customers.sql
```
"""

    result = _run(
        ["write", "--record", str(record), "--project-dir", str(project)],
        stdin=block,
    )

    assert result.returncode == 2
    assert "line 2: key" in result.stderr
    assert "already given on line 1" in result.stderr
    assert not record.exists()


def test_a_rejected_second_round_leaves_the_first_record_intact(tmp_path):
    """Validation must not be able to destroy a good record."""
    project = _project(tmp_path)
    record = tmp_path / "record.json"
    _run(["write", "--record", str(record), "--project-dir", str(project)], stdin=ROUND_1)
    before = record.read_text()

    result = _run(
        ["write", "--record", str(record), "--project-dir", str(project)],
        stdin="```recce-findings\nF1 open bad:word models/schema.yml\n```\n",
    )

    assert result.returncode == 2
    assert record.read_text() == before


def test_an_unreadable_record_is_treated_as_absent(tmp_path):
    project = _project(tmp_path)
    record = tmp_path / "record.json"
    record.write_text("{not json")

    read = _run(["read", "--record", str(record), "--project-dir", str(project)])
    assert "PRIOR_ROUND=0" in read.stdout

    write = _run(
        ["write", "--record", str(record), "--project-dir", str(project)],
        stdin=ROUND_1,
    )
    assert write.returncode == 0, write.stderr
    assert "ROUND=1" in write.stdout


def test_the_record_path_matches_the_shell_hash_scheme(tmp_path):
    """_project-hash.sh derives the same 8 characters from the same input."""
    project = str(tmp_path)
    shell = subprocess.run(
        ["bash", "-c", 'printf "%s" "$1" | md5 2>/dev/null || printf "%s" "$1" | md5sum',
         "_", project],
        capture_output=True,
        text=True,
    )
    digest = shell.stdout.split()[0][:8]

    assert findings.record_path(project) == "/tmp/recce-findings-%s.json" % digest


# --- `table`: the open findings the PR-prep step writes up -------------------

ROUND_2_ONE_FIX = """```recce-findings
F1 open customers:join_shape models/customers.sql
F2 open customers.customer_lifetime_value:doc_mismatch models/schema.yml
- verified customers.customer_lifetime_value:value_shift models/customers.sql
```
"""


def _two_rounds(tmp_path):
    """Round 1, then a round that drops one open and one verified finding."""
    project = _project(tmp_path)
    record = tmp_path / "record.json"
    args = ["--record", str(record), "--project-dir", str(project)]
    _run(["write"] + args, stdin=ROUND_1)
    _run(["write"] + args, stdin=ROUND_2_ONE_FIX)
    return project, record, args


def test_table_lists_an_open_finding_that_stopped_being_reported(tmp_path):
    """The row `read` hides is the row a resolution can be written for."""
    project, record, args = _two_rounds(tmp_path)
    gone = "customers.customer_lifetime_value:null_introduced"

    assert gone not in _run(["read"] + args).stdout

    result = _run(["table"] + args)

    assert result.returncode == 0, result.stderr
    assert "ROUND=2" in result.stdout
    assert "stopped  %s models/customers.sql" % gone in result.stdout


def test_table_omits_every_verified_finding(tmp_path):
    """The table is the list of things someone still has to decide about."""
    project, record, args = _two_rounds(tmp_path)

    result = _run(["table"] + args)

    assert result.returncode == 0, result.stderr
    # Still reported as verified, and verified but no longer reported.
    assert "customers.customer_lifetime_value:value_shift" not in result.stdout
    assert "stg_payments.coupon_amount:schema_add" not in result.stdout
    assert "verified" not in result.stdout


def test_table_prints_no_ordinal(tmp_path):
    """An ordinal belongs to the round that printed it, so this view has none."""
    project, record, args = _two_rounds(tmp_path)
    stored = json.loads(record.read_text())["findings"]
    assert [f["ordinal"] for f in stored if f["key"].endswith("join_shape")] == ["F1"]

    result = _run(["table"] + args)

    assert result.returncode == 0, result.stderr
    assert not re.search(r"\bF\d+\b", result.stdout)


def test_table_prints_one_order_for_one_record(tmp_path):
    """Reported before stopped, and by key inside each, whatever the round printed."""
    project, record, args = _two_rounds(tmp_path)

    result = _run(["table"] + args)

    assert result.stdout.splitlines() == [
        "ROUND=2",
        "SESSION_ID=",
        "reported customers.customer_lifetime_value:doc_mismatch models/schema.yml - -",
        "reported customers:join_shape models/customers.sql - -",
        "stopped  customers.customer_lifetime_value:null_introduced models/customers.sql - -",
    ]


def test_table_reports_round_zero_when_there_is_no_record(tmp_path):
    """No review has run on this branch, so there is nothing to write up."""
    project = _project(tmp_path)

    result = _run(
        ["table", "--record", str(tmp_path / "absent.json"), "--project-dir", str(project)]
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == "ROUND=0\n"


# --- the check-params block: which check backs which finding ----------------

ROUND_1_WITH_CHECKS = (
    ROUND_1
    + """
```recce-check-params
customers.customer_lifetime_value:null_introduced profile_diff {"model":"customers","columns":["customer_lifetime_value"]}
customers.customer_lifetime_value:value_shift value_diff {"model":"customers","primary_key":"customer_id"}
```
"""
)


def _bad_check_params(line):
    """One valid finding, and one check-params line that must be rejected."""
    return """```recce-findings
F1 open customers.customer_lifetime_value:null_introduced models/customers.sql
```

```recce-check-params
%s
```
""" % line


def test_the_check_params_block_reaches_the_record_and_the_table(tmp_path):
    """The reviewer's own diff call, stored against the finding it produced."""
    project = _project(tmp_path)
    record = tmp_path / "record.json"

    result = _run(
        ["write", "--record", str(record), "--project-dir", str(project),
         "--session-id", "c29669b4"],
        stdin=ROUND_1_WITH_CHECKS,
    )

    assert result.returncode == 0, result.stderr
    # Two of the four findings were measured with a diff; two were read from
    # code and can never have a check.
    assert "NO_CHECK_PARAMS=2" in result.stdout
    stored = {f["key"]: f["check"] for f in json.loads(record.read_text())["findings"]}
    assert stored["customers.customer_lifetime_value:null_introduced"] == {
        "type": "profile_diff",
        "params": {"model": "customers", "columns": ["customer_lifetime_value"]},
    }
    assert stored["customers.customer_lifetime_value:doc_mismatch"] is None

    table = _run(["table", "--record", str(record), "--project-dir", str(project)])

    assert table.stdout.splitlines() == [
        "ROUND=1",
        "SESSION_ID=c29669b4",
        "reported customers.customer_lifetime_value:doc_mismatch models/schema.yml - -",
        'reported customers.customer_lifetime_value:null_introduced models/customers.sql'
        ' profile_diff {"model":"customers","columns":["customer_lifetime_value"]}',
    ]


def test_a_check_params_key_no_finding_uses_is_rejected(tmp_path):
    """A typo drops the params for the finding it meant, silently. Not silently."""
    project = _project(tmp_path)
    record = tmp_path / "record.json"
    block = _bad_check_params(
        'customers.custome_lifetime_value:null_introduced profile_diff {"model":"customers"}'
    )

    result = _run(
        ["write", "--record", str(record), "--project-dir", str(project)],
        stdin=block,
    )

    assert result.returncode == 2, result.stdout
    assert "is not a finding in this round" in result.stderr
    assert not record.exists()


def test_a_check_type_create_check_does_not_accept_is_rejected(tmp_path):
    """The server refuses it after the run is paid for, so refuse it here."""
    project = _project(tmp_path)
    record = tmp_path / "record.json"
    block = _bad_check_params(
        'customers.customer_lifetime_value:null_introduced column_diff {"model":"customers"}'
    )

    result = _run(
        ["write", "--record", str(record), "--project-dir", str(project)],
        stdin=block,
    )

    assert result.returncode == 2, result.stdout
    assert "is not one create_check accepts" in result.stderr
    assert not record.exists()


def test_check_params_that_is_not_json_is_rejected(tmp_path):
    project = _project(tmp_path)
    record = tmp_path / "record.json"
    block = _bad_check_params(
        "customers.customer_lifetime_value:null_introduced profile_diff {model: customers}"
    )

    result = _run(
        ["write", "--record", str(record), "--project-dir", str(project)],
        stdin=block,
    )

    assert result.returncode == 2, result.stdout
    assert "params is not JSON" in result.stderr
    assert not record.exists()


def test_a_review_with_no_check_params_block_still_writes_its_record(tmp_path):
    """Five of the ten concerns can never carry one, so the block is optional."""
    project = _project(tmp_path)
    record = tmp_path / "record.json"

    result = _run(
        ["write", "--record", str(record), "--project-dir", str(project)],
        stdin=ROUND_1,
    )

    assert result.returncode == 0, result.stderr
    assert "NO_CHECK_PARAMS=4" in result.stdout
    assert all(f["check"] is None for f in json.loads(record.read_text())["findings"])


def test_a_record_written_before_the_check_field_still_tables(tmp_path):
    """RECORD_VERSION did not move, so live records have neither field."""
    project = _project(tmp_path)
    record = tmp_path / "record.json"
    record.write_text(
        json.dumps(
            {
                "version": findings.RECORD_VERSION,
                "project": str(project),
                "branch": None,
                "round": 3,
                "updated_at": "2026-08-20T00:00:00Z",
                "findings": [
                    {
                        "key": "customers:join_shape",
                        "group": "open",
                        "file": "models/customers.sql",
                        "ordinal": "F1",
                        "first_seen": 3,
                        "last_seen": 3,
                    }
                ],
            }
        )
    )

    result = _run(["table", "--record", str(record), "--project-dir", str(project)])

    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [
        "ROUND=3",
        "SESSION_ID=",
        "reported customers:join_shape models/customers.sql - -",
    ]


# --- `match-checks`: is this check already on the session? -------------------

# The two checks that were on session 3a5fa9a6 during the 2026-08-31 run,
# copied from artifacts/stream.jsonl line 91. Both are Recce presets.
LIVE_CHECKS = {
    "checks": [
        {
            "check_id": "54363d01-7fe8-4b2f-b543-ec061f8e8c2a",
            "type": "schema_diff",
            "params": {"node_id": "model.jaffle_shop.customers"},
            "is_preset": True,
        },
        {
            "check_id": "b0e7d841-be6d-471b-8a53-18b9e835eecf",
            "type": "top_k_diff",
            # Snowflake uppercases the column, and the preset carries `k`.
            "params": {"model": "customer_segments", "column_name": "VALUE_SEGMENT", "k": 50},
            "is_preset": True,
        },
    ],
    "total": 2,
}


def _match(tmp_path, candidates, checks=LIVE_CHECKS):
    existing = tmp_path / "existing.json"
    existing.write_text(json.dumps(checks))
    return _run(["match-checks", "--existing", str(existing)], stdin=candidates)


def test_a_check_differing_only_in_case_and_extra_keys_is_the_same_check(tmp_path):
    """The live pair. Key for key these are unequal, and they are one check."""
    result = _match(
        tmp_path,
        'customer_segments.value_segment:value_shift top_k_diff'
        ' {"model":"customer_segments","column_name":"value_segment"}\n',
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == (
        "SKIP=customer_segments.value_segment:value_shift"
        " b0e7d841-be6d-471b-8a53-18b9e835eecf\n"
    )


def test_a_different_model_or_column_is_a_different_check(tmp_path):
    """Folding case must not fold away a real difference."""
    result = _match(
        tmp_path,
        'a:value_shift top_k_diff {"model":"customers","column_name":"value_segment"}\n'
        'b:value_shift top_k_diff {"model":"customer_segments","column_name":"size_segment"}\n',
    )

    assert result.returncode == 0, result.stderr
    assert [line.split("=")[0] for line in result.stdout.splitlines()] == [
        "CREATE",
        "CREATE",
    ]


def test_a_candidate_naming_a_param_the_existing_check_lacks_does_not_match(tmp_path):
    """Extra keys are ignored on the existing check only, never on the candidate."""
    # `primary_key` is on no check in LIVE_CHECKS, so the existing check does
    # not make the comparison this candidate asks for.
    result = _match(
        tmp_path,
        'a:value_shift top_k_diff'
        ' {"model":"customer_segments","column_name":"value_segment","primary_key":"id"}\n',
    )

    assert result.stdout.startswith("CREATE="), result.stdout


def test_a_candidate_with_no_params_matches_nothing(tmp_path):
    """It names no comparison, so nothing can be the same comparison."""
    result = _match(tmp_path, "a:value_shift top_k_diff {}\n")

    assert result.stdout.startswith("CREATE="), result.stdout


def test_match_checks_reads_the_block_the_reviewer_already_writes(tmp_path):
    """The fenced form is accepted, so the agent pipes the same lines twice."""
    block = """```recce-check-params
customer_segments.value_segment:value_shift top_k_diff {"model":"customer_segments","column_name":"value_segment"}
customers.customer_lifetime_value:value_shift value_diff {"model":"customers","primary_key":"customer_id"}
```
"""
    result = _match(tmp_path, block)

    assert result.returncode == 0, result.stderr
    assert "SKIP=customer_segments.value_segment:value_shift" in result.stdout
    assert "CREATE=customers.customer_lifetime_value:value_shift" in result.stdout


def test_match_checks_stops_when_it_cannot_read_the_existing_checks(tmp_path):
    """Silently treating them as absent would create a duplicate of every one."""
    result = _run(
        ["match-checks", "--existing", str(tmp_path / "absent.json")],
        stdin='a:value_shift top_k_diff {"model":"m","column_name":"c"}\n',
    )

    assert result.returncode == 2
    assert "cannot read" in result.stderr
    assert result.stdout == ""


# --- the five concerns no diff re-runs ---------------------------------------

# The reviewer's own check-params block from the 2026-08-31 round-3 run,
# verbatim from artifacts/r2-summary.md. Its fourth line created check
# 0c4e12fa, a profile_diff of stg_payments standing in for "two filters remove
# zero rows" -- a check that passes whatever those filters do, and that nothing
# in Recce can delete.
LIVE_BLOCK_LINES = [
    'customers.customer_lifetime_value:value_shift value_diff'
    ' {"model":"customers","primary_key":"customer_id"}',
    'customer_segments.value_segment:value_shift top_k_diff'
    ' {"model":"customer_segments","column_name":"value_segment"}',
    'customers.customer_lifetime_value:null_introduced profile_diff'
    ' {"model":"customers","columns":["customer_lifetime_value","profit_based_customer_lifetime_value"]}',
    'customers:dead_filter profile_diff'
    ' {"model":"stg_payments","columns":["amount","coupon_amount"]}',
    'stg_payments.coupon_amount:schema_add profile_diff'
    ' {"model":"stg_payments","columns":["amount","coupon_amount"]}',
    'customers.profit_based_customer_lifetime_value:schema_add profile_diff'
    ' {"model":"customers","columns":["customer_lifetime_value","profit_based_customer_lifetime_value"]}',
    'customer_segments.profit_based_value_segment:schema_add schema_diff'
    ' {"select":"state:modified+"}',
]
DEAD_FILTER_LINE = LIVE_BLOCK_LINES[3]
# The three the reviewer actually offered as open candidates, minus that one.
LIVE_OPEN_CANDIDATES = LIVE_BLOCK_LINES[:3]

# The four checks on the session at that moment, verbatim from the file the
# reviewer piped into match-checks (artifacts/r2-stream.jsonl line 100). The
# two presets, plus the two the round before had created.
LIVE_CHECKS_ROUND3 = {
    "checks": LIVE_CHECKS["checks"]
    + [
        {
            "check_id": "37e396cd-3352-4ab9-9f54-def110841bcf",
            "type": "value_diff",
            "params": {"model": "customers", "primary_key": "customer_id"},
            "is_preset": False,
        },
        {
            "check_id": "8baeb9a3-99ca-4396-9b03-67f7f29908a4",
            "type": "profile_diff",
            "params": {
                "model": "customers",
                "columns": [
                    "customer_lifetime_value",
                    "profit_based_customer_lifetime_value",
                ],
            },
            "is_preset": False,
        },
    ],
    "total": 4,
}


def test_the_five_no_check_concerns_partition_the_concern_list(tmp_path):
    """A concern word added later must be put on one side or the other."""
    assert set(findings.NO_CHECK_CONCERNS) < set(findings.CONCERNS)
    checkable = set(findings.CONCERNS) - set(findings.NO_CHECK_CONCERNS)
    assert checkable == {
        "value_shift",
        "row_count_shift",
        "schema_add",
        "schema_drop",
        "null_introduced",
    }


def test_the_live_dead_filter_line_is_refused(tmp_path):
    """The exact line that created check 0c4e12fa on 2026-08-31."""
    result = _match(tmp_path, DEAD_FILTER_LINE + "\n")

    assert result.returncode == 2, result.stdout
    assert "customers:dead_filter" in result.stderr
    assert "no check" in result.stderr
    # Nothing to create from, so nothing the agent could have acted on. The
    # agent's own instruction states this, so it has to stay true.
    assert result.stdout == ""
    assert result.stderr.count("ERROR=") == 1


def test_match_checks_prints_nothing_at_all_when_one_candidate_is_refused(tmp_path):
    """One good candidate and one refused: no partial CREATE= or SKIP= output.

    `recce-dev-reviewer` is told the script prints no CREATE or SKIP lines when
    it exits non-zero. A partial list would be worse than none: the agent would
    act on half a decision.
    """
    result = _match(
        tmp_path,
        LIVE_OPEN_CANDIDATES[1] + "\n" + DEAD_FILTER_LINE + "\n",
        LIVE_CHECKS_ROUND3,
    )

    assert result.returncode == 2
    assert result.stdout == ""
    assert result.stderr.count("ERROR=") == 1
    assert "customers:dead_filter" in result.stderr


def test_write_drops_the_refused_line_and_keeps_the_round(tmp_path):
    """`write` runs after the agent returned, so losing the round buys nothing.

    The whole seven-line block from the round-3 run, including the line that
    created check 0c4e12fa. Every finding is still recorded; only that line's
    params are dropped, and the drop is printed.
    """
    project = _project(tmp_path)
    record = tmp_path / "record.json"
    block = "```recce-findings\n%s\n```\n\n```recce-check-params\n%s\n```\n" % (
        "\n".join(
            [
                "F1 open customers.customer_lifetime_value:value_shift models/customers.sql",
                "F2 open customer_segments.value_segment:value_shift models/customers.sql",
                "F3 open customers.customer_lifetime_value:null_introduced models/customers.sql",
                "F4 open customers:dead_filter models/customers.sql",
            ]
        ),
        "\n".join(LIVE_BLOCK_LINES[:4]),
    )

    result = _run(
        ["write", "--record", str(record), "--project-dir", str(project)],
        stdin=block,
    )

    assert result.returncode == 0, result.stderr
    assert "FINDINGS=4" in result.stdout
    assert "DROPPED_CHECK_PARAMS=1" in result.stdout
    assert "DROPPED_CHECK_PARAMS_KEY=customers:dead_filter" in result.stdout

    stored = {f["key"]: f["check"] for f in json.loads(record.read_text())["findings"]}
    # The round survived whole: four findings, three carrying their diff call.
    assert len(stored) == 4
    assert stored["customers:dead_filter"] is None
    assert stored["customers.customer_lifetime_value:value_shift"]["type"] == "value_diff"


def test_a_check_params_error_that_is_not_a_refusal_still_loses_the_round(tmp_path):
    """Only the concern guard is a drop. An unknown type is still fatal."""
    project = _project(tmp_path)
    record = tmp_path / "record.json"
    block = """```recce-findings
F1 open customers.customer_lifetime_value:value_shift models/customers.sql
```

```recce-check-params
customers.customer_lifetime_value:value_shift column_diff {"model":"customers"}
```
"""

    result = _run(
        ["write", "--record", str(record), "--project-dir", str(project)],
        stdin=block,
    )

    assert result.returncode == 2, result.stdout
    assert not record.exists()


def test_the_legitimate_live_candidates_still_match_as_they_did(tmp_path):
    """The guard must not change the answer for the other lines."""
    result = _match(
        tmp_path, "\n".join(LIVE_OPEN_CANDIDATES) + "\n", LIVE_CHECKS_ROUND3
    )

    assert result.returncode == 0, result.stderr
    # The same three SKIP lines, with the same check ids, that
    # artifacts/r2-stream.jsonl line 101 recorded for these candidates.
    assert result.stdout.splitlines() == [
        "SKIP=customer_segments.value_segment:value_shift"
        " b0e7d841-be6d-471b-8a53-18b9e835eecf",
        "SKIP=customers.customer_lifetime_value:null_introduced"
        " 8baeb9a3-99ca-4396-9b03-67f7f29908a4",
        "SKIP=customers.customer_lifetime_value:value_shift"
        " 37e396cd-3352-4ab9-9f54-def110841bcf",
    ]


def test_the_whole_live_block_is_refused_only_for_that_one_line(tmp_path):
    """One bad line, one error. The other six are not implicated."""
    result = _match(tmp_path, "\n".join(LIVE_BLOCK_LINES) + "\n")

    assert result.returncode == 2
    assert result.stderr.count("ERROR=") == 1
    assert "customers:dead_filter" in result.stderr
