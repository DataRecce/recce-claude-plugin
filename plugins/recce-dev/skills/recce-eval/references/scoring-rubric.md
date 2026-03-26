# Scoring Rubric

## Deterministic Scoring

### case_type: problem_exists

| Check Name | Logic | PASS condition |
|------------|-------|---------------|
| `issue_found` | exact match | agent says `true`, ground truth says `true` |
| `root_cause_keywords` | any keyword match (case-insensitive) | agent's `root_cause` contains at least one keyword from `root_cause_keywords` |
| `impacted: <model>` | set membership | each model in ground truth `impacted_models` appears in agent's `impacted_models` |
| `not_impacted: <model>` | set exclusion | each model in ground truth `not_impacted_models` does NOT appear in agent's `impacted_models` |
| `affected_row_count` | exact match | agent's count equals ground truth count |
| `all_tests_pass` | exact match | agent says `true`, ground truth says `true` |

### case_type: no_problem

| Check Name | Logic | PASS condition |
|------------|-------|---------------|
| `issue_found` | exact match | agent says `false` |
| `issues_empty` | length check | agent's `issues` array has 0 elements |
| `no_false_positive: <keyword>` | keyword absence | keyword does NOT appear in agent's `raw_response` (case-insensitive) |

### Aggregate Metrics

- `pass_rate` = pass_count / total
- `pass_count` = number of PASS checks
- `fail_count` = number of FAIL checks

## v2 Deterministic Scoring

### Layer 1 (Review) — case_type: problem_exists

| Check Name | Logic | PASS condition |
|------------|-------|---------------|
| `issue_found` | exact match | agent says `true`, ground truth says `true` |
| `root_cause_keywords` | any keyword match (case-insensitive) | agent's `root_cause` contains at least one keyword from `root_cause_keywords` |
| `impacted: <model>` | set membership | each model in ground truth `impacted_models` appears in agent's `impacted_models` |
| `not_impacted: <model>` | set exclusion | each model in ground truth `not_impacted_models` does NOT appear in agent's `impacted_models` |
| `affected_row_count` | ±20% tolerance | agent's count is within 20% of ground truth count |
| `dashboard_impact` | exact match | agent's `dashboard_impact` matches ground truth |

**Changes from v1:**
- `affected_row_count` uses ±20% tolerance (v1 used exact match)
- `dashboard_impact` is a new check (v1 had no dashboard dimension)
- `all_tests_pass` removed (v2 scenarios always have passing tests by design)
- `not_impacted_models` list reduced to ambiguous cases only (v1 listed all models)

### v2 LLM Judge

Two dimensions on a 0-3 scale (replaces v1's 5 dimensions on 1-5 scale):

**Evidence Quality** (both layers):
- 0: Conclusion based only on code reading, no data evidence
- 1: Mentions data but no specific numbers
- 2: Has row count or value comparison, but incomplete
- 3: Complete data evidence (row counts + value diff + distribution analysis)

**Self-Verification** (Layer 2 only, future):
- 0: No verification after completion
- 1: Ran dbt test only
- 2: Some data-level verification, incomplete
- 3: Systematic — confirmed new data correct, existing data unchanged, downstream safe

## v1 LLM Judge Scoring

See `${CLAUDE_PLUGIN_ROOT}/agents/eval-judge.md` for the 5 scoring dimensions and calibration anchors.

The judge scores **reasoning quality**, not answer correctness. A run can have perfect deterministic scores but mediocre judge scores (right answer, sloppy process) or vice versa (wrong answer, excellent reasoning that was undermined by one wrong assumption).

## Adding New Scenarios

1. Create a new YAML in `scenarios/` following the schema in the spec
2. Define `ground_truth` with the appropriate checks for the `case_type`
3. Define `judge_criteria` with 2-4 scenario-specific evaluation points
4. If the scenario needs a code state change, add a patch file in `patches/`
5. Run `/recce-eval run --case <new-id>` to validate
