# Runner configs — Tier-0 / Tier-1 sandbox profiles

Self-contained sandbox profile templates for the eval runners (Claude Code and Codex). They make the Tier-0 / Tier-1 distinction enforceable rather than aspirational: the lens-3 counterfactual delta in `RUBRIC.md` (Tier-0 verdict → Tier-1 verdict) is only meaningful if a Tier-0 agent provably cannot reach Recce-shaped signals.

See [`../ENFORCEMENT.md`](../ENFORCEMENT.md) for the end-to-end runner recipe and the per-baseline recording requirement.

```
runner-configs/
├── README.md                                ← (this file)
├── claude-code/
│   ├── tier-0/
│   │   └── .claude/
│   │       ├── settings.json                ← permissions.deny + PreToolUse hook
│   │       └── hooks/deny-tier-0.sh         ← exit-2 block on Recce + dbt regen + SQL clients
│   └── tier-1/
│       └── .claude/
│           ├── settings.json                ← narrower deny (Recce allowed; dbt regen + SQL clients still denied)
│           └── hooks/deny-tier-1.sh
└── codex/
    ├── tier-0/
    │   ├── README.md                        ← invocation recipe (PATH scrub + sandbox flag + cwd)
    │   └── config.toml                      ← empty mcp_servers
    └── tier-1/
        ├── README.md
        └── config.toml                      ← template mcp_servers.recce entry to fill in
```

## Quick start

**Claude Code, Tier 0:**

```bash
SLUG="pr1-fix-clv"
WT_ROOT="$(git rev-parse --show-toplevel)"
FIXTURE_DIR="${WT_ROOT}/evals/agent-blind-spots/.tmp/sources/${SLUG}"
TIER_DIR="${WT_ROOT}/evals/agent-blind-spots/runner-configs/claude-code/tier-0"

cp -r "${TIER_DIR}/.claude" "${FIXTURE_DIR}/"

# Optional but recommended — neuter user-level settings for this run:
export CLAUDE_CONFIG_DIR="$(mktemp -d)"

cd "${FIXTURE_DIR}"
claude "<the prompt — see RUBRIC.md Tier-0 prompt-shape contract>"
```

**Codex, Tier 0:** see [`codex/tier-0/README.md`](codex/tier-0/README.md).

## Why both `permissions.deny` and a `PreToolUse` hook

Claude Code's `permissions.deny` is the documented mechanism, but open issue [anthropics/claude-code#6699](https://github.com/anthropics/claude-code/issues/6699) shows it can be bypassed in some shapes. The PreToolUse hook is belt-and-suspenders: a deny-by-default exit-2 script. If `permissions.deny` regresses, the hook still blocks; if the hook regresses, `permissions.deny` still blocks.

## Maintenance

When you add a new Recce CLI verb, new MCP tool namespace, or a new dbt subcommand that mutates state, update **both** the relevant tier's `settings.json` deny list **and** the hook script's case statement. The hook is the source of truth — `settings.json` mirrors it for the documented path.
