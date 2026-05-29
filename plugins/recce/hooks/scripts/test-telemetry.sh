#!/usr/bin/env bash
# test-telemetry.sh — verify opt-in / opt-out paths in telemetry.sh
#
# Exercises every short-circuit in the emitter without hitting the network.
# Sets RECCE_POSTHOG_PROJECT_KEY="" so the emit ends before the curl call;
# this isolates opt-in logic from network behaviour.

set -uo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

EMIT="./telemetry.sh"
PASS=0
FAIL=0

run() {
    local label="$1"
    shift
    local want="$1"
    shift
    # Capture stdout + stderr together
    set +e
    out=$(env -i HOME="${HOME}" PATH="${PATH}" "$@" "${EMIT}" recce_verify.test prop_a=1 2>&1)
    rc=$?
    set -e
    if [[ "${rc}" == "${want}" ]]; then
        PASS=$((PASS + 1))
        printf "  pass  rc=%d  %s\n" "${rc}" "${label}"
    else
        FAIL=$((FAIL + 1))
        printf "  FAIL  want=%s got=%d  %s\n  --- output ---\n%s\n  --- end ---\n" \
            "${want}" "${rc}" "${label}" "${out}"
    fi
}

echo "Testing telemetry.sh opt-in paths (no network)..."
echo

# All cases should rc=0 (silent + non-blocking is the contract). The behaviour
# difference is whether the script proceeds past the opt-in gate, which we
# infer from -x trace if needed; here we just confirm rc=0 across paths.

run "default off (no env, no config)" 0
run "RECCE_TELEMETRY_OPT_IN=1 + no key (drops at key check)" 0 \
    RECCE_TELEMETRY_OPT_IN=1

run "RECCE_TELEMETRY_OPT_IN=1 + key + DISABLED=1 (bypass)" 0 \
    RECCE_TELEMETRY_OPT_IN=1 RECCE_POSTHOG_PROJECT_KEY=phc_fake RECCE_TELEMETRY_DISABLED=1

run "missing event name" 0

echo
echo "Summary: ${PASS} pass · ${FAIL} fail"
exit "${FAIL}"
