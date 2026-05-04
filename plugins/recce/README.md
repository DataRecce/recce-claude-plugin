# recce

Intelligent data review workflow for dbt developers.

## What it does

The recce plugin automatically tracks dbt model file changes and triggers progressive data validation using Recce. When you modify a dbt model, the plugin records the change. After your dbt run or build, it dispatches an agent that runs lineage diff, row count diff, and schema diff in sequence — producing an actionable summary with risk level before changes leave your machine.

## Components

- **Skill:** `/recce-review` — triggers the data review workflow; dispatches the recce-reviewer agent with tracked model context. Also resolves a Recce Cloud session ID from a GitHub PR and guides relaunching MCP in cloud mode when invoked with a PR URL.
- **Agent:** `recce-reviewer` — runs progressive diff analysis (lineage, row count, schema) and produces a risk-assessed summary
- **Hooks:**
  - `SessionStart` — detects dbt project environment and starts the Recce MCP server if prerequisites are met
  - `PostToolUse` (Write|Edit) — tracks modified dbt model files for change-aware review
  - `PostToolUse` (Bash) — suggests `/recce-review` after dbt run/build commands
  - `PreToolUse` (Bash) — pre-commit guard to warn about uncommitted dbt model changes
- **MCP Servers:**
  - `recce` — Recce SSE server on `http://localhost:8081/sse` (local, project-scoped)
  - `recce-docs` — Recce documentation stdio server (local path, for doc lookups)

## Requirements

- **Recce >= 1.39.0** installed in the project's virtual environment (`pip install "recce>=1.39.0"`) — SSE transport (`--sse` flag) requires this version
- The virtual environment must be activated before starting a Claude Code session so `recce` is on PATH
- dbt project with two environments configured (base + target) for comparison diffs
- Base artifacts generated: `dbt docs generate --target-path target-base` on the comparison branch

## Known Limitations

- **Port hardcoded in `.mcp.json`**: The MCP server URL is `http://localhost:8081/sse`. If you override `mcp_port` in settings (e.g., `.claude/recce/settings.json`), the actual server starts on the configured port but `.mcp.json` still points to 8081. Claude Code MCP config is static — dynamic port resolution requires a future Claude Code feature.
- **Mid-session plugin install**: Installing the plugin mid-session does not activate hooks or MCP tools. Start a new Claude Code session after installation for full functionality.
- **recce-docs MCP bundled size**: The `recce-docs` MCP server is distributed as a pre-built esbuild bundle (~2 MB). Changes to `packages/recce-docs-mcp/src/` require rebuilding via `npm run build:bundle` and committing the updated `dist/cli.js`.
- **HTTP-only MCP**: The `recce` MCP server uses `http://localhost:8081/sse` (not HTTPS). This is expected for a local SSE server.

## Reviewing a Recce Cloud session

Recce Cloud hosts shared review sessions for PRs. The plugin can flip its
running MCP server to point at a Cloud session — useful when you want to
review a teammate's PR without regenerating dbt artifacts locally.

The MCP server is **launched once at Claude Code startup in local mode** and
stays alive for the entire session. Mode switching happens **inside** that
running server via the `set_backend` MCP tool — no reconnect, no restart.

### Workflow

1. In Claude Code, run `/recce-review <PR_URL>` (or `/recce-review` and paste the URL when prompted).
2. The skill scans the PR comments via `gh` for a `cloud.reccehq.com/sessions/<id>` link (falls back to prompting), and checks for Recce Cloud credentials in `~/.recce/profile.yml` (`api_token`) or `$RECCE_API_TOKEN`. If neither is present, it instructs you to run `recce connect-to-cloud` (browser-based OAuth that writes the token back to `~/.recce/profile.yml`).
3. The skill calls `set_backend(mode="cloud", session_id=<id>)` on the running `recce` MCP server, verifies via `get_server_info`, and continues straight into the review. Metadata tools (lineage / schema / model / select / cll) work immediately. Data-path tools (row count, profile, value diff, query, etc.) may return HTTP 405 for ~30 seconds on a cold session — the reviewer agent retries 405 up to 5×10 s before giving up, so cold-start latency is absorbed transparently in most cases.
4. To return to local mode: `/recce-review local` (the skill calls `set_backend(mode="local", project_dir=<cwd>)`).

### How it works

- `scripts/run-mcp-stdio.sh` and `.mcp.json` are unchanged — they always launch `recce mcp-server` in local mode against the current dbt project.
- The `recce` MCP server exposes `set_backend(mode, session_id?, project_dir?)` and `get_server_info` tools that allow the skill to flip the active backend at runtime.
- The same MCP process therefore serves both local and Cloud reviews across the chat session — Claude Code keeps the stdio child alive throughout.

### Troubleshooting cloud mode

- **`set_backend` tool not found** — your installed `recce` predates the runtime cloud-mode MCP feature. Upgrade with `pip install -U 'recce[mcp]'` and restart Claude Code so the new binary is launched.
- **Expired or missing token** — `set_backend(mode="cloud", ...)` will return an auth error. Run `recce connect-to-cloud` to refresh the token, then re-run `/recce-review` with the same PR. `recce connect-to-cloud` opens a browser for OAuth and writes `api_token` back to `~/.recce/profile.yml`. As an alternative, `export RECCE_API_TOKEN=<token>` before launching Claude Code.
- **Browser callback hangs in `recce connect-to-cloud`** — the command spins up a short-lived loopback HTTP server on a random port to receive the OAuth callback. Make sure your firewall allows loopback connections and that the browser is on this machine. If you are SSH'd into a remote box, run `recce connect-to-cloud` locally and copy `~/.recce/profile.yml` over, or set `RECCE_API_TOKEN` directly on the remote.
- **Spawning / not connected** — if `/mcp` shows `recce` as failed at startup, the local-mode launch is broken (typically missing venv or `target/manifest.json`). Fix the local boot first; cloud flips happen on top of an already-connected server.
- **Cloud instance still warming up (HTTP 405 on diff tools)** — Recce Cloud spins the instance for a session on demand; the first data-path call after a flip can take 10–30 seconds. Metadata tools (`lineage_diff`, `schema_diff`, `get_model`, `get_cll`, `select_nodes`) are unaffected — they are served from artifacts and return immediately. Data-path tools (row count, profile, value diff, query, etc.) return 405 until the instance is ready; the reviewer agent retries 405 transparently for up to ~40 seconds. If it gives up, wait ~30 seconds and re-run `/recce-review` (without the PR URL — the cloud flip is already in effect). Persistent warm-up failures usually mean the session itself is stuck; check it at `https://cloud.reccehq.com/sessions/<SESSION_ID>`.
- **PR comment parse failure** — the skill could not find a `cloud.reccehq.com/sessions/<uuid>` link in the PR comments. Ask the PR author to push artifacts to Recce Cloud, or share the session UUID directly so you can paste it into the skill prompt.
- **Stuck in cloud mode** — call `mcp__plugin_recce_recce__set_backend(mode="local", project_dir="<cwd>")` directly (or run `/recce-review local`) to flip back. No reconnect required.
