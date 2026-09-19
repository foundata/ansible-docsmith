#!/usr/bin/env bash
# Bash required for: arrays (the version matrix) and BASH_SOURCE.
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
#
# The release artifacts themselves are built and validated by
# "uv run release build", which exports the committed revision, prepares the
# README that ships in them and records their digests. See DEVELOPMENT.md.

# Consistent environment for predictable tool and shell behavior.
export PATH="${PATH:-/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin}"
if command -v locale >/dev/null 2>&1; then
  for locale_candidate in 'C.UTF-8' 'C.utf8' 'en_US.UTF-8' 'UTF-8' 'C'; do
    if LC_ALL="${locale_candidate}" locale charmap >/dev/null 2>&1; then
      export LC_ALL="${locale_candidate}"
      break
    fi
  done
else
  export LC_ALL='C'
fi
readonly LC_ALL
unset locale_candidate

# Against the style guide's default, and deliberately: this is a gate of
# roughly twenty commands where any single failure must stop the release,
# so an abort-by-default is worth more here than the edge cases set -e is
# rightly criticised for. The three options below close the ones that
# would otherwise let a failure through, and every check whose exit
# status carries meaning is still tested explicitly.
set -e
set -u
set -o pipefail
shopt -s inherit_errexit

# Temp environments live under $TMPDIR, often on a different filesystem than
# the uv cache; copy instead of hardlink to avoid a noisy fallback warning.
export UV_LINK_MODE=copy

# Supported Python versions (keep in sync with pyproject classifiers and the
# README). Override by passing versions as arguments.
SUPPORTED_PYTHONS=("3.11" "3.12" "3.13")
if [ "$#" -gt 0 ]; then
  SUPPORTED_PYTHONS=("$@")
fi
readonly SUPPORTED_PYTHONS

# Resolve the package directory (this script lives in <pkg>/scripts/).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly SCRIPT_DIR
PKG_DIR="$(dirname "${SCRIPT_DIR}")"
readonly PKG_DIR
cd "${PKG_DIR}"

# Every shell script this repository ships, with the option sets the shell
# style guide prescribes.
readonly -a BASH_SCRIPTS=(
  'scripts/release-check.sh'
)
readonly -a SHFMT_OPTS_COMMON=(
  '--indent' '2' '--case-indent' '--binary-next-line' '--simplify'
)
readonly -a SHELLCHECK_OPTS_COMMON=(
  '--severity=style' '--exclude=SC2292' '--exclude=SC3040'
  '--exclude=SC3043' '--enable=all'
)

# Expected distribution and import names.
readonly DIST_NAME="ansible-docsmith"
readonly IMPORT_NAME="ansible_docsmith"
readonly COMMAND_NAME="ansible-docsmith"

WORK_DIR="$(mktemp -d)"
readonly WORK_DIR
trap 'rm -rf "${WORK_DIR}"; git -C "${PKG_DIR}" worktree prune >/dev/null 2>&1 || true' EXIT

log() { printf '\n=== %s ===\n' "$*"; }

###
# Abort unless every named tool is available.
# Arguments:
#   $@ - The commands this gate is about to drive.
# Outputs:
#   Writes an error naming the first missing tool to STDERR.
# Returns:
#   0 when all are present, exits 1 otherwise.
require_tools() {
  local command_name
  for command_name in "$@"; do
    if ! command -v "${command_name}" >/dev/null 2>&1; then
      printf "error: '%s' is required but not found in PATH\n" "${command_name}" >&2
      exit 1
    fi
  done
}

###
# Check every shipped shell script with the tools and the exact options
# the shell style guide prescribes, so the style holds without anyone
# remembering to run them. The dialect parse is part of it: a script can
# lint clean and still not parse under the shell in its shebang.
# Globals:
#   BASH_SCRIPTS, SHELLCHECK_OPTS_COMMON, SHFMT_OPTS_COMMON
# Returns:
#   0 when every script passes, non-zero otherwise.
check_shell_scripts() {
  log "Shell scripts (shfmt, shellcheck, syntax)"
  local script
  for script in "${BASH_SCRIPTS[@]}"; do
    shfmt --language-dialect bash "${SHFMT_OPTS_COMMON[@]}" --diff "${script}"
    shellcheck --shell=bash "${SHELLCHECK_OPTS_COMMON[@]}" "${script}"
    bash -n "${script}"
  done
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
    uv run --python "${py}" --isolated pytest -q
  done
}

