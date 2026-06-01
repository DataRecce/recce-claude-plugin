#!/usr/bin/env bash
#
# build_fixtures.sh — Rebuild the local-dbt-only artifacts for every fixture
# under fixtures/<slug>/. Idempotent: existing artifacts/ are removed first.
#
# Required: git, uv. Everything else (Python 3.11.11, dbt-core, dbt-duckdb,
# duckdb) is installed into ./.tmp/.venv/ from the pinned versions below.
#
# Output: one "OK <fixture-id>" line per fixture. Non-zero exit on any failure.
#
# See fixtures/README.md for the canonical description of the per-fixture
# layout and the gitignored artifact paths.

set -euo pipefail

# ---- Pins (DRC-3402) --------------------------------------------------------
PYTHON_VERSION="3.11.11"
DBT_CORE_VERSION="1.11.9"
DBT_DUCKDB_VERSION="1.10.1"
DUCKDB_VERSION="1.5.2"

# ---- Paths ------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FIXTURES_DIR="${SCRIPT_DIR}/fixtures"
TMP_DIR="${SCRIPT_DIR}/.tmp"
JSG_DIR="${TMP_DIR}/jaffle_shop_golden"
SOURCES_DIR="${TMP_DIR}/sources"
VENV_DIR="${TMP_DIR}/.venv"
PROFILES_DIR="${TMP_DIR}/profiles"

JSG_REPO="DataRecce/jaffle_shop_golden"
JSG_URL="https://github.com/${JSG_REPO}.git"

mkdir -p "${TMP_DIR}" "${PROFILES_DIR}" "${SOURCES_DIR}"

# ---- Step 1: clone / fetch the source repo ---------------------------------
if [[ ! -d "${JSG_DIR}/.git" ]]; then
    # Pre-flight auth: jaffle_shop_golden is private. Confirm the runner has
    # access before the bare "Repository not found" git clone error.
    if ! git ls-remote "${JSG_URL}" >/dev/null 2>&1; then
        echo "Cannot reach ${JSG_REPO} (the repo is private)." >&2
        echo "Run 'gh auth setup-git' once so git uses your gh token, or configure another credential helper." >&2
        exit 1
    fi
    echo "Cloning ${JSG_REPO} into ${JSG_DIR}..." >&2
    git clone "${JSG_URL}" "${JSG_DIR}"
fi

# Always fetch PR heads so all fixture SHAs are reachable
echo "Fetching all branches + PR heads from ${JSG_REPO}..." >&2
git -C "${JSG_DIR}" fetch --quiet origin
git -C "${JSG_DIR}" fetch --quiet origin '+refs/pull/*/head:refs/remotes/origin/pr/*'

# Allow per-fixture clones below to fetch arbitrary SHAs from this local
# cache (needed for `git fetch <local-cache> <sha>`). Idempotent.
git -C "${JSG_DIR}" config uploadpack.allowAnySHA1InWant true

# ---- Step 2: venv with pinned versions -------------------------------------
if [[ ! -d "${VENV_DIR}" ]]; then
    echo "Creating venv with Python ${PYTHON_VERSION}..." >&2
    uv venv --python "${PYTHON_VERSION}" "${VENV_DIR}"
fi

# uv pip install is idempotent; cheap to run every time.
echo "Installing pinned dbt-duckdb stack into ${VENV_DIR}..." >&2
VIRTUAL_ENV="${VENV_DIR}" uv pip install --quiet \
    "dbt-core==${DBT_CORE_VERSION}" \
    "dbt-duckdb==${DBT_DUCKDB_VERSION}" \
    "duckdb==${DUCKDB_VERSION}"

DBT="${VENV_DIR}/bin/dbt"

# ---- Step 3: DuckDB profile ------------------------------------------------
# DuckDB path picks a deterministic file under TMP_DIR so the compiled SQL
# references "jaffle_shop_fixture_build" as the database, matching the original
# build. The actual file is gitignored (lives under .tmp/) and gets reused.
cat > "${PROFILES_DIR}/profiles.yml" <<YAML
jaffle_shop:
  target: dev
  outputs:
    dev:
      type: duckdb
      path: "${TMP_DIR}/jaffle_shop_fixture_build.duckdb"
      threads: 1
