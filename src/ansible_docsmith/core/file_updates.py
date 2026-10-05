"""Prepare file snapshots and commit complete files without replacing symlinks."""

import os
import stat
import tempfile
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path

from .exceptions import FileOperationError


def _signature(path: Path) -> tuple[int, int, int, int, int] | None:
    try:
        info = path.stat()
    except FileNotFoundError:
        return None
    if not stat.S_ISREG(info.st_mode):
        raise FileOperationError(f"Not a regular output file: {path}")
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_mode)


@dataclass(frozen=True)
class FileSnapshot:
    """Original content and destination, captured before preparation."""

    path: Path
    target: Path
    content: str | None
    signature: tuple[int, int, int, int, int] | None

    @classmethod
    def read(cls, path: Path) -> "FileSnapshot":
        """Read a regular file or record a missing target, following symlinks."""
        target = path.resolve()
        signature = _signature(target)
        content = target.read_text(encoding="utf-8") if signature else None
        snapshot = cls(path, target, content, signature)
        snapshot.verify()
        return snapshot

    def verify(self) -> None:
        """Refuse to overwrite a destination changed since preparation began."""
        if (
            self.path.resolve() != self.target
            or _signature(self.target) != self.signature
        ):
            raise FileOperationError(f"Output changed during preparation: {self.path}")


@dataclass(frozen=True)
class FileUpdate:
    """A candidate for one previously captured output."""

    original: FileSnapshot
    content: str
    create_parent: bool = False

    @property
    def changed(self) -> bool:
        """Whether a write is needed, including creation of an empty file."""
        return self.original.content != self.content


class FileCommitError(FileOperationError):
    """A failed commit with the logical paths already replaced."""

    def __init__(self, message: str, committed: set[Path]) -> None:
        super().__init__(message)
        self.committed = committed


def _remove_empty_directory(path: Path) -> None:
    try:
        path.rmdir()
    except OSError:
        pass  # A committed output or concurrent change may now occupy it.


def apply_file_updates(updates: list[FileUpdate]) -> set[Path]:
    """Stage every changed file before atomically replacing individual targets.

    Symlinks survive because replacements affect their resolved destinations.
    Multiple replacements are not a transaction; failures report committed paths.
    """
    committed: set[Path] = set()
    try:
        destinations: dict[Path, FileUpdate] = {}
        for update in updates:
            update.original.verify()
            target = update.original.target
            previous = destinations.get(target)
            if previous is not None and previous.content != update.content:
                raise FileOperationError(f"Conflicting outputs for {target}")
            destinations[target] = update

        with ExitStack() as stack:
            staged: dict[Path, Path] = {}
            for target, update in destinations.items():
                if not update.changed:
                    continue
                if update.create_parent and not target.parent.exists():
                    target.parent.mkdir()
                    stack.callback(_remove_empty_directory, target.parent)
                directory = stack.enter_context(
                    tempfile.TemporaryDirectory(
                        prefix=".ansible-docsmith-", dir=target.parent
                    )
                )
                candidate = Path(directory) / target.name
                # Exclusive creation retains the caller's umask for new outputs.
                with candidate.open("x", encoding="utf-8", newline="\n") as stream:
                    stream.write(update.content)
                    stream.flush()
                    os.fsync(stream.fileno())
                if update.original.signature is not None:
                    candidate.chmod(stat.S_IMODE(update.original.signature[-1]))
                staged[target] = candidate

            for update in updates:
                update.original.verify()
            for target, candidate in staged.items():
                destinations[target].original.verify()
                candidate.replace(target)
                committed.update(
                    update.original.path
                    for update in updates
                    if update.original.target == target
                )
        return committed
    except (OSError, ValueError, RuntimeError, FileOperationError) as error:
        pending = {u.original.path for u in updates if u.changed} - committed
        done = ", ".join(str(path) for path in sorted(committed)) or "none"
        remaining = ", ".join(str(path) for path in sorted(pending)) or "none"
        raise FileCommitError(
            f"Output commit failed: {error}. Committed: {done}; pending: {remaining}",
            committed,
        ) from error