build_artifacts() {
  # Build from a pristine checkout of HEAD: the developer tree carries
  # ignored litter (tool caches, editor droppings) that must never decide
  # what ships. Local uncommitted changes are deliberately not built; a
  # release is a commit, not a working tree.
  log "Build wheel and source distribution (clean checkout of HEAD)"
  local tree_status
  tree_status="$(git status --porcelain)"
  if [ -n "${tree_status}" ]; then
    printf 'note: local changes present; artifacts are built from HEAD without them\n'
  fi
  local clean_dir="${WORK_DIR}/clean-src"
  git worktree add --detach --quiet "${clean_dir}" HEAD
  rm -rf dist
  (cd "${clean_dir}" && uv build --out-dir "${PKG_DIR}/dist")
  git worktree remove --force "${clean_dir}"
  ls -1 dist
  check_artifact_hygiene
}

check_artifact_hygiene() {
  log "Artifact hygiene (no caches or bytecode inside)"
  uv run python - dist/* <<'PY'
import sys
import tarfile
import zipfile

bad: list[str] = []
for name in sys.argv[1:]:
    if name.endswith(".whl"):
        entries = zipfile.ZipFile(name).namelist()
    else:
        with tarfile.open(name) as archive:
            entries = archive.getnames()
    for entry in entries:
        parts = entry.split("/")
        if any(
            part == "__pycache__" or (part.startswith(".") and "cache" in part)
            for part in parts
        ) or entry.endswith(".pyc"):
            bad.append(f"{name}: {entry}")
if bad:
    print("error: developer litter inside release artifacts:", file=sys.stderr)
    for line in bad:
        print(f"  {line}", file=sys.stderr)
    raise SystemExit(1)
print(f"clean: {len(sys.argv) - 1} artifact(s) checked")
PY
}

smoke_test_matrix() {
  # An unmatched glob stays literal, so the -f test below is what
  # actually decides whether the wheel is there.
  local -a wheels=(dist/*.whl)
  local wheel="${wheels[0]}"
  if [ ! -f "${wheel}" ]; then
    printf 'error: no wheel found in dist/\n' >&2
    exit 1
  fi

  local expected_version
  expected_version="$(uv run python -c "import ${IMPORT_NAME}; print(${IMPORT_NAME}.__version__)")"

  for py in "${SUPPORTED_PYTHONS[@]}"; do
    log "Install + smoke test on Python ${py} (clean environment)"
    local venv="${WORK_DIR}/venv-${py}"
    uv venv --python "${py}" "${venv}" >/dev/null
    # Install ONLY the built wheel (no project sources on the path).
    uv pip install --python "${venv}/bin/python" "${wheel}" >/dev/null

    # Import smoke test against the installed artifact.
    local installed_version
    installed_version="$(
      "${venv}/bin/python" -c "import ${IMPORT_NAME}; print(${IMPORT_NAME}.__version__)"
    )"
    if [ "${installed_version}" != "${expected_version}" ]; then
      printf "error: installed version '%s' != source version '%s'\n" \
        "${installed_version}" "${expected_version}" >&2
      exit 1
    fi
    printf 'import ok: %s %s\n' "${IMPORT_NAME}" "${installed_version}"

    # Distribution metadata must agree with the runtime version; the
    # __version__ check above cannot see a stale pyproject version.
    local meta_version
    meta_version="$("${venv}/bin/python" -c \
      "from importlib.metadata import version; print(version('${DIST_NAME}'))")"
    if [ "${meta_version}" != "${installed_version}" ]; then
      printf 'error: version skew: metadata %s, runtime %s\n' \
        "${meta_version}" "${installed_version}" >&2
      exit 1
    fi
    printf 'metadata ok: %s %s\n' "${DIST_NAME}" "${meta_version}"

    # Command-line smoke test against the installed console script.
    "${venv}/bin/${COMMAND_NAME}" --version >/dev/null
    "${venv}/bin/${COMMAND_NAME}" --help >/dev/null
    printf 'cli ok: %s --version / --help\n' "${COMMAND_NAME}"
  done
}

main() {
  require_tools 'uv' 'shellcheck' 'shfmt'
  printf 'Release check for %s\n' "${DIST_NAME}"
  printf 'Python versions: %s\n' "${SUPPORTED_PYTHONS[*]}"
  ensure_pythons
  run_static_checks
  check_shell_scripts
  run_tests_matrix
  build_artifacts
  smoke_test_matrix
  log "All release checks passed"
}

main
