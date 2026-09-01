#!/usr/bin/env python3
"""findings.py -- Carry review findings from one /recce-dev-review round to the next.

The reviewer agent runs in an isolated context, so without a record on disk
every round re-derives the same findings and reports them all again. The
developer then re-reads what they already accepted. This script is the record.

It owns the shape of that record, and of the block the agent emits. Nothing
else defines it: the validation here is the specification, and a rejection
prints the expected form. A separate schema or template file could not be
enforced (plugin scripts cannot assume `pip install`) and would go stale.

Args:    read     [--record PATH] [--project-dir PATH]
         write    [--record PATH] [--project-dir PATH] [--session-id ID]
         decide   <F<n>|key> --state STATE --note TEXT [--round N]
                  [--record PATH] [--project-dir PATH]
         pr-table [--record PATH] [--project-dir PATH]
         concerns
         match-checks --existing PATH

Stdin:   write and match-checks. The agent's output, or just its block. The fenced
         ```recce-findings block is extracted from whatever is given, so the
         caller does not have to cut it out first.

         A second block, ```recce-check-params, carries the (type, params) of
         the diff call that produced each finding. It is optional: five of the
         ten concerns are read from code and no diff re-runs them. The reviewer
         creates the check itself during the round, so what is stored here is
         the record of which check backs which finding.

         A review that finds nothing writes a block holding the single word
         `none`. An empty block is an error, because a forgotten block looks
         exactly like an all-fixed round, and the two must not be confused: one
         should be reported as a success, the other loudly as a fault.

         An open finding carries an ordinal, F1..Fn with no gap and no
         repeat. A verified finding carries "-", because the summary never
         prints a number for one. Every finding also carries a title: the
         Finding cell the summary printed for it, so no later step has to
         read the title back out of the conversation.

         The ordinal is a position in one round's list, not a name. Sorting
         the list again moves the numbers, so nothing compares ordinals
         between rounds. Each round's ordinal is kept under its own round
         number, which is what lets `decide F2 --round 2` mean one finding
         and `decide F2 --round 1` mean another. `key` is what identifies a
         finding over time.

Stdout:  read      PRIOR_ROUND=<n>
                   <group> <key> <file>        (one per live prior finding)
                   CONCERNS=<comma separated>
         write     ROUND=<n> FINDINGS=<n> NEW=<n> CARRIED=<n>
                   RETURNED=<n> RESOLVED=<n>
                   RESOLVED_KEY=<key>          (one per newly resolved finding)
                   RETURNED_KEY=<key>          (one per finding that came back)
                   NO_CHECK_PARAMS=<n>
                   DROPPED_CHECK_PARAMS=<n>
                   DROPPED_CHECK_PARAMS_KEY=<key>
                                               (one per line the concern guard
                                               dropped; the round is still
                                               written)
         decide    DECIDED=<key>
                   STATE=<state>
         pr-table  the finished markdown table, then any note lines
         concerns  CONCERNS=<comma separated>
         match-checks
                   CREATE=<key> <type> <params>   (no check covers it yet)
                   SKIP=<key> <check_id>          (this check already does)

Exit:    0 on success. 2 when a block fails validation, and then nothing is
         written -- a half-written record is worse than none, because next
         round would report live findings as resolved.

A finding never leaves the record. Its state is derived from `last_seen`
against the round number, so no field stores it:

    absent from the record, in the block          -> new
    last_seen == prior round, in the block        -> carried
    last_seen == prior round, not in the block    -> resolved, reported once
    last_seen <  prior round, in the block        -> returned, it came back
    last_seen <  prior round, not in the block    -> still resolved, silent

`resolved` and `returned` are reported for findings that were **open**. Only an
open finding is something the developer acts on, so only an open one can be
fixed or come back. A verified finding that stops being reported is not a fix:
the column is still there, the agent just did not repeat it. Reporting that as
resolved is noise the developer cannot act on, and it was doing so.

An accepted or deferred finding that stops being reported is not a fix either.
The developer said it stays, and the reviewer has stopped repeating it, which
is the record doing its job. Only `fixed` and undecided findings can be
resolved.

Deleting a resolved finding would make the fourth case impossible to see: the
same problem coming back would be indistinguishable from a first sighting, for
ever, including for any display written later. `read` lists live findings only,
so the reviewer's view is unchanged by the ones being kept.

`decide` and `pr-table` are the PR side of the same record. `decide` stores
what the developer said about one finding at the moment they say it, while the
round that printed the number is still on screen. `pr-table` prints the
finished markdown, so one record always gives one table and no agent composes
any part of it.

A fix is visible in the diff and a decision is not, so `pr-table` prints the
decisions and leaves the fixes out. `fixed` is therefore a way of saying "drop
this row", not a claim that the fix landed: nothing in this script reads the
tree. A finding nobody decided is neither a fix nor a decision, so it goes
under the table on a note line rather than into a row. Hiding it would lose an
open problem, and giving it a row would put an empty cell exactly where the
grounds belong.

A decision owns its row from the round it was made in, whatever group a later
round gives the finding. The group only decides what happens to a finding
nobody has spoken about: an open one goes on the note line, and a verified one
is not printed at all, because it needs no decision from anyone. A verified
finding can still be `accepted` -- that is the developer agreeing with it out
loud -- but not `deferred` or `fixed`, because nothing is owed on one the
reviewer already settled.

The three state words never reach the output. They select which findings get a
row; the note is what the reader sees, and it says what was decided in prose.

Round numbers drive every comparison above, because ordering is all the
comparison needs and integers cannot drift. Timestamps are stored alongside
them as information, not mechanism. A round number cannot answer "how old is
this finding", and the time it happened cannot be recovered afterwards, so it
is written even though nothing displays it yet. A finding carried over from a
record written before timestamps existed has `first_seen_at: null`, which says
unknown rather than inventing a time.
"""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone

# Same scheme as _project-hash.sh in this directory, and as the two copies
# named in its header comment. Four places now derive this hash; change them
# together.
RECORD_DIR = "/tmp"
RECORD_VERSION = 2

# Closed list. A finding's identity across rounds is model[.column]:concern, so
# two rounds must name the same problem the same way -- an invented word never
# matches next round. Add a word here rather than inline.
CONCERNS = [
    "value_shift",  # existing values changed
    "row_count_shift",  # the row count moved
    "schema_add",  # a column or model was added
    "schema_drop",  # a column was dropped or retyped
    "null_introduced",  # nulls appear where there were none
    "doc_mismatch",  # the code disagrees with its documentation or stated intent
    "test_cannot_hold",  # a test the model's own shape cannot satisfy
    "dead_filter",  # a filter or branch that excludes nothing
    "join_shape",  # join grain, or an ON / WHERE placement
    "unexplained",  # measured, cause not determined
]

# The five concerns read from code or documentation. create_check's type is one
# of eight diff types, and none of them re-runs a claim about a document, a
# test, a filter, a join grain, or a cause nobody determined. A check built from
# one of these measures something the finding never measured.
NO_CHECK_CONCERNS = (
    "doc_mismatch",
    "test_cannot_hold",
    "dead_filter",
    "join_shape",
    "unexplained",
)

GROUPS = ("open", "verified")

