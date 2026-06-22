#!/usr/bin/env python3
"""Karpathy-style spike driver for /recce-verify v1 eval (DRC-3586).

Dispatches up to 6 fixtures × 2 agents × 2 tiers = 24 cells, captures
each agent's transcript, runs a Claude-as-judge pass per transcript to
produce a three-axis verdict (catch / tier / delta), and writes a
CSV + Markdown summary under `runs/<date>/spike-driver/`.

Two stability modes:
  --judge-stability     Run the judge twice per cell; report self-consistency.
  --baseline-dir <dir>  Compare judge verdicts against DRC-3585 manual baseline.

Both are optional. Without either, the driver still produces a verdict
matrix; stability checks are how you decide whether the judge can replace
hand-grading at N=6.

Usage:
  uv run driver.py --smoke               # 1 fixture × 2 agents × 2 tiers
  uv run driver.py                       # full 24-cell run
  uv run driver.py --agents claude       # claude only
  uv run driver.py --tiers 0             # tier-0 only
  uv run driver.py --judge-stability     # double-judge for self-consistency
  uv run driver.py --no-run \\
                   --run-dir runs/2026-05-29/spike-driver/   # re-judge only
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

SPIKE_DIR = Path(__file__).resolve().parent
EVAL_DIR = SPIKE_DIR.parent
SOURCES_DIR = EVAL_DIR / ".tmp" / "sources"
RUNS_DIR = EVAL_DIR / "runs"
RUNNER_CONFIGS = EVAL_DIR / "runner-configs"

DEFAULT_FIXTURES = (
    "pr1-fix-clv",
    "pr2-refactor-cte-to-models",
    "pr3-amount-double-to-decimal",
    "pr42-is-closed-filter",
    "pr44-promotion-flags",
    "pr46-net-clv-segments",
)
AGENTS = ("claude", "codex")
TIERS = (0, 1)

AGENT_PROMPT = (
    "Review this dbt PR. The current working directory is the dbt project at the "
    "head SHA (models/, dbt_project.yml, etc.). The frozen Tier-0 inputs are "
    "staged under `_eval_inputs/`:\n"
    "  - _eval_inputs/diff.patch — source-model diff base..head\n"
    "  - _eval_inputs/artifacts/manifest-{before,after}.json — dbt manifests pre/post\n"
    "  - _eval_inputs/artifacts/compiled-{before,after}/ — compiled SQL pre/post\n"
    "  - _eval_inputs/artifacts/catalog-{before,after}.json — schema-only (row stats are zero)\n"
    "Decide catch / miss / partial per the rubric. Recommend "
    "approve / request-changes / abstain. End your output with one line, exactly:\n"
    "VERDICT: <catch|miss|partial> · <approve|request-changes|abstain>"
)

JUDGE_SYSTEM = (
    "You are a strict, terse judge. Score the agent transcript against the "
    "locked three-axis rubric (catch, primary evidence tier, counterfactual "
    "delta vs Tier-0 baseline). Emit ONLY JSON. No prose outside JSON."
)

JUDGE_USER_TEMPLATE = """Rubric (excerpt):
{rubric}

Fixture: {fixture}
Agent: {agent}
Tier: {tier}
Tier-0 baseline catch for this fixture (if known): {baseline_catch}

Agent transcript:
---
{transcript}
---

