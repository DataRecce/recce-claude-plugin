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
VENV_DIR="${TMP_DIR}/.venv"
PROFILES_DIR="${TMP_DIR}/profiles"

JSG_REPO="DataRecce/jaffle_shop_golden"
JSG_URL="https://github.com/${JSG_REPO}.git"

mkdir -p "${TMP_DIR}" "${PROFILES_DIR}"

# ---- Step 1: clone / fetch the source repo ---------------------------------
if [[ ! -d "${JSG_DIR}/.git" ]]; then
    echo "Cloning ${JSG_REPO} into ${JSG_DIR}..." >&2
    git clone "${JSG_URL}" "${JSG_DIR}"
fi

# Always fetch PR heads so all fixture SHAs are reachable
echo "Fetching all branches + PR heads from ${JSG_REPO}..." >&2
git -C "${JSG_DIR}" fetch --quiet origin
git -C "${JSG_DIR}" fetch --quiet origin '+refs/pull/*/head:refs/remotes/origin/pr/*'

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