# What the developer decided about an open finding. The record had no room for
# this, so an accepted finding had to sit in `open` and be re-read every round,
# or be called `verified`, which claims a fix that never happened.
#
# `fixed` means "leave this out of the PR table", because the diff already
# shows it. It is not a check that the fix landed: nothing here reads the tree.
DECISIONS = ("accepted", "deferred", "fixed")
# The states that reach a row. `fixed` is the one that does not, because the
# diff already carries it. None of these words is ever printed: the note says
# what was decided, in prose.
IN_TABLE = ("accepted", "deferred")
# A note is one markdown table cell, so it is one line and it is short.
NOTE_MAX = 200
# A review that found nothing says so, rather than sending an empty block. An
# empty block stays an error: it is what a forgotten block looks like.
NO_FINDINGS = "none"
ORDINAL_RE = re.compile(r"^F(\d+)$")
NO_ORDINAL = "-"
MODEL_RE = re.compile(r"^[A-Za-z_][\w]*(\.[A-Za-z_][\w]*)?$")
BLOCK_RE = re.compile(r"^```recce-findings\s*$(.*?)^```\s*$", re.MULTILINE | re.DOTALL)
CHECK_BLOCK_RE = re.compile(
    r"^```recce-check-params\s*$(.*?)^```\s*$", re.MULTILINE | re.DOTALL
)
# The eight types create_check accepts. A type outside this list is refused by
# the server, and on the cloud path only after the run has been paid for, so it
# is refused here first.
CHECK_TYPES = (
    "row_count_diff",
    "schema_diff",
    "query_diff",
    "profile_diff",
    "value_diff",
    "value_diff_detail",
    "top_k_diff",
    "histogram_diff",
)

EXPECTED = """Expected form, one line per finding:

  <ordinal> <group> <model[.column]:concern> <file> <title>

  ordinal   F1, F2, ... for an open finding: exactly F1..Fn, no gap, no
            repeat. "-" for a verified one, which is never numbered in the
            summary. A number on a verified line is an error
  group     open | verified
  concern   one of: {concerns}
  file      path relative to the project root, and it must exist
  title     the Finding cell this round printed, running to the end of the
            line. The PR table prints it, so no later step has to read it
            back out of the summary. It must not contain "|"

Wrapped in a fence:

  ```recce-findings
  F1 open customers.customer_lifetime_value:doc_mismatch models/schema.yml CLV documentation omits the completed-orders restriction
  - verified stg_payments.coupon_amount:schema_add models/staging/stg_payments.sql coupon_amount is a new column
  ```

When the review found nothing at all, the whole block is one word:

  ```recce-findings
  none
  ```"""


def utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def record_path(project_dir):
    digest = hashlib.md5(project_dir.encode()).hexdigest()[:8]
    return os.path.join(RECORD_DIR, "recce-findings-%s.json" % digest)


def current_branch(project_dir):
    try:
        out = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return out.stdout.strip() if out.returncode == 0 else ""


def load_record(path, project_dir, branch):
    """Return the prior record, or None when it cannot be trusted.

    An unreadable record is treated as absent rather than fatal: a review must
    still run. A record from another project or another branch is about models
    the developer is not touching, so it is discarded too.
    """
    try:
        with open(path) as fh:
            record = json.load(fh)
    except (OSError, ValueError):
        return None
    if not isinstance(record, dict) or record.get("version") != RECORD_VERSION:
        return None
    if record.get("project") != project_dir:
        return None
    if branch and record.get("branch") not in (branch, None):
        return None
    if not isinstance(record.get("findings"), list):
        return None
    return record


def parse_block(text):
    """Pull the finding lines out of the agent's output.

    Accepts the whole summary or a bare block. Returns (lines, error) where
    lines are (lineno, raw) pairs, numbered within the block.
    """
    match = BLOCK_RE.search(text)
    # The captured group opens with the newline that ended the fence line, so
    # strip it: otherwise every reported line number is one too high.
    body = match.group(1).lstrip("\n") if match else text
    if not match and "```" in text:
        return [], "a fence is present but no ```recce-findings block was found"
    lines = []
    for offset, raw in enumerate(body.splitlines(), start=1):
        if raw.strip():
            lines.append((offset, raw.strip()))
    if len(lines) == 1 and lines[0][1] == NO_FINDINGS:
        return [], None
    if not lines:
        return [], (
            "the block is empty. A review that found nothing writes %r; an "
            "empty block is what a forgotten block looks like" % NO_FINDINGS
        )
    return lines, None


