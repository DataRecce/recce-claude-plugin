"""findings.py -- the record that carries findings between review rounds.

Covers the contract the agent and the skill both depend on: what a valid block
produces, what is rejected (and that nothing is written when it is), the
new / open / resolved split across two rounds, and the decisions the PR table
is built from.
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
    """A directory with the model files the fixtures name."""
    (tmp_path / "models" / "staging").mkdir(parents=True)
    (tmp_path / "models" / "customers.sql").write_text("select 1\n")
    (tmp_path / "models" / "daily_metrics.sql").write_text("select 1\n")
    (tmp_path / "models" / "schema.yml").write_text("version: 2\n")
    (tmp_path / "models" / "staging" / "stg_payments.sql").write_text("select 1\n")
    return tmp_path


ROUND_1 = """```recce-findings
F1 open customers.customer_lifetime_value:doc_mismatch models/schema.yml CLV documentation omits the completed-orders restriction
F2 open customers.customer_lifetime_value:null_introduced models/customers.sql 5 customers have NULL CLV where none did before
- verified customers.customer_lifetime_value:value_shift models/customers.sql CLV moved on 12 of 998 customers
- verified stg_payments.coupon_amount:schema_add models/staging/stg_payments.sql coupon_amount is a new column
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
    assert (
        written["findings"][0]["title"]
        == "CLV documentation omits the completed-orders restriction"
    )
    assert written["findings"][3]["title"] == "coupon_amount is a new column"
    # A verified finding is never numbered, so it has no round to file under.
    assert written["findings"][3]["ordinals"] == {}
    assert written["findings"][0]["ordinals"] == {"1": "F1"}
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
F1 open customers.customer_lifetime_value:doc_mismatch models/schema.yml CLV documentation omits the completed-orders restriction
F2 open customers:join_shape models/customers.sql The new join changes the grain of the customer table
- verified customers.customer_lifetime_value:value_shift models/customers.sql CLV moved on 12 of 998 customers
- verified stg_payments.coupon_amount:schema_add models/staging/stg_payments.sql coupon_amount is a new column
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
    # The resolved finding stays, with last_seen behind the round.
    gone = by_key["customers.customer_lifetime_value:null_introduced"]
    assert gone["last_seen"] == 1
    assert written["round"] == 2
    assert gone["ordinals"] == {"1": "F2"}
    assert by_key["customers:join_shape"]["ordinals"] == {"2": "F2"}
    # Open ordinals only, and unambiguous within the round.
    live_open = [
        f["ordinals"]["2"]
        for f in written["findings"]
        if f["last_seen"] == 2 and f["group"] == "open"
    ]
    assert len(live_open) == len(set(live_open)), "an ordinal is ambiguous"
    assert [f["ordinals"] for f in written["findings"] if f["group"] == "verified"] == [
        {},
        {},
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
F1 open customers.customer_lifetime_value:doc_mismatch models/schema.yml CLV documentation omits the completed-orders restriction
- verified customers.customer_lifetime_value:value_shift models/customers.sql CLV moved on 12 of 998 customers
- verified stg_payments.coupon_amount:schema_add models/staging/stg_payments.sql coupon_amount is a new column
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


def test_an_open_finding_must_carry_an_ordinal(tmp_path):
    """The summary prints it, so it has to be there."""
    project = _project(tmp_path)
    record = tmp_path / "record.json"
    block = """```recce-findings
