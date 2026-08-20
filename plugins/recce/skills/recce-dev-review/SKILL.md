---
name: recce-dev-review
description: >
  Review the dbt changes in the current working tree against the team's base in
  Recce Cloud. Uploads the local `target/` artifacts to a Cloud dev session,
  attaches the Recce MCP server to that session, and produces an impact report.
  Triggers when: user asks to review their local dbt changes through Recce
  Cloud, run a dev review, upload their working tree and review it, or review
  this branch against the cloud base. For a PR, MR, or an existing Cloud
  session URL, use /recce-review. For a quick single-environment read with no
  base at all, use /recce-verify.
---

# /recce-dev-review — Cloud dev-session review of the current working tree

This skill reviews **what is in the working tree right now**. It prepares a Recce Cloud dev session from the local `target/` artifacts, points the running MCP server at that session, and dispatches `recce-dev-reviewer` against it.

Recce Cloud holds a base maintained by CI. Uploading the current `target/` as a dev session turns this into a full base-vs-current diff with no local `target-base/`. The base is attached on the cloud side; it does not need naming.

Claude Code launches `recce mcp-server` (stdio) at session start in **local mode** and the same server stays alive for the whole session. Mode switching happens **inside** that running server via MCP tool calls — no reconnect, no restart.

Follow these steps in order.

---

## Step 0: Entry check

This skill owns one input: the current dbt project and its working tree.

If the user supplied a **GitHub PR URL, a GitLab MR URL, a Recce Cloud session or launch URL, or a bare session UUID**, that is a different journey — someone else's session already exists and nothing needs preparing. Say one line and stop:

> That's an existing session, so `/recce-review <the URL they gave>` is the one to run — it attaches to that session directly.

Do not prepare a dev session, and do not upload anything, when an explicit session was named.

---

## Step 1: Precondition — the Recce MCP server

Look at whether the `recce` MCP tools (`mcp__plugin_recce_recce__*`) are available in this session. Every step below needs them.

That is the only judgement you make here. No script can read your tool list. Pass what you saw:

```bash
bash ${CLAUDE_PLUGIN_ROOT}/skills/recce-dev-review/scripts/check-preflight.sh --tools present
bash ${CLAUDE_PLUGIN_ROOT}/skills/recce-dev-review/scripts/check-preflight.sh --tools absent
```

It prints one `REMEDY`, and nothing you have to ignore.

| `REMEDY` | What to do |
|---|---|
| `none` | Say nothing. Keep the `RECCE_CLOUD` value it printed for Step 2 and continue. |
| `install` | Say the install message below, then stop. |
| `dbt-docs` | Say: "This project has no `target/` artifacts yet. Run `dbt docs generate`, then `/recce-dev-review` again." Then stop. |
| `restart` | Say: "Recce is installed but its MCP server isn't connected in this session. Restart Claude Code — a new session, not `--resume` — then run `/recce-dev-review` again." Then stop. |

The `restart` case is the common one after a fresh `pip install`: the server only starts when a session starts, and resuming does not relaunch it.

For `install`, copy the script's own `INSTALL` line so the package list matches what is actually missing:

> Recce isn't installed in this project yet.
>
> ```
> source .venv/bin/activate
> pip install <INSTALL>
> ```
>
> Then restart Claude Code and run `/recce-dev-review` again.

`INSTALL` names `recce-cloud` as well when it is absent. That is deliberate: `recce-cloud` needs no restart of its own, so installing it in the same command is the difference between one restart and two. Do not mention it separately.

Say nothing beyond the line for your `REMEDY`. In particular:

- **Do not explain the cause** — not the SessionStart hook, not `.mcp.json`, not PATH resolution. The user asked for a review, not a diagnosis.
- **Do not mention base artifacts.** A missing `target-base/` is not a precondition problem.
- **Do not start the MCP server by hand** to learn more.
- **Do not ask the user to choose.** There is one fix.

---