def parse_check_params(text):
    """Pull the (key, type, params) lines out of the agent's second block.

    The block is optional. A review whose findings all come from code has no
    diff call to record, and five of the ten concerns can never have one --
    a line for one of those is an error, not an omission, because the check it
    would build is permanent and measures something else.

    Returns (mapping, errors, refused), keyed by finding key. `refused` holds
    the lines the concern guard rejected, as (key, concern) pairs. They are
    separate from `errors` because the two callers owe them different answers:
    `match-checks` runs before any check exists and must stop, while `write`
    runs after and must keep the round.
    """
    match = CHECK_BLOCK_RE.search(text)
    if not match:
        return {}, [], []
    return check_param_lines(match.group(1))


def check_param_lines(body):
    """Parse the body of a check-params block. See parse_check_params."""
    mapping, errors, refused = {}, [], []
    for offset, raw in enumerate(body.lstrip("\n").splitlines(), start=1):
        raw = raw.strip()
        if not raw:
            continue
        # Two splits only: params is JSON and owns the rest of the line.
        parts = raw.split(None, 2)
        if len(parts) != 3:
            errors.append(
                "check-params line %d: %d fields, expected 3 -- %r"
                % (offset, len(parts), raw)
            )
            continue
        key, check_type, blob = parts
        concern = key.rsplit(":", 1)[-1] if ":" in key else ""
        if concern in NO_CHECK_CONCERNS:
            refused.append((key, concern))
            continue
        if check_type not in CHECK_TYPES:
            errors.append(
                "check-params line %d: type %r is not one create_check accepts"
                % (offset, check_type)
            )
            continue
        try:
            params = json.loads(blob)
        except ValueError as exc:
            errors.append(
                "check-params line %d: params is not JSON -- %s" % (offset, exc)
            )
            continue
        if not isinstance(params, dict):
            errors.append("check-params line %d: params must be an object" % offset)
            continue
        if key in mapping:
            errors.append("check-params line %d: key %r already given" % (offset, key))
            continue
        mapping[key] = {"type": check_type, "params": params}
    return mapping, errors, refused


def fold(value):
    """Lowercase every string inside a params value, leaving structure alone."""
    if isinstance(value, str):
        return value.lower()
    if isinstance(value, list):
        return [fold(item) for item in value]
    if isinstance(value, dict):
        return dict((key, fold(item)) for key, item in value.items())
    return value


def check_matches(candidate, existing):
    """Is `existing` already the check `candidate` describes?

    Same type, and every param the candidate names is on the existing check
    with the same value. Two allowances, both from what the live data does:

    - Case is ignored. Snowflake returns column names uppercased, so a
      candidate built from the model's SQL says `value_segment` where the
      check on the session says `VALUE_SEGMENT`. They are one column.
    - Keys only the existing check has are ignored. Recce's preset checks
      carry extras such as `k`, which narrow the same comparison rather than
      make it a different one.

    Equality key for key fails both, and the cost of that failure is a second
    permanent check plus the warehouse query that creates it.

    A candidate with no params matches nothing: it names no comparison, so
    "the same one" cannot be true of it.
    """
    if candidate.get("type") != existing.get("type"):
        return False
    want = candidate.get("params") or {}
    have = existing.get("params") or {}
    if not want:
        return False
    for key, value in want.items():
        if key not in have or fold(have[key]) != fold(value):
            return False
    return True


def cmd_match_checks(args):
    text = sys.stdin.read()
    if CHECK_BLOCK_RE.search(text):
        candidates, errors, refused = parse_check_params(text)
    else:
        candidates, errors, refused = check_param_lines(text)
    try:
        with open(args.existing) as fh:
            listed = json.load(fh)
    except (OSError, ValueError) as exc:
        print("ERROR=cannot read %r -- %s" % (args.existing, exc), file=sys.stderr)
        return 2
    if isinstance(listed, dict):
        listed = listed.get("checks", [])
    if not isinstance(listed, list):
        print("ERROR=%r holds no list of checks" % args.existing, file=sys.stderr)
        return 2
    # Refusals stop this call. It runs before any create_check, so stopping
    # here is what keeps a check that should never exist from being made.
    for key, concern in refused:
        errors.append(
            "%r is a %s finding. No diff type re-runs one, so it gets no check"
            % (key, concern)
        )
    if errors:
        for message in errors:
            print("ERROR=%s" % message, file=sys.stderr)
        return 2
    for key in sorted(candidates):
        candidate = candidates[key]
        match = next((c for c in listed if check_matches(candidate, c)), None)
        if match:
            print("SKIP=%s %s" % (key, match.get("check_id", "")))
        else:
            print(
                "CREATE=%s %s %s"
                % (
                    key,
                    candidate["type"],
                    json.dumps(candidate["params"], separators=(",", ":")),
                )
            )
    return 0


