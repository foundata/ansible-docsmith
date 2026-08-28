"""Tests for the release artifact validator's tree-state classifier.

`classify_tree_state` decides which changes `scripts/release-check.sh
--artifacts` accepts before trusting `dist/`: a plain modification to the
prepared README, nothing else. These tests exercise the pure classifier
directly against crafted `git status --porcelain=v1 -z` snapshots; no
repository, worktree or build is needed.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

SCRIPTS = Path(__file__).parent.parent.parent / "scripts"


def _load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


release_tree_state = _load("release_tree_state")
classify_tree_state = release_tree_state.classify_tree_state
ALLOWED_MODIFIED_PATHS = release_tree_state.ALLOWED_MODIFIED_PATHS


def _porcelain(*records: str) -> str:
    """A `git status --porcelain=v1 -z` snapshot from literal XY-path records.

    Matches real git behaviour exactly: NUL-terminated records (including
    a trailing NUL after the last one), empty string for a clean tree.
    """
    if not records:
        return ""
    return "\0".join(records) + "\0"


def test_allowed_paths_are_exactly_the_prepared_readme() -> None:
    assert ALLOWED_MODIFIED_PATHS == {"README.md"}


def test_clean_status_is_accepted() -> None:
    assert classify_tree_state(_porcelain()) == []


def test_readme_modification_is_accepted() -> None:
    assert classify_tree_state(_porcelain(" M README.md")) == []


@pytest.mark.parametrize("code", ["M ", " M", "MM"])
def test_readme_modification_accepted_staged_and_unstaged(code: str) -> None:
    # "M ": staged only. " M": unstaged only. "MM": both at once (the
    # README was staged, then edited again before the check ran).
    assert classify_tree_state(_porcelain(f"{code} README.md")) == []


def test_untracked_file_under_licenses_is_rejected() -> None:
    # license-files globs match the working tree regardless of Git
    # tracking, so an untracked file here alone could enter a built
    # sdist unnoticed.
    path = "LICENSES/review-sentinel.txt"
    errors = classify_tree_state(_porcelain(f"?? {path}"))
    assert len(errors) == 1
    assert path in errors[0]


def test_untracked_file_under_src_is_rejected() -> None:
    path = "src/ansible_docsmith/sneaky.py"
    errors = classify_tree_state(_porcelain(f"?? {path}"))
    assert len(errors) == 1
    assert path in errors[0]


def test_untracked_file_at_repository_root_is_rejected() -> None:
    path = "sneaky.txt"
    errors = classify_tree_state(_porcelain(f"?? {path}"))
    assert len(errors) == 1
    assert path in errors[0]


def test_untracked_directory_is_rejected() -> None:
    path = "src/ansible_docsmith/newdir/"
    errors = classify_tree_state(_porcelain(f"?? {path}"))
    assert len(errors) == 1
    assert path in errors[0]


def test_untracked_path_with_spaces_is_parsed_and_rejected_intact() -> None:
    # -z output is never quoted or escaped, so a space in the path must
    # not be mistaken for a field boundary.
    path = "src/ansible_docsmith/some folder/file with spaces.txt"
    errors = classify_tree_state(_porcelain(f"?? {path}"))
    assert len(errors) == 1
    assert path in errors[0]


def test_modification_of_another_tracked_file_is_rejected() -> None:
    path = "src/ansible_docsmith/cli.py"
    errors = classify_tree_state(_porcelain(f" M {path}"))
    assert len(errors) == 1
    assert path in errors[0]


def test_staged_modification_of_another_file_is_rejected() -> None:
    path = "src/ansible_docsmith/core/processor.py"
    errors = classify_tree_state(_porcelain(f"M  {path}"))
    assert len(errors) == 1
    assert path in errors[0]


def test_deletion_of_the_readme_is_rejected() -> None:
    # Permission covers modification only; a deleted README must not
    # slip through just because its path is in the allowed set.
    errors = classify_tree_state(_porcelain(" D README.md"))
    assert len(errors) == 1
    assert "README.md" in errors[0]


def test_rename_is_rejected_and_does_not_desync_later_records() -> None:
    # A staged rename's second NUL field is the bare original path with
    # no XY prefix; consuming it incorrectly would misparse every record
    # that follows. Prove that by placing an allowed change right after.
    errors = classify_tree_state(
        _porcelain("R  README.new", "README.md") + _porcelain(" M README.md")
    )
    assert len(errors) == 1
    assert "README.new" in errors[0]


def test_mixture_of_allowed_modification_and_untracked_file_is_rejected() -> None:
    path = "LICENSES/review-sentinel.txt"
    errors = classify_tree_state(_porcelain(" M README.md", f"?? {path}"))
    assert len(errors) == 1
    assert path in errors[0]


def test_ignored_path_is_skipped_not_reported() -> None:
    # Only reachable if a caller ever passes --ignored; dist/ and caches
    # must never become errors merely because they exist.
    assert (
        classify_tree_state(_porcelain("!! dist/ansible_docsmith-2.2.0.tar.gz")) == []
    )