Emit JSON ONLY in this exact shape:
{{
  "catch": "catch" | "miss" | "partial",
  "tier": "0" | "1a" | "1b" | "1c" | "2",
  "delta": "improvement" | "same" | "regression",
  "reasoning": "1-2 sentences citing the decisive evidence the agent used"
}}
"""


@dataclass
class Cell:
    fixture: str
    agent: str
    tier: int
    model: str | None = None
    transcript_path: str | None = None
    returncode: int | None = None
    verdict: dict | None = None
    verdict_2: dict | None = None
    error: str | None = None


def cli_available(name: str) -> bool:
    return shutil.which(name) is not None


def scrub_env(extra_unset: tuple[str, ...] = ()) -> dict:
    env = os.environ.copy()
    for var in (
        "RECCE_API_TOKEN", "DBT_PROFILES_DIR",
        "SNOWFLAKE_USER", "SNOWFLAKE_PASSWORD", "SNOWFLAKE_ACCOUNT",
        "POSTGRES_PASSWORD", "BIGQUERY_PROJECT", *extra_unset,
    ):
        env.pop(var, None)
    return env


def scrub_path(strip_patterns: tuple[str, ...]) -> str:
    pat = re.compile("|".join(strip_patterns))
    return ":".join(p for p in os.environ.get("PATH", "").split(":") if not pat.search(p))


def codex_tier0_path(stub_bin: Path) -> str:
    """Return a PATH for Codex Tier-0 that genuinely masks `recce`/`dbt`.

    The earlier regex scrub only stripped directories whose path contained
    `/recce/` or `/dbt/` literally; bin dirs like `/opt/homebrew/bin`,
    `~/.local/bin`, and `.venv/bin` (where the real binaries live) survived
    the scrub. Prepending `stub-bin/` — which contains `recce` and `dbt`
    scripts that exit 127 — makes the masking real: shell name resolution
    hits the stub first.
    """
    # Belt-and-suspenders: keep the regex scrub for any path literally
    # containing /recce/ or /dbt/ or .recce, AND prepend the stub-bin so
    # the standard bin dirs are overridden.
    scrubbed = scrub_path((r"/recce(/|$)", r"/dbt(/|$)", r"\.recce"))
    return f"{stub_bin}:{scrubbed}" if scrubbed else str(stub_bin)


def assert_codex_tier0_masked(env: dict, cwd: Path) -> None:
    """Fail fast if `recce`/`dbt` resolve to anything other than the stub.

    Codex's Tier-0 Recce/dbt block is now PATH stub-bin masking; the cell
    is contaminated the moment `recce list` or `dbt list` could actually
    run. Run `command -v` under the scrubbed env before invoking the
    agent — if either resolves outside the stub-bin, abort.
    """
    stub_bin_dir = str(RUNNER_CONFIGS / "codex" / "tier-0" / "stub-bin")
    for binary in ("recce", "dbt"):
        proc = subprocess.run(
            ["bash", "-c", f"command -v {binary} || true"],
            cwd=str(cwd), env=env, capture_output=True, text=True, timeout=5,
        )
        resolved = proc.stdout.strip()
        if resolved and not resolved.startswith(stub_bin_dir):
            raise RuntimeError(
                f"Codex Tier-0 PATH masking failed: '{binary}' resolves to "
                f"{resolved!r} (expected stub under {stub_bin_dir!r}). "
                "Aborting before the cell runs to avoid contaminating the "
                "Tier-0 baseline."
            )


def stage_inputs(fixture_dir: Path, fixture_id: str) -> None:
    """Stage frozen Tier-0 inputs into the agent's cwd at `_eval_inputs/`.

    Symlinks `fixtures/<id>/{diff.patch, artifacts/}` into a `_eval_inputs/`
    subdirectory of the per-fixture worktree, so an agent whose sandbox is
    anchored on cwd (notably Codex Tier-0 read-only) can still reach the
    frozen artifacts. Without this, only Claude Code (which doesn't anchor
    Read on cwd) could see the inputs.

    Raises FileNotFoundError if neither `diff.patch` nor `artifacts/` exists
    under `fixtures/<id>/`; otherwise the agent would see an empty
    `_eval_inputs/` and review the PR with no Tier-0 inputs (silent miss).
    """
    src_root = EVAL_DIR / "fixtures" / fixture_id
    if not src_root.exists():
        raise FileNotFoundError(f"fixture dir missing: {src_root}")
    dst = fixture_dir / "_eval_inputs"
    if dst.is_symlink() or dst.exists():
        if dst.is_symlink():
            dst.unlink()
        else:
            shutil.rmtree(dst)
    dst.mkdir()
    staged = 0
    for name in ("diff.patch", "artifacts"):
        src = src_root / name
        if src.exists():
            (dst / name).symlink_to(src.resolve())
            staged += 1
    if staged == 0:
        dst.rmdir()
        raise FileNotFoundError(
            f"no Tier-0 inputs under {src_root} (need diff.patch and/or artifacts/); "
            "did build_fixtures.sh complete for this fixture?"
        )


def render_claude_settings(tier: int, run_dir: Path, fixture_name: str) -> Path:
    """Render the Tier-N settings.json template to a per-cell temp location.

    Andy's iter-8 BLOCKER (Tier-0 overlay leak): a copied-into-cwd
    `.claude/{settings.json, hooks/deny-tier-N.py}` is reachable by a
    non-adversarial agent through ordinary recursive reads
    (`grep -r recce .`, `find . -type f -exec cat {} \\;`, `cat .*/settings.json`)
    that the Bash AST hook cannot see ahead of glob expansion. Pass 0
    token-matching is whack-a-mole; the root cause is structural —
    Recce-shaped files in the agent's cwd.

    The fix (verified by Andy on CC v2.1.160): load the settings via
    `claude --settings <abs-path>` from *outside* cwd, with the hook
    `command` field pointing to an absolute path also outside cwd. This
    keeps the agent's cwd a pristine dbt project with no Recce-shaped
    files whatsoever, making the leak structurally impossible.

    The template at `runner-configs/claude-code/tier-{tier}/claude-overlay/
    settings.json` declares the hook command as `python3
    "${RUNNER_HOOK_PATH}"`; we substitute that placeholder with the
    absolute path to the corresponding `deny-tier-{tier}.py` (which lives
    in the runner-configs tree, also outside cwd) and write the rendered
    file under `run_dir/_settings/<fixture>_t<tier>.json`. The runner
    passes that rendered path to `claude --settings`.
    """
    tier_dir = RUNNER_CONFIGS / "claude-code" / f"tier-{tier}"
    template_path = tier_dir / "claude-overlay" / "settings.json"
    hook_path = (tier_dir / "claude-overlay" / "hooks" / f"deny-tier-{tier}.py").resolve()

    template_text = template_path.read_text()
    rendered_text = template_text.replace("${RUNNER_HOOK_PATH}", str(hook_path))

    settings_dir = run_dir / "_settings"
    settings_dir.mkdir(parents=True, exist_ok=True)
    rendered_path = settings_dir / f"{fixture_name}_t{tier}.json"
    rendered_path.write_text(rendered_text)
    return rendered_path


def run_claude(fixture_dir: Path, tier: int, run_dir: Path, prompt: str, model: str | None) -> tuple[Path, int]:
    # No overlay copy. The settings.json + hook live outside cwd; cwd
    # stays a pristine dbt project with `_eval_inputs/` symlink + project
    # files only. See render_claude_settings() for the rationale.
    settings_path = render_claude_settings(tier, run_dir, fixture_dir.name)

    transcript_path = run_dir / "transcripts" / f"{fixture_dir.name}_claude_t{tier}.md"
    transcript_path.parent.mkdir(parents=True, exist_ok=True)

    # NOTE: ENFORCEMENT.md recipe step 3 (CLAUDE_CONFIG_DIR=$(mktemp -d)) is
    # *intentionally not applied here* — neutering ~/.claude/ also strips the
    # auth state, which breaks unattended runs. The load-bearing enforcement
    # for Tier-0 is the `--settings` override + the PreToolUse hook
    # (deny-tier-N.py); a stray user-level `permissions.allow` cannot bypass
    # an exit-2 hook. For paranoid mode, set RECCE_EVAL_STRICT_CONFIG=1 to
    # override CLAUDE_CONFIG_DIR; the cell will fail with "Not logged in"
    # unless auth is preseeded under that dir.
    env = scrub_env()
    if os.environ.get("RECCE_EVAL_STRICT_CONFIG"):
        cfg_dir = run_dir / "_claude_cfg" / f"{fixture_dir.name}_t{tier}"
        cfg_dir.mkdir(parents=True, exist_ok=True)
        env["CLAUDE_CONFIG_DIR"] = str(cfg_dir)

    cmd = [
        "claude", "--print",
        "--settings", str(settings_path),
        "--dangerously-skip-permissions",
    ]
    if model:
        cmd += ["--model", model]
    cmd.append(prompt)
    proc = subprocess.run(
        cmd, cwd=str(fixture_dir), env=env, capture_output=True, text=True, timeout=900,
    )
    transcript_path.write_text(
        f"# Cell: {fixture_dir.name} · claude · tier-{tier}\n"
        f"# model: {model or '(unpinned)'}\n"
        f"# returncode: {proc.returncode}\n\n"
        f"## stdout\n{proc.stdout}\n\n## stderr\n{proc.stderr}\n"
    )
    return transcript_path, proc.returncode


def run_codex(fixture_dir: Path, tier: int, run_dir: Path, prompt: str, model: str | None) -> tuple[Path, int]:
    tier_dir = RUNNER_CONFIGS / "codex" / f"tier-{tier}"
    config = tier_dir / "config.toml"
    sandbox = "read-only" if tier == 0 else "workspace-write"

    transcript_path = run_dir / "transcripts" / f"{fixture_dir.name}_codex_t{tier}.md"
    transcript_path.parent.mkdir(parents=True, exist_ok=True)

    env = scrub_env()
    if tier == 0:
        # Tier 0: real PATH masking via stub-bin (the earlier regex-only
        # scrub left `recce`/`dbt` reachable via `/opt/homebrew/bin`,
        # `.venv/bin`, etc.). Pre-flight `command -v` confirms the mask.
        stub_bin = tier_dir / "stub-bin"
        env["PATH"] = codex_tier0_path(stub_bin)
        assert_codex_tier0_masked(env, fixture_dir)
    else:
        # Tier 1: strip only dbt-named directories; Recce CLI must remain
        # reachable. Single-env warehouse credentials are inherited from
        # the parent shell; operator is responsible for absence of
        # base/prod creds (see codex/tier-1/README.md).
        env["PATH"] = scrub_path((r"/dbt(/|$)",))

    cmd = ["codex", "exec",
           f"--sandbox={sandbox}",
           "--ask-for-approval=never",
           "--config", str(config)]
    if model:
        cmd += ["--model", model]
    cmd.append(prompt)
    proc = subprocess.run(
        cmd, cwd=str(fixture_dir), env=env, capture_output=True, text=True, timeout=900,
    )
    transcript_path.write_text(
        f"# Cell: {fixture_dir.name} · codex · tier-{tier}\n"
        f"# model: {model or '(unpinned)'}\n"
        f"# returncode: {proc.returncode}\n\n"
        f"## stdout\n{proc.stdout}\n\n## stderr\n{proc.stderr}\n"
    )
    return transcript_path, proc.returncode


def reset_fixture_dir(fixture_dir: Path) -> None:
    """Reset the fixture worktree to its committed HEAD before a cell runs.

    Each fixture's `.tmp/sources/<slug>/` directory is reused across all
    4 cells (claude×{0,1}, codex×{0,1}). Without an explicit reset, a
    write from cell N (Claude Code at Tier 0 was previously
    write-capable; Tier 1 is write-capable by design for staging Recce
    artifacts) persists into cell N+1, breaking the "all cells start
    from the same base" contract in ENFORCEMENT.md.

    `_eval_inputs/` is staged by stage_inputs() *after* this reset so
    the symlinks survive — git treats them as untracked and
    `git clean -fdx` removes them, which is intended (stage_inputs()
    re-creates them per cell).
    """
    subprocess.run(
        ["git", "reset", "--hard", "HEAD"],
        cwd=str(fixture_dir), check=True, capture_output=True, text=True,
    )
    subprocess.run(
        ["git", "clean", "-fdx"],
        cwd=str(fixture_dir), check=True, capture_output=True, text=True,
    )


def run_cell(cell: Cell, run_dir: Path, model: str | None) -> None:
    fixture_dir = SOURCES_DIR / cell.fixture
    if not fixture_dir.exists():
        cell.error = f"per-fixture worktree missing: {fixture_dir} (did you run build_fixtures.sh?)"
        return
    if not cli_available(cell.agent):
        cell.error = f"{cell.agent} CLI not found on PATH; skipping"
        return
    # Reset the fixture worktree before staging inputs, so each cell
    # starts from the same base — no Claude write from a prior cell
    # bleeds across. Must run *before* stage_inputs() (whose
    # `_eval_inputs/` symlinks are untracked and would be removed by
    # `git clean -fdx`). The Claude Code settings are loaded via
    # `--settings <abs-path>` outside cwd (see render_claude_settings),
    # so the fixture cwd stays Recce-shaped-free.
    try:
        reset_fixture_dir(fixture_dir)
    except subprocess.CalledProcessError as e:
        cell.error = (
            f"reset_fixture_dir failed for {fixture_dir}: "
            f"rc={e.returncode}; stderr={(e.stderr or '').strip()[:200]}"
        )
        return
    try:
        stage_inputs(fixture_dir, cell.fixture)
    except FileNotFoundError as e:
        cell.error = f"stage_inputs failed: {e}"
        return
    cell.model = model
    try:
        if cell.agent == "claude":
            path, rc = run_claude(fixture_dir, cell.tier, run_dir, AGENT_PROMPT, model)
        else:
            path, rc = run_codex(fixture_dir, cell.tier, run_dir, AGENT_PROMPT, model)
        cell.transcript_path = str(path)
        cell.returncode = rc
    except subprocess.TimeoutExpired:
        cell.error = f"{cell.agent} timed out after 900s"
    except FileNotFoundError as e:
        cell.error = f"{cell.agent} setup failed: {e}"
    except RuntimeError as e:
        # Pre-flight assertion failures (e.g., Codex Tier-0 PATH masking
        # didn't take) surface here so the cell is recorded as errored
        # rather than producing a contaminated transcript.
        cell.error = f"{cell.agent} pre-flight failed: {e}"


def _shrink(text: str, limit: int = 30000) -> str:
    if len(text) <= limit:
        return text
    half = limit // 2
    return text[:half] + "\n…[truncated]…\n" + text[-half:]


def judge_cell(cell: Cell, rubric: str, baseline_catch: str, model: str | None) -> dict:
    if not cell.transcript_path:
        return {"error": "no transcript"}
    transcript = _shrink(Path(cell.transcript_path).read_text())
    user = JUDGE_USER_TEMPLATE.format(
        rubric=_shrink(rubric, 8000),
        fixture=cell.fixture, agent=cell.agent, tier=cell.tier,
        transcript=transcript, baseline_catch=baseline_catch,
    )
    judge_cmd = ["claude", "--print", "--dangerously-skip-permissions"]
    if model:
        judge_cmd += ["--model", model]
    judge_cmd += ["--append-system-prompt", JUDGE_SYSTEM, user]
    proc = subprocess.run(
        judge_cmd, capture_output=True, text=True, timeout=300,
    )
    if proc.returncode != 0:
        return {"error": f"judge rc={proc.returncode}", "stderr": proc.stderr[:300]}
    text = proc.stdout.strip()
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < 0:
        return {"error": "no JSON in judge output", "raw": text[:500]}
    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError as e:
        return {"error": f"JSON parse: {e}", "raw": text[start:end + 1][:500]}


def parse_baseline_dir(baseline_dir: Path) -> dict[str, str]:
    """Extract `catch / miss / partial` per fixture from tier-0-baseline.md files.

    Expects files at <baseline_dir>/<fixture-id>/tier-0-baseline.md following
    the template at templates/tier-0-baseline.md. Returns {fixture: catch}.
    """
    out: dict[str, str] = {}
    if not baseline_dir or not baseline_dir.exists():
        return out
    catch_re = re.compile(r"Catch\s*/\s*miss\s*/\s*partial:\s*`?(catch|miss|partial)`?", re.IGNORECASE)
    for sub in baseline_dir.iterdir():
        baseline = sub / "tier-0-baseline.md"
        if baseline.is_file():
            m = catch_re.search(baseline.read_text())
            if m:
                out[sub.name] = m.group(1).lower()
    return out


def axis_agreement(cells: list[Cell], axis: str) -> tuple[int, int]:
    paired = [
        (c.verdict, c.verdict_2) for c in cells
        if c.verdict and c.verdict_2 and "error" not in c.verdict and "error" not in c.verdict_2
    ]
    if not paired:
        return 0, 0
    agree = sum(1 for v1, v2 in paired if v1.get(axis) == v2.get(axis))
    return agree, len(paired)


def write_csv(cells: list[Cell], path: Path) -> None:
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow([
            "fixture", "agent", "tier",
            "catch", "evidence_tier", "delta",
            "catch_2", "tier_2", "delta_2",
            "returncode", "error",
        ])
        for c in cells:
            v = c.verdict or {}
            v2 = c.verdict_2 or {}
            w.writerow([
                c.fixture, c.agent, c.tier,
                v.get("catch", ""), v.get("tier", ""), v.get("delta", ""),
                v2.get("catch", ""), v2.get("tier", ""), v2.get("delta", ""),
                "" if c.returncode is None else c.returncode,
                c.error or "",
            ])


def write_summary(cells: list[Cell], path: Path, stability: bool, baseline: dict[str, str]) -> None:
    lines = [
        "# Spike driver run — summary",
        "",
        f"- Run date: {dt.date.today().isoformat()}",
        f"- Cells attempted: {len(cells)}",
        f"- Cells with transcript: {sum(1 for c in cells if c.transcript_path)}",
        f"- Cells judged: {sum(1 for c in cells if c.verdict and 'error' not in c.verdict)}",
        f"- Cells errored: {sum(1 for c in cells if c.error)}",
        "",
        "## Cell matrix",
        "",
        "| Fixture | Agent | Tier | Catch | Evidence | Delta | Status |",
        "|---|---|---|---|---|---|---|",
    ]
    for c in cells:
        v = c.verdict or {}
        status = c.error or ("judge_error" if v.get("error") else "ok")
        lines.append(
            f"| {c.fixture} | {c.agent} | {c.tier} | "
            f"{v.get('catch','-')} | {v.get('tier','-')} | {v.get('delta','-')} | {status} |"
        )

    if stability:
        lines += ["", "## Judge self-consistency (two passes on the same transcript)", ""]
        for axis in ("catch", "tier", "delta"):
            agree, total = axis_agreement(cells, axis)
            pct = f"{agree / total:.0%}" if total else "n/a"
            lines.append(f"- **{axis}**: {pct} ({agree}/{total} double-judged cells)")
        lines += [
            "",
            "**Stability bar:** ≥80% per axis. Below that, the judge can't replace human grading at N=6.",
        ]

    if baseline:
        lines += ["", "## Judge vs DRC-3585 manual baseline (catch axis)", ""]
        compare = [
            (c, baseline[c.fixture])
            for c in cells if c.tier == 0 and c.fixture in baseline and c.verdict and "error" not in c.verdict
        ]
        if compare:
            agree = sum(1 for c, b in compare if (c.verdict or {}).get("catch") == b)
            lines.append(f"- Tier-0 cells with manual baseline available: {len(compare)}")
            lines.append(f"- Judge–human catch agreement: {agree}/{len(compare)} ({agree / len(compare):.0%})")
        else:
            lines.append("- No Tier-0 cells overlap with baseline files; provide --baseline-dir pointing at fixtures/")

    path.write_text("\n".join(lines) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--smoke", action="store_true", help="One fixture × all agents × all tiers")
    parser.add_argument("--agents", default=",".join(AGENTS), help="comma-list of agents")
    parser.add_argument("--tiers", default=",".join(str(t) for t in TIERS), help="comma-list of tiers")
    parser.add_argument("--fixtures", default=",".join(DEFAULT_FIXTURES), help="comma-list of fixtures")
    parser.add_argument("--judge-stability", action="store_true", help="Run judge twice per cell")
    parser.add_argument("--baseline-dir", type=Path, help="DRC-3585 manual baseline dir; compares judge to human on catch axis")
    parser.add_argument("--no-run", action="store_true", help="Skip agent runs; judge existing transcripts in --run-dir")
    parser.add_argument("--run-dir", type=Path, help="Override run output dir (default runs/<date>/spike-driver/)")
    parser.add_argument(
        "--model",
        default="claude-opus-4-5",
        help=(
            "Model id to pin on every agent + judge invocation "
            "(ENFORCEMENT.md:157 requires the runner to pin a single model "
            "across the matrix). Same value is passed to both `claude --model` "
            "and `codex --model`. Use --no-model to opt out for ad-hoc smoke runs."
        ),
    )
    parser.add_argument(
        "--no-model",
        action="store_true",
        help="Skip --model pin (cells fall back to each CLI's default). "
             "Recorded as '(unpinned)' in transcripts and cells.json.",
    )
    args = parser.parse_args()
    model = None if args.no_model else args.model

    agents = [a for a in args.agents.split(",") if a]
    tiers = [int(t) for t in args.tiers.split(",") if t]
    fixtures = list(args.fixtures.split(","))
    if args.smoke:
        fixtures = fixtures[:1]

    run_dir = args.run_dir or (RUNS_DIR / dt.date.today().isoformat() / "spike-driver")
    run_dir.mkdir(parents=True, exist_ok=True)

    rubric_path = EVAL_DIR / "RUBRIC.md"
    rubric = rubric_path.read_text() if rubric_path.exists() else "(RUBRIC.md missing)"
    baseline = parse_baseline_dir(args.baseline_dir) if args.baseline_dir else {}
    if args.baseline_dir and not baseline:
        print(f"[warn] --baseline-dir given but no baselines parsed from {args.baseline_dir}", file=sys.stderr)

    cells: list[Cell] = [
        Cell(fixture=f, agent=a, tier=t)
        for f in fixtures for a in agents for t in tiers
    ]

    if not args.no_run:
        for cell in cells:
            print(f"[run]   {cell.fixture} · {cell.agent} · tier-{cell.tier} · model={model or '(unpinned)'}", file=sys.stderr)
            run_cell(cell, run_dir, model)
            if cell.error:
                print(f"         → {cell.error}", file=sys.stderr)
    else:
        # Re-judge mode: discover existing transcripts in run_dir
        for cell in cells:
            t = run_dir / "transcripts" / f"{cell.fixture}_{cell.agent}_t{cell.tier}.md"
            if t.exists():
                cell.transcript_path = str(t)
            else:
                cell.error = f"no existing transcript at {t}"

    for cell in cells:
        if not cell.transcript_path:
            continue
        baseline_catch = baseline.get(cell.fixture, "unknown")
        print(f"[judge] {cell.fixture} · {cell.agent} · tier-{cell.tier} · model={model or '(unpinned)'}", file=sys.stderr)
        cell.verdict = judge_cell(cell, rubric, baseline_catch, model)
        if args.judge_stability:
            cell.verdict_2 = judge_cell(cell, rubric, baseline_catch, model)

    csv_path = run_dir / "verdicts.csv"
    write_csv(cells, csv_path)
    summary_path = run_dir / "summary.md"
    write_summary(cells, summary_path, args.judge_stability, baseline)
    cells_json = run_dir / "cells.json"
    cells_json.write_text(json.dumps([asdict(c) for c in cells], indent=2))

    print(f"\n[output] verdicts: {csv_path}", file=sys.stderr)
    print(f"[output] summary:  {summary_path}", file=sys.stderr)
    print(f"[output] raw:      {cells_json}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
