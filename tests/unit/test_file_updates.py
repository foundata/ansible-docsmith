"""Staging, destination checks and symlink-preserving commits."""

from pathlib import Path

import pytest

from ansible_docsmith.core.exceptions import FileOperationError
from ansible_docsmith.core.file_updates import (
    FileCommitError,
    FileSnapshot,
    FileUpdate,
    apply_file_updates,
)


def test_unchanged_and_permissions(tmp_path: Path) -> None:
    path = tmp_path / "README.md"
    path.write_text("before\n")
    path.chmod(0o640)
    original = FileSnapshot.read(path)
    assert apply_file_updates([FileUpdate(original, "before\n")]) == set()
    assert original.signature is not None
    assert path.stat().st_mtime_ns == original.signature[3]
    assert apply_file_updates([FileUpdate(original, "after\n")]) == {path}
    assert path.read_text() == "after\n"
    assert path.stat().st_mode & 0o777 == 0o640
    assert not list(tmp_path.glob(".ansible-docsmith-*"))


@pytest.mark.parametrize("exists", [True, False])
def test_symlink_chains_and_missing_targets(tmp_path: Path, exists: bool) -> None:
    target = tmp_path / "target"
    if exists:
        target.write_text("before")
    middle = tmp_path / "middle"
    middle.symlink_to(target.name)
    link = tmp_path / "README.md"
    link.symlink_to(middle.name)
    apply_file_updates([FileUpdate(FileSnapshot.read(link), "after")])
    assert link.is_symlink() and middle.is_symlink()
    assert target.read_text() == "after"


def test_destination_change_prevents_every_write(tmp_path: Path) -> None:
    first = tmp_path / "first"
    first.write_text("before")
    second = tmp_path / "second"
    second.symlink_to(first)
    updates = [FileUpdate(FileSnapshot.read(path), "after") for path in (first, second)]
    second.unlink()
    second.symlink_to(tmp_path / "different")
    with pytest.raises(FileCommitError, match="changed during preparation"):
        apply_file_updates(updates)
    assert first.read_text() == "before"
    assert not (tmp_path / "different").exists()


@pytest.mark.parametrize("conflict", [True, False])
def test_shared_destination(tmp_path: Path, conflict: bool) -> None:
    first = tmp_path / "first"
    first.write_text("before")
    second = tmp_path / "second"
    second.symlink_to(first)
    updates = [
        FileUpdate(FileSnapshot.read(first), "after"),
        FileUpdate(FileSnapshot.read(second), "different" if conflict else "after"),
    ]
    if conflict:
        with pytest.raises(FileCommitError, match="Conflicting outputs"):
            apply_file_updates(updates)
        assert first.read_text() == "before"
    else:
        assert apply_file_updates(updates) == {first, second}
        assert first.read_text() == "after"
        assert second.is_symlink()


def test_staging_failure_leaves_targets_intact(tmp_path: Path) -> None:
    first = tmp_path / "first"
    first.write_text("before")
    missing = tmp_path / "absent-directory" / "second"
    updates = [
        FileUpdate(FileSnapshot.read(path), "after") for path in (first, missing)
    ]
    with pytest.raises(FileCommitError) as caught:
        apply_file_updates(updates)
    assert not caught.value.committed
    assert first.read_text() == "before"
    assert not missing.exists()
    assert not list(tmp_path.glob(".ansible-docsmith-*"))


def test_create_parent_only_during_commit(tmp_path: Path) -> None:
    path = tmp_path / "defaults/main.yml"
    update = FileUpdate(
        FileSnapshot.read(path), "# Documentation\n", create_parent=True
    )
    assert not path.parent.exists()

    assert apply_file_updates([update]) == {path}
    assert path.read_text(encoding="utf-8") == "# Documentation\n"


def test_staging_failure_removes_new_empty_parent(tmp_path: Path) -> None:
    path = tmp_path / "defaults/main.yml"
    missing = tmp_path / "other/file.yml"
    updates = [
        FileUpdate(FileSnapshot.read(path), "# Documentation\n", create_parent=True),
        FileUpdate(FileSnapshot.read(missing), "unwritable"),
    ]

    with pytest.raises(FileCommitError) as caught:
        apply_file_updates(updates)

    assert not caught.value.committed
    assert not path.parent.exists()
    assert not missing.parent.exists()


def test_replace_failure_reports_partial_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = [tmp_path / "first", tmp_path / "second"]
    for path in paths:
        path.write_text("before")
    updates = [FileUpdate(FileSnapshot.read(path), "after") for path in paths]
    original_replace = Path.replace

    def failing_replace(self: Path, target: Path) -> Path:
        if target == paths[1]:
            raise OSError("simulated write failure")
        return original_replace(self, target)

    monkeypatch.setattr(Path, "replace", failing_replace)
    with pytest.raises(FileCommitError) as caught:
        apply_file_updates(updates)
    assert caught.value.committed == {paths[0]}
    assert "pending:" in str(caught.value)
    assert paths[0].read_text() == "after"
    assert paths[1].read_text() == "before"
    assert not list(tmp_path.glob(".ansible-docsmith-*"))


def test_nonregular_output_rejected(tmp_path: Path) -> None:
    """Do not read or stage an output that is not a regular file."""
    with pytest.raises(FileOperationError, match="Not a regular output"):
        FileSnapshot.read(tmp_path)


def test_concurrent_content_edit_is_not_overwritten(tmp_path: Path) -> None:
    """Changes after the snapshot invalidate the plan before staging."""
    path = tmp_path / "README.md"
    path.write_text("before")
    update = FileUpdate(FileSnapshot.read(path), "generated")
    path.write_text("edited by the user")
    with pytest.raises(FileCommitError, match="changed during preparation"):
        apply_file_updates([update])
    assert path.read_text() == "edited by the user"