- open customers.clv:doc_mismatch models/schema.yml CLV docs omit the restriction
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
F1 open customers.clv:doc_mismatch models/schema.yml CLV docs omit the restriction
F2 verified stg_payments.coupon_amount:schema_add models/staging/stg_payments.sql coupon_amount is a new column
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
F1 open customers.clv:doc_mismatch models/schema.yml CLV docs omit the restriction
- verified stg_payments.coupon_amount:schema_add models/staging/stg_payments.sql coupon_amount is a new column
F2 open customers.clv:null_introduced models/customers.sql 5 customers have NULL CLV
```
"""

    result = _run(
        ["write", "--record", str(record), "--project-dir", str(project)],
        stdin=block,
    )

    assert result.returncode == 0, result.stderr
    written = json.loads(record.read_text())
    by_key = {f["key"]: f for f in written["findings"]}
    assert by_key["customers.clv:doc_mismatch"]["ordinals"] == {"1": "F1"}
    assert by_key["customers.clv:null_introduced"]["ordinals"] == {"1": "F2"}
    assert by_key["stg_payments.coupon_amount:schema_add"]["ordinals"] == {}


def test_ordinals_that_are_not_f1_to_fn_are_rejected(tmp_path):
    """A gap and a repeat both break the map from a printed number to a
    finding, and one check in findings.py catches both."""
    project = _project(tmp_path)
    line = "%s open customers.clv:%s models/customers.sql A title for it"

    for name, second in (("gap", "F3"), ("repeat", "F1")):
        record = tmp_path / ("%s.json" % name)
        block = "```recce-findings\n%s\n%s\n```\n" % (
            line % ("F1", "doc_mismatch"),
            line % (second, "null_introduced"),
        )

        result = _run(
            ["write", "--record", str(record), "--project-dir", str(project)],
            stdin=block,
        )

        assert result.returncode == 2, name
        assert "expected F1..F2" in result.stderr, name
        assert not record.exists(), name


def test_a_verified_finding_dropping_out_is_not_reported_as_resolved(tmp_path):
    """Nothing was fixed: a new column is still there, the agent just moved on."""
    project = _project(tmp_path)
    record = tmp_path / "record.json"
    _run(["write", "--record", str(record), "--project-dir", str(project)], stdin=ROUND_1)

    # Round 2 keeps the open findings and drops the verified ones.
    round_2 = """```recce-findings
F1 open customers.customer_lifetime_value:doc_mismatch models/schema.yml CLV documentation omits the completed-orders restriction
F2 open customers.customer_lifetime_value:null_introduced models/customers.sql 5 customers have NULL CLV where none did before
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
F1 open customers.customer_lifetime_value:doc_mismatch models/schema.yml CLV documentation omits the completed-orders restriction
F2 open customers.customer_lifetime_value:null_introduced models/customers.sql 5 customers have NULL CLV where none did before
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


