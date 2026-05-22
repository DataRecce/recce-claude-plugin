---
name: recce-verify
description: >
  Lightweight pre-commit verification for dbt model changes in the
  single-environment dev loop — when the user has a warehouse-connected dbt
  project but no `target-base/` artifacts. Triggers when: user asks to verify
  a model change, check whether an edit is safe to commit, sanity-check a
  filter/aggregation/join change without setting up a base environment, or
  asks for a quick risk read before running /recce-review. Uses Tier-1
  evidence only — column lineage, AST analysis, and targeted current-env
  SQL probes. Routes to /recce-review when `target-base/` is fresh.
---

# /recce-verify — Single-Env Dev-Loop Verification

This skill is the **lightweight pre-cursor** to `/recce-review`. It targets the dev-loop case: warehouse-connected dbt project, mid-edit, **no fresh `target-base/` artifacts** (missing, stale, single-env mode, or unverified) and the user does not want to regenerate them yet. The verifier produces a Tier-1 risk read using column lineage, AST/semantic analysis, and small targeted SQL probes against the current environment — no row-count or value diffs against a base.

If `target-base/` is fresh, this skill routes to `/recce-review` (which owns full diff-based review).

Follow these steps in order.

---

## Step 0: Confirm single-env preconditions

Call `mcp__plugin_recce_recce__get_server_info` and inspect `mode` + `base_status`.

- **`mode='cloud'`** — stop and tell the user: "Cloud session detected. Use `/recce-review` instead — it owns cloud-mode review."
- **`mode='local'` and `base_status='fresh'`** — stop and tell the user, verbatim: "Base artifacts are fresh — use `/recce-review` instead for full diff-based review. `/recce-verify` is for the single-env dev-loop case."
- **`mode='local'` and `base_status` in {`single_env`, `missing`, `stale_time`, `stale_sha`, `unknown`}** — proceed. (`unknown` means the freshness check did not run — e.g., cloud mode or skipped — so the base cannot be trusted; treat as single-env for evidence purposes.)

Do not start MCP, do not health-check it. The server is owned by Claude Code; if `get_server_info` fails the user will see it in `/mcp`.

---

## Step 1: Identify changed models

Resolve the model scope from three sources in this precedence order. Stop at the first source that yields models.

### 1A. Models named explicitly in the user's prompt

If the user passed model names as arguments (e.g., `/recce-verify customers orders` or "verify stg_orders and fct_revenue"), parse them and use directly. Skip to Step 2.

### 1B. Tracked-changes file from the PostToolUse hook

Reuse the existing script — do **not** duplicate it:

```bash
bash ${CLAUDE_PLUGIN_ROOT}/skills/recce-review/scripts/get-tracked-models.sh
```

Parse the output exactly as `/recce-review` Step 1B does:
- `TRACKED=true` followed by `MODELS=<comma+space separated>` — record `MODELS` and skip to Step 2.
- `TRACKED=false` — fall through to Step 1C.

### 1C. Git working-tree fallback

```bash
git diff --name-only HEAD -- 'models/**/*.sql'
```

Derive model names from the basenames (strip `models/...` prefix and `.sql` suffix). If git returns nothing, ALSO check untracked new model files:

```bash
git status --porcelain models/ | awk '$1 == "??" && $2 ~ /\.sql$/ { print $2 }'
```

Derive model names from those basenames too.

**Do NOT use `state:modified+`** — it requires a base manifest comparison that does not exist in single-env. `/recce-review` uses that selector; this skill cannot.

### No models found

If none of 1A/1B/1C yield models, tell the user, verbatim, and stop:

> No changed models found. Either name a model explicitly (`/recce-verify <model_name>`), or make a SQL edit first.

---

## Step 2: Dispatch verifier agent

Use the `agent:` tool to dispatch `recce-verifier`. Include in the dispatch context:

> "Changed models: {model1, model2, ...}. Active backend is local (`base_status={status}`); treat as Tier-1 only because base artifacts are absent (`single_env`/`missing`), stale (`stale_time`/`stale_sha`), or unverified (`unknown`). Use Tier-1 evidence only: `select_nodes` (to resolve bare model names to dbt unique IDs before any other call), `get_cll`, `analyze_model`, `get_model`, `lineage_diff` (metadata only — `change_status` is partial in single-env, use the graph shape), and targeted `query` probes against the current environment. If `analyze_model` is unavailable in this recce build, fall back to text-level inspection (`Read` the SQL + `git diff`). Do NOT call any diff tool (`row_count_diff`, `value_diff`, `profile_diff`, `query_diff`, `top_k_diff`, `histogram_diff`, `schema_diff`, `impact_analysis`) — they degrade to current-vs-current in single-env and waste budget."

**Context passthrough:** If the user's request includes any of the following, include it verbatim in the dispatch message so the verifier can validate findings against intent:

- **Stakeholder request** (who asked for the change and what they asked for)
- **Change rationale** (why the change was made)
- **Intent** ("safe to commit?", "did I break downstream?", etc.)

Format: `Context: [stakeholder] requested '[request]'. Intent: '[intent]'.`

Wait for the agent to complete and capture its full output.

---

## Step 3: Surface the verdict

The verifier returns a `## Verification Summary` block. Show it to the user verbatim — do not paraphrase, do not truncate.

If the agent's output does **not** contain `## Verification Summary`, do NOT proceed to Step 4. Tell the user: "Verification did not complete. Re-run `/recce-verify`." Then stop.

---

## Step 4: Recommend next steps based on risk level

Parse `Risk level: HIGH|MEDIUM|LOW` from the summary (literal match).

- **LOW**: "No measurable data concern detected. Safe to commit."
- **MEDIUM**: "Bounded impact detected. Review the findings above, then commit when satisfied. For a full base-vs-current diff, run `dbt docs generate --target-path target-base` on the base branch and use `/recce-review`."
- **HIGH**: "High-risk change. Before committing, set up target-base on the base branch (`dbt docs generate --target-path target-base`) and run `/recce-review` for full row-count/value diffs."
