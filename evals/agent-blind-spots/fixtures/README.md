# Fixtures — Agent Blind Spots / `/recce-verify` v1

Six PR fixtures from [`DataRecce/jaffle_shop_golden`](https://github.com/DataRecce/jaffle_shop_golden) covering distinct verification classes (semantic, row-grain, refactor, type, schema-expansion, multi-model). One directory per fixture, each holding a README, a frozen Tier-0 baseline template, the base/head commit SHAs (`commits.txt`), and a small source-models `diff.patch`.

## Artifacts are not committed — build them locally

The large dbt artifacts (`manifest-before.json`, `manifest-after.json`, `catalog-*.json`, `compiled-before/`, `compiled-after/`) are **gitignored** and produced by the build script. Run it once before each eval run:

```bash
cd evals/agent-blind-spots
./build_fixtures.sh
```

The script clones `DataRecce/jaffle_shop_golden` into `.tmp/jaffle_shop_golden/` (also gitignored), swaps the upstream Snowflake `profiles.yml` for a local DuckDB profile, then for each fixture checks out the base + head (+ intermediate for PR #20), runs `dbt deps && dbt parse && dbt compile && dbt docs generate` against an empty DuckDB, and writes the outputs into `fixtures/<slug>/artifacts/`. Host-specific manifest fields (`user_id`, `invocation_id`, `root_path`) are scrubbed.

Re-running is idempotent — existing `artifacts/` directories are removed and rebuilt.

## Index

| Fixture | Source PR | Class | Notes |
|---------|-----------|-------|-------|
| [`pr1-fix-clv`](./pr1-fix-clv/) | [#13](https://github.com/DataRecce/jaffle_shop_golden/pull/13) | semantic | Adds `where status='completed'` inside `customers.customer_payments` CTE. |
| [`pr42-is-closed-filter`](./pr42-is-closed-filter/) | [#14](https://github.com/DataRecce/jaffle_shop_golden/pull/14) | row-grain | New `is_closed` column + `where is_closed=true` on `orders`. Different (older) base SHA than the rest. |
| [`pr2-refactor-cte-to-models`](./pr2-refactor-cte-to-models/) | [#15](https://github.com/DataRecce/jaffle_shop_golden/pull/15) | refactor | Behavior-preserving; the negative control for the rubric. |
| [`pr3-amount-double-to-decimal`](./pr3-amount-double-to-decimal/) | [#16](https://github.com/DataRecce/jaffle_shop_golden/pull/16) | type | `amount` narrowed to `DECIMAL(10,2)`. PR has a mechanical merge commit on top of the substantive change at `6ffc23f`; fixture captures the merge head. |
| [`pr44-promotion-flags`](./pr44-promotion-flags/) | [#20](https://github.com/DataRecce/jaffle_shop_golden/pull/20) | schema-expansion | Plus an *intermediate-commit* artifact snapshot for the row-filter accident at `23b96ca` (reverted by `1500eb4`). Uses Snowflake-specific `boolor_agg` — DuckDB does not validate at compile but would fail at execute. |
| [`pr46-net-clv-segments`](./pr46-net-clv-segments/) | [#2](https://github.com/DataRecce/jaffle_shop_golden/pull/2) | multi-model semantic | "Stress-test" fixture — redefines `customer_lifetime_value` in place, introduces three row filters on payments, copy-pastes a threshold for `net_value_segment`, and adds a `finance_revenue` model with no downstream consumers. |

## Per-fixture layout

```
fixtures/<slug>/
├── README.md                                ← what the PR does, expected verdicts without/with Recce, caveats
├── tier-0-baseline.md                       ← template instance, fields filled in by the eval runner
├── commits.txt                              ← base + head SHAs (and intermediate for PR #20)
├── diff.patch                               ← source-model diff base..head (small, reading-friendly)
└── artifacts/                               ← gitignored — produced by build_fixtures.sh
    ├── manifest-before.json                 ← `target/manifest.json` from `dbt parse` on base SHA
    ├── manifest-after.json                  ← same on head SHA
    ├── compiled-before/                     ← `target/compiled/` from `dbt compile` on base SHA
    ├── compiled-after/                      ← same on head SHA
    ├── catalog-before.json                  ← `target/catalog.json` from `dbt docs generate` on base SHA (empty data)
    └── catalog-after.json                   ← same on head SHA
```

`pr44-promotion-flags/` additionally has a top-level `diff-from-base-to-intermediate.patch` (committed) and an `artifacts/intermediate-commit-23b96ca/` directory (gitignored) with `manifest.json`, `compiled/`, and `catalog.json` for the problematic intermediate commit.

## Caveats — rolled up

- **PR #16 (`pr3-amount-double-to-decimal`)** — head SHA `1c56861` is a mechanical merge commit; the substantive type narrowing lives at `6ffc23f`. The fixture captures the merge head; the source-models diff is identical.
- **PR #20 (`pr44-promotion-flags`)** — four-commit PR. The row-filter accident lives at the intermediate commit `23b96ca` and was reverted at `1500eb4`. Snowflake-specific `boolor_agg` appears in source but compiles fine under DuckDB (no compile-time function validation); it would fail at execute on DuckDB.
- **PR #2 (`pr46-net-clv-segments`)** — the "stress test" of the set. Redefines `customer_lifetime_value` in place, introduces three row filters on `payments`, copy-pastes a magic threshold for `net_value_segment`, and adds a `finance_revenue` model with no downstream consumers. Largest diff in the set.
- **Catalog row/column stats are zero everywhere** — `dbt docs generate` runs against an empty DuckDB, so `catalog-*.json` carries schema info (column names, types) but **no row counts and no column stats**. Do not score rubric items off catalog row stats.
- **PR #14 (`pr42-is-closed-filter`)** uses an older base SHA (`62d6dc9`) than the rest (`f09861a`). Don't mix bases when computing inter-fixture deltas.

## dbt environment

The source repo `jaffle_shop_golden` ships a **Snowflake-only** `profiles.yml`. Compile and docs-generate against Snowflake require warehouse credentials, which the eval baseline explicitly does not have. The fixture build pipeline therefore swaps in a local DuckDB profile *for parse/compile/docs-generate only*. The model SQL is portable between the two adapters with one exception noted above (`boolor_agg` in PR #20).

Pinned versions for reproducibility:

| Component | Version |
|-----------|---------|
| Python | 3.11.11 |
| dbt-core | 1.11.9 |
| dbt-duckdb | 1.10.1 |
| duckdb | 1.5.2 |
| dbt packages | `data-mie/dbt_profiler@0.8.1`, `dbt-labs/dbt_utils@0.9.6`, `dbt-labs/audit_helper@0.11.0` (per upstream `packages.yml`) |

## Reproducing or extending

- Add a fixture: create `fixtures/<slug>/{README.md,tier-0-baseline.md,commits.txt,diff.patch}` and re-run `build_fixtures.sh`. The script reads `commits.txt` to discover the SHAs to build against.
- Required system tools: `uv`, `git`. Everything else is installed into `evals/agent-blind-spots/.tmp/.venv/` from pinned versions in the script.
- **GitHub access**: `DataRecce/jaffle_shop_golden` is a **private** repo. The first run clones it over HTTPS, which requires either (a) a credential helper with access to the repo, or (b) running `gh auth setup-git` once so `git clone https://github.com/...` uses your `gh` token. Subsequent runs only `git fetch`, so the credential only matters on first clone. If you hit a "Repository not found / authentication failed" error, that's the cause.
- Eval-baseline assets are **warehouse-free** — the local-dbt-only artifacts (manifest, compiled SQL, catalog, git diff) plus the per-fixture head-SHA source tree at `.tmp/sources/<slug>/` are the canonical Tier-0 inputs.

## `commits.txt` format

One SHA per line, with an optional message after the first whitespace. The first non-comment line is treated as the head; the build script also reads the per-fixture `README.md` to discover the base SHA (look for ``- Base SHA: `<sha>` ``). For PR #20, the intermediate commit is the line with SHA `23b96ca`.
