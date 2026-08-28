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
    / "recce"
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
        "reported customers.customer_lifetime_value:doc_mismatch models/schema.yml",
        "reported customers:join_shape models/customers.sql",
        "stopped  customers.customer_lifetime_value:null_introduced models/customers.sql",
    ]


def test_table_reports_round_zero_when_there_is_no_record(tmp_path):
    """No review has run on this branch, so there is nothing to write up."""
    project = _project(tmp_path)

    result = _run(
        ["table", "--record", str(tmp_path / "absent.json"), "--project-dir", str(project)]
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == "ROUND=0\n"
