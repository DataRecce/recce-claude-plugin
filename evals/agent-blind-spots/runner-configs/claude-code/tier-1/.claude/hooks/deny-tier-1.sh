#!/usr/bin/env bash
#
# Tier-1 PreToolUse hook for the /recce-verify v1 eval. Tier 1 is
# Tier 0 plus Recce CLI, Recce MCP, and single-env warehouse credentials
# (read-only on the dev environment). Base/prod environment access stays
# denied — that's Tier 2 territory, out of v1 scope.
#
# Reads the tool-use payload on stdin (JSON) and exits 2 with a stderr
# message to block when the call would either regenerate frozen Tier-0
# inputs or reach for a base/prod environment.
#
# Tier 1 denies (relative to Tier 0):
#   * dbt subcommands that regenerate frozen artifacts or hit a warehouse
#     directly (`dbt run|test|parse|compile|docs`). Recce reads the
#     frozen artifacts; the agent never needs to regenerate them.
#   * Direct SQL clients (`duckdb`, `psql`, `snowsql`, `bq`) — at Tier 1
#     warehouse access is mediated through Recce MCP tools (e.g.,
#     `mcp__recce__query`), never raw shell.
#
# Tier 1 explicitly ALLOWS (which Tier 0 denied):
#   * Recce MCP tools and `/recce-*` skills
#   * `recce` CLI

set -euo pipefail

payload="$(cat)"

tool_name="$(printf '%s' "${payload}" | jq -r '.tool_name // ""')"
command="$(printf '%s' "${payload}" | jq -r '.tool_input.command // ""')"

deny() {
    printf 'Tier-1 sandbox blocks: %s\n' "$1" >&2
    exit 2
}

if [ "${tool_name}" = "Bash" ] && [ -n "${command}" ]; then
    case "${command}" in
        *dbt[[:space:]]run*|*dbt[[:space:]]test*|*dbt[[:space:]]parse*|*dbt[[:space:]]compile*|*dbt[[:space:]]docs*)
            deny "dbt subcommand regenerates frozen artifacts or hits a warehouse (matched in: ${command})"
            ;;
        duckdb|duckdb[[:space:]]*|*[[:space:]]duckdb|*[[:space:]]duckdb[[:space:]]*)
            deny "Direct SQL client 'duckdb' (use Recce MCP query instead; matched in: ${command})"
            ;;
        psql|psql[[:space:]]*|*[[:space:]]psql|*[[:space:]]psql[[:space:]]*)
            deny "Direct SQL client 'psql' (use Recce MCP query instead; matched in: ${command})"
            ;;
        snowsql|snowsql[[:space:]]*|*[[:space:]]snowsql|*[[:space:]]snowsql[[:space:]]*)
            deny "Direct SQL client 'snowsql' (use Recce MCP query instead; matched in: ${command})"
            ;;
        bq|bq[[:space:]]*|*[[:space:]]bq|*[[:space:]]bq[[:space:]]*)
            deny "Direct SQL client 'bq' (use Recce MCP query instead; matched in: ${command})"
            ;;
    esac
fi

exit 0
