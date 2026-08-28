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
#   scripts/release-check.sh --artifacts
#
# Without arguments the supported version matrix below is used.
#
# --artifacts validates the artifacts currently in dist/ without rebuilding
# them: the exact files "uv publish" would upload. The main gate runs before
# the version bump and the PyPI README preparation, so it never sees those;
# this mode checks litter, version and tag agreement, the prepared README
# and that the working tree differs from HEAD in nothing but that README.
# Run it directly before uploading.

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
ARTIFACTS_ONLY="no"
if [ "${1:-}" = "--artifacts" ]; then
  ARTIFACTS_ONLY="yes"
elif [ "$#" -gt 0 ]; then
  SUPPORTED_PYTHONS=("$@")
fi
readonly SUPPORTED_PYTHONS ARTIFACTS_ONLY

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
  # scripts/ is included so the release tooling's own Python (the
  # tree-state classifier below) is held to the same strictness as the
  # package it ships.
  log "Static checks (format, lint, type check)"
  uv run ruff format --check .
  uv run ruff check .
  uv run mypy src tests scripts
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

validate_artifacts() {
  # Pre-publish validation of dist/ exactly as it lies there. The rebuild
  # after the version bump and the README preparation happens from the
  # working tree on purpose (the prepared README only exists there), so
  # these are the only checks the uploaded bytes ever get.
  if ! ls dist/*.whl >/dev/null 2>&1; then
    printf "error: no artifacts in dist/ -- run 'uv build' first\n" >&2
    exit 1
  fi
  check_artifact_hygiene

  log "Tree state, version, tag and prepared README"
  uv run python - dist/* <<'PY'
import re
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

sys.path.insert(0, "scripts")
from release_tree_state import classify_tree_state

errors: list[str] = []

# The working tree may differ from the tagged HEAD in exactly the prepared
# README, and only by modification; a build backend's own file-inclusion
# globs (license-files, package data, ...) can match an untracked path
# anywhere, so every untracked path is refused regardless of location --
# see scripts/release_tree_state.py for the exact rules.
status = subprocess.run(
    ["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"],
    capture_output=True,
    text=True,
    check=True,
).stdout
errors.extend(classify_tree_state(status))

match = re.search(
    r'__version__ = "([^"]+)"',
    Path("src/ansible_docsmith/__init__.py").read_text(),
)
version = match.group(1) if match else ""
if not version:
    errors.append("cannot read __version__ from src/ansible_docsmith/__init__.py")
tags = subprocess.run(
    ["git", "tag", "--points-at", "HEAD"], capture_output=True, text=True, check=True
).stdout.split()
if version and f"v{version}" not in tags:
    errors.append(
        f"no v{version} tag on HEAD (found: {tags or 'none'}); "
        "artifacts must be built from the tagged release state"
    )

def metadata_text(artifact: str) -> str:
    if artifact.endswith(".whl"):
        with zipfile.ZipFile(artifact) as bundle:
            meta = next(n for n in bundle.namelist() if n.endswith(".dist-info/METADATA"))
            return bundle.read(meta).decode("utf-8", errors="replace")
    with tarfile.open(artifact) as bundle:
        meta = next(n for n in bundle.getnames() if n.endswith("/PKG-INFO"))
        member = bundle.extractfile(meta)
        assert member is not None
        return member.read().decode("utf-8", errors="replace")

relative_link = re.compile(r"\]\((?!https?://|#|mailto:)")
for artifact in sys.argv[1:]:
    text = metadata_text(artifact)
    headers, _, description = text.partition("\n\n")
    meta_version = ""
    for line in headers.splitlines():
        if line.startswith("Version:"):
            meta_version = line.split(":", 1)[1].strip()
    if meta_version != version:
        errors.append(f"{artifact}: metadata version {meta_version} != {version}")
    if version and version not in Path(artifact).name:
        errors.append(f"{artifact}: file name does not carry version {version}")
    # The PyPI page is this description; relative links break on pypi.org.
    if len(description) < 5000:
        errors.append(
            f"{artifact}: description is {len(description)} chars; "
            "looks unprepared (see the release checklist)"
        )
    hits = relative_link.findall(description)
    if hits:
        errors.append(
            f"{artifact}: description contains {len(hits)} relative link(s); "
            "run the README preparation first"
        )

if errors:
    for line in errors:
        print(f"error: {line}", file=sys.stderr)
    raise SystemExit(1)
print(f"consistent: {len(sys.argv) - 1} artifact(s) at {version}, tag v{version} on HEAD")
PY

  log "Install + smoke test of the artifacts (clean environment)"
  local venv="${WORK_DIR}/venv-artifacts"
  uv venv "${venv}" >/dev/null
  uv pip install --python "${venv}/bin/python" dist/*.whl >/dev/null
  "${venv}/bin/${COMMAND_NAME}" --version >/dev/null
  local runtime_version meta_version
  runtime_version="$("${venv}/bin/python" -c "import ${IMPORT_NAME}; print(${IMPORT_NAME}.__version__)")"
  meta_version="$("${venv}/bin/python" -c "from importlib.metadata import version; print(version('${DIST_NAME}'))")"
  if [ "${meta_version}" != "${runtime_version}" ]; then
    printf 'error: version skew after install: runtime %s, metadata %s\n' \
      "${runtime_version}" "${meta_version}" >&2
    exit 1
  fi
  printf 'install ok: %s %s\n' "${DIST_NAME}" "${meta_version}"
  log "Artifacts are ready to publish"
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
  require_tools 'uv'
  if [ "${ARTIFACTS_ONLY}" = "yes" ]; then
    printf 'Artifact validation for %s\n' "${DIST_NAME}"
    validate_artifacts
    return
  fi
  require_tools 'shellcheck' 'shfmt'
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
