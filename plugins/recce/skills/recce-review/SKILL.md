---
name: recce-review
description: >
  Review dbt model data changes using Recce. Triggers when: user asks to review
  data changes, check data impact, run recce review, validate model changes
  before committing, review a Recce Cloud PR session, connect MCP to a cloud
  session, or pastes a GitHub PR / GitLab MR URL for cloud-mode review.
---

# /recce-review — Data Review Orchestration

This skill orchestrates tracked-model handoff, sub-agent dispatch, post-review cleanup, and risk-based next-step suggestions.

It also handles **cloud-mode flips from a PR/MR**: when invoked with a PR URL (GitHub) or MR URL (GitLab, including self-hosted), the skill resolves a Recce Cloud session ID from the PR/MR comments, verifies cloud authentication, and flips the running MCP server into cloud mode by calling its `set_backend` tool — no reconnect, no restart.

Claude Code launches `recce mcp-server` (stdio) at session start in **local mode** and the same server stays alive for the whole session. Mode switching happens **inside** that running server via MCP tool calls.

Follow these steps in order.

---

## Step 0: Cloud-mode PR/MR resolution (only if user provided a PR/MR URL or asked for cloud review)

> Skip this step if the user did not provide a PR/MR URL and did not mention "cloud", "cloud session", or "Recce Cloud".

### 0.1 Resolve the PR/MR reference

The skill supports GitHub PRs and GitLab MRs (including self-hosted GitLab). If the user provided one of:

- GitHub PR URL: `https://github.com/<owner>/<repo>/pull/<n>` (or just the PR number when the working directory is already a GitHub repo)
- GitLab MR URL: `https://<host>/<group>[/<subgroup>...]/<project>/-/merge_requests/<iid>` (works for `gitlab.com` and self-hosted hosts)

…use that. Otherwise ask: "Which PR/MR should I review? Paste a GitHub PR URL, GitLab MR URL, or PR number."

### 0.2 Detect the SCM and verify access

First identify which source-control host owns the URL:

```bash
bash ${CLAUDE_PLUGIN_ROOT}/skills/recce-review/scripts/scm/detect.sh "<PR_OR_MR_URL>"
```

The script prints exactly one of `SCM=github`, `SCM=gitlab`, `SCM=bitbucket`, or `SCM=unknown`. Detection is path-based (recognizes `/pull/`, `/-/merge_requests/`, `/pull-requests/`) so it works for self-hosted hosts.

Then run the matching readiness check:

**If `SCM=github`:**

```bash
bash ${CLAUDE_PLUGIN_ROOT}/skills/recce-review/scripts/scm/github-ready.sh
```

The script prints `GITHUB=ready` (with `GITHUB_VIA=cli`) or `GITHUB=unavailable`. If unavailable, tell the user: "GitHub CLI is not authenticated. Run `gh auth login` and re-run /recce-review." Stop.

**If `SCM=gitlab`:**

```bash
bash ${CLAUDE_PLUGIN_ROOT}/skills/recce-review/scripts/scm/gitlab-ready.sh
```

GitLab access works via either the `glab` CLI **or** a `GITLAB_TOKEN` environment variable (either is sufficient; both work for self-hosted GitLab). The script prints `GITLAB=ready` (with `GITLAB_VIA=cli` when `glab auth status` succeeds, otherwise `GITLAB_VIA=token`) or `GITLAB=unavailable`.

If unavailable, tell the user: "No GitLab credentials found. Either run `glab auth login` (for self-hosted, use `glab auth login --hostname <host>`) or export `GITLAB_TOKEN=<your-personal-access-token>` (with `read_api` scope), then re-run /recce-review."

Stop on unavailable.

**If `SCM=bitbucket` or `SCM=unknown`:** tell the user the URL's source-control host is not yet supported by this skill (Bitbucket support is planned). Stop.

### 0.3 Fetch PR/MR comments and parse the session ID

Run the comments fetcher matching the detected SCM:

**If `SCM=github`:**

```bash
bash ${CLAUDE_PLUGIN_ROOT}/skills/recce-review/scripts/scm/github-comments.sh "<PR_REF>"
```

`<PR_REF>` is the PR URL or PR number.

**If `SCM=gitlab`:**

```bash
bash ${CLAUDE_PLUGIN_ROOT}/skills/recce-review/scripts/scm/gitlab-comments.sh "<MR_URL>"
```

`<MR_URL>` must be the full URL (the script parses host, project path, and IID from it). The script prefers `glab api` when available (which already knows about self-hosted host config), falling back to `curl` against `https://<host>/api/v4` with `GITLAB_TOKEN`.

