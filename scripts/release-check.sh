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

set -euo pipefail

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

# Resolve the package directory (this script lives in <pkg>/scripts/).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PKG_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PKG_DIR"

# Expected distribution and import names.
DIST_NAME="ansible-docsmith"
IMPORT_NAME="ansible_docsmith"
COMMAND_NAME="ansible-docsmith"

WORK_DIR="$(mktemp -d)"
trap 'rm -rf "$WORK_DIR"; git -C "$PKG_DIR" worktree prune >/dev/null 2>&1 || true' EXIT

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
    # Build from a pristine checkout of HEAD: the developer tree carries
    # ignored litter (tool caches, editor droppings) that must never decide
    # what ships. Local uncommitted changes are deliberately not built; a
    # release is a commit, not a working tree.
    log "Build wheel and source distribution (clean checkout of HEAD)"
    if [ -n "$(git status --porcelain)" ]; then
        echo "note: local changes present; artifacts are built from HEAD without them"
    fi
    local clean_dir="${WORK_DIR}/clean-src"
    git worktree add --detach --quiet "$clean_dir" HEAD
    rm -rf dist
    (cd "$clean_dir" && uv build --out-dir "${PKG_DIR}/dist")
    git worktree remove --force "$clean_dir"
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
        echo "error: no artifacts in dist/ -- run 'uv build' first" >&2
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

errors: list[str] = []

# The working tree may differ from the tagged HEAD in exactly the prepared
# README; anything else would ship untested content.
status = subprocess.run(
    ["git", "status", "--porcelain"], capture_output=True, text=True, check=True
).stdout
for line in status.splitlines():
    code, path = line[:2], line[3:]
    if code.strip() == "M" and path == "README.md":
        continue
    if code == "??":
        if path.startswith("src/"):
            errors.append(f"untracked file would enter the artifacts: {path}")
        continue
    errors.append(f"tree differs from HEAD beyond the prepared README: {line}")

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
    uv venv "$venv" >/dev/null
    uv pip install --python "$venv/bin/python" dist/*.whl >/dev/null
    "$venv/bin/${COMMAND_NAME}" --version >/dev/null
    local runtime_version meta_version
    runtime_version="$("$venv/bin/python" -c "import ${IMPORT_NAME}; print(${IMPORT_NAME}.__version__)")"
    meta_version="$("$venv/bin/python" -c "from importlib.metadata import version; print(version('${DIST_NAME}'))")"
    if [ "$meta_version" != "$runtime_version" ]; then
        echo "error: version skew after install: runtime ${runtime_version}," \
             "metadata ${meta_version}" >&2
        exit 1
    fi
    echo "install ok: ${DIST_NAME} ${meta_version}"
    log "Artifacts are ready to publish"
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

        # Distribution metadata must agree with the runtime version; the
        # __version__ check above cannot see a stale pyproject version.
        local meta_version
        meta_version="$("$venv/bin/python" -c \
            "from importlib.metadata import version; print(version('${DIST_NAME}'))")"
        if [ "$meta_version" != "$installed_version" ]; then
            echo "error: version skew: metadata ${meta_version}," \
                 "runtime ${installed_version}" >&2
            exit 1
        fi
        echo "metadata ok: ${DIST_NAME} ${meta_version}"

        # Command-line smoke test against the installed console script.
        "$venv/bin/${COMMAND_NAME}" --version >/dev/null
        "$venv/bin/${COMMAND_NAME}" --help >/dev/null
        echo "cli ok: ${COMMAND_NAME} --version / --help"
    done
}

main() {
    require_uv
    if [ "$ARTIFACTS_ONLY" = "yes" ]; then
        echo "Artifact validation for ${DIST_NAME}"
        validate_artifacts
        return
    fi
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