def validate(lines, project_dir):
    """Return (findings, errors). findings is empty when errors is not."""
    findings, errors, seen = [], [], {}
    for lineno, raw in lines:
        # The title runs to the end of the line, so it is split off last and it
        # is the only field that may contain a space.
        parts = raw.split(None, 4)
        if len(parts) != 5:
            errors.append(
                "line %d: %d fields, expected 5 -- %r" % (lineno, len(parts), raw)
            )
            continue
        ordinal, group, key, path, title = parts
        if group == "verified":
            if ordinal != NO_ORDINAL:
                errors.append(
                    "line %d: ordinal %r on a verified finding. Use %r: the "
                    "summary never numbers a verified bullet"
                    % (lineno, ordinal, NO_ORDINAL)
                )
        elif not ORDINAL_RE.match(ordinal):
            errors.append(
                "line %d: ordinal %r is not F<n>. An open finding needs a "
                "number, because the summary prints one" % (lineno, ordinal)
            )
        if group not in GROUPS:
            errors.append(
                "line %d: group %r is not %s" % (lineno, group, " or ".join(GROUPS))
            )
        if key.count(":") != 1:
            errors.append("line %d: key %r needs exactly one colon" % (lineno, key))
        else:
            model, concern = key.split(":")
            if not MODEL_RE.match(model):
                errors.append(
                    "line %d: %r is not a model or model.column" % (lineno, model)
                )
            if concern not in CONCERNS:
                errors.append("line %d: concern %r is not in the list" % (lineno, concern))
        if os.path.isabs(path) or ".." in path.split("/"):
            errors.append("line %d: file %r must be inside the project" % (lineno, path))
        elif not os.path.isfile(os.path.join(project_dir, path)):
            errors.append("line %d: file %r does not exist" % (lineno, path))
        if "|" in title:
            errors.append(
                "line %d: title %r contains '|', which breaks the PR table row"
                % (lineno, title)
            )
        if key in seen:
            errors.append(
                "line %d: key %r already given on line %d" % (lineno, key, seen[key])
            )
        else:
            seen[key] = lineno
        findings.append(
            {
                "key": key,
                "group": group,
                "file": path,
                "title": title,
                # None rather than "-" so this says "no number" instead of
                # carrying a placeholder that reads like one. cmd_write files
                # it under this round's number and drops the field.
                "ordinal": None if ordinal == NO_ORDINAL else ordinal,
            }
        )

    # F1..Fn exactly, over the open findings only. One check catches a gap, a
    # repeat and an off-by-one start, and each of those breaks the mapping from
    # a number the reader saw to the finding it named.
    open_count = sum(1 for f in findings if f["group"] == "open")
    matches = (ORDINAL_RE.match(f["ordinal"] or "") for f in findings)
    numbers = sorted(int(m.group(1)) for m in matches if m)
    if not errors and numbers != list(range(1, open_count + 1)):
        errors.append(
            "open ordinals are %s, expected F1..F%d with no gap and no repeat"
            % (", ".join("F%d" % n for n in numbers) or "(none)", open_count)
        )
    return ([], errors) if errors else (findings, [])