YAML

# ---- Helpers ----------------------------------------------------------------
# Extract the "Base SHA" from a fixture README (full SHA inside backticks).
extract_base_sha() {
    local readme="$1"
    grep -E '^- Base SHA: `[0-9a-f]+`' "${readme}" | head -1 | sed -E 's/.*`([0-9a-f]+)`.*/\1/'
}

# Scrub host-specific fields from a manifest or catalog JSON file in place.
#   user_id        -> "redacted"
#   invocation_id  -> "redacted"
#   root_path      -> "<project-root>"
scrub_json() {
    local path="$1"
    VIRTUAL_ENV="${VENV_DIR}" "${VENV_DIR}/bin/python" - "${path}" <<'PY'
import json
import sys

path = sys.argv[1]
with open(path, "r") as f:
    data = json.load(f)

def walk(node):
    if isinstance(node, dict):
        for k, v in list(node.items()):
            if k == "user_id" and isinstance(v, str):
                node[k] = "redacted"
            elif k == "invocation_id" and isinstance(v, str):
                node[k] = "redacted"
            elif k == "root_path" and isinstance(v, str):
                node[k] = "<project-root>"
            else:
                walk(v)
    elif isinstance(node, list):
        for item in node:
            walk(item)

walk(data)
with open(path, "w") as f:
    json.dump(data, f, indent=2, sort_keys=True)
PY
}

# Compile a single SHA into a temporary target directory and copy the artifacts
# of interest into <out_dir>/. Layout depends on caller (before/after/intermediate).
#
# Args:
#   sha           commit to check out in jaffle_shop_golden
#   manifest_out  destination path for manifest.json (file)
#   compiled_out  destination dir for compiled/ (directory)
#   catalog_out   destination path for catalog.json (file)
build_at_sha() {
    local sha="$1"
    local manifest_out="$2"
    local compiled_out="$3"
    local catalog_out="$4"

    # Detached checkout; abort any local edits from prior runs.
    git -C "${JSG_DIR}" reset --quiet --hard
    git -C "${JSG_DIR}" clean --quiet -fdx
    git -C "${JSG_DIR}" checkout --quiet --detach "${sha}"

    # Swap upstream Snowflake profile for our DuckDB one (kept only inside JSG_DIR).
    cp "${PROFILES_DIR}/profiles.yml" "${JSG_DIR}/profiles.yml"

    # Stage seed CSVs so dbt parse resolves seed nodes (dbt doesn't *need* the data
    # for parse/compile/docs-generate, but the project expects seeds/ to exist).
    mkdir -p "${JSG_DIR}/seeds"
    cp "${JSG_DIR}/jaffle-shop-data/"*.csv "${JSG_DIR}/seeds/"

    # dbt deps fetches packages.yml entries into dbt_packages/.
    (cd "${JSG_DIR}" && DBT_PROFILES_DIR="${JSG_DIR}" "${DBT}" deps --quiet)

    # Empty target dir so we never silently mix old artifacts.
    rm -rf "${JSG_DIR}/target"

    (cd "${JSG_DIR}" && DBT_PROFILES_DIR="${JSG_DIR}" "${DBT}" parse --quiet)
    (cd "${JSG_DIR}" && DBT_PROFILES_DIR="${JSG_DIR}" "${DBT}" compile --quiet)
    (cd "${JSG_DIR}" && DBT_PROFILES_DIR="${JSG_DIR}" "${DBT}" docs generate --empty-catalog --quiet)

    # Copy outputs to the fixture artifacts/.
    mkdir -p "$(dirname "${manifest_out}")"
    cp "${JSG_DIR}/target/manifest.json" "${manifest_out}"
    scrub_json "${manifest_out}"

    rm -rf "${compiled_out}"
    mkdir -p "${compiled_out}"
    if [[ -d "${JSG_DIR}/target/compiled" ]]; then
        cp -R "${JSG_DIR}/target/compiled/." "${compiled_out}/"
    fi

    cp "${JSG_DIR}/target/catalog.json" "${catalog_out}"
    scrub_json "${catalog_out}"
}