## Step 2: Cloud readiness

Three things have to be in place beyond `recce`: `recce-cloud`, a login, and a project binding.

**Ask about each missing piece. Never skip one silently.** The local fallback exists for a user who *declines*, not for a user who has not been asked. The target user is an existing Recce Cloud client whose team already maintains a prod base — for them the base is not missing, only unreached, and quietly serving a single-environment estimate hands them a guess in place of a diff they already have.

Use the `RECCE_CLOUD` value Step 1 printed. **Do not re-resolve it** — re-asking costs the user an approval prompt in the middle of a review they requested. Use that path for **every** `recce-cloud` call; a bare `recce-cloud` reports missing for a correctly installed project.

Re-resolve in exactly one case — the user has just told you they installed it:

```bash
bash ${CLAUDE_PLUGIN_ROOT}/skills/recce-dev-review/scripts/resolve-recce-cloud.sh
```

When `RECCE_CLOUD=missing`, skip `doctor` and go straight to that outcome below. Otherwise one command answers the rest:

```bash
COLUMNS=10000 "$RECCE_CLOUD" doctor --json
```

`COLUMNS=10000` is required, not cosmetic. `doctor` prints its JSON through `rich`, which hard-wraps at 80 columns when stdout is not a terminal and splits long `suggestion` strings across lines — the result is not parseable JSON. `list --json` needs the same prefix for the same reason. `list-orgs` and `list-projects` do not; they print through `click.echo` and never wrap.

`doctor` prints four checks plus `all_passed`, each carrying `status` (`pass` / `fail` / `skip`), `message`, and `suggestion`:

| Key | Means | Act on it |
|---|---|---|
| `login` | credentials present and accepted | **yes** |
| `project_binding` | this directory is bound to a cloud project | **yes** |
| `production_metadata` | the project has a prod base uploaded | no |
| `dev_session` | some dev session exists in this project | no |

**Do not key on the exit code.** `doctor` exits `0` only when all four pass, and `dev_session` fails on every project that has not uploaded one yet — the normal state. A fully set-up client therefore exits `1`. Read `login` and `project_binding`; they are the only two a developer can act on.

Report a check only when its `status` is `fail`. A `skip` means an earlier check blocked it.

`doctor` validates the stored token against the cloud, so it makes a network call. It sends no project data.

Handle three outcomes:

- **`RECCE_CLOUD=missing`** — the CLI that reaches your team's base is not installed. **Stop and ask.** Say:

  > Your team's base lives in Recce Cloud, but the CLI that reaches it isn't installed in this project. Run this, then tell me and I'll carry on:
  >
  > ```
  > source .venv/bin/activate
  > pip install recce-cloud
  > ```
  >
  > Or say "skip" and I'll do a local check instead — a rougher read, since it estimates from one environment rather than diffing against your base.

  Do **not** run `pip install` yourself. It mutates the user's virtualenv, and in `auto` permission mode a Bash call can execute with no prompt at all — so the harness's approval dialog cannot be relied on as their consent. The `recce-cloud login` offer below is different: it writes only a credential the user asked for, and it cannot proceed without them clicking in their own browser.

  When they report it installed, re-resolve the binary and continue from `doctor`. If they skip, take the **local fallback** and do not ask again this session.

- **`login` has `status: fail`** — the user is not authenticated, which is the **normal** state on a first dev-time run. Being logged in to the Recce Cloud web app is a browser session, not a local credential; the CLI keeps its own token in `~/.recce/profile.yml` and it starts absent. **Offer to fix it here**; do not just name the command:

  > You're not logged in to Recce Cloud. Shall I run `recce-cloud login`? It opens your browser, takes about half a minute, and then this review can diff against your team's base instead of guessing from one environment.

  **If they accept**, run it with a long timeout — they have to click through the browser flow:

  ```bash
  "$RECCE_CLOUD" login
  ```

  Pass `timeout: 600000` to the Bash tool. Stream its output: if the browser does not open, the command prints a URL the user has to open by hand. When it exits, re-run `doctor` and continue from the new result.

  **If they decline**, say nothing further and take the **local fallback**. Do not ask again this session.

