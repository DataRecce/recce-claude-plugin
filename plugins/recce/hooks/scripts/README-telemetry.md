# `/recce-verify` telemetry — opt-in PostHog events

L3 funnel signal for the `Agent-blind spots: /recce-verify v1` project ([DRC-3597](https://linear.app/recce/issue/DRC-3597)). Lets the project see whether real-world agent users reach for the skill, complete it, and convert downstream — the production complement to the L1 offline eval (DRC-3405) and L2 in-driver trace metrics (DRC-3586).

**Off by default.** Telemetry fires only when the user opts in.

## What gets emitted

| Event | When | Properties |
|---|---|---|
| `recce_verify.skill_invoked` | `/recce-verify` SKILL.md activates | `tier_detected` (0 / 1 / 2), `agent` (claude_code / codex), `recce_version`, `plugin_version` |
| `recce_verify.tier_degraded` | Skill detects degraded capability and falls back | `from_tier`, `to_tier`, `reason` (recce_missing / mcp_unreachable / no_dev_env / …) |
| `recce_verify.tool_call` | Any `mcp__plugin_recce_recce__*` call inside the skill flow | `tool_name`, `success` (true/false), `error_class` (truncated), `duration_ms_bucket` |
| `recce_verify.verdict_emitted` | Skill writes its structured verdict | `verdict` (catch/miss/partial/abstain), `evidence_tier`, `subset` (1a/1b/1c) |
| `recce_verify.session_completed` | Last skill step before agent yields | `cells_invoked` count, `total_duration_ms_bucket` |

**No PII, no SQL bodies, no model identifiers in event properties** — coarse buckets only. The `verdict` value is event-bound (`catch` / `miss` / `partial`), not free-form.

## How to opt in (user side)

Either:

```bash
export RECCE_TELEMETRY_OPT_IN=1                # per-shell
```

Or write to `~/.recce/config.yml`:

```yaml
telemetry_opt_in: true
```

To opt out for one invocation while the env / config is on:

```bash
RECCE_TELEMETRY_DISABLED=1 claude            # bypass for this session
```

## How to wire (plugin maintainer side)

The emitter script is at `plugins/recce/hooks/scripts/telemetry.sh`. Call it with the event name + key=value props:

```bash
bash "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/telemetry.sh" recce_verify.skill_invoked \
    tier_detected=1 agent=claude_code recce_version=0.42.0 plugin_version=0.2.0
```

Fires in the background. Never blocks. Returns 0 unconditionally.

### Auto-wired (via hooks.json)

None yet — the wiring needs design decisions (which events fire from hooks vs from inline SKILL.md calls) that should happen in a follow-up PR. This PR ships the emitter foundation only.

Recommended next steps (see DRC-3597 acceptance):

1. Add `PostToolUse` hook matcher `mcp__plugin_recce_recce__.*` → `telemetry.sh recce_verify.tool_call tool_name=$TOOL_NAME success=$SUCCESS`. Requires deciding how to scope to "only when /recce-verify is active" — proposal: SKILL.md sets a marker file at Step 0, hook checks marker before firing.
2. Add `Stop` hook → `telemetry.sh recce_verify.session_completed cells_invoked=…`. Requires aggregating per-session counts (e.g. from the marker file).
3. Inline `bash ${CLAUDE_PLUGIN_ROOT}/hooks/scripts/telemetry.sh recce_verify.skill_invoked …` in SKILL.md Step 0 (single-line addition, low risk).
4. Inline `… recce_verify.verdict_emitted …` in the SKILL.md verdict-write step.

### PostHog project configuration

The plugin maintainer fills in the PostHog public project key during release packaging — either by patching `telemetry.sh` (constant) or by shipping a small wrapper that exports `RECCE_POSTHOG_PROJECT_KEY` before calling the script. Both approaches keep the key in plugin-controlled code, not in user config.

For development:

```bash
export RECCE_POSTHOG_PROJECT_KEY=phc_xxxxx
export RECCE_TELEMETRY_OPT_IN=1
bash plugins/recce/hooks/scripts/test-telemetry.sh
```

## Funnel attribution

Each user's events carry a stable `distinct_id` from `~/.recce/installation-id` (UUID4, lazily created on first opt-in emit, persisted across sessions). The file holds only the UUID — no credentials, no personal info.

Attribution to Recce Cloud signups requires a join key on the Cloud side. That's not in this PR — coordinate with @Andy when Cloud's signup form picks up the parameter.

## Failure modes (all silent, all non-blocking)

- Opt-in unset → script exits 0 before doing anything.
- `~/.recce/` unwriteable → installation-id creation skipped, script exits 0.
- No PostHog key configured → script exits 0 before any HTTP call.
- PostHog endpoint unreachable / 5xx / timeout → `curl --max-time 2`; the request runs in a background subshell, so the script returns immediately regardless of outcome.
- `jq` missing → properties JSON falls back to empty `{}`; event still fires with no props.
- Any other unexpected failure → trailing `|| true` and `set -u` (no `-e`) keep the script returning 0.

## Audit script

`test-telemetry.sh` exercises the opt-in paths without firing a real network request, by setting `RECCE_POSTHOG_PROJECT_KEY=""` so the emit short-circuits before the `curl`. Use it after editing `telemetry.sh`:

```bash
bash plugins/recce/hooks/scripts/test-telemetry.sh
```
