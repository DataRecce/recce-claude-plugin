# Runner configs — Tier-0 / Tier-1 sandbox profiles

Self-contained sandbox profile templates for the eval runners (Claude Code and Codex). They make the Tier-0 / Tier-1 distinction enforceable rather than aspirational: the lens-3 counterfactual delta in `RUBRIC.md` (Tier-0 verdict → Tier-1 verdict) is only meaningful if a Tier-0 agent provably cannot reach Recce-shaped signals.

See [`../ENFORCEMENT.md`](../ENFORCEMENT.md) for the end-to-end runner recipe and the per-baseline recording requirement.

```
runner-configs/
├── README.md                                ← (this file)
├── claude-code/
│   ├── tier-0/
│   │   └── claude-overlay/                  ← copied to <fixture>/.claude/ by the runner
│   │       ├── settings.json                ← permissions.deny (documentation) + PreToolUse hook
│   │       └── hooks/deny-tier-0.py         ← exit-2 block, positive Bash allowlist
│   └── tier-1/
│       └── claude-overlay/
│           ├── settings.json                ← narrower deny (Recce allowed; dbt regen + SQL clients denied)
│           └── hooks/deny-tier-1.py         ← exit-2 block, tokenised denylist
└── codex/
    ├── tier-0/
    │   ├── README.md                        ← invocation recipe (PATH scrub + sandbox flag + cwd)
    │   └── config.toml                      ← empty mcp_servers
    └── tier-1/
        ├── README.md
        └── config.toml                      ← template mcp_servers.recce entry to fill in
```

The template directory is named `claude-overlay/` rather than `.claude/` so it isn't swallowed by the repo's `.claude/` gitignore rule. The eval runner renames it to `.claude/` when it copies the overlay into the per-fixture working tree (see Quick start below).

## Quick start

**Claude Code, Tier 0:**

```bash
SLUG="pr1-fix-clv"
WT_ROOT="$(git rev-parse --show-toplevel)"
FIXTURE_DIR="${WT_ROOT}/evals/agent-blind-spots/.tmp/sources/${SLUG}"
TIER_DIR="${WT_ROOT}/evals/agent-blind-spots/runner-configs/claude-code/tier-0"

cp -r "${TIER_DIR}/claude-overlay" "${FIXTURE_DIR}/.claude"

# Optional but recommended — neuter user-level settings for this run:
export CLAUDE_CONFIG_DIR="$(mktemp -d)"

cd "${FIXTURE_DIR}"
claude "<the prompt — see RUBRIC.md Tier-0 prompt-shape contract>"
```

**Codex, Tier 0:** see [`codex/tier-0/README.md`](codex/tier-0/README.md).

## Why both `permissions.deny` and a `PreToolUse` hook

Claude Code's `permissions.deny` uses shell-glob matching that is conceded to be unreliable: open issue [anthropics/claude-code#6699](https://github.com/anthropics/claude-code/issues/6699) shows bypasses, and the glob shape can't express the things the rubric requires (path-stripped basenames, `sh -c "<banned>"` recursion, dbt subcommands with global flags interposed, case-insensitive skill matching).

The PreToolUse hook is therefore the **load-bearing layer**, not a backup. It uses `shlex` tokenisation, basenames each executable, recurses into shell wrappers, lowercases skill names, and matches MCP namespaces with a regex.

**`permissions.deny` and the hook do not mirror each other**, and that's deliberate:

* `permissions.deny` covers only what shell-glob can express crisply — the user-facing documented attack surface.
* The hook covers the full surface, including the bypass shapes the glob can't address.

Treat `permissions.deny` as documentation for human readers. Trust the hook for enforcement.

## Maintenance

When you add a new Recce CLI verb, new MCP tool namespace, or a new dbt subcommand that mutates state:

1. Update the hook script (`deny-tier-{0,1}.py`) — it's the source of truth.
2. Update the documented `permissions.deny` patterns to match the new shape.
3. Add the new shape to the Bypass attempts table in `runs/<date>/sandbox-verification.md` so a future regression is caught.

The hook's MCP namespace regex is `^mcp__(plugin_)?recce(_|-|$)` — adding a `mcp__recce_<foo>__*` namespace is automatically covered. New Bash basenames (e.g. a `recce` CLI rename) require a Python-level change.