# The rules with no test of their own. A rule whose message and accepting case
# are worth pinning gets a named test instead, further down.
BAD_BLOCKS = {
    "bad_ordinal": (
        "X1 open customers.clv:doc_mismatch models/schema.yml CLV docs omit the restriction"
    ),
    "bad_group": (
        "F1 maybe customers.clv:doc_mismatch models/schema.yml CLV docs omit the restriction"
    ),
    "no_colon": (
        "F1 open customers.clv.doc_mismatch models/schema.yml CLV docs omit the restriction"
    ),
    "missing_file": (
        "F1 open customers.clv:doc_mismatch models/nope.sql CLV docs omit the restriction"
    ),
    "absolute_file": (
        "F1 open customers.clv:doc_mismatch /etc/passwd CLV docs omit the restriction"
    ),
    "escaping_file": (
        "F1 open customers.clv:doc_mismatch ../outside.sql CLV docs omit the restriction"
    ),
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


def test_a_line_without_a_title_is_short_a_field(tmp_path):
    """The title is a field, so a four-field line is now incomplete."""
    project = _project(tmp_path)
    record = tmp_path / "record.json"
    args = ["--record", str(record), "--project-dir", str(project)]
    line = "F1 open customers.clv:doc_mismatch models/schema.yml"

    short = _run(["write"] + args, stdin="```recce-findings\n%s\n```\n" % line)
    assert short.returncode == 2
    assert "4 fields, expected 5" in short.stderr
    assert not record.exists()

    whole = _run(
        ["write"] + args,
        stdin="```recce-findings\n%s CLV docs omit the restriction\n```\n" % line,
    )
    assert whole.returncode == 0, whole.stderr


def test_a_title_with_a_pipe_is_rejected(tmp_path):
    """It goes in a markdown cell, so a pipe would split the row."""
    project = _project(tmp_path)
    record = tmp_path / "record.json"
    args = ["--record", str(record), "--project-dir", str(project)]
    line = "F1 open customers.clv:doc_mismatch models/schema.yml CLV docs omit %s the restriction"

    piped = _run(["write"] + args, stdin="```recce-findings\n%s\n```\n" % (line % "|"))
    assert piped.returncode == 2
    assert "contains '|', which breaks the PR table row" in piped.stderr
    assert not record.exists()

    plain = _run(["write"] + args, stdin="```recce-findings\n%s\n```\n" % (line % "and"))
    assert plain.returncode == 0, plain.stderr


def test_the_rejection_names_the_valid_concern_words(tmp_path):
    project = _project(tmp_path)
    block = (
        "```recce-findings\n"
        "F1 open customers.clv:not_a_word models/schema.yml CLV docs omit the restriction\n"
        "```\n"
    )

    result = _run(
        ["write", "--record", str(tmp_path / "r.json"), "--project-dir", str(project)],
        stdin=block,
    )

    assert result.returncode == 2
    # The concern check has to be the thing that fired, not the field count.
    assert "concern 'not_a_word' is not in the list" in result.stderr
    for word in findings.CONCERNS:
        assert word in result.stderr


def test_a_duplicate_key_is_rejected(tmp_path):
    project = _project(tmp_path)
    record = tmp_path / "record.json"
    block = """```recce-findings
F1 open customers.clv:doc_mismatch models/schema.yml CLV docs omit the restriction
- verified customers.clv:doc_mismatch models/customers.sql CLV docs omit the restriction
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
        stdin=(
            "```recce-findings\n"
            "F1 open bad:word models/schema.yml A title on a bad key\n"
            "```\n"
        ),
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
    """Run _project-hash.sh itself, so a change to it fails here."""
    project = str(tmp_path)
    shell = subprocess.run(
        ["bash", "-c", '. "$1"; printf "%s" "$RECCE_PROJECT_HASH"', "_",
         str(SCRIPT.parent / "_project-hash.sh")],
        cwd=project,
        capture_output=True,
        text=True,
    )

    assert shell.returncode == 0, shell.stderr
    assert len(shell.stdout) == 8, shell.stdout
    assert findings.record_path(project) == "/tmp/recce-findings-%s.json" % shell.stdout


# --- `decide` and `pr-table`: the decisions the PR description is built from -

ROUND_2_ONE_FIX = """```recce-findings
F1 open customers:join_shape models/customers.sql The new join changes the grain of the customer table
F2 open customers.customer_lifetime_value:doc_mismatch models/schema.yml CLV documentation omits the completed-orders restriction
- verified customers.customer_lifetime_value:value_shift models/customers.sql CLV moved on 12 of 998 customers
```
"""


def _two_rounds(tmp_path):
    """Round 1 with both open findings decided, then a round that drops one
    open and one verified finding and adds an undecided one."""
    project = _project(tmp_path)
    record = tmp_path / "record.json"
    args = ["--record", str(record), "--project-dir", str(project)]
    _run(["write"] + args, stdin=ROUND_1)
    _run(
        ["decide", "F1", "--state", "accepted",
         "--note", "The docs are rewritten in a follow-up that finance signs off."] + args
    )
    _run(
        ["decide", "F2", "--state", "accepted",
         "--note", "The nulls are pre-existing rows the new filter does not reach."] + args
    )
    _run(["write"] + args, stdin=ROUND_2_ONE_FIX)
    return project, record, args


def test_pr_table_keeps_a_decided_finding_the_reviewer_stopped_reporting(tmp_path):
    """The row `read` hides is still a decision the reviewer may disagree with."""
    project, record, args = _two_rounds(tmp_path)
    gone = "customers.customer_lifetime_value:null_introduced"

    assert gone not in _run(["read"] + args).stdout

    result = _run(["pr-table"] + args)

    assert result.returncode == 0, result.stderr
    assert "| 5 customers have NULL CLV where none did before |" in result.stdout


def test_pr_table_omits_an_undecided_verified_finding(tmp_path):
    """A verified finding nobody spoke about needs no decision, so it is not a
    row and not a note line either. One the developer accepted is a row --
    test_decide_on_a_verified_finding_takes_accepted_only covers that."""
    project, record, args = _two_rounds(tmp_path)

    result = _run(["pr-table"] + args)

    assert result.returncode == 0, result.stderr
    # Still reported as verified, and verified but no longer reported.
    assert "CLV moved on 12 of 998 customers" not in result.stdout
    assert "coupon_amount is a new column" not in result.stdout
    assert "verified" not in result.stdout


def test_pr_table_prints_one_order_for_one_record(tmp_path):
    """Reported before stopped, and by key inside each, whatever the round printed."""
    project, record, args = _two_rounds(tmp_path)

    result = _run(["pr-table"] + args)

    assert result.stdout.splitlines() == [
        "| Finding | Why |",
        "|---|---|",
        "| CLV documentation omits the completed-orders restriction | The docs are"
        " rewritten in a follow-up that finance signs off. |",
        "| 5 customers have NULL CLV where none did before | The nulls are"
        " pre-existing rows the new filter does not reach. |",
        "",
        "Not decided, and round 2 still reports these: `customers:join_shape`.",
    ]


def test_pr_table_errors_when_there_is_no_record(tmp_path):
    """No review has run on this branch, so there is nothing to write up."""
    project = _project(tmp_path)

    result = _run(
        [
            "pr-table",
            "--record",
            str(tmp_path / "absent.json"),
            "--project-dir",
            str(project),
        ]
    )

    assert result.returncode == 2
    assert result.stdout == ""
    assert "ERROR=no findings record for this branch" in result.stderr


# --- Session 2830c52c, the case the change was written for -------------------

SESSION_ROUND_1 = """```recce-findings
F1 open customers.customer_lifetime_value:doc_mismatch models/schema.yml CLV documentation omits the completed-orders restriction
F2 open customers:test_cannot_hold models/customers.sql A not_null test the left join can break
F3 open customers.customer_segment:value_shift models/customers.sql High Value lost 313 customers, 60% of the segment
F4 open customers.customer_lifetime_value:null_introduced models/customers.sql 5 customers have NULL CLV where none did before
F5 open stg_payments:dead_filter models/staging/stg_payments.sql Both payment filters remove zero rows
```
"""

SESSION_ROUND_2 = """```recce-findings
F1 open daily_metrics.avg_order_amount:value_shift models/daily_metrics.sql avg_order_amount differs on 678 of 730 days
F2 open customers.profit_segment:doc_mismatch models/customers.sql Profit segments reuse the gross CLV thresholds 4000 and 1500
```
"""

SESSION_DECISIONS = (
    (
        1,
        "F1",
        "fixed",
        "Descriptions are being rewritten in this change.",
    ),
    (
        1,
        "F4",
        "fixed",
        "The left join becomes an inner join with coalesce, so no NULL CLV remains.",
    ),
    (
        1,
        "F2",
        "accepted",
        "The not_null test holds today. The join only returns NULL if an order has"
        " no payment row.",
    ),
    (
        1,
        "F5",
        "accepted",
        "The filters come from the old model and remove nothing yet. Removing them"
        " is a separate change.",
    ),
    (
        1,
        "F3",
        "accepted",
        "Intended. The completed-orders restriction moves low-activity customers"
        " down a tier.",
    ),
    (
        2,
        "F2",
        "accepted",
        "Intended. The profit thresholds stay at the gross values until finance"
        " agrees new ones.",
    ),
    (
        2,
        "F1",
        "deferred",
        "This change does not touch avg_order_amount, so the shift is left for a"
        " separate change.",
    ),
)

SESSION_TABLE = [
    "| Finding | Why |",
    "|---|---|",
    "| Profit segments reuse the gross CLV thresholds 4000 and 1500 | Intended. The"
    " profit thresholds stay at the gross values until finance agrees new ones. |",
    "| avg_order_amount differs on 678 of 730 days | This change does not touch"
    " avg_order_amount, so the shift is left for a separate change. |",
    "| High Value lost 313 customers, 60% of the segment | Intended. The"
    " completed-orders restriction moves low-activity customers down a tier. |",
    "| A not_null test the left join can break | The not_null test holds today. The"
    " join only returns NULL if an order has no payment row. |",
    "| Both payment filters remove zero rows | The filters come from the old model"
    " and remove nothing yet. Removing them is a separate change. |",
]


def _session(tmp_path):
    """Two rounds, seven findings, and the decisions the developer gave."""
    project = _project(tmp_path)
    record = tmp_path / "record.json"
    args = ["--record", str(record), "--project-dir", str(project)]
    rounds = {1: SESSION_ROUND_1, 2: SESSION_ROUND_2}
    written = {}
    for number in (1, 2):
        written[number] = _run(["write"] + args, stdin=rounds[number])
        assert written[number].returncode == 0, written[number].stderr
        for round_number, target, state, note in SESSION_DECISIONS:
            if round_number != number:
                continue
            decided = _run(
                ["decide", target, "--state", state, "--note", note] + args
            )
            assert decided.returncode == 0, decided.stderr
    return project, record, args, written[2]


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
F1 open customers.customer_lifetime_value:null_introduced models/customers.sql 5 customers have NULL CLV where none did before
```

```recce-check-params
%s
```
""" % line


def test_the_check_params_block_reaches_the_record(tmp_path):
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
    written = json.loads(record.read_text())
    stored = {f["key"]: f["check"] for f in written["findings"]}
    assert stored["customers.customer_lifetime_value:null_introduced"] == {
        "type": "profile_diff",
        "params": {"model": "customers", "columns": ["customer_lifetime_value"]},
    }
    assert stored["customers.customer_lifetime_value:value_shift"] == {
        "type": "value_diff",
        "params": {"model": "customers", "primary_key": "customer_id"},
    }
    # Read from code, so no diff re-runs it and it carries no check.
    assert stored["customers.customer_lifetime_value:doc_mismatch"] is None
    # The checks were created on a session, so the record names which one.
    assert written["session_id"] == "c29669b4"


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
    """A concern no diff re-runs can never carry one, so the block is optional."""
    project = _project(tmp_path)
    record = tmp_path / "record.json"

    result = _run(
        ["write", "--record", str(record), "--project-dir", str(project)],
        stdin=ROUND_1,
    )

    assert result.returncode == 0, result.stderr
    assert "NO_CHECK_PARAMS=4" in result.stdout
    assert all(f["check"] is None for f in json.loads(record.read_text())["findings"])


def test_pr_table_on_a_round_nobody_decided_yet(tmp_path):
    """The developer ran a review and answered nothing. There is no table, and
    the finding goes on a note line rather than a row with an empty cell."""
    project = _project(tmp_path)
    record = tmp_path / "record.json"
    args = ["--record", str(record), "--project-dir", str(project)]
    _run(["write"] + args, stdin="""```recce-findings
F1 open customers:join_shape models/customers.sql The new join changes the grain
```
""")

    result = _run(["pr-table"] + args)

    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [
        "No findings were decided on this branch.",
        "",
        "Not decided, and round 1 still reports these: `customers:join_shape`.",
    ]


# --- `match-checks`: is this check already on the session? -------------------

# The two checks that were on the session during a recorded run. Both are
# Recce presets.
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


# --- the concerns no diff re-runs --------------------------------------------

# The reviewer's own check-params block from a recorded round-3 run. Its
# fourth line created a profile_diff of stg_payments standing in for "two
# filters remove zero rows": a check that passes whatever those filters do,
# and that nothing in Recce can delete.
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

# The four checks on the session at that moment, as the reviewer piped them
# into match-checks: the two presets, plus the two the round before created.
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
                "F1 open customers.customer_lifetime_value:value_shift"
                " models/customers.sql CLV average dropped 32%",
                "F2 open customer_segments.value_segment:value_shift"
                " models/customers.sql High Value lost 313 customers",
                "F3 open customers.customer_lifetime_value:null_introduced"
                " models/customers.sql 5 customers have NULL CLV where none did before",
                "F4 open customers:dead_filter"
                " models/customers.sql Both new payment filters remove zero rows",
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
    # The same three SKIP lines, with the same check ids, that the recorded
    # run produced for these candidates.
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


def test_the_table_carries_the_decisions_and_leaves_out_the_fixes(tmp_path):
    """AC-1. Two of the seven were fixed, and the diff already shows those."""
    project, record, args, _ = _session(tmp_path)

    result = _run(["pr-table"] + args)

    assert result.returncode == 0, result.stderr
    rows = [line for line in result.stdout.splitlines() if line.startswith("| ")]
    assert len(rows) == 6, result.stdout  # the header and five decided findings
    for fixed in (
        "CLV documentation omits the completed-orders restriction",
        "5 customers have NULL CLV where none did before",
    ):
        assert fixed not in result.stdout
    # The largest one the old table never printed.
    assert "High Value lost 313 customers, 60% of the segment" in result.stdout


def test_every_row_carries_the_stored_note_and_no_state_word(tmp_path):
    """AC-2. The note is the reason recorded at decision time, on the finding it
    was given for, and the state that selected the row is never printed."""
    project, record, args, _ = _session(tmp_path)
    notes = {
        f["title"]: (f.get("decision") or {}).get("note")
        for f in json.loads(record.read_text())["findings"]
    }

    result = _run(["pr-table"] + args)

    printed = []
    for line in result.stdout.splitlines():
        if not line.startswith("| ") or line == "| Finding | Why |":
            continue
        title, why = [cell.strip() for cell in line.strip("|").split(" | ")]
        assert why, title
        # Attribution: this row's reason is the one stored on THIS finding.
        assert why == notes[title], title
        printed.append(why)
    # One sentence pasted onto two rows is the defect this change was filed for.
    # Every decision in the fixture was given its own reason, so no reason may
    # appear twice.
    assert len(set(printed)) == len(printed), printed
    assert len(printed) == 5
    lowered = result.stdout.lower()
    for word in findings.DECISIONS:
        assert word not in lowered, word


def test_an_accepted_finding_survives_the_round_after_it(tmp_path):
    """AC-3. `write` must not overwrite the decision it merges."""
    project = _project(tmp_path)
    record = tmp_path / "record.json"
    args = ["--record", str(record), "--project-dir", str(project)]
    _run(["write"] + args, stdin=ROUND_1)
    _run(
        ["decide", "F1", "--state", "accepted",
         "--note", "Intended. The restriction is the point of the change."] + args
    )

    _run(["write"] + args, stdin=ROUND_1)

    after = {f["key"]: f for f in json.loads(record.read_text())["findings"]}
    kept = after["customers.customer_lifetime_value:doc_mismatch"]["decision"]
    assert kept["state"] == "accepted"
    assert kept["round"] == 1
    assert after["customers.customer_lifetime_value:doc_mismatch"]["ordinals"] == {
        "1": "F1",
        "2": "F1",
    }


def test_a_decision_survives_the_reviewer_reclassifying_the_finding(tmp_path):
    """AC-3. Accepted while open in round 1; round 2 calls the same finding
    verified and nobody says anything, so the decision stands and the row stays.
    """
    project = _project(tmp_path)
    record = tmp_path / "record.json"
    args = ["--record", str(record), "--project-dir", str(project)]
    _run(["write"] + args, stdin=ROUND_1)
    _run(["decide", "F2", "--state", "accepted",
          "--note", "Intended. The nulls are rows the new filter does not reach."]
         + args)
    before = _run(["pr-table"] + args)
    assert "5 customers have NULL CLV where none did before" in before.stdout

    _run(["write"] + args, stdin="""```recce-findings
F1 open customers.customer_lifetime_value:doc_mismatch models/schema.yml CLV documentation omits the completed-orders restriction
- verified customers.customer_lifetime_value:null_introduced models/customers.sql 5 customers have NULL CLV where none did before
```
""")

    after = _run(["pr-table"] + args)

    stored = {f["key"]: f for f in json.loads(record.read_text())["findings"]}
    kept = stored["customers.customer_lifetime_value:null_introduced"]
    assert kept["group"] == "verified", "the reviewer did reclassify it"
    assert kept["decision"]["state"] == "accepted", "the decision is still stored"
    # The row the developer saw in round 1 must still be there in round 2.
    assert "5 customers have NULL CLV where none did before" in after.stdout
    assert "No findings were decided on this branch." not in after.stdout


def test_the_same_record_always_produces_the_same_table(tmp_path):
    """AC-4. Nothing in the ordering comes from the clock or from dict order."""
    project, record, args, _ = _session(tmp_path)

    first = _run(["pr-table"] + args)
    second = _run(["pr-table"] + args)

    assert first.stdout == second.stdout
    assert first.stdout.splitlines() == SESSION_TABLE


def test_an_ordinal_resolves_by_lookup_against_its_own_round(tmp_path):
    """AC-5. F2 of round 1 and F2 of round 2 are different findings, and no
    conversation is read to tell them apart."""
    project, record, args, _ = _session(tmp_path)
    stored = {f["key"]: f for f in json.loads(record.read_text())["findings"]}
    assert stored["customers:test_cannot_hold"]["ordinals"] == {"1": "F2"}
    assert stored["customers.profit_segment:doc_mismatch"]["ordinals"] == {"2": "F2"}

    one = _run(
        ["decide", "F2", "--round", "1", "--state", "deferred",
         "--note", "Named against round one."] + args
    )
    two = _run(
        ["decide", "F2", "--round", "2", "--state", "deferred",
         "--note", "Named against round two."] + args
    )

    assert "DECIDED=customers:test_cannot_hold" in one.stdout
    assert "DECIDED=customers.profit_segment:doc_mismatch" in two.stdout
    # A number the named round never printed is an error, not a near miss.
    missing = _run(
        ["decide", "F9", "--round", "1", "--state", "deferred", "--note", "Nope."] + args
    )
    assert missing.returncode == 2
    assert "round 1 printed no F9" in missing.stderr


def test_a_version_1_record_is_not_read(tmp_path):
    """The block gained a field, so a record written before it cannot be read."""
    project, record, args, _ = _session(tmp_path)
    assert _run(["pr-table"] + args).returncode == 0

    stale = json.loads(record.read_text())
    stale["version"] = 1
    record.write_text(json.dumps(stale))

    result = _run(["pr-table"] + args)

    assert result.returncode == 2
    assert "ERROR=no findings record for this branch" in result.stderr


def test_decide_on_a_verified_finding_takes_accepted_only(tmp_path):
    """Nothing is owed on a finding the reviewer settled, so `deferred` and
    `fixed` are refused. `accepted` is the developer agreeing with it out loud,
    which is a decision and earns a row."""
    project = _project(tmp_path)
    record = tmp_path / "record.json"
    args = ["--record", str(record), "--project-dir", str(project)]
    _run(["write"] + args, stdin=ROUND_1)
    verified = "customers.customer_lifetime_value:value_shift"
    before = record.read_text()

    for state in ("deferred", "fixed"):
        refused = _run(["decide", verified, "--state", state,
                        "--note", "Something is owed here."] + args)
        assert refused.returncode == 2, state
        assert "Only --state accepted applies" in refused.stderr, state
    assert record.read_text() == before, "a refused decision was written anyway"

    allowed = _run(["decide", verified, "--state", "accepted",
                    "--note", "Intended. The restriction is the point of the change."]
                   + args)

    assert allowed.returncode == 0, allowed.stderr
    stored = {f["key"]: f for f in json.loads(record.read_text())["findings"]}
    assert stored[verified]["decision"]["state"] == "accepted"
    # It reaches the table even though its group is verified.
    assert "CLV moved on 12 of 998 customers" in _run(["pr-table"] + args).stdout


def test_decide_refuses_a_target_it_cannot_resolve(tmp_path):
    """A wrong key or a word that is neither is an error, not a guess."""
    project = _project(tmp_path)
    record = tmp_path / "record.json"
    args = ["--record", str(record), "--project-dir", str(project)]
    _run(["write"] + args, stdin=ROUND_1)
    before = record.read_text()

    shapeless = _run(["decide", "the-doc-one", "--state", "accepted",
                      "--note", "Intended."] + args)
    unknown = _run(["decide", "customers.clv:join_shape", "--state", "accepted",
                    "--note", "Intended."] + args)

    assert shapeless.returncode == 2
    assert "neither F<n> nor a model[.column]:concern key" in shapeless.stderr
    assert unknown.returncode == 2
    assert "no finding with key" in unknown.stderr
    assert record.read_text() == before

    named = _run(["decide", "customers.customer_lifetime_value:doc_mismatch",
                  "--state", "accepted", "--note", "Intended."] + args)
    assert named.returncode == 0, named.stderr


def test_a_note_that_would_break_the_row_is_refused(tmp_path):
    """One note is one markdown cell, so a pipe or an essay is rejected."""
    project = _project(tmp_path)
    record = tmp_path / "record.json"
    args = ["--record", str(record), "--project-dir", str(project)]
    _run(["write"] + args, stdin=ROUND_1)
    before = record.read_text()

    piped = _run(
        ["decide", "F1", "--state", "accepted", "--note", "Intended | as it is"] + args
    )
    too_long = _run(
        ["decide", "F1", "--state", "accepted",
         "--note", "x" * (findings.NOTE_MAX + 1)] + args
    )
    # Whitespace only: the cell would be blank where the grounds belong.
    blank = _run(["decide", "F1", "--state", "accepted", "--note", "   \n  "] + args)

    assert piped.returncode == 2
    assert "breaks the PR table row" in piped.stderr
    assert too_long.returncode == 2
    assert "one table cell holds" in too_long.stderr
    assert blank.returncode == 2
    assert "--note is empty" in blank.stderr
    assert record.read_text() == before, "a refused note was written anyway"

    fits = _run(
        ["decide", "F1", "--state", "accepted", "--note", "x" * findings.NOTE_MAX] + args
    )
    assert fits.returncode == 0, fits.stderr
    # A newline in an otherwise good note is folded, not rejected.
    folded = _run(
        ["decide", "F1", "--state", "accepted", "--note", "Intended.\nIt stays."] + args
    )
    assert folded.returncode == 0, folded.stderr
    kept = {f["key"]: f for f in json.loads(record.read_text())["findings"]}
    assert (
        kept["customers.customer_lifetime_value:doc_mismatch"]["decision"]["note"]
        == "Intended. It stays."
    )


def test_a_decision_does_not_survive_the_finding_coming_back(tmp_path):
    """The answer was about a state of the tree that no longer holds."""
    project = _project(tmp_path)
    record = tmp_path / "record.json"
    args = ["--record", str(record), "--project-dir", str(project)]
    _run(["write"] + args, stdin=ROUND_1)
    _run(
        ["decide", "F2", "--state", "accepted",
         "--note", "The nulls are pre-existing rows the new filter does not reach."]
        + args
    )
    # Round 2 stops reporting it; round 3 reports it again.
    _run(["write"] + args, stdin=ROUND_2_WITHOUT_NULLS)
    _run(["write"] + args, stdin=ROUND_1)

    back = {f["key"]: f for f in json.loads(record.read_text())["findings"]}[
        "customers.customer_lifetime_value:null_introduced"
    ]
    assert back["decision"] is None
    assert back["ordinals"] == {"1": "F2", "3": "F2"}


def test_an_accepted_finding_the_reviewer_drops_is_not_a_fix(tmp_path):
    """Step 6 would otherwise say five of five were fixed, about three nobody
    touched."""
    project, record, args, round_2 = _session(tmp_path)

    assert "RESOLVED=2" in round_2.stdout
    resolved = [
        line[len("RESOLVED_KEY="):]
        for line in round_2.stdout.splitlines()
        if line.startswith("RESOLVED_KEY=")
    ]
    assert sorted(resolved) == [
        "customers.customer_lifetime_value:doc_mismatch",
        "customers.customer_lifetime_value:null_introduced",
    ]