Both scripts print one comment/note body per record on stdout. Search those bodies for a Recce Cloud session URL of the form:

```
https://cloud.reccehq.com/sessions/<SESSION_ID>
```

where `<SESSION_ID>` is a UUID (`[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}`).

- Exactly one match — show it and confirm with the user.
- Multiple distinct matches — list with author/timestamp; ask the user to choose. Prefer the latest comment from the Recce Cloud bot (force-pushed PRs/MRs may have multiple).
- No match — tell the user: "No Recce Cloud session URL found in PR/MR comments. Run `recce-cloud list --type pr` to find an existing session, or `recce-cloud upload` from the PR/MR branch to create one — then paste the session ID (UUID) here." Wait for input and validate against the UUID regex.

### 0.4 Verify Recce Cloud authentication

Recce Cloud credentials live in **`~/.recce/profile.yml`** (key: `api_token`) or in the **`RECCE_API_TOKEN`** environment variable. Either is sufficient; `RECCE_API_TOKEN` takes precedence.

Run:

```bash
bash ${CLAUDE_PLUGIN_ROOT}/skills/recce-review/scripts/check-recce-auth.sh
```

The script prints exactly one of `AUTH=env`, `AUTH=file`, or `AUTH=missing`. It does not print or transmit the token itself — it only reports which source supplied it.

- `AUTH=env` or `AUTH=file` — proceed to Step 0.5.
- `AUTH=missing` — tell the user, verbatim, then **stop**:

  > Recce Cloud credentials not found in `~/.recce/profile.yml` and `RECCE_API_TOKEN` is not set. Please run:
  >
  > ```
  > recce connect-to-cloud
  > ```
  >
  > This opens a browser for the OAuth flow; on success it writes `api_token` back into `~/.recce/profile.yml`. Then re-run `/recce-review` with the same PR/MR.

  > Note: `recce connect-to-cloud` starts a short-lived local HTTP server on a random port to receive the OAuth callback — make sure no firewall blocks loopback callbacks and that the browser it opens is on this machine.

### 0.5 Flip the running MCP server into cloud mode

Call the `set_backend` MCP tool on the `recce` server:

> `mcp__plugin_recce_recce__set_backend(mode="cloud", session_id="<SESSION_ID>")`

Then call `mcp__plugin_recce_recce__get_server_info` and verify the response reports the cloud backend with the matching `session_id`.

`set_backend` returns quickly. The MCP server begins serving cloud-mode requests immediately, but the **Recce Cloud instance behind the session may still be warming up** (cold-start ~30 seconds). During warmup:

- **Metadata tools work right away** — `lineage_diff`, `schema_diff`, `get_model`, `get_cll`, `select_nodes`, `get_server_info` are served from artifacts and do not depend on the warming instance.
- **Data-path tools return HTTP 405** until ready — `row_count_diff`, `profile_diff`, `value_diff`, `value_diff_detail`, `top_k_diff`, `histogram_diff`, `query`, `query_diff`. The 405 body usually says "please try after 10–30 seconds".

The skill therefore does **not** probe upfront — that would only exercise metadata tools (which always succeed) and tell us nothing. Instead, it lets the review proceed immediately and handles 405 reactively when the agent's first data-path tool call lands. See Step 2 for the retry contract.

Outcomes for the flip itself:

- **`set_backend` succeeds and `get_server_info` confirms `mode=cloud`** — tell the user, verbatim, replacing `<SESSION_ID>` with the resolved value:

  ```
  Recce MCP flipped to cloud mode.
    Session: <SESSION_ID>
  Starting the review. The first data-path call may pause briefly while the
  Cloud instance warms up (up to ~30 seconds on a cold session).
  ```

  Then continue inline to **Step 1**.

- **`set_backend` fails with a missing/expired token error** — tell the user:

  > The `recce` MCP server rejected the cloud flip with an authentication error. Run `recce connect-to-cloud` to refresh the token, then re-run `/recce-review` with the same PR/MR. (`recce connect-to-cloud` opens a browser for the OAuth flow and writes `api_token` back into `~/.recce/profile.yml`.)

  Stop.

- **Tool not found (`set_backend` missing)** — tell the user:

  > Your installed `recce` predates cloud-mode MCP. Upgrade with `pip install -U 'recce[mcp]'` and restart Claude Code (`/mcp` reconnect picks up the new binary).

  Stop.

- **`set_backend` fails for another reason** — surface the error message verbatim and stop. Do **not** silently fall back to local mode.