def cmd_read(args):
    project_dir = args.project_dir
    branch = current_branch(project_dir)
    record = load_record(args.record or record_path(project_dir), project_dir, branch)
    if record is None:
        print("PRIOR_ROUND=0")
    else:
        prior_round = record.get("round", 0)
        print("PRIOR_ROUND=%d" % prior_round)
        # Live only. A resolved finding is kept in the record, but showing it
        # here would invite the reviewer to report something already fixed.
        for finding in record["findings"]:
            if finding.get("last_seen") == prior_round:
                print("%-8s %s %s" % (finding["group"], finding["key"], finding["file"]))
    # Printed on every round, including the first: the agent needs the words to
    # build its keys even when there is no prior round to compare against.
    print("CONCERNS=%s" % ",".join(CONCERNS))
    return 0


def resolve_target(record, target, round_number):
    """Return (finding, None), or (None, message) when the target does not fit.

    A key names a finding directly. An ordinal names a position in one round's
    list, so it means nothing without the round: F2 of round 1 and F2 of round
    2 are different findings, and the record holds both numbers.
    """
    if ":" in target:
        for finding in record["findings"]:
            if finding["key"] == target:
                return finding, None
        return None, "no finding with key %r in the record" % target
    if not ORDINAL_RE.match(target):
        return None, "%r is neither F<n> nor a model[.column]:concern key" % target
    matched = [
        finding
        for finding in record["findings"]
        if (finding.get("ordinals") or {}).get(str(round_number)) == target
    ]
    if len(matched) == 1:
        return matched[0], None
    if not matched:
        return None, "round %d printed no %s" % (round_number, target)
    # Only reachable on a hand-edited record: validate() rejects a repeat.
    return None, "round %d has %d findings numbered %s" % (
        round_number, len(matched), target
    )


def cmd_decide(args):
    """Store what the developer decided about one finding.

    Called in-round, by the review skill, right after the developer answers.
    The reason for a decision exists only in that answer, and a later step
    reconstructing it from the conversation is what this replaces.
    """
    project_dir = args.project_dir
    path = args.record or record_path(project_dir)
    record = load_record(path, project_dir, current_branch(project_dir))
    if record is None:
        print("ERROR=no findings record for this branch", file=sys.stderr)
        return 2

    # One table cell holds one line, so a newline is folded rather than
    # rejected: the caller's text is fine, its shape is not.
    note = " ".join(args.note.split())
    if not note:
        print("ERROR=--note is empty. The cell it fills is the only thing a "
              "reviewer can disagree with", file=sys.stderr)
        return 2
    if "|" in note:
        print("ERROR=the note contains '|', which breaks the PR table row",
              file=sys.stderr)
        return 2
    if len(note) > NOTE_MAX:
        print("ERROR=the note is %d characters and one table cell holds %d"
              % (len(note), NOTE_MAX), file=sys.stderr)
        return 2

    # No --round means the newest one, which is what a reply in this sitting
    # means. An older round has to be named.
    round_number = record.get("round", 0) if args.round is None else args.round
    finding, error = resolve_target(record, args.target, round_number)
    if error:
        print("ERROR=%s" % error, file=sys.stderr)
        return 2
    # `accepted` means "this is fine as it is", which is exactly what a
    # developer says about a verified finding. `fixed` and `deferred` both
    # claim work is owed, and nothing is owed on one the reviewer settled.
    if finding.get("group") != "open" and args.state != "accepted":
        print("ERROR=%s is verified. Only --state accepted applies to one, "
              "because nothing is owed on a finding the reviewer settled"
              % finding["key"], file=sys.stderr)
        return 2

    finding["decision"] = {
        "state": args.state,
        "note": note,
        "round": round_number,
        "at": utc_now(),
    }
    with open(path, "w") as fh:
        json.dump(record, fh, indent=2)
        fh.write("\n")
    print("DECIDED=%s" % finding["key"])
    print("STATE=%s" % args.state)
    return 0


