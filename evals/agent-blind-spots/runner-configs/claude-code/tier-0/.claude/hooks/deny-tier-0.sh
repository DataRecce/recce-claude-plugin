#!/usr/bin/env bash
#
# Tier-0 PreToolUse hook for the /recce-verify v1 eval.
# Belt-and-suspenders alongside `permissions.deny` in ../settings.json
# (see DRC-3584 issue body: hooks are more reliable than deny rules per
# open Claude Code issue #6699).
#
# Reads the tool-use payload on stdin (JSON) and exits 2 with a stderr
# message to block when the call would let a Tier-0 agent reach for
# Recce-shaped signals or regenerate frozen Tier-0 inputs.
#
# Tier 0 denies:
#   * Recce MCP tools (any mcp__recce__* or mcp__plugin_recce_*)
#   * Recce CLI (`recce ...` in Bash)
#   * `/recce-*` skills (invoked through the Skill tool)
#   * dbt subcommands that regenerate manifest/compiled/catalog or hit
#     a warehouse (`dbt run|test|parse|compile|docs`)
#   * Direct SQL clients (`duckdb`, `psql`, `snowsql`, `bq`)

set -euo pipefail

payload="$(cat)"

tool_name="$(printf '%s' "${payload}" | jq -r '.tool_name // ""')"
command="$(printf '%s' "${payload}" | jq -r '.tool_input.command // ""')"
skill="$(printf '%s' "${payload}" | jq -r '.tool_input.skill // ""')"

deny() {
    printf 'Tier-0 sandbox blocks: %s\n' "$1" >&2
    exit 2
}

# Recce MCP — any namespace variant
case "${tool_name}" in
    mcp__recce__*|mcp__plugin_recce_*)
        deny "Recce MCP tool '${tool_name}' (Tier-0 disallows Recce)"
        ;;
esac

# Skill invocation — /recce-* or recce:* (plugin-namespaced)
case "${skill}" in
    recce-*|recce:*)
        deny "Recce skill '${skill}' (Tier-0 disallows /recce-* skills)"
        ;;
esac

# Bash command inspection
if [ "${tool_name}" = "Bash" ] && [ -n "${command}" ]; then
    case "${command}" in
        recce|recce[[:space:]]*|*[[:space:]]recce|*[[:space:]]recce[[:space:]]*)
            deny "Recce CLI invocation (matched in: ${command})"
            ;;
        *dbt[[:space:]]run*|*dbt[[:space:]]test*|*dbt[[:space:]]parse*|*dbt[[:space:]]compile*|*dbt[[:space:]]docs*)
            deny "dbt subcommand regenerates frozen Tier-0 artifacts or hits a warehouse (matched in: ${command})"
            ;;
        duckdb|duckdb[[:space:]]*|*[[:space:]]duckdb|*[[:space:]]duckdb[[:space:]]*)
            deny "Direct SQL client 'duckdb' (matched in: ${command})"
            ;;
        psql|psql[[:space:]]*|*[[:space:]]psql|*[[:space:]]psql[[:space:]]*)
            deny "Direct SQL client 'psql' (matched in: ${command})"
            ;;
        snowsql|snowsql[[:space:]]*|*[[:space:]]snowsql|*[[:space:]]snowsql[[:space:]]*)
            deny "Direct SQL client 'snowsql' (matched in: ${command})"
            ;;
        bq|bq[[:space:]]*|*[[:space:]]bq|*[[:space:]]bq[[:space:]]*)
            deny "Direct SQL client 'bq' (matched in: ${command})"
            ;;
    esac
fi

exit 0
