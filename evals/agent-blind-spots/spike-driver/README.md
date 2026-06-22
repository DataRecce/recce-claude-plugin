# Spike driver — DRC-3586

Single-file Python driver for the Karpathy-style spike in [DRC-3586](https://linear.app/recce/issue/DRC-3586). De-risks two unknowns before any durable-harness work (DRC-3587):

1. **Judge stability** — does the Claude-as-judge prompt produce consistent verdicts on the locked three-axis rubric?
2. **Codex-under-sandbox** — does Codex behave in a programmatic loop under the Tier-0 / Tier-1 sandbox profiles from DRC-3584?

Not the durable harness. Output artifacts live under `runs/<date>/spike-driver/`. If the spike's stability + sandbox checks pass, the next ticket (DRC-3587) ports this to Inspect AI; if they fail, the project falls back to Candidate B (manual scoring loop).

## Prereqs

- Per-fixture worktrees built: `( cd evals/agent-blind-spots && ./build_fixtures.sh )`
- `bashlex` installed for the Claude Code Tier-0/1 PreToolUse hook: `python3 -m pip install bashlex`
- `claude` CLI on PATH (for both agent + judge passes)
- `codex` CLI on PATH (optional — codex cells skip gracefully if missing)
- `uv` available (per repo convention)

## Auth note — `CLAUDE_CONFIG_DIR`

`ENFORCEMENT.md` recipe step 3 sets `CLAUDE_CONFIG_DIR=$(mktemp -d)` to neuter
a stray `~/.claude/settings.json`. The driver **does not** apply that override
by default because it also strips the auth state — the child `claude --print`
fails with `Not logged in`. For unattended runs the load-bearing enforcement is
the project-level `.claude/settings.json` overlay (stamped per cell) plus the
`PreToolUse` hook; a user-level `permissions.allow` cannot bypass an exit-2
hook regardless.

To enable the strict override (paranoid mode), set:

```bash
RECCE_EVAL_STRICT_CONFIG=1 uv run driver.py --smoke
```

You must preseed auth under the per-cell `_claude_cfg/<fixture>_t<n>/` dir
before each run; the driver does not provision auth.

## Usage

```bash
# Smoke test (1 fixture × 2 agents × 2 tiers = 4 cells, ~5-10 min)
uv run evals/agent-blind-spots/spike-driver/driver.py --smoke

# Full run (6 fixtures × 2 agents × 2 tiers = 24 cells, ~1-2 hours)
uv run evals/agent-blind-spots/spike-driver/driver.py

# Limit to one agent / tier
uv run evals/agent-blind-spots/spike-driver/driver.py --agents claude --tiers 0

# Double-judge each transcript for self-consistency
uv run evals/agent-blind-spots/spike-driver/driver.py --judge-stability

# Re-judge an existing run without re-running agents
uv run evals/agent-blind-spots/spike-driver/driver.py \
  --no-run --run-dir evals/agent-blind-spots/runs/2026-05-29/spike-driver/

# Compare judge verdicts to DRC-3585 manual baseline once it lands
uv run evals/agent-blind-spots/spike-driver/driver.py \
  --baseline-dir evals/agent-blind-spots/fixtures/
```

## Output layout

```
runs/<date>/spike-driver/
├── transcripts/                   # raw agent stdout/stderr per cell
│   ├── pr1-fix-clv_claude_t0.md
│   ├── pr1-fix-clv_claude_t1.md
│   ├── pr1-fix-clv_codex_t0.md
│   └── ...
├── _claude_cfg/                   # neutered CLAUDE_CONFIG_DIR per cell
├── verdicts.csv                   # one row per cell
├── cells.json                     # raw cells (re-judgeable)
└── summary.md                     # rendered matrix + stability check
```

## Stability checks

Two ways to validate judge quality (use both when possible):

**Self-consistency** (`--judge-stability`): judges each transcript twice in independent subprocess calls; reports per-axis agreement. Floor: ≥80% on each of catch / tier / delta. Below that, the judge is too noisy to replace hand-grading.

**Judge vs human** (`--baseline-dir <path>`): if [DRC-3585](https://linear.app/recce/issue/DRC-3585)'s manual rubric-lock has produced `fixtures/<id>/tier-0-baseline.md` files, this compares the judge's catch verdict for Tier-0 cells to the human's. This is the canonical check from DRC-3586's acceptance criterion 2; self-consistency is the proxy when no manual baseline exists yet.

## Codex-under-sandbox check

After a run, grep transcripts under `transcripts/*_codex_*.md` for:

- `mcp__recce__*` references in Tier-0 → leak (MCP table is empty in `runner-configs/codex/tier-0/config.toml`).
- `recce ` shell calls in Tier-0 → check exit was non-zero (PATH scrub).
- Reads of `../README.md` or `../../RUBRIC.md` → leak (cwd separation).
- `dbt ` shell calls in either tier → check exit was non-zero (PATH scrub).

If every Codex cell ran to completion without these escape attempts succeeding, criterion 3 passes.

## Non-goals (deferred to DRC-3587 / DRC-3405)

- Durable harness with resume / parallel dispatch — that's Inspect AI.
- Gap-report generator across 6 fixtures — that's DRC-3405.
- Auto-iteration on prompt / skill changes — explicit non-goal of the spike (closed-loop optimization overfits at N=6).
