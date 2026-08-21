#!/usr/bin/env python3
"""findings.py -- Carry review findings from one /recce-dev-review round to the next.

The reviewer agent runs in an isolated context, so without a record on disk
every round re-derives the same findings and reports them all again. The
developer then re-reads what they already accepted. This script is the record.

It owns the shape of that record, and of the block the agent emits. Nothing
else defines it: the validation here is the specification, and a rejection
prints the expected form. A separate schema or template file could not be
enforced (plugin scripts cannot assume `pip install`) and would go stale.

Args:    read  [--record PATH] [--project-dir PATH]
         write [--record PATH] [--project-dir PATH] [--session-id ID]
         concerns

Stdin:   write only. The agent's output, or just its block. The fenced
         ```recce-findings block is extracted from whatever is given, so the
         caller does not have to cut it out first.

         A review that finds nothing writes a block holding the single word
         `none`. An empty block is an error, because a forgotten block looks
         exactly like an all-fixed round, and the two must not be confused: one
         should be reported as a success, the other loudly as a fault.

         An open finding carries an ordinal, F1..Fn with no gap and no
         repeat. A verified finding carries "-", because the summary never
         prints a number for one.

         The ordinal is a position in one round's list, not a name. Sorting the
         list again moves the numbers, so nothing compares ordinals between
         rounds. It is stored only so a reply in the same sitting can say "F2"
         and be understood. `key` is what identifies a finding over time.

Stdout:  read      PRIOR_ROUND=<n>
                   <group> <key> <file>        (one per live prior finding)
                   CONCERNS=<comma separated>
         write     ROUND=<n> FINDINGS=<n> NEW=<n> CARRIED=<n>
                   RETURNED=<n> RESOLVED=<n>
                   RESOLVED_KEY=<key>          (one per newly resolved finding)
                   RETURNED_KEY=<key>          (one per finding that came back)
         concerns  CONCERNS=<comma separated>

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

Deleting a resolved finding would make the fourth case impossible to see: the
same problem coming back would be indistinguishable from a first sighting, for
ever, including for any display written later. `read` lists live findings only,
so the reviewer's view is unchanged by the ones being kept.

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
RECORD_VERSION = 1

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

GROUPS = ("open", "verified")
# A review that found nothing says so, rather than sending an empty block. An
# empty block stays an error: it is what a forgotten block looks like.
NO_FINDINGS = "none"
ORDINAL_RE = re.compile(r"^F(\d+)$")
NO_ORDINAL = "-"
MODEL_RE = re.compile(r"^[A-Za-z_][\w]*(\.[A-Za-z_][\w]*)?$")
BLOCK_RE = re.compile(r"^```recce-findings\s*$(.*?)^```\s*$", re.MULTILINE | re.DOTALL)

EXPECTED = """Expected form, one line per finding:

  <ordinal> <group> <model[.column]:concern> <file>

  ordinal   F1, F2, ... for an open finding: exactly F1..Fn, no gap, no
            repeat. "-" for a verified one, which is never numbered in the
            summary. A number on a verified line is an error
  group     open | verified
  concern   one of: {concerns}
  file      path relative to the project root, and it must exist

Wrapped in a fence:

  ```recce-findings
  F1 open customers.customer_lifetime_value:doc_mismatch models/schema.yml
  - verified stg_payments.coupon_amount:schema_add models/staging/stg_payments.sql
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


def validate(lines, project_dir):
    """Return (findings, errors). findings is empty when errors is not."""
    findings, errors, seen = [], [], {}
    for lineno, raw in lines:
        parts = raw.split()
        if len(parts) != 4:
            errors.append(
                "line %d: %d fields, expected 4 -- %r" % (lineno, len(parts), raw)
            )
            continue
        ordinal, group, key, path = parts
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
                # Stored as None rather than "-" so the record says "no number"
                # instead of carrying a placeholder that reads like one.
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


def cmd_write(args):
    project_dir = args.project_dir
    path = args.record or record_path(project_dir)
    branch = current_branch(project_dir)

    lines, error = parse_block(sys.stdin.read())
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
        if was is None:
            new_count += 1
            finding["first_seen"] = round_number
            finding["first_seen_at"] = now
        else:
            finding["first_seen"] = was["first_seen"]
            # None when the prior record predates timestamps. Filling it with
            # the current time would claim this round first saw it.
            finding["first_seen_at"] = was.get("first_seen_at")
            if was.get("last_seen") == prior_round:
                carried += 1
            elif was_open(was):
                returned.append(finding["key"])
            else:
                # Known to the record, and it was never open, so nothing was
                # fixed and nothing came back. Not news.
                carried += 1
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
        if was.get("last_seen") == prior_round and was_open(was):
            resolved.append(key)
        # Drop the ordinal. It pointed at a position in the round that
        # reported it, and this round has given that number to something else.
        merged.append(dict(was, ordinal=None))

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
    return 0


def cmd_concerns(args):
    print("CONCERNS=%s" % ",".join(CONCERNS))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for name, handler in (("read", cmd_read), ("write", cmd_write)):
        child = sub.add_parser(name)
        child.add_argument("--record", default=None)
        child.add_argument("--project-dir", default=os.getcwd())
        if name == "write":
            child.add_argument("--session-id", default="")
        child.set_defaults(handler=handler)
    sub.add_parser("concerns").set_defaults(handler=cmd_concerns)

    args = parser.parse_args(argv)
    args.project_dir = os.path.abspath(args.project_dir)
    return args.handler(args)


if __name__ == "__main__":
    sys.exit(main())