- **`project_binding` has `status: fail`** and login passed — this directory is not bound to a cloud project.

  **Resolve the binding yourself before you consider asking anything.** Run these three now, in this order:

  ```bash
  "$RECCE_CLOUD" list-orgs --json
  "$RECCE_CLOUD" list-projects --org "<ORG_ID>" --json
  git remote -v
  ```

  Never run bare `recce-cloud init` — it prints an interactive org/project picker, and a tool call has no stdin to answer it, so the command hangs. `init --org <id> --project <id>` is the non-interactive form and is safe.

  **If `list-orgs` fails with an unknown-command error**, this `recce-cloud` predates the automatic binding path. Do not retry and do not guess an org. Say this and stop:

  > This project isn't linked to Recce Cloud yet, and your `recce-cloud` is too old to link it automatically — that needs 1.61.0 or newer. Either upgrade with `pip install -U recce-cloud`, or run `recce-cloud init` in your terminal to pick the organization and project and tell me when it's done.

  `list-projects` already omits archived projects. Match this repo to a project on `repository.full_name` (e.g. `DataRecce/jaffle_shop_golden`) against the `origin` remote. Project id is `id`; its label is `display_name` or `name`.

  - **Exactly one project matches** — bind it. **No question needed**, so do not ask one:

    ```bash
    "$RECCE_CLOUD" init --org "<ORG_ID>" --project "<PROJECT_ID>"
    ```

    Say one line — "Linked this project to `<org label>` / `<project label>`." — so the user can catch a wrong guess. Then re-run `doctor` and continue to Step 3.

  - **No match, or more than one** — do **not** pick. Binding to the wrong project would upload this project's `manifest.json` and `catalog.json` into another team's project, and no later step undoes that. Show the candidates, ask which one, and **stop there**.

  Continue **only** once the user has answered. Never in the same turn as the question.

- Say nothing about `production_metadata` or `dev_session` in either case. A developer cannot fix an org-level upload, and a missing dev session is expected — this skill is about to create one.

- **Both pass** — say nothing and continue to Step 3.

Run `doctor` whenever you need its answer — after an install, after a login, after a binding, and on later invocations. It is a fast network call, and reusing a remembered result is how a fixed setup keeps being reported as broken. Do not cache it.

Asking is what to ration, not the call. **Ask about any one gap at most once per session.** If the user skipped `recce-cloud` or declined the login, they have decided.

**Asking means ending your turn.** A question and the fallback must never appear in the same reply. Write the question, stop, and wait for an actual answer.

### How to word it

- **No status table.** The user asked for a review, not a report on their setup.
- **Nothing that passed.** Only what is missing, and only what they can act on.
- **No internals.** No check names, no `status: fail`, no JSON keys, no mention of `doctor` itself.
- **One question at a time, and each one is a single action.** A first dev-time run can legitimately ask more than once, because the pieces are found one after another; ask, wait, resolve, then look for the next gap. Never batch them into a setup checklist, and never offer a menu.

---

## Step 3: Prepare the Cloud dev session

### Session name

One stable name per developer per branch, so repeated runs reuse a single session instead of creating a new one each time. Compute it once and reuse it as `SESSION_NAME`:

```
dev-<local part of the email from doctor's `login` check>-<current branch, with `/` replaced by `-`>
```

Take the email from the `login` check you already ran — **do not call `git config user.email`**. The session lives in Recce Cloud, so it carries the cloud account's name; a local git email can belong to a different person entirely.

The branch does need git:

```bash
git rev-parse --abbrev-ref HEAD
```

More generally in this step: never run a command for something an earlier step already returned. Each one costs the user an approval prompt in the middle of a review they asked for.

### Check the artifacts describe the working tree