def cmd_pr_table(args):
    """Print the PR table, finished. The whole product of /recce-pr-prep."""
    project_dir = args.project_dir
    record = load_record(
        args.record or record_path(project_dir),
        project_dir,
        current_branch(project_dir),
    )
    if record is None:
        print("ERROR=no findings record for this branch", file=sys.stderr)
        return 2
    current = record.get("round", 0)

    rows, undecided = [], []
    for finding in record["findings"]:
        decision = finding.get("decision") or {}
        state = decision.get("state")
        if state == "fixed":
            continue
        # A decision owns its row from the round it was made in. The group only
        # governs a finding nobody has spoken about, because the reviewer
        # reclassifying one the developer already settled is not the developer
        # changing their mind.
        if state not in IN_TABLE and finding.get("group") != "open":
            continue
        # Still-reported first, then by key. One record always prints one order.
        rank = (finding.get("last_seen") != current, finding["key"])
        if state in IN_TABLE:
            rows.append(rank + (finding["title"], decision["note"]))
        else:
            undecided.append(rank)
    rows.sort()
    undecided.sort()

    if rows:
        print("| Finding | Why |")
        print("|---|---|")
        for _, _, title, note in rows:
            print("| %s | %s |" % (title, note))
    else:
        print("No findings were decided on this branch.")

    def keys(stopped):
        return ", ".join("`%s`" % key for gone, key in undecided if gone == stopped)

    notes = []
    if keys(False):
        notes.append("Not decided, and round %d still reports these: %s."
                     % (current, keys(False)))
    if keys(True):
        notes.append("Not decided, and round %d does not report these: %s."
                     % (current, keys(True)))
    if notes:
        print()
        for line in notes:
            print(line)
    return 0