> To return to local mode later: call `mcp__plugin_recce_recce__set_backend(mode="local", project_dir="<absolute-project-path>")`. The skill exposes this as the user-visible action `/recce-review local` (no PR/MR argument and an explicit "local" keyword) — handle it in Step 0 by skipping PR/MR resolution and calling `set_backend(mode="local", ...)` directly.

---

## Step 1: Determine Model Scope

Run:

```bash
bash ${CLAUDE_PLUGIN_ROOT}/skills/recce-review/scripts/get-tracked-models.sh
```

The script reads the project-scoped tracked-changes file written by the PostToolUse hook (`track-changes.sh`) and prints either `TRACKED=false`, or `TRACKED=true` followed by `MODEL_COUNT=<n>` and `MODELS=<comma+space separated names>`.

Parse the output:
- If `TRACKED=true` — record the `MODELS` value (comma-separated model names). Use these in Step 2.
- If `TRACKED=false` — no tracked changes file exists. Do **not** abort. Do **not** ask the user for model names. The agent will use `state:modified+` as a fallback selector.

> Note: cloud-mode reviewers usually have no local edits, so `TRACKED=false` is normal — the agent will resolve the changed nodes from the cloud session via `state:modified+`.

---

## Step 2: Dispatch Review Agent

Use the `agent:` tool to dispatch `recce-reviewer`. The MCP server is owned by Claude Code (stdio child of `.mcp.json`); if it is not connected, the agent's tool calls will fail and Claude Code will surface the error in `/mcp`. The skill does not start or health-check MCP itself.

**If tracked models were found (Step 1 returned TRACKED=true):**
Include in the dispatch context:
> "Changed models (from tracked file): {MODELS}. Focus review on these models using selector: {model1}+ {model2}+ (one per model from the list)."

**If no tracked models (Step 1 returned TRACKED=false):**
Include in the dispatch context:
> "No tracked changes file found. Use state:modified+ as the default selector to review all modified models."

**Context passthrough:** If the user's request includes any of the following, include it in the dispatch message so the reviewer can validate findings against intent:
- **Stakeholder request** (who asked for the change and what they asked for)
- **PR/MR description** (what the change claims to do)
- **Change rationale** (why the change was made)

Format: `Context: [stakeholder] requested '[request]'. PR/MR says: '[description]'.`

This enables the reviewer's context validation step (Step 4 in the agent workflow).

**Cloud warmup retry contract (only when the active backend is cloud — check via `get_server_info` if unsure):**

Include in the dispatch context:

> "Active backend is cloud. Data-path tools (`row_count_diff`, `profile_diff`, `value_diff`, `value_diff_detail`, `top_k_diff`, `histogram_diff`, `query`, `query_diff`) may return HTTP 405 with a 'try again' message while the Cloud instance warms up. On 405, retry the same call up to 5 times with 10-second waits between attempts (~40 seconds total). Metadata tools (`lineage_diff`, `schema_diff`, `get_model`, `get_cll`, `select_nodes`) are not affected — run those first; they will succeed immediately and you can produce partial findings while the instance warms. If a data-path tool is still 405 after the retry budget, report that the Cloud instance did not become ready and recommend the user re-run /recce-review in ~30 seconds."

Wait for the agent to complete and capture its full output.

---

## Step 3: Post-Review Cleanup (on success only)

Check if the agent's output contains `## Data Review Summary`.

**If YES** (successful review):

Run:

```bash
bash ${CLAUDE_PLUGIN_ROOT}/skills/recce-review/scripts/clear-tracked-models.sh
```

The script removes the project-scoped tracked-changes file (`rm -f`, so it is a no-op if the file is absent) and prints `CLEARED=<path>`. This clears tracked changes so the pre-commit guard no longer warns about already-reviewed models.

**If NO** (agent error or incomplete review):

Do **not** delete the file. Tell the user: "Review did not complete successfully. Tracked changes preserved for retry. Run /recce-review again." Then **STOP** — do not proceed to Step 4.

---

## Step 4: Next Steps Based on Risk Level

> Skip this step if the review did not complete successfully (no `## Data Review Summary` found in Step 3).

Parse the risk level from the agent's summary output (look for `Risk level: HIGH`, `Risk level: MEDIUM`, or `Risk level: LOW`).

- **HIGH**: "Schema breaking changes detected. Consider running `/recce-check` for detailed profile and query analysis before committing."
- **MEDIUM**: "Row count changes detected. Review the deltas above, then commit when satisfied."
- **LOW**: "No significant data impact detected. Looks safe to commit."
