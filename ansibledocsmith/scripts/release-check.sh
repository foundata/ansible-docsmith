#!/usr/bin/env bash
#
# Local, provider-independent release check for ansible-docsmith.
#
# Runs the full quality gate (format, lint, type check, tests) on every
# supported Python version, then builds the wheel and source distribution,
# installs the wheel into a clean throwaway environment and runs an import
# and a command-line smoke test against the installed artifact.
#
# This is intended to be run before tagging a release. It does not depend on
# any CI service; CI (if added) should call the same steps.
#
# Usage:
#   scripts/release-check.sh [PYTHON_VERSION ...]
#
# Without arguments the supported version matrix below is used.

set -euo pipefail

# Temp environments live under $TMPDIR, often on a different filesystem than
# the uv cache; copy instead of hardlink to avoid a noisy fallback warning.
export UV_LINK_MODE=copy

# Supported Python versions (keep in sync with pyproject classifiers and the
# README). Override by passing versions as arguments.
SUPPORTED_PYTHONS=("3.11" "3.12" "3.13")
if [ "$#" -gt 0 ]; then
    SUPPORTED_PYTHONS=("$@")
fi

# Resolve the package directory (this script lives in <pkg>/scripts/).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PKG_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PKG_DIR"

# Expected distribution and import names.
DIST_NAME="ansible-docsmith"
IMPORT_NAME="ansible_docsmith"
COMMAND_NAME="ansible-docsmith"

WORK_DIR="$(mktemp -d)"
trap 'rm -rf "$WORK_DIR"' EXIT

log() { printf '\n=== %s ===\n' "$*"; }

require_uv() {
    if ! command -v uv >/dev/null 2>&1; then
        echo "error: 'uv' is required but not found in PATH" >&2
        exit 1
    fi
}

ensure_pythons() {
    # Make sure every supported interpreter is available so the matrix can
    # actually run. `uv python install` is idempotent and a no-op when the
    # version is already present.
    log "Ensure Python interpreters: ${SUPPORTED_PYTHONS[*]}"
    uv python install "${SUPPORTED_PYTHONS[@]}"
}

run_static_checks() {
    # Formatter, linter and type checker are version-independent here
    # (mypy targets the project minimum via pyproject), so run them once.
    log "Static checks (format, lint, type check)"
    uv run ruff format --check .
    uv run ruff check .
    uv run mypy src tests
}

run_tests_matrix() {
    for py in "${SUPPORTED_PYTHONS[@]}"; do
        log "Tests on Python ${py}"
        uv run --python "$py" --isolated pytest -q
    done
}

build_artifacts() {
    log "Build wheel and source distribution"
    rm -rf dist
    uv build
    ls -1 dist
}

smoke_test_matrix() {
    local wheel
    wheel="$(ls -1 dist/*.whl | head -n1)"
    if [ -z "$wheel" ]; then
        echo "error: no wheel found in dist/" >&2
        exit 1
    fi

    local expected_version
    expected_version="$(uv run python -c "import ${IMPORT_NAME}; print(${IMPORT_NAME}.__version__)")"

    for py in "${SUPPORTED_PYTHONS[@]}"; do
        log "Install + smoke test on Python ${py} (clean environment)"
        local venv="${WORK_DIR}/venv-${py}"
        uv venv --python "$py" "$venv" >/dev/null
        # Install ONLY the built wheel (no project sources on the path).
        uv pip install --python "$venv/bin/python" "$wheel" >/dev/null

        # Import smoke test against the installed artifact.
        local installed_version
        installed_version="$(
            "$venv/bin/python" -c "import ${IMPORT_NAME}; print(${IMPORT_NAME}.__version__)"
        )"
        if [ "$installed_version" != "$expected_version" ]; then
            echo "error: installed version '${installed_version}' != source" \
                 "version '${expected_version}'" >&2
            exit 1
        fi
        echo "import ok: ${IMPORT_NAME} ${installed_version}"

        # Command-line smoke test against the installed console script.
        "$venv/bin/${COMMAND_NAME}" --version >/dev/null
        "$venv/bin/${COMMAND_NAME}" --help >/dev/null
        echo "cli ok: ${COMMAND_NAME} --version / --help"
    done
}

main() {
    require_uv
    echo "Release check for ${DIST_NAME}"
    echo "Python versions: ${SUPPORTED_PYTHONS[*]}"
    ensure_pythons
    run_static_checks
    run_tests_matrix
    build_artifacts
    smoke_test_matrix
    log "All release checks passed"
}

main
