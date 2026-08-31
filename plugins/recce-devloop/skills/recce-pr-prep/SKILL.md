---
name: recce-pr-prep
description: >
  Prepare the Recce part of a pull request. Reads this branch's review
  findings and what the developer decided about each one, and prints a
  markdown table to paste into the PR description. Triggers when: user is
  opening or creating a PR, is about to commit and push for a PR, asks to
  bring the Recce findings into the PR, asks what was decided about the
  findings, or asks for the findings table. Prints that table only — it
  does not write the PR description, does not open or edit a PR, and
  reviews nothing. To run a review, use /recce-dev-review.
---

# /recce-pr-prep — bring the review findings into your PR description

This is the PR-preparation step. A review has already run on this branch; this skill writes up what it found and what you decided, as markdown you paste into the PR description.

The record says whether a finding is still being reported. It cannot say what happened to one, and neither can the reviewer: it sees only the working tree, so it knows a finding is gone but never why. You know, and you said so in this conversation. This skill takes the findings from the record, the decisions from what you wrote, and prints one table.

**A finding nobody discussed gets no resolution.** Silence is not acceptance. A review summary caps at eight findings and collapses the rest onto one line, so a finding may never have been in front of you at all.

**This step records what you decided. It gathers no new information about the code or the data.** The record and this conversation are its only two inputs. Step 1's one command is the only command it runs — it does not read the models, run a query, check what a file says now, or call out to anything else. To have the code looked at, use `/recce-dev-review`.

**In particular, do not compare what you said against what the code currently says.** Listing which of the described fixes are or are not in the working tree is a check on the code, so it is outside this step even though it looks useful. If the code disagrees with a decision, a review finds that; this table does not.

Follow these steps in order.

---

## Step 1: Read the record

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/recce-dev-review/scripts/findings.py table
```

It prints `ROUND=<n>`, `SESSION_ID=<id>`, and one line per finding:

```
ROUND=2
SESSION_ID=c29669b4-64ea-4592-be99-0ae5d6f1cfb0
reported customers.customer_lifetime_value:doc_mismatch models/schema.yml - -
reported customers:value_shift models/customers.sql value_diff {"model":"customers","primary_key":"customer_id"}
stopped  customers.customer_lifetime_value:null_introduced models/customers.sql - -
```

- `reported` — the newest round reported it. `stopped` — an earlier round reported it and the newest one did not.
- The last two fields are the diff call the review measured that finding with. When the developer agreed to checks, `/recce-dev-review` made that call a check on the session named by `SESSION_ID=`. `-` means no diff re-runs that finding, so it never had one. The table below uses none of this: it is here so you can see which findings the Recce checklist can cover.
- Only findings the record last saw as **open** are listed. A verified finding needs no decision from anyone, so it is not in this output and not in the table.

**On `ROUND=0`** there is no usable record for this branch: no review has run here, or the record was written on another branch or before a reboot. Say one line and stop.

> There is no findings record for this branch, so there is nothing to write up. Run `/recce-dev-review` first.

Still-reported rows come first, then the stopped ones, and by key inside each. The rows are the whole table: do not add a finding the script did not print, and do not drop one.

---

## Step 2: Find the rounds in this conversation

Every `## Data Review Summary` in this conversation is one review round, in the order they appear. The last one is the newest.

For each round, note its `Open items` rows: the ordinal, the Finding cell, and the model and column its Evidence cell names. The Finding cell is the title this skill prints.

**An ordinal belongs to the round that printed it.** Every round numbers from `F1`, so `F2` in one round and `F2` in the next are different findings. When a message says `F2`, the round it means is the nearest `## Data Review Summary` **above** that message. Read the ordinal from that round's table and from nowhere else.

**Never take an ordinal from the record.** The record stores one and overwrites it every round, so matching against it attaches the resolution to whichever finding holds that number now. `findings.py table` prints no ordinal for this reason.

When `ROUND=` is higher than the number of summaries in this conversation, the earlier rounds ran in an earlier session. Their findings have no title and no words available here. Step 5 says so on the note line.

---

## Step 3: Match each finding to what was decided

Take the script's rows one at a time. For each, look for the developer's own words about that finding in this conversation:

- a message naming it by ordinal, resolved through Step 2
- a message naming its model, or its column
- a message answering a question that was asked about it

**Only the developer's words count.** What you said about a finding, and what the reviewer said about it, are not decisions about it. A resolution needs a sentence the developer wrote.

**A mention is not a decision.** "What is F2?" and "F2 is intended" both name F2, and only the second settles anything. When the words name the finding and decide nothing, that finding has no resolution.

**When two rows fit the same words, neither gets the resolution.** One model and column can carry several findings with different concerns. If the words do not say which one, leave both cells empty rather than picking one.

No claim without a citation, and here the citation is the sentence itself: it goes in the cell. Quote the developer's words. Cut to the sentence that carries the decision if you need to, and do not paraphrase, tidy, or complete it.

---

## Step 4: Print the table

One row per script row, in the order the script printed them.

```markdown
| Finding | Status | Resolution |
|---------|--------|------------|
| {Finding cell from the round that reported it} | {status} | {the developer's words, quoted} |
```

- **Finding** — the Finding cell from the round that reported it. When no round in this conversation reported it, print the key in backticks instead, and nothing else.
- **Resolution** — the quoted words, or empty.
- **Status** — one of three words, from the script's state and whether the resolution cell is filled:

| script row | resolution | Status | what it says |
|---|---|---|---|
| `reported` | empty | `still reported` | the newest round lists it, and this conversation says nothing about it |
| `reported` | filled | `discussed` | you wrote something about it |
| `stopped` | filled | `discussed` | you wrote something about it |
| `stopped` | empty | `no longer reported` | the newest round does not list it, and this conversation says nothing about it |

**`discussed` deliberately covers both middle rows.** Once you have written about a finding, the Status stops saying whether the newest round still lists it — your words in the Resolution cell are the more useful fact, and the reader has them right there. This was considered and chosen; do not split `discussed` into two words to recover the distinction.

Every finding in this table was reported at some point, which is why the first word is `still reported` and not `reported`.

Print the table, then the note lines in Step 5. **That table and those lines are the whole of this skill's product.** They are built from the findings record and this conversation, and they are the only part of any answer that is. Anything else an answer contains came from somewhere else, was not checked against those two inputs, and carries none of this skill's guarantees.

---

## Step 5: Say what the table cannot know

Under the table, print only the lines that apply:

- When `ROUND=` is higher than the number of summaries in this conversation: "The record is at round {ROUND} and this conversation holds {n} of them, so findings from the earlier rounds appear by key with no resolution."
- When any row is `stopped` with an empty resolution: "{n} findings stopped being reported and this conversation does not say why."

Then stop. Separately from gathering nothing, this step also **changes** nothing: do not commit, do not push, do not open or edit a PR, do not write the record, and do not run `dbt` — `dbt build` and `dbt run` write tables into the warehouse, and `dbt test` queries it. The table is markdown for you to paste; whether it becomes a PR body, a comment, or a file is your call.