Before deciding anything about the upload, run:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/recce-dev-review/scripts/check-artifacts.py
```

It prints one `ARTIFACTS` verdict, plus `STALE_MODELS` when there is something to name.

| `ARTIFACTS` | What to do |
|---|---|
| `ok` | Say nothing. Continue. |
| `stale_docs` | Ask them to run `dbt docs generate`, then stop. |
| `stale_tables` | Ask them to run `dbt run`, then stop. |
| `stale_both` | Ask them to run `dbt run && dbt docs generate`, then stop. |

Word it as one line naming the models and the command, and nothing else:

> `<STALE_MODELS>` changed after your last `<dbt run / dbt docs generate>`, so `target/` no longer matches your working tree. Run `<command>`, then `/recce-dev-review` again.

**Stop there. Do not upload and do not offer to review anyway.** The upload decision below compares timestamps against the Cloud session, and a stale `target/` passes that check while describing code the user no longer has — the review then reports on the previous version and reads as current. This is the one case where the timestamp comparison is confidently wrong.

The check reads file modification times, so a `git checkout`, a formatter, or a `touch` can make it ask for a rebuild that changes nothing. That direction is cheap. It never reports fresh for a file that changed later, which is the direction that matters.

### Decide whether to upload

Find the session with this exact name and compare its timestamp against the local manifest:

```bash
COLUMNS=10000 "$RECCE_CLOUD" list --type dev --json
```

Take the entry whose `name` equals `<SESSION_NAME>` and read its `updated_at` (falling back to `created_at`).

**Never use `doctor`'s `dev_session.uploaded_at` for this.** That field describes the most recent dev session anywhere in the project — it can belong to a teammate or to another branch, and a fresher one of theirs would silently suppress this branch's upload.

Read the local manifest's modification time **in UTC**. `updated_at` is UTC; a plain `stat` prints local time, and the obvious `stat -f '%Sm' -t '%Y-%m-%dT%H:%M:%SZ'` labels that local time `Z`. For a developer east of UTC the manifest then always looks newer, so the skip never fires and every run re-uploads. Use:

```bash
python3 -c "import os,datetime as d;print(d.datetime.fromtimestamp(os.path.getmtime('target/manifest.json'),d.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'))"
```

Not `stat` with a hand-written format — the flags differ between macOS and Linux, and the timezone mistake is silent.

- **The session exists and its timestamp is newer than the manifest** — the cloud already holds these artifacts. Set `SESSION_ID` to that entry's `id` and go to Step 4.
- **No entry matches, the timestamp is absent, or the manifest is newer** — upload.

Nothing here may depend on remembering an earlier run. A second `/recce-dev-review` in the same conversation and a first one in a fresh session must reach the same decision, so every input comes from the server or from disk. In-conversation memory is a shortcut for the same session only, never the source of truth.

### First upload of a session: show, then ask

Uploading sends `manifest.json` and `catalog.json` to Recce Cloud. Those carry model names, column names, and SQL structure. Show what would go before it goes:

```bash
"$RECCE_CLOUD" upload --session-name "<SESSION_NAME>" --yes --dry-run
```

`--yes` belongs in the preview even though nothing is uploaded: without it the preview says it will prompt before creating a session, which is not what the real command does. The preview has to describe the command the user is about to approve.

Show that output, then ask whether to proceed. If the user declines, say nothing further and take the **local fallback**.

Ask **once per session**. Later uploads in the same session proceed without asking — the user already agreed to this session.

### Upload

```bash
"$RECCE_CLOUD" upload --session-name "<SESSION_NAME>" --yes
```

`--yes` is required. Without it the command stops at an interactive `Create new session "<name>"?` prompt that nothing here can answer, and the call hangs. Consent was taken at the dry-run step above.

**Do not pass `--type`.** It only accepts `pr` or `prod`; there is no `dev` value. Left alone, the CLI auto-detects, and a local branch with no CI environment resolves to a dev session.

If the upload fails for any reason, show the error and take the **local fallback**.

### Resolve the session ID

**Do not read the ID from the `Found existing session:` / `Created new session:` line.** That line is printed through `rich`, which wraps at 80 columns when stdout is not a terminal — the UUID gets split from `(ID:` and a value read out of it is whatever survived the wrap. Look it up instead:

```bash
COLUMNS=10000 "$RECCE_CLOUD" list --type dev --json
```

Take the `id` of the entry whose `name` equals `<SESSION_NAME>` and set `SESSION_ID` to it. If no entry matches after a successful upload, do not guess — report that the session could not be resolved and take the **local fallback**.

---

## Step 4: Attach the session

Call the `set_backend` MCP tool on the `recce` server:

> `mcp__plugin_recce_recce__set_backend(mode="cloud", session_id="<SESSION_ID>")`

Then call `mcp__plugin_recce_recce__get_server_info` and require **both** `mode=cloud` and a `session_id` equal to `SESSION_ID`. A mismatch is a failure, not a detail — the long-lived MCP process may still be attached to a session from an earlier review.

`set_backend` returns quickly. Two classes of tool behave differently behind it:

- **Metadata tools** — `lineage_diff`, `schema_diff`, `get_model`, `get_cll`, `select_nodes`, `get_server_info` — are served from the session's artifacts and work as soon as the flip succeeds.
- **Data-path tools** — `row_count_diff`, `profile_diff`, `value_diff`, `value_diff_detail`, `top_k_diff`, `histogram_diff` — run against the Cloud instance and can fail for the whole session.

Do **not** probe upfront. A metadata call always succeeds and tells you nothing; the first data-path call is the real signal, and Step 5 tells the reviewer what to do with it.

Outcomes:

- **Confirmed `mode=cloud` with the matching session** — tell the user, verbatim, replacing `<SESSION_ID>`:

  ```
  Recce MCP flipped to cloud mode.
    Session: <SESSION_ID>
  Starting the review.
  ```

  Then continue to Step 5.

- **A 400 naming the warehouse connection** — the project has no warehouse connection configured, so Recce Cloud cannot launch an instance. `doctor` does not check this, so a project can pass every readiness check and still land here:

  > Recce Cloud cannot start an instance for this project — it has no warehouse connection configured. A project admin needs to add one. Falling back to a local review.

  Then take the **local fallback**.

- **A missing or expired token error** — say: "The `recce` MCP server rejected the cloud flip with an authentication error. Run `recce connect-to-cloud` to refresh the token, then run `/recce-dev-review` again." Stop.

- **`set_backend` not found** — say: "Your installed `recce` predates cloud-mode MCP. Upgrade with `pip install -U 'recce[mcp]'` and restart Claude Code." Stop.

- **Any other failure** — surface the error verbatim and take the **local fallback**. Never leave the server attached to a session you could not verify.

---

## Step 5: Dispatch the reviewer

Use the `agent:` tool to dispatch `recce-dev-reviewer`. The MCP server is owned by Claude Code (stdio child of `.mcp.json`); the skill does not start or health-check it.

Include in the dispatch context:

> "Active backend is cloud (session `<SESSION_ID>`), uploaded from this working tree. Use `state:modified+` as the selector — the MCP server resolves it against the session's stored base and head manifests, which are the authoritative pair. Do **not** read the local tracked-changes file; it adds nothing here."

> "The data path either works for this session or it does not, and the first data-path call tells you which. If your first two data-path calls both come back `null` or with an HTTP error, stop calling data tools: report `Data status: unmeasured`, quote the error text if you got one, and score from metadata and code. A `null` on a later call, when earlier ones returned data, means that one measurement is unavailable — record it in `Not measured:` and carry on. Do **not** wait and retry with `sleep`; this harness runs `sleep` in the background, so the wait never happens and you only burn turns."

**Context passthrough:** if the user's request includes a stakeholder request, a change rationale, or a PR/MR description, include it so the reviewer can validate findings against intent. Format: `Context: [stakeholder] requested '[request]'. The change is meant to '[rationale]'.`

Wait for the agent to complete and capture its full output.

**If the agent reports it cannot run** — its MCP tools are missing, no backend is attached, or any other blocker — **do not run the review yourself.** Report what it said and stop:

> The review agent could not run: {the agent's own words}. Nothing was reviewed. Check that `/mcp` shows `plugin:recce:recce` connected, then re-run `/recce-dev-review`.

Calling the diff tools directly and assembling a summary looks like success and is not. `recce-dev-reviewer.md` carries the tool sequence, the summary template, and the risk rules; a summary written here follows none of them, and the reader cannot tell the two apart.

---

## Step 6: Report, cleanup, and the launch link

Check whether the agent's output contains `## Data Review Summary`.

**If it does not** — the review did not complete. Say: "Review did not complete successfully. Tracked changes preserved for retry. Run /recce-dev-review again." Then stop. Do not clear anything and do not report a risk level.

**If it does** — surface the summary unchanged, then:

1. Clear the tracked-change record — **only when the summary reports `Data status: measured`**. On `Data status: unmeasured`, or on `Risk level: UNKNOWN`, leave the file alone and say one line: "Data comparison did not run, so these models stay marked as unreviewed." Clearing it silences the pre-commit guard, and a review with no data evidence has not earned that.

   When the data did run, the session under review is an upload of *this* working tree, so those edits are exactly what was reviewed:

   ```bash
   bash ${CLAUDE_PLUGIN_ROOT}/skills/recce-dev-review/scripts/clear-tracked-models.sh
   ```

   **Do not report this to the user.** The path is internal bookkeeping — a temp file keyed by a hash of the project directory.

2. Add one next step, from the risk level in the summary (`Risk level: HIGH | MEDIUM | LOW | UNKNOWN`):

   - **HIGH**: "High-impact changes detected. Read the root cause above before committing."
   - **MEDIUM**: "Row count changes detected. Review the deltas above, then commit when satisfied."
   - **LOW**: "No significant data impact detected. Looks safe to commit."
   - **UNKNOWN**: "The comparison could not run, so there is no data verdict — this is not an all-clear." When the summary's `Not measured:` line carries a Cloud error, quote it and add: "That is a Recce Cloud problem, not a problem with your models — retrying now will hit the same error." Otherwise offer `/recce-verify` for a Tier-1 read.

3. Append one line, and only this line:

   > Open this session in Recce: `<host>/launch/<SESSION_ID>`

   Take `<host>` from `RECCE_CLOUD_BASE_URL` when it is set, otherwise `RECCE_CLOUD_API_HOST`, otherwise `https://cloud.reccehq.com` — the same order `recce-cloud` itself uses. The path is `/launch/`, not `/sessions/`; the web app serves no `/sessions` route, so that form 404s.

Offer nothing else here — no login prompt, since the user is already authenticated, and no local `recce server`, since the data is in the cloud.

---

## Local fallback

Reached when the user declines a setup step, or when Cloud preparation fails in a way this skill cannot fix. It is a normal ending, not an error.

**Restore local mode explicitly and verify it first:**

> `mcp__plugin_recce_recce__set_backend(mode="local", project_dir="<absolute project path>")`
> `mcp__plugin_recce_recce__get_server_info()` → require `mode=local`

Never treat an already-active cloud backend as a local fallback. A review earlier in the same Claude Code session may have left the long-lived MCP process attached to an unrelated session, and the local review would then silently describe someone else's data.

Then hand off to `/recce-review`, which owns local review — the base check, the local model scope, and its own handoff to `/recce-verify` when there is no base to diff against. Say one line about why, then let that skill run:

> Reviewing locally instead.

Do not duplicate the local review here, and do not append a Cloud launch link to a review that never reached the cloud.
