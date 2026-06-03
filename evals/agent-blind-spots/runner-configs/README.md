# Runner configs — Tier-0 / Tier-1 sandbox profiles

Self-contained sandbox profile templates for the eval runners (Claude Code and Codex). They make the Tier-0 / Tier-1 distinction enforceable rather than aspirational: the lens-3 counterfactual delta in `RUBRIC.md` (Tier-0 verdict → Tier-1 verdict) is only meaningful if a Tier-0 agent provably cannot reach Recce-shaped signals.

See [`../ENFORCEMENT.md`](../ENFORCEMENT.md) for the end-to-end runner recipe and the per-baseline recording requirement.

```
runner-configs/
├── README.md                                ← (this file)
├── claude-code/
│   ├── tier-0/
│   │   └── claude-overlay/                  ← template; the runner renders settings.json
│   │       │                                  to a per-cell temp path and loads it via
│   │       │                                  `claude --settings <abs-path>`. NEVER
│   │       │                                  copied into the fixture cwd — see below.
│   │       ├── settings.json                ← permissions.deny (documentation) + PreToolUse
│   │       │                                  hook; `command` field uses `${RUNNER_HOOK_PATH}`
│   │       │                                  placeholder substituted by the runner with an
│   │       │                                  absolute path to the hook.
│   │       └── hooks/deny-tier-0.py         ← exit-2 block, positive Bash allowlist
│   └── tier-1/
│       └── claude-overlay/
│           ├── settings.json                ← narrower deny (Recce allowed; dbt regen + SQL
│           │                                  clients denied). Same `${RUNNER_HOOK_PATH}`
│           │                                  placeholder pattern as Tier-0.
│           └── hooks/deny-tier-1.py         ← exit-2 block, tokenised denylist
└── codex/
    ├── tier-0/
    │   ├── README.md                        ← invocation recipe (PATH scrub + sandbox flag + cwd)
    │   └── config.toml                      ← empty mcp_servers
    └── tier-1/
        ├── README.md
        └── config.toml                      ← template mcp_servers.recce entry to fill in
```

The template directory is named `claude-overlay/` rather than `.claude/` so it isn't swallowed by the repo's `.claude/` gitignore rule. **It is NOT copied into the fixture working tree.** Earlier iterations of the recipe did exactly that, but the overlay file and the hook source both name Recce vocabulary (`mcp__recce__*`, `Bash(recce *)`, `RECCE_API_TOKEN`, recce-shaped tokens in the hook code), and a Tier-0 agent doing non-adversarial recursive reads (`grep -r recce .`, `find . -type f -exec cat {} \;`, `cat .*/settings.json`) would reach those tokens through bypass shapes the AST hook cannot pre-empt (glob expansion happens after the hook reads the literal argument). The eval runner now renders the template settings.json to a path *outside* the agent's cwd and loads it via `claude --settings <abs-path>`, leaving the agent's cwd a pristine dbt project with no Recce-shaped files at all. Verified on Claude Code v2.1.160.

## Quick start

**Claude Code, Tier 0:**

```bash
SLUG="pr1-fix-clv"
WT_ROOT="$(git rev-parse --show-toplevel)"
FIXTURE_DIR="${WT_ROOT}/evals/agent-blind-spots/.tmp/sources/${SLUG}"
TIER_DIR="${WT_ROOT}/evals/agent-blind-spots/runner-configs/claude-code/tier-0"

# Render the template with an absolute hook path (both file paths live
# OUTSIDE the fixture cwd by design).
HOOK_PATH="${TIER_DIR}/claude-overlay/hooks/deny-tier-0.py"
RENDERED_DIR="$(mktemp -d)"
RENDERED_SETTINGS="${RENDERED_DIR}/tier-0.json"
python3 -c "
from pathlib import Path
tpl = Path('${TIER_DIR}/claude-overlay/settings.json').read_text()
Path('${RENDERED_SETTINGS}').write_text(tpl.replace('\${RUNNER_HOOK_PATH}', '${HOOK_PATH}'))
"

# Optional but recommended — neuter user-level settings for this run:
export CLAUDE_CONFIG_DIR="$(mktemp -d)"

cd "${FIXTURE_DIR}"
claude --settings "${RENDERED_SETTINGS}" \
       "<the prompt — see RUBRIC.md Tier-0 prompt-shape contract>"
```

**Codex, Tier 0:** see [`codex/tier-0/README.md`](codex/tier-0/README.md).

## Why both `permissions.deny` and a `PreToolUse` hook

Claude Code's `permissions.deny` uses shell-glob matching that is conceded to be unreliable: open issue [anthropics/claude-code#6699](https://github.com/anthropics/claude-code/issues/6699) shows bypasses, and the glob shape can't express the things the rubric requires (path-stripped basenames, `sh -c "<banned>"` recursion, dbt subcommands with global flags interposed, case-insensitive skill matching, nested `$()` smuggling, ANSI-C / parameter-expansion head smuggling).

The PreToolUse hook is therefore the **load-bearing layer**, not a backup. It parses each Bash command with `bashlex` (a real Bash AST parser) and walks the AST — substitutions, ANSI-C quoting, parameter defaults, Bash keywords, command modifiers, and exec wrappers are handled by their AST shape rather than regex.

**`permissions.deny` and the hook do not mirror each other**, and that's deliberate:

* `permissions.deny` covers only what shell-glob can express crisply — the user-facing documented attack surface.
* The hook covers the full surface, including the bypass shapes the glob can't address.

Treat `permissions.deny` as documentation for human readers. Trust the hook for enforcement.

## Prerequisite: `bashlex`

The hook depends on `bashlex`. Install once in the eval-runner Python:

```bash
python3 -m pip install bashlex
```

Without `bashlex` the hook fails closed (exit 2 with an install message) so a missing dependency cannot silently allow bypasses.

## Maintenance

When you add a new Recce CLI verb, new MCP tool namespace, or a new dbt subcommand that mutates state:

1. Update the hook script (`deny-tier-{0,1}.py`) — it's the source of truth.
2. Update the documented `permissions.deny` patterns to match the new shape.
3. Add the new shape to the Bypass attempts table in `runs/<date>/sandbox-verification.md` so a future regression is caught.

The hook's MCP namespace regex is `^mcp__(plugin_)?recce(_|-|$)` — adding a `mcp__recce_<foo>__*` namespace is automatically covered. New Bash basenames (e.g. a `recce` CLI rename, a new SQL client, a new dbt subcommand) require a Python-level change to `DENIED_BINS` / `DBT_DENIED_SUBCOMMANDS` / `TIER_0_ALLOWLIST` / `EXEC_WRAPPERS` / `SHELL_WRAPPERS` / `TRANSPARENT_PREFIXES`.
