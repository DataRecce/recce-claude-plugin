---
name: recce-pr-prep
description: >
  Prepare the Recce part of a pull request. Prints this branch's review
  findings and what the developer decided about each one, as a markdown
  table to paste into the PR description. Triggers when: user is
  opening or creating a PR, is about to commit and push for a PR, asks to
  bring the Recce findings into the PR, asks what was decided about the
  findings, or asks for the findings table. Prints that table only — it
  does not write the PR description, does not open or edit a PR, and
  reviews nothing. To run a review, use /recce-dev-review.
---

# /recce-pr-prep — bring the review findings into your PR description

This is the PR-preparation step. A review has already run on this branch and you answered it round by round. This skill prints what you decided, as markdown you paste into the PR description.

**It prints the decisions and leaves out the fixes.** A fix is in the diff, and the reviewer sees it there. A decision is not in the diff. It is your judgment, the reviewer may disagree with it, and that makes it the part worth writing down.

**This step records what you decided. It gathers no new information about the code or the data.** The findings record is its only input. Step 1's one command is the only command it runs — it does not read the models, run a query, check what a file says now, or call out to anything else. To have the code looked at, use `/recce-dev-review`.

**In particular, do not compare what you said against what the code currently says.** Listing which of the described fixes are or are not in the working tree is a check on the code, so it is outside this step even though it looks useful. If the code disagrees with a decision, a review finds that; this table does not.

---

## Step 1: Print the table

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/recce-dev-review/scripts/findings.py pr-table
```

Its output is finished markdown. Print it unchanged: do not add a row, do not drop one, do not reword a cell, do not sort it differently, and do not add a column. Every row was decided in front of you during a review round, and the script reads it back from the record — so one record gives one table, and no part of it is written from memory of the conversation.

**On exit 2** the script prints one `ERROR=` line and there is nothing to write up. Say one line and stop.

> There is no findings record for this branch, so there is nothing to write up. Run `/recce-dev-review` first.

---

## Step 2: Stop

The script's output is **the whole of this skill's product**. It is built from the findings record, and it is the only part of any answer that is. Anything else an answer contains came from somewhere else, was not checked against the record, and carries none of this skill's guarantees.

**A finding under `Not decided` stays there.** Nobody said anything about it during the review, and silence is not acceptance. Do not write a decision for it now: this step has not looked at the code, so it has nothing to decide from. To settle it, run `/recce-dev-review` and answer it there.

Separately from gathering nothing, this step also **changes** nothing: do not commit, do not push, do not open or edit a PR, do not write the record, and do not run `dbt` — `dbt build` and `dbt run` write tables into the warehouse, and `dbt test` queries it. The table is markdown for you to paste; whether it becomes a PR body, a comment, or a file is your call.