# ---- Step 4: build each fixture --------------------------------------------
build_fixture() {
    local slug="$1"
    local fdir="${FIXTURES_DIR}/${slug}"
    local readme="${fdir}/README.md"
    local commits_file="${fdir}/commits.txt"
    local artifacts="${fdir}/artifacts"

    if [[ ! -f "${readme}" ]] || [[ ! -f "${commits_file}" ]]; then
        echo "FAIL ${slug} (missing README.md or commits.txt)" >&2
        return 1
    fi

    local base_sha
    base_sha="$(extract_base_sha "${readme}")"
    if [[ -z "${base_sha}" ]]; then
        echo "FAIL ${slug} (no Base SHA in README.md)" >&2
        return 1
    fi

    # Head SHA = first non-blank line of commits.txt (already in repo order: newest first).
    local head_sha
    head_sha="$(awk 'NF>0 {print $1; exit}' "${commits_file}")"
    if [[ -z "${head_sha}" ]]; then
        echo "FAIL ${slug} (no head SHA in commits.txt)" >&2
        return 1
    fi

    rm -rf "${artifacts}"
    mkdir -p "${artifacts}"

    build_at_sha "${base_sha}" \
        "${artifacts}/manifest-before.json" \
        "${artifacts}/compiled-before" \
        "${artifacts}/catalog-before.json"

    build_at_sha "${head_sha}" \
        "${artifacts}/manifest-after.json" \
        "${artifacts}/compiled-after" \
        "${artifacts}/catalog-after.json"

    # Materialize a per-fixture standalone repo at the head SHA so eval
    # runners can read the head-SHA source for THIS fixture in isolation.
    #
    # Tier-0 frozen-input contract (RUBRIC.md): the agent must not see
    # later commits on the same branch, other fixtures' SHAs, or any
    # other ref from the upstream repo. A `git worktree add` off
    # ${JSG_DIR} would share that cache's object database — `git log
    # --all`, `git rev-parse origin/pr/<n>`, `git show <sibling-sha>`
    # would all succeed inside the fixture. Instead, we initialise a
    # fresh repo and fetch only the head SHA from the local cache, so
    # the fixture's `.git` ends up structurally minimal: one commit, no
    # remotes, no other refs reachable.
    local source_dir="${SOURCES_DIR}/${slug}"
    # `fetch <local-cache> <sha>` needs the full 40-char SHA; the
    # commits.txt entries are abbreviated. Resolve via the cache first.
    local full_head
    full_head="$(git -C "${JSG_DIR}" rev-parse "${head_sha}^{commit}")"
    rm -rf "${source_dir}"
    mkdir -p "${source_dir}"
    git -C "${source_dir}" init --quiet
    # Single-commit fetch from the local cache, landed into a named
    # local ref (refs/fixture/head). No `git remote add` — leaving the
    # repo with zero configured remotes means a stray `git fetch`
    # inside the fixture cannot pull additional history.
    git -C "${source_dir}" fetch --quiet --depth 1 --no-tags \
        "${JSG_DIR}" "+${full_head}:refs/fixture/head"
    git -C "${source_dir}" checkout --quiet --detach refs/fixture/head

    # Tier-0 leak check: the fixture's reachable history (across all
    # refs + HEAD) must contain only its own head commit. Anything
    # larger means a ref or pack from the cache leaked through.
    local reachable
    reachable="$(git -C "${source_dir}" rev-list --all HEAD --count)"
    if [[ "${reachable}" != "1" ]]; then
        echo "FAIL ${slug} (Tier-0 leak: rev-list --all HEAD --count = ${reachable}, expected 1)" >&2
        return 1
    fi

    # DRC-3430: strip Recce-aware automation that would leak the
    # with-Recce answer to a Tier-0 agent reading the source tree.
    # `jaffle_shop_golden` is a Recce-dogfood repo, so the per-fixture
    # checkout ships:
    #   * .github/prompts/*.md — system prompt + worked-example tables
    #     for Recce-aware PR review (lists mcp__recce__ tool names,
    #     prescribed call sequences, numeric anchors for the affected
    #     column)
    #   * .github/workflows/recce-*.yml, recce_*.yml — Recce CI workflows
    #   * .github/workflows/claude.yml — "Claude Code + Recce MCP"
    #     reviewer workflow (primes the agent with the same playbook)
    #   * .github/workflows/dbt-build-{pr,base}.yml, dbt_base.yml —
    #     dbt CI that uses `DataRecce/recce-cloud-cicd-action` (the
    #     names are dbt-shaped but the steps wire Recce in)
    #   * .github/mcp_config.json — explicit Recce MCP registration
    #   * .devcontainer/ — Recce-specific dev container + post-start
    #     script that boots Recce
    #   * recce.yml — preset Recce checks
    #
    # A random dbt project in the wild would not have any of these;
    # their presence here is fixture-source-specific, not a contract
    # bug. Strip them so a Tier-0 baseline measures what the agent
    # deduces without Recce-style structured surfacing.
    local stripped_paths=(
        ".github/prompts"
        ".github/mcp_config.json"
        ".github/workflows/claude.yml"
        ".github/workflows/recce_ci.yml"
        ".github/workflows/dbt-build-pr.yml"
        ".github/workflows/dbt-build-base.yml"
        ".github/workflows/dbt_base.yml"
        ".devcontainer"
        "recce.yml"
    )
    for stripped in "${stripped_paths[@]}"; do
        rm -rf "${source_dir:?}/${stripped}"
    done
    # Glob removal: any .github/workflows/recce-*.{yml,yaml} or
    # recce_*.{yml,yaml}. Guard against empty matches because
    # `nullglob` isn't set globally.
    for glob in \
        "${source_dir}/.github/workflows/recce-*.yml" \
        "${source_dir}/.github/workflows/recce-*.yaml" \
        "${source_dir}/.github/workflows/recce_*.yml" \
        "${source_dir}/.github/workflows/recce_*.yaml"
    do
        if compgen -G "${glob}" > /dev/null; then
            rm -f ${glob}
        fi
    done

    # DRC-3430 belt-and-suspenders: grep for Recce-shaped strings in the
    # stripped working tree. Catches future regressions where a new
    # Recce-aware file lands at a path the strip list doesn't cover.
    #
    # Two layers:
    #
    #   (a) Tight identifier match — MCP namespace, recce.yml filename,
    #       known env vars. False-positive-free, but only catches the
    #       exact shapes we know about.
    #   (b) Loose `[Rr]ecce` substring — catches natural-language
    #       priming like a CI workflow that says
    #       `prompt: "Use the recce CLI to review this PR"`. False
    #       positives are possible on a fresh source tree (a model
    #       column called `recce_score`, say); when one surfaces we
    #       either expand the strip list or whitelist the path here.
    #
    # Both grep over the working tree only (`--exclude-dir=.git`) so
    # packed objects don't false-positive — the agent cannot read those
    # without first invoking a git command, and even then sees decoded
    # content, not raw byte strings.
    # `profiles.yml` is whitelisted: the upstream Snowflake role is
    # literally named "RECCE", which is unfortunate naming, not Recce
    # priming. A role name doesn't tell the agent how to use Recce-
    # the-tool. Whitelisting one filename is preferable to tightening
    # the regex back to identifier-only matches (which would let
    # natural-language priming like `prompt: "use the recce CLI"`
    # through).
    local leak_hits
    leak_hits="$(grep -rlEi --exclude-dir=.git --exclude=profiles.yml \
        'mcp__recce|recce\.yml|RECCE_API_TOKEN|recce' \
        "${source_dir}" 2>/dev/null || true)"
    if [[ -n "${leak_hits}" ]]; then
        echo "FAIL ${slug} (Tier-0 strip leak — Recce-shaped strings still present in:)" >&2
        # Indent each path on its own line; sed is robust against
        # whitespace in filenames where `printf '  %s\n' ${unquoted}`
        # would word-split. dbt projects don't use spaces in paths
        # today, but the cost of belt-and-suspenders is one sed call.
        sed 's/^/  /' <<< "${leak_hits}" >&2
        echo "  Extend the strip list in build_fixtures.sh and re-run." >&2
        return 1
    fi

    # DRC-3584 Andy review B1 / orchestrator iter-6: rewrite the per-
    # fixture repo's history so stripped Recce-aware content is NOT
    # recoverable via `git show HEAD`, `git cat-file -p HEAD^{tree}`,
    # `git log -p`, etc. `git` is Tier-0-allowlisted, so without this
    # rewrite the working-tree strip is bypassable.
    #
    # The simplest history-rewrite: delete `.git/` and re-init a fresh
    # single-commit repo from the already-stripped working tree. The
    # new commit's tree contains ONLY the stripped paths; no
    # ancestor commit, no other ref, no reflog entry references the
    # original head SHA's tree.
    #
    # The upstream head SHA is recorded in commits.txt for
    # documentation — losing it from the per-fixture repo is fine
    # (and arguably better, since the SHA itself is a weak leak
    # vector: an agent could `git log` and infer the upstream
    # project from the commit message + author).
    rm -rf "${source_dir}/.git"
    git -c init.defaultBranch=main -C "${source_dir}" init --quiet
    git -c user.email=fixture@recce.eval -c user.name=fixture-build \
        -C "${source_dir}" add -A
    git -c user.email=fixture@recce.eval -c user.name=fixture-build \
        -C "${source_dir}" commit --quiet \
        -m "Stripped fixture tree for ${slug} (build_fixtures.sh)"

    # Re-verify the post-rewrite invariants. The rev-list count must
    # still be 1 (single commit), and `git ls-tree -r` over the new
    # tree must not contain Recce-shaped paths (same regex layers as
    # the working-tree leak grep above, but now applied to git
    # objects — closes the BLOCKER).
    local post_rev_count
    post_rev_count="$(git -C "${source_dir}" rev-list --all HEAD --count)"
    if [[ "${post_rev_count}" != "1" ]]; then
        echo "FAIL ${slug} (post-rewrite Tier-0 leak: rev-list = ${post_rev_count}, expected 1)" >&2
        return 1
    fi
    # Anchored regex — match path components exactly, not substrings.
    # `\.devcontainer/` matches files inside the dir but NOT the
    # sibling `.devcontainer.json` (generic VS Code dbt config, no
    # Recce content; would false-positive without the trailing slash).
    local git_tree_leak
    git_tree_leak="$(git -C "${source_dir}" ls-tree -r --name-only HEAD \
        | grep -E '(^|/)recce\.yml$|(^|/)mcp_config\.json$|(^|/)\.devcontainer/|(^|/)\.github/prompts/|(^|/)\.github/workflows/(claude|recce[-_].*|dbt-build-[a-z]+|dbt_base)\.ya?ml$' \
        || true)"
    if [[ -n "${git_tree_leak}" ]]; then
        echo "FAIL ${slug} (post-rewrite git tree still has Recce-shaped paths:)" >&2
        sed 's/^/  /' <<< "${git_tree_leak}" >&2
        return 1
    fi

    # PR #20 intermediate snapshot — keyed on the well-known SHA in commits.txt.
    if [[ "${slug}" == "pr44-promotion-flags" ]]; then
        local intermediate_sha="23b96ca"
        # Resolve to a full SHA from commits.txt to avoid ambiguity.
        local full_intermediate
        full_intermediate="$(awk -v p="${intermediate_sha}" '$1 ~ "^"p { print $1; exit }' "${commits_file}")"
        if [[ -z "${full_intermediate}" ]]; then
            echo "FAIL ${slug} (commits.txt does not list intermediate ${intermediate_sha})" >&2
            return 1
        fi
        local idir="${artifacts}/intermediate-commit-${intermediate_sha}"
        mkdir -p "${idir}/compiled"
        build_at_sha "${full_intermediate}" \
            "${idir}/manifest.json" \
            "${idir}/compiled" \
            "${idir}/catalog.json"
    fi

    echo "OK ${slug}"
}

cd "${SCRIPT_DIR}"

FIXTURES=(
    pr1-fix-clv
    pr2-refactor-cte-to-models
    pr3-amount-double-to-decimal
    pr42-is-closed-filter
    pr44-promotion-flags
    pr46-net-clv-segments
)

for slug in "${FIXTURES[@]}"; do
    build_fixture "${slug}"
done
