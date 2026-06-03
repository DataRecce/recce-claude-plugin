#!/usr/bin/env bash
# telemetry.sh — opt-in PostHog event emitter (DRC-3597, L3 funnel signal)
#
# Fires events for the /recce-verify skill funnel:
#   - recce_verify.skill_invoked
#   - recce_verify.tier_degraded
#   - recce_verify.tool_call
#   - recce_verify.verdict_emitted
#   - recce_verify.session_completed
#
# Off by default. Activate via one of:
#   - export RECCE_TELEMETRY_OPT_IN=1
#   - write `telemetry_opt_in: true` to ~/.recce/config.yml
#
# Failure modes are silent — never blocks the agent flow.
#
# Usage:
#   telemetry.sh <event_name> [key=value] [key=value] ...

set -u

# ── Opt-in gate ────────────────────────────────────────────────────────────────

if [[ "${RECCE_TELEMETRY_OPT_IN:-}" != "1" ]]; then
    cfg="${HOME}/.recce/config.yml"
    if [[ ! -f "${cfg}" ]] || ! grep -qE '^telemetry_opt_in:[[:space:]]*true$' "${cfg}" 2>/dev/null; then
        exit 0
    fi
fi

# ── Per-tool one-flag bypass ───────────────────────────────────────────────────

if [[ "${RECCE_TELEMETRY_DISABLED:-}" == "1" ]]; then
    exit 0
fi

# ── Event + properties ─────────────────────────────────────────────────────────

event="${1:-}"
shift || true

if [[ -z "${event}" ]]; then
    echo "telemetry.sh: missing event name" >&2
    exit 0
fi

# ── Anonymous, stable installation ID ─────────────────────────────────────────

install_id_file="${HOME}/.recce/installation-id"
if [[ ! -f "${install_id_file}" ]]; then
    mkdir -p "$(dirname "${install_id_file}")" 2>/dev/null || exit 0
    if command -v uuidgen >/dev/null 2>&1; then
        uuidgen | tr '[:upper:]' '[:lower:]' > "${install_id_file}" 2>/dev/null || exit 0
    elif command -v python3 >/dev/null 2>&1; then
        python3 -c 'import uuid; print(uuid.uuid4())' > "${install_id_file}" 2>/dev/null || exit 0
    else
        exit 0
    fi
fi
install_id="$(cat "${install_id_file}" 2>/dev/null || true)"
[[ -z "${install_id}" ]] && exit 0

# ── PostHog destination ────────────────────────────────────────────────────────

posthog_host="${POSTHOG_HOST:-https://us.i.posthog.com}"
posthog_key="${RECCE_POSTHOG_PROJECT_KEY:-}"

# If no key configured, drop the event silently. The plugin maintainer fills
# this in during plugin packaging; users opting in still need a key to fire.
if [[ -z "${posthog_key}" ]]; then
    exit 0
fi

# ── Build properties JSON from key=value args ─────────────────────────────────

props='{}'
if command -v jq >/dev/null 2>&1; then
    for kv in "$@"; do
        k="${kv%%=*}"
        v="${kv#*=}"
        [[ "${k}" == "${kv}" ]] && continue   # no '=' → skip
        props=$(jq --arg k "${k}" --arg v "${v}" '. + {($k): $v}' <<< "${props}" 2>/dev/null) || props='{}'
    done
fi

# ── Fire-and-forget POST ───────────────────────────────────────────────────────

payload=$(cat <<EOF
{"api_key":"${posthog_key}","event":"${event}","distinct_id":"${install_id}","properties":${props}}
EOF
)

# Background so we never block; --max-time caps wait at 2s if foregrounded
(
    curl -fsS -X POST "${posthog_host}/capture/" \
        -H "Content-Type: application/json" \
        -d "${payload}" \
        --max-time 2 >/dev/null 2>&1 || true
) &

exit 0