def cmd_write(args):
    project_dir = args.project_dir
    path = args.record or record_path(project_dir)
    branch = current_branch(project_dir)

    text = sys.stdin.read()
    lines, error = parse_block(text)
    if error:
        print("ERROR=%s" % error, file=sys.stderr)
        print(EXPECTED.format(concerns=", ".join(CONCERNS)), file=sys.stderr)
        return 2
    findings, errors = validate(lines, project_dir)
    if errors:
        for message in errors:
            print("ERROR=%s" % message, file=sys.stderr)
        print(EXPECTED.format(concerns=", ".join(CONCERNS)), file=sys.stderr)
        return 2

    check_params, param_errors, refused = parse_check_params(text)
    # A refused line is dropped, not fatal. By the time this runs the agent has
    # returned and any check it made already exists, so rejecting the block
    # would destroy this round's history over damage that match-checks either
    # prevented or did not. The dropped keys are printed so it is not silent.
    # A key here that no finding uses is a typo, and a typo silently drops the
    # params for the finding it meant. Catch it while the block is still
    # rejectable as a whole.
    named = {f["key"] for f in findings}
    for key in sorted(check_params):
        if key not in named:
            param_errors.append(
                "check-params: key %r is not a finding in this round" % key
            )
    if param_errors:
        for message in param_errors:
            print("ERROR=%s" % message, file=sys.stderr)
        return 2
    for finding in findings:
        # None when the finding was read from code, which is correct for five
        # of the ten concerns and never becomes a check.
        finding["check"] = check_params.get(finding["key"])

    prior = load_record(path, project_dir, branch)
    prior_findings = {f["key"]: f for f in prior["findings"]} if prior else {}
    prior_round = prior["round"] if prior else 0
    round_number = prior_round + 1

    now = utc_now()
    reported = {f["key"] for f in findings}
    # A finding is trackable if the record last saw it as open. Its group this
    # round does not decide that: a fix removes the line entirely, so there is
    # no current group to read.
    def was_open(entry):
        return entry.get("group") == "open"
    merged, new_count, carried, returned = [], 0, 0, []
    for finding in findings:
        was = prior_findings.get(finding["key"])
        ordinal = finding.pop("ordinal")
        finding["ordinals"] = {}
        finding["decision"] = None
        if was is None:
            new_count += 1
            finding["first_seen"] = round_number
            finding["first_seen_at"] = now
        else:
            finding["first_seen"] = was["first_seen"]
            # None when the prior record predates timestamps. Filling it with
            # the current time would claim this round first saw it.
            finding["first_seen_at"] = was.get("first_seen_at")
            # Every round's number for this finding, kept. "F2 of round 1" is
            # then a lookup, and a later round taking F2 costs nothing.
            finding["ordinals"] = dict(was.get("ordinals") or {})
            finding["decision"] = was.get("decision")
            if was.get("last_seen") == prior_round:
                carried += 1
            elif was_open(was):
                returned.append(finding["key"])
                # It was decided, then it came back. The decision answered a
                # state of the tree that no longer holds, so asking again is
                # better than carrying an answer to a question that changed.
                finding["decision"] = None
            else:
                # Known to the record, and it was never open, so nothing was
                # fixed and nothing came back. Not news.
                carried += 1
        if ordinal:
            finding["ordinals"][str(round_number)] = ordinal
        finding["last_seen"] = round_number
        finding["last_seen_at"] = now
        merged.append(finding)

    # Everything the block did not report stays in the record untouched. Only
    # the round it goes missing reports it, so last_seen is what makes the
    # difference between "resolved just now" and "resolved a while ago".
    resolved = []
    for key, was in prior_findings.items():
        if key in reported:
            continue
        # Accepted or deferred, and the reviewer stopped repeating it: that is
        # the decision working, not a fix. `fixed` still counts, because the
        # developer said the diff would carry it and the reviewer agrees.
        held = (was.get("decision") or {}).get("state") in ("accepted", "deferred")
        if was.get("last_seen") == prior_round and was_open(was) and not held:
            resolved.append(key)
        # Kept exactly as it is, decision included. Its numbers are filed under
        # the rounds that printed them, so this round giving F2 to something
        # else takes nothing away from it.
        merged.append(was)

    record = {
        "version": RECORD_VERSION,
        "project": project_dir,
        "branch": branch,
        "round": round_number,
        "session_id": args.session_id,
        "updated_at": now,
        "findings": merged,
    }
    with open(path, "w") as fh:
        json.dump(record, fh, indent=2)
        fh.write("\n")

    # FINDINGS counts what this round reported, not what the record holds --
    # the record also carries every finding already resolved.
    print("ROUND=%d" % round_number)
    print("FINDINGS=%d" % len(findings))
    print("NEW=%d" % new_count)
    print("CARRIED=%d" % carried)
    print("RETURNED=%d" % len(returned))
    print("RESOLVED=%d" % len(resolved))
    for key in resolved:
        print("RESOLVED_KEY=%s" % key)
    for key in returned:
        print("RETURNED_KEY=%s" % key)
    print("NO_CHECK_PARAMS=%d" % sum(1 for f in findings if f.get("check") is None))
    print("DROPPED_CHECK_PARAMS=%d" % len(refused))
    for key, _ in refused:
        print("DROPPED_CHECK_PARAMS_KEY=%s" % key)
    return 0


def cmd_concerns(args):
    print("CONCERNS=%s" % ",".join(CONCERNS))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for name, handler in (
        ("read", cmd_read),
        ("write", cmd_write),
        ("decide", cmd_decide),
        ("pr-table", cmd_pr_table),
    ):
        child = sub.add_parser(name)
        child.add_argument("--record", default=None)
        child.add_argument("--project-dir", default=os.getcwd())
        if name == "write":
            child.add_argument("--session-id", default="")
        if name == "decide":
            child.add_argument("target", help="F<n> from a round, or a finding key")
            child.add_argument("--state", choices=DECISIONS, required=True)
            child.add_argument("--note", required=True)
            child.add_argument("--round", type=int, default=None)
        child.set_defaults(handler=handler)
    sub.add_parser("concerns").set_defaults(handler=cmd_concerns)
    matcher = sub.add_parser("match-checks")
    matcher.add_argument("--existing", required=True)
    matcher.set_defaults(handler=cmd_match_checks, project_dir=os.getcwd())

    args = parser.parse_args(argv)
    args.project_dir = os.path.abspath(args.project_dir)
    return args.handler(args)


if __name__ == "__main__":
    sys.exit(main())
